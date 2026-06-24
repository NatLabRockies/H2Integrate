import math

import numpy as np
from attrs import define, field

from h2integrate.converters.hydrogen.electrolyzer_baseclass import (
    ElectrolyzerCostBaseClass,
    ElectrolyzerPerformanceBaseClass,
)
from h2integrate.converters.hydrogen.utilities import size_electrolyzer_for_hydrogen_demand
from h2integrate.core.model_baseclasses import CostModelBaseConfig, ResizeablePerformanceModelBaseConfig
from h2integrate.core.utilities import merge_shared_inputs
from h2integrate.core.validators import contains, gt_zero


@define(kw_only=True)
class HTSEElectrolyzerPerformanceModelConfig(ResizeablePerformanceModelBaseConfig):
    """Configuration for the HTSE performance model."""

    n_clusters: int = field(validator=gt_zero)
    nominal_heat_required: float = field(validator=gt_zero)
    nominal_electricity_required: float = field(validator=gt_zero)
    location: str = field(default="onshore", validator=contains(["onshore", "offshore"]))
    cluster_rating_MW: float = field(validator=gt_zero)
    eol_eff_percent_loss: float = field(default=10.0, validator=gt_zero)
    uptime_hours_until_eol: int = field(default=80000, validator=gt_zero)
    include_degradation_penalty: bool = field(default=False)
    turndown_ratio: float = field(default=0.1, validator=gt_zero)
    pressure_H2: float = field(default=1.0, validator=gt_zero)


class HTSEPerformanceModel(ElectrolyzerPerformanceBaseClass):
    """A simplified HTSE model using electricity and heat inputs."""

    def setup(self):
        self.config = HTSEElectrolyzerPerformanceModelConfig.from_dict(
            merge_shared_inputs(self.options["tech_config"]["model_inputs"], "performance"),
            strict=False,
            additional_cls_name=self.__class__.__name__,
        )
        super().setup()

        self.add_output(
            "efficiency",
            val=0.0,
            units="unitless",
            desc="Average first-law efficiency based on utilized input energy",
        )
        self.add_output(
            "time_until_replacement",
            val=float(self.config.uptime_hours_until_eol),
            units="h",
            desc="Operating hours until replacement",
        )
        self.add_input(
            "n_clusters",
            val=self.config.n_clusters,
            units="unitless",
            desc="Number of HTSE clusters in the system",
        )
        self.add_input(
            "heat_in",
            val=0.0,
            shape=self.n_timesteps,
            units="kW",
            desc="Thermal energy supplied to the HTSE system",
        )
        self.add_output(
            "electrolyzer_size_mw",
            val=0.0,
            units="MW",
            desc="Installed HTSE nameplate capacity",
        )
        self.add_input("cluster_size", val=-1.0, units="MW")
        self.add_input("max_hydrogen_capacity", val=1000.0, units="kg/h")

        self.add_output(
            "water_demand",
            val=0.0,
            shape=self.n_timesteps,
            units="kg/h",
            desc="Water consumption",
        )
        self.add_output(
            "heat_demand",
            val=0.0,
            shape=self.n_timesteps,
            units="kW",
            desc="Thermal energy used by the HTSE system",
        )
        self.add_output(
            "electricity_demand",
            val=0.0,
            shape=self.n_timesteps,
            units="kW",
            desc="Electric energy used by the HTSE system",
        )

    def compute(self, inputs, outputs, discrete_inputs, discrete_outputs):
        electrolyzer_size_mw = float(inputs["n_clusters"][0]) * self.config.cluster_rating_MW

        size_mode = discrete_inputs["size_mode"]
        if size_mode != "normal":
            size_flow = discrete_inputs["flow_used_for_sizing"]
            if size_mode == "resize_by_max_feedstock":
                feed_ratio = max(float(inputs["max_feedstock_ratio"][0]), 1.0e-6)
                if size_flow == "electricity":
                    electrolyzer_size_mw = np.max(inputs["electricity_in"]) / 1000.0 * feed_ratio
                else:
                    raise ValueError(f"Cannot resize for '{size_flow}' feedstock")
            elif size_mode == "resize_by_max_commodity":
                comm_ratio = max(float(inputs["max_commodity_ratio"][0]), 1.0e-6)
                if size_flow == "hydrogen":
                    electrolyzer_size_mw = size_electrolyzer_for_hydrogen_demand(
                        float(inputs["max_hydrogen_capacity"][0]) * comm_ratio
                    )
                else:
                    raise ValueError(f"Cannot resize for '{size_flow}' commodity")
            else:
                raise NotImplementedError(f"Sizing mode '{size_mode}' not implemented")

        n_clusters = max(1, int(math.ceil(electrolyzer_size_mw / self.config.cluster_rating_MW)))
        electrolyzer_size_mw = n_clusters * self.config.cluster_rating_MW
        electrolyzer_size_kw = electrolyzer_size_mw * 1000.0

        heat_available_kw = inputs["heat_in"]
        electricity_available_kw =inputs["electricity_in"]
        total_specific_energy = (
            self.config.nominal_heat_required + self.config.nominal_electricity_required
        )
        rated_hydrogen_production = electrolyzer_size_kw / self.config.nominal_electricity_required

        hydrogen_from_energy = (electricity_available_kw + heat_available_kw) / total_specific_energy
        hydrogen_out = np.minimum(hydrogen_from_energy, rated_hydrogen_production)

        min_turn_down = self.config.turndown_ratio * rated_hydrogen_production
        hydrogen_out = np.where(hydrogen_out >= min_turn_down, hydrogen_out, 0.0)

        heat_demand_kw = hydrogen_out * self.config.nominal_heat_required
        actual_heat_kw = np.minimum(heat_demand_kw, heat_available_kw)
        electricity_demand_kw = hydrogen_out * total_specific_energy - actual_heat_kw
        electricity_demand_kw = np.minimum(electricity_demand_kw, electricity_available_kw)

        outputs["hydrogen_out"] = hydrogen_out
        outputs["heat_demand"] = self.config.nominal_heat_required*electrolyzer_size_kw
        outputs["electricity_demand"] = electricity_demand_kw
        outputs["water_demand"] = hydrogen_out * 18.015 / 2.016
        outputs["rated_hydrogen_production"] = rated_hydrogen_production
        outputs["electrolyzer_size_mw"] = electrolyzer_size_mw

        total_hydrogen_produced = np.sum(hydrogen_out) * (self.dt / 3600.0)
        outputs["total_hydrogen_produced"] = total_hydrogen_produced
        annual_hydrogen = total_hydrogen_produced / self.fraction_of_year_simulated
        outputs["annual_hydrogen_produced"] = np.full(self.plant_life, annual_hydrogen)

        max_production = rated_hydrogen_production * self.n_timesteps * (self.dt / 3600.0)
        capacity_factor = total_hydrogen_produced / max_production if max_production > 0 else 0.0
        outputs["capacity_factor"] = np.full(self.plant_life, capacity_factor)

        utilized_input_kw = actual_heat_kw + electricity_demand_kw
        available_input_kw = heat_available_kw + electricity_available_kw
        with np.errstate(divide="ignore", invalid="ignore"):
            timestep_efficiency = np.divide(
                utilized_input_kw,
                available_input_kw,
                out=np.zeros_like(utilized_input_kw),
                where=available_input_kw > 0,
            )
        outputs["efficiency"] = float(np.mean(timestep_efficiency))

        refurb_schedule = np.zeros(self.plant_life)
        refurb_period = max(1, round(self.config.uptime_hours_until_eol / 8760))
        refurb_schedule[refurb_period : self.plant_life : refurb_period] = 1.0
        outputs["replacement_schedule"] = refurb_schedule
        outputs["time_until_replacement"] = float(self.config.uptime_hours_until_eol)


@define(kw_only=True)
class HTSECostModelConfig(CostModelBaseConfig):
    """Configuration for the HTSE cost model."""

    unit_capex: float = field(validator=gt_zero)
    fixed_opex: float | None = field(default=None)
    fixed_capex: float | None = field(default=None)
    cost_year: int = field(default=2025, converter=int)

    def __attrs_post_init__(self):
        if self.fixed_opex is None:
            self.fixed_opex = 0.0 if self.fixed_capex is None else float(self.fixed_capex)


class HTSECostModel(ElectrolyzerCostBaseClass):
    """A simple size-based cost model for HTSE."""

    def setup(self):
        self.config = HTSECostModelConfig.from_dict(
            merge_shared_inputs(self.options["tech_config"]["model_inputs"], "cost"),
            strict=False,
            additional_cls_name=self.__class__.__name__,
        )
        super().setup()

        self.add_input(
            "electrolyzer_size_mw",
            val=0.0,
            units="MW",
            desc="Installed HTSE nameplate capacity",
        )

    def compute(self, inputs, outputs, discrete_inputs, discrete_outputs):
        electrolyzer_size_kw = float(inputs["electrolyzer_size_mw"][0]) * 1000.0
        outputs["CapEx"] = self.config.unit_capex * electrolyzer_size_kw
        outputs["OpEx"] = self.config.fixed_opex * electrolyzer_size_kw
