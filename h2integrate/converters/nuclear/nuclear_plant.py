import numpy as np
from attrs import field, define

from h2integrate.core.utilities import BaseConfig, merge_shared_inputs
from h2integrate.core.validators import gt_zero, range_val
from h2integrate.core.model_baseclasses import (
    CostModelBaseClass,
    CostModelBaseConfig,
    PerformanceModelBaseClass,
)


@define(kw_only=True)
class NuclearPerformanceConfig(BaseConfig):
    """Configuration class for the nuclear plant performance model.

    Args:
            system_capacity_mw (float): Rated electric capacity in MW.
            capacity_factor (float): Average availability (0-1).
    """

    system_capacity_mw: float = field(validator=gt_zero)
    capacity_factor: float = field(validator=range_val(0.0, 1.0))


class NuclearPerformanceModel(PerformanceModelBaseClass):
    """
    Simple nuclear performance model producing electricity.

    The model limits output by a fixed capacity factor and optional demand profile.
    """

    def initialize(self):
        super().initialize()
        self.commodity = "electricity"
        self.commodity_rate_units = "MW"
        self.commodity_amount_units = "MW*h"

    def setup(self):
        super().setup()
        n_timesteps = self.options["plant_config"]["plant"]["simulation"]["n_timesteps"]

        self.config = NuclearPerformanceConfig.from_dict(
            merge_shared_inputs(self.options["tech_config"]["model_inputs"], "performance"),
            additional_cls_name=self.__class__.__name__,
        )

        self.add_input(
            "system_capacity",
            val=self.config.system_capacity_mw,
            units="MW",
            desc="Nuclear plant rated capacity",
        )
        self.add_input(
            f"{self.commodity}_demand",
            val=self.config.system_capacity_mw,
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
class NuclearCostModelConfig(CostModelBaseConfig):
    """Configuration class for the nuclear plant cost model.

    Args:
            system_capacity_mw (float): Rated electric capacity in MW.
            reactor_type (str): Key selecting a reactor type in type_costs.
            type_costs (dict): Reactor type cost data with keys:
                    capex_per_kw, fixed_opex_per_kw_year, variable_opex_per_mwh
                    Optional: reference_capacity_mw, capex_scaling_exponent
            cost_year (int): Dollar year corresponding to input costs.
    """

    system_capacity_mw: float = field(validator=gt_zero)
    reactor_type: str = field()
    type_costs: dict = field()

    def __attrs_post_init__(self):
        if self.reactor_type not in self.type_costs:
            raise ValueError(
                f"reactor_type '{self.reactor_type}' not found in type_costs keys: "
                f"{list(self.type_costs.keys())}"
            )
        required = {"capex_per_kw", "fixed_opex_per_kw_year", "variable_opex_per_mwh"}
        missing = required - set(self.type_costs[self.reactor_type].keys())
        if missing:
            raise ValueError("type_costs entry is missing required keys: " f"{sorted(missing)}")


class NuclearCostModel(CostModelBaseClass):
    """
    Cost model for nuclear power plants.

    The model supports type-based parameters and optional scaling by size.
    """

    def setup(self):
        self.config = NuclearCostModelConfig.from_dict(
            merge_shared_inputs(self.options["tech_config"]["model_inputs"], "cost"),
            additional_cls_name=self.__class__.__name__,
        )
        n_timesteps = self.options["plant_config"]["plant"]["simulation"]["n_timesteps"]
        self.plant_life = int(self.options["plant_config"]["plant"]["plant_life"])

        super().setup()

        self.add_input(
            "system_capacity",
            val=self.config.system_capacity_mw,
            units="MW",
            desc="Nuclear plant capacity",
        )
        self.add_input(
            "electricity_out",
            val=0.0,
            shape=n_timesteps,
            units="MW",
            desc="Hourly electricity output from performance model",
        )

    def compute(self, inputs, outputs, discrete_inputs, discrete_outputs):
        type_costs = self.config.type_costs[self.config.reactor_type]
        capex_per_kw = type_costs["capex_per_kw"]
        fixed_opex_per_kw_year = type_costs["fixed_opex_per_kw_year"]
        variable_opex_per_mwh = type_costs["variable_opex_per_mwh"]
        reference_capacity_mw = type_costs.get(
            "reference_capacity_mw", self.config.system_capacity_mw
        )
        capex_scaling_exponent = type_costs.get("capex_scaling_exponent", 1.0)

        if reference_capacity_mw <= 0:
            raise ValueError("reference_capacity_mw must be greater than zero")

        system_capacity_mw = inputs["system_capacity"]
        capacity_kw = system_capacity_mw * 1000
        scale_ratio = system_capacity_mw / reference_capacity_mw

        scaled_capex_per_kw = capex_per_kw * (scale_ratio ** (capex_scaling_exponent - 1.0))
        capex = scaled_capex_per_kw * capacity_kw

        electricity_out = inputs["electricity_out"]
        dt = self.options["plant_config"]["plant"]["simulation"]["dt"]
        delivered_electricity_MWh = electricity_out.sum() * dt / 3600

        fixed_om = fixed_opex_per_kw_year * capacity_kw
        variable_om = variable_opex_per_mwh * delivered_electricity_MWh

        outputs["CapEx"] = capex
        outputs["OpEx"] = fixed_om + variable_om
        outputs["VarOpEx"] = np.full(self.plant_life, variable_om)
