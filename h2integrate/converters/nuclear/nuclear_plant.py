import numpy as np
from attrs import field, define

from h2integrate.core.utilities import BaseConfig, merge_shared_inputs
from h2integrate.core.validators import gt_zero, gte_zero
from h2integrate.core.model_baseclasses import (
    CostModelBaseClass,
    CostModelBaseConfig,
    PerformanceModelBaseClass,
)


@define(kw_only=True)
class NuclearPerformanceConfig(BaseConfig):
    """Configuration class for the nuclear plant performance model.

    Args:
        system_capacity_kw (float): Rated electric capacity in kW.
    """

    system_capacity_kw: float = field(validator=gt_zero)


class QuinnNuclearPerformanceModel(PerformanceModelBaseClass):
    """
    Simple nuclear performance model producing electricity.

    The model limits output by a fixed capacity factor and optional demand profile.

    Based on Quinn, J. et al., 2023.
    Small modular reactor light water reactor techno-economic analysis.
    Applied Energy 120669.
    https://doi.org/10.1016/j.apenergy.2023.120669
    """

    _time_step_bounds = (
        3600,
        3600,
    )  # (min, max) time step lengths (in seconds) compatible with this model

    def initialize(self):
        super().initialize()
        self.commodity = "electricity"
        self.commodity_rate_units = "kW"
        self.commodity_amount_units = "kW*h"

    def setup(self):
        super().setup()
        n_timesteps = self.options["plant_config"]["plant"]["simulation"]["n_timesteps"]

        self.config = NuclearPerformanceConfig.from_dict(
            merge_shared_inputs(self.options["tech_config"]["model_inputs"], "performance"),
            additional_cls_name=self.__class__.__name__,
        )

        self.add_input(
            "system_capacity",
            val=self.config.system_capacity_kw,
            units="kW",
            desc="Nuclear plant rated capacity",
        )
        self.add_input(
            f"{self.commodity}_demand",
            val=self.config.system_capacity_kw,
            shape=n_timesteps,
            units=self.commodity_rate_units,
            desc="Electricity demand for nuclear plant",
        )

    def compute(self, inputs, outputs):
        system_capacity = inputs["system_capacity"]
        electricity_demand = inputs[f"{self.commodity}_demand"]

        electricity_out = np.minimum(electricity_demand, system_capacity)
        electricity_out = np.clip(electricity_out, 0.0, system_capacity)

        outputs["electricity_out"] = electricity_out
        outputs["rated_electricity_production"] = system_capacity

        total_electricity = np.sum(electricity_out) * (self.dt / 3600)
        outputs["total_electricity_produced"] = total_electricity
        outputs["annual_electricity_produced"] = total_electricity * (
            1 / self.fraction_of_year_simulated
        )

        max_production = system_capacity * len(electricity_out) * (self.dt / 3600)
        outputs["capacity_factor"] = (
            total_electricity / max_production if max_production > 0 else 0.0
        )


@define(kw_only=True)
class QuinnNuclearCostModelConfig(CostModelBaseConfig):
    """Configuration class for the nuclear plant cost model.

    Args:
        system_capacity_kw (float): Rated electric capacity in kW.
        capex_per_kw (float): Capital cost per kW.
        fixed_opex_per_kw_year (float): Fixed O&M per kW per year.
        variable_opex_per_mwh (float): Variable O&M per MWh.
        reference_capacity_kw (float | None): Reference capacity for capex scaling in kW.
        capex_scaling_exponent (float): Capex scaling exponent.
        cost_year (int): Dollar year corresponding to input costs.
    """

    system_capacity_kw: float = field(validator=gt_zero)
    capex_per_kw: float = field(validator=gte_zero)
    fixed_opex_per_kw_year: float = field(validator=gte_zero)
    variable_opex_per_mwh: float = field(validator=gte_zero)
    reference_capacity_kw: float | None = field(default=None)
    capex_scaling_exponent: float = field(default=1.0, validator=gt_zero)

    def __attrs_post_init__(self):
        if self.reference_capacity_kw is None:
            self.reference_capacity_kw = self.system_capacity_kw
        if self.reference_capacity_kw <= 0:
            raise ValueError("reference_capacity_kw must be greater than zero")


class QuinnNuclearCostModel(CostModelBaseClass):
    """
    Cost model for nuclear power plants.

    The model supports type-based parameters and optional scaling by size.

    Based on Quinn, J. et al., 2023.
    Small modular reactor light water reactor techno-economic analysis.
    Applied Energy 120669.
    https://doi.org/10.1016/j.apenergy.2023.120669
    """

    _time_step_bounds = (
        3600,
        3600,
    )  # (min, max) time step lengths (in seconds) compatible with this model

    def setup(self):
        self.config = QuinnNuclearCostModelConfig.from_dict(
            merge_shared_inputs(self.options["tech_config"]["model_inputs"], "cost"),
            additional_cls_name=self.__class__.__name__,
        )
        n_timesteps = self.options["plant_config"]["plant"]["simulation"]["n_timesteps"]
        self.plant_life = int(self.options["plant_config"]["plant"]["plant_life"])

        super().setup()

        self.add_input(
            "system_capacity",
            val=self.config.system_capacity_kw,
            units="kW",
            desc="Nuclear plant capacity",
        )
        self.add_input(
            "electricity_out",
            val=0.0,
            shape=n_timesteps,
            units="kW",
            desc="Hourly electricity output from performance model",
        )

    def compute(self, inputs, outputs, discrete_inputs, discrete_outputs):
        capex_per_kw = self.config.capex_per_kw
        fixed_opex_per_kw_year = self.config.fixed_opex_per_kw_year
        variable_opex_per_mwh = self.config.variable_opex_per_mwh
        reference_capacity_kw = self.config.reference_capacity_kw
        capex_scaling_exponent = self.config.capex_scaling_exponent

        system_capacity_kw = inputs["system_capacity"]
        scale_ratio = system_capacity_kw / reference_capacity_kw

        scaled_capex_per_kw = capex_per_kw * (scale_ratio ** (capex_scaling_exponent - 1.0))
        capex = scaled_capex_per_kw * system_capacity_kw

        electricity_out = inputs["electricity_out"]
        dt = self.options["plant_config"]["plant"]["simulation"]["dt"]
        delivered_electricity_mwh = electricity_out.sum() * dt / 3600 / 1000.0

        fixed_om = fixed_opex_per_kw_year * system_capacity_kw
        variable_om = variable_opex_per_mwh * delivered_electricity_mwh

        outputs["CapEx"] = capex
        outputs["OpEx"] = fixed_om
        outputs["VarOpEx"] = np.full(self.plant_life, variable_om)
