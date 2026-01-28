import math

import numpy as np
from attrs import field, define

from h2integrate.core.utilities import merge_shared_inputs
from h2integrate.core.validators import gt_zero, contains
from h2integrate.core.model_baseclasses import ResizeablePerformanceModelBaseConfig
from h2integrate.converters.hydrogen.utilities import size_electrolyzer_for_hydrogen_demand
from h2integrate.converters.hydrogen.pem_model.run_h2_PEM import run_h2_PEM
from h2integrate.converters.hydrogen.electrolyzer_baseclass import ElectrolyzerPerformanceBaseClass


@define(kw_only=True)
class ECOElectrolyzerPerformanceModelConfig(ResizeablePerformanceModelBaseConfig):
    """
    Configuration class for the ECOElectrolyzerPerformanceModel.

    Args:
        size_mode (str): The mode in which the component is sized. Options:
            - "normal": The component size is taken from the tech_config.
            - "resize_by_max_feedstock": Resize based on maximum feedstock availability.
            - "resize_by_max_commodity": Resize based on maximum commodity demand.
        flow_used_for_sizing (str | None): The feedstock/commodity flow used for sizing.
            Required when size_mode is not "normal".
        max_feedstock_ratio (float): Ratio for sizing in "resize_by_max_feedstock" mode.
            Defaults to 1.0.
        max_commodity_ratio (float): Ratio for sizing in "resize_by_max_commodity" mode.
            Defaults to 1.0.
        n_clusters (int): number of electrolyzer clusters within the system.
        location (str): The location of the electrolyzer; options include "onshore" or "offshore".
        cluster_rating_MW (float): The rating of the clusters that the electrolyzer is grouped
            into, in MW.
        eol_eff_percent_loss (float): End-of-life (EOL) defined as a percent change in efficiency
            from beginning-of-life (BOL).
        uptime_hours_until_eol (int): Number of "on" hours until the electrolyzer reaches EOL.
        include_degradation_penalty (bool): Flag to include degradation of the electrolyzer due to
            operational hours, ramping, and on/off power cycles.
        turndown_ratio (float): The ratio at which the electrolyzer will shut down.
        electrolyzer_capex (int): $/kW overnight installed capital costs for a 1 MW system in
            2022 USD/kW (DOE hydrogen program record 24005 Clean Hydrogen Production Cost Scenarios
            with PEM Electrolyzer Technology 05/20/24) #TODO: convert to refs
            (https://www.hydrogen.energy.gov/docs/hydrogenprogramlibraries/pdfs/24005-clean-hydrogen-production-cost-pem-electrolyzer.pdf?sfvrsn=8cb10889_1)
    """

    n_clusters: int = field(validator=gt_zero)
    location: str = field(validator=contains(["onshore", "offshore"]))
    cluster_rating_MW: float = field(validator=gt_zero)
    eol_eff_percent_loss: float = field(validator=gt_zero)
    uptime_hours_until_eol: int = field(validator=gt_zero)
    include_degradation_penalty: bool = field()
    turndown_ratio: float = field(validator=gt_zero)
    electrolyzer_capex: int = field()


class ECOElectrolyzerPerformanceModel(ElectrolyzerPerformanceBaseClass):
    """
    An OpenMDAO component that wraps the PEM electrolyzer model.
    Takes electricity input and outputs hydrogen and oxygen generation rates.
    """

    def setup(self):
        self.config = ECOElectrolyzerPerformanceModelConfig.from_dict(
            merge_shared_inputs(self.options["tech_config"]["model_inputs"], "performance"),
            strict=False,
        )
        super().setup()
        self.add_output("efficiency", val=0.0, desc="Average efficiency of the electrolyzer")
        self.add_output(
            "rated_h2_production_kg_pr_hr",
            val=0.0,
            units="kg/h",
            desc="Rated hydrogen production of system in kg/hour",
        )

        self.add_input(
            "n_clusters",
            val=self.config.n_clusters,
            units="unitless",
            desc="number of electrolyzer clusters in the system",
        )

        self.add_output(
            "electrolyzer_size_mw",
            val=0.0,
            units="MW",
            desc="Size of the electrolyzer in MW",
        )
        self.add_input("cluster_size", val=-1.0, units="MW")
        self.add_input("max_hydrogen_capacity", val=1000.0, units="kg/h")
        self.add_output("hydrogen_capacity_factor", val=0.0, units="unitless")

    def compute(self, inputs, outputs, discrete_inputs, discrete_outputs):
        plant_life = self.options["plant_config"]["plant"]["plant_life"]
        electrolyzer_size_mw = inputs["n_clusters"][0] * self.config.cluster_rating_MW
        electrolyzer_capex_kw = self.config.electrolyzer_capex

        hydrogen_production_capacity_required_kgphr = []
        grid_connection_scenario = "off-grid"
        energy_to_electrolyzer_kw = inputs["electricity_in"]

        # Resize if necessary based on sizing mode
        size_mode = discrete_inputs["size_mode"]
        # Make changes to computation based on sizing_mode:
        if size_mode != "normal":
            size_flow = discrete_inputs["flow_used_for_sizing"]
        if size_mode == "resize_by_max_feedstock":
            # In this sizing mode, electrolyzer size comes from feedstock
            feed_ratio = inputs["max_feedstock_ratio"][0]
            # Make sure COBLYA doesn't cause any shenanigans trying to set feed_ratio <= 0
            if feed_ratio <= 1e-6:
                feed_ratio = 1.0e-6
            if size_flow == "electricity":
                electrolyzer_size_mw = np.max(inputs["electricity_in"]) / 1000.0 * feed_ratio
            else:
                raise ValueError(f"Cannot resize for '{size_flow}' feedstock")
        elif size_mode == "resize_by_max_commodity":
            # In this sizing mode, electrolyzer size comes from a connected tech's capacity
            # to take in one of the electrolyzer's commodities
            comm_ratio = inputs["max_commodity_ratio"]
            # Make sure COBLYA doesn't cause any shenanigans trying to set comm_ratio <= 0
            if comm_ratio <= 1e-6:
                comm_ratio = 1e-6
            if size_flow == "hydrogen":
                h2_kgphr = inputs["max_hydrogen_capacity"]
                electrolyzer_size_mw = size_electrolyzer_for_hydrogen_demand(h2_kgphr * comm_ratio)
            else:
                raise ValueError(f"Cannot resize for '{size_flow}' commodity")
        elif size_mode != "normal":
            raise NotImplementedError("Sizing mode '%s' not implemented".format())

        n_pem_clusters = int(math.ceil(electrolyzer_size_mw / self.config.cluster_rating_MW))

        electrolyzer_actual_capacity_MW = n_pem_clusters * self.config.cluster_rating_MW
        pem_param_dict = {
            "eol_eff_percent_loss": self.config.eol_eff_percent_loss,
            "uptime_hours_until_eol": self.config.uptime_hours_until_eol,
            "include_degradation_penalty": self.config.include_degradation_penalty,
            "turndown_ratio": self.config.turndown_ratio,
        }

        energy_to_electrolyzer_kw = inputs["electricity_in"]
        H2_Results, h2_ts, h2_tot, power_to_electrolyzer_kw = run_h2_PEM(
            electrical_generation_timeseries=energy_to_electrolyzer_kw,
            electrolyzer_size=electrolyzer_size_mw,
            useful_life=plant_life,
            n_pem_clusters=n_pem_clusters,
            electrolyzer_direct_cost_kw=electrolyzer_capex_kw,
            user_defined_pem_param_dictionary=pem_param_dict,
            grid_connection_scenario=grid_connection_scenario,  # if not offgrid, assumes steady h2 demand in kgphr for full year  # noqa: E501
            hydrogen_production_capacity_required_kgphr=hydrogen_production_capacity_required_kgphr,
            debug_mode=False,
            verbose=False,
        )

        # Assuming `h2_results` includes hydrogen and oxygen rates per timestep
        outputs["hydrogen_out"] = H2_Results["Hydrogen Hourly Production [kg/hr]"]
        outputs["total_hydrogen_produced"] = H2_Results["Life: Annual H2 production [kg/year]"]
        outputs["efficiency"] = H2_Results["Sim: Average Efficiency [%-HHV]"]
        outputs["time_until_replacement"] = H2_Results["Time Until Replacement [hrs]"]
        outputs["rated_h2_production_kg_pr_hr"] = H2_Results["Rated BOL: H2 Production [kg/hr]"]
        outputs["electrolyzer_size_mw"] = electrolyzer_actual_capacity_MW
        outputs["hydrogen_capacity_factor"] = H2_Results["Life: Capacity Factor"]
