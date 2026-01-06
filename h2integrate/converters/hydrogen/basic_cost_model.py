import warnings

import numpy as np
from attrs import field, define

from h2integrate.core.utilities import CostModelBaseConfig, merge_shared_inputs
from h2integrate.core.validators import gt_zero, contains, must_equal
from h2integrate.converters.hydrogen.electrolyzer_baseclass import ElectrolyzerCostBaseClass


@define(kw_only=True)
class BasicElectrolyzerCostModelConfig(CostModelBaseConfig):
    """
    Configuration class for the basic_H2_cost_model which is based on costs from
    `HFTO Program Record 19009 <https://www.hydrogen.energy.gov/pdfs/19009_h2_production_cost_pem_electrolysis_2019.pdf>`_
    which provides costs in 2016 USD.

    Args:
        location (str): The location of the electrolyzer; options include "onshore" or "offshore".
        electrolyzer_capex (int): $/kW overnight installed capital costs for a 1 MW system in
            2022 USD/kW (DOE hydrogen program record 24005 Clean Hydrogen Production Cost Scenarios
            with PEM Electrolyzer Technology 05/20/24) #TODO: convert to refs
            (https://www.hydrogen.energy.gov/docs/hydrogenprogramlibraries/pdfs/24005-clean-hydrogen-production-cost-pem-electrolyzer.pdf?sfvrsn=8cb10889_1)
    """

    location: str = field(validator=contains(["onshore", "offshore"]))
    electrolyzer_capex: int = field()
    time_between_replacement: int = field(validator=gt_zero)
    cost_year: int = field(default=2016, converter=int, validator=must_equal(2016))


class BasicElectrolyzerCostModel(ElectrolyzerCostBaseClass):
    """
    An OpenMDAO component that computes the cost of a PEM electrolyzer.
    """

    def setup(self):
        self.config = BasicElectrolyzerCostModelConfig.from_dict(
            merge_shared_inputs(self.options["tech_config"]["model_inputs"], "cost")
        )
        super().setup()

        self.add_input(
            "electrolyzer_size_mw",
            val=0.0,
            units="MW",
            desc="Size of the electrolyzer in MW",
        )

    def compute(self, inputs, outputs, discrete_inputs, discrete_outputs):
        # unpack inputs
        self.options["plant_config"]

        electrolyzer_size_mw = float(inputs["electrolyzer_size_mw"][0])
        electrical_generation_timeseries_kw = inputs["electricity_in"]
        electrolyzer_capex_kw = self.config.electrolyzer_capex

        # run hydrogen production cost model - from hopp examples
        if self.config.location == "onshore":
            offshore = 0
        else:
            offshore = 1

        # Basic cost modeling for a PEM electrolyzer.
        # Looking at cost projections for PEM electrolyzers over years 2022, 2025, 2030, 2035.
        # Electricity costs are calculated outside of hydrogen cost model

        # Basic information in our analysis
        kw_continuous = electrolyzer_size_mw * 1000

        # Capacity factor
        avg_generation = np.mean(electrical_generation_timeseries_kw)  # Avg Generation
        cap_factor = avg_generation / kw_continuous

        if cap_factor > 1.0:
            cap_factor = 1.0
            warnings.warn(
                "Electrolyzer capacity factor would be greater than 1 with provided energy profile."
                " Capacity factor has been reduced to 1 for electrolyzer cost estimate purposes."
            )

        # Hydrogen Production Cost From PEM Electrolysis - 2019 (HFTO Program Record)
        # https://www.hydrogen.energy.gov/pdfs/19009_h2_production_cost_pem_electrolysis_2019.pdf

        # Capital costs provide by Hydrogen Production Cost From PEM Electrolysis - 2019 (HFTO
        # Program Record)
        mechanical_bop_cost = 36  # [$/kW] for a compressor
        electrical_bop_cost = 82  # [$/kW] for a rectifier

        # Installed capital cost
        stack_installation_factor = 12 / 100  # [%] for stack cost
        elec_installation_factor = 12 / 100  # [%] and electrical BOP

        # scale installation fraction if offshore (see Singlitico 2021 https://doi.org/10.1016/j.rset.2021.100005)
        stack_installation_factor *= 1 + offshore
        elec_installation_factor *= 1 + offshore

        # mechanical BOP install cost = 0%

        # Indirect capital cost as a percentage of installed capital cost
        site_prep = 2 / 100  # [%]
        engineering_design = 10 / 100  # [%]
        project_contingency = 15 / 100  # [%]
        permitting = 15 / 100  # [%]
        land = 250000  # [$]

        total_direct_electrolyzer_cost_kw = (
            (electrolyzer_capex_kw * (1 + stack_installation_factor))
            + mechanical_bop_cost
            + (electrical_bop_cost * (1 + elec_installation_factor))
        )

        # Assign CapEx for electrolyzer from capacity based installed CapEx
        electrolyzer_total_installed_capex = (
            total_direct_electrolyzer_cost_kw * electrolyzer_size_mw * 1000
        )

        # Add indirect capital costs
        electrolyzer_total_capital_cost = (
            (
                (site_prep + engineering_design + project_contingency + permitting)
                * electrolyzer_total_installed_capex
            )
            + land
            + electrolyzer_total_installed_capex
        )

        # O&M costs
        # https://www.sciencedirect.com/science/article/pii/S2542435121003068
        # for 700 MW electrolyzer (https://www.hydrogen.energy.gov/pdfs/19009_h2_production_cost_pem_electrolysis_2019.pdf)
        h2_FOM_kg = 0.24  # [$/kg]

        # linearly scaled current central fixed O&M for a 700MW electrolyzer up to a
        # 1000MW electrolyzer
        scaled_h2_FOM_kg = h2_FOM_kg * electrolyzer_size_mw / 700

        h2_FOM_kWh = scaled_h2_FOM_kg / 55.5  # [$/kWh] used 55.5 kWh/kg for efficiency
        fixed_OM = h2_FOM_kWh * 8760  # [$/kW-y]
        property_tax_insurance = 1.5 / 100  # [% of Cap/y]
        variable_OM = 1.30  # [$/MWh]

        # Total O&M costs [% of installed cap/year]
        total_OM_costs = (
            fixed_OM + (property_tax_insurance * total_direct_electrolyzer_cost_kw)
        ) / total_direct_electrolyzer_cost_kw + (
            variable_OM / 1000 * 8760 * (cap_factor / total_direct_electrolyzer_cost_kw)
        )

        electrolyzer_OM_cost = electrolyzer_total_installed_capex * total_OM_costs  # Capacity based

        outputs["CapEx"] = electrolyzer_total_capital_cost
        outputs["OpEx"] = electrolyzer_OM_cost
