import numpy as np
from attrs import field, define, validators

from h2integrate.core.utilities import BaseConfig, merge_shared_inputs
from h2integrate.core.model_baseclasses import (
    CostModelBaseClass,
    CostModelBaseConfig,
    PerformanceModelBaseClass,
)


@define(kw_only=True)
class SimpleThermalNuclearReactorConfig(BaseConfig):
    """Configuration class for the thermal nuclear reactor performance model.

    Args:
        operating_mode (str): Dispatch mode of the reactor. Must be ``"heat"`` or
            ``"electricity"``. In ``heat`` mode the reactor satisfies process heat demand
            first and converts the remaining low-pressure heat to electricity; in
            ``electricity`` mode it satisfies the electricity command first and delivers
            the remaining available heat.
        electricity_command_value (float): Requested electrical output in kW.
        high_pressure_electrical_efficiency (float): Fraction of total thermal input
            converted to electricity in the high-pressure stage (unitless).
        low_pressure_electrical_efficiency (float): Efficiency applied to the remaining
            low-pressure heat when generating electricity (unitless).
        rated_capacity (float): Rated electrical capacity in kW, used to infer the reactor
            thermal capacity.
        minimum_heat_extract (float): Minimum process heat reserved for extraction in kW.
            Defaults to ``0.0``.
    """

    operating_mode: str = field(validator=validators.in_(["heat", "electricity"]))
    electricity_command_value: float = field(validator=validators.gt(0))
    high_pressure_electrical_efficiency: float = field(
        validator=(validators.ge(0), validators.le(1))
    )
    low_pressure_electrical_efficiency: float = field(
        validator=(validators.ge(0), validators.le(1))
    )
    rated_capacity: float = field(validator=validators.gt(0))
    minimum_heat_extract: float = field(default=0.0)


class SimpleThermalNuclearReactorPerformanceModel(PerformanceModelBaseClass):
    """Simple thermal nuclear reactor model with heat and electricity outputs.

    This model represents a reactor with a high-pressure electric conversion stage, a
    low-pressure electric conversion stage, and an extractable process heat stream taken
    upstream of the low-pressure turbine stages. It trades off electricity production and
    process heat delivery according to the selected operating mode, making it suitable for
    coupled workflows such as nuclear plus HTSE.

    The reactor infers its thermal capacity from the rated electrical capacity using a
    combined electric efficiency and supports two operating modes:

    - ``heat``: satisfy heat demand first, then convert the remaining low-pressure heat to
      electricity.
    - ``electricity``: satisfy the electricity command first, then send the remaining
      available process heat to ``heat_out``.
    """

    _time_step_bounds = (3600, 3600)

    def initialize(self) -> None:
        super().initialize()
        self.commodity = "electricity"
        self.commodity_rate_units = "MW"
        self.commodity_amount_units = "MW*h"

    def setup(self):
        self.config = SimpleThermalNuclearReactorConfig.from_dict(
            merge_shared_inputs(self.options["tech_config"]["model_inputs"], "performance"),
            strict=False,
            additional_cls_name=self.__class__.__name__,
        )
        super().setup()

        self.add_discrete_input("operating_mode", val=self.config.operating_mode)
        self.add_input(
            f"{self.commodity}_command_value",
            val=self.config.electricity_command_value,
            shape=self.n_timesteps,
            units=self.commodity_rate_units,
            desc="Requested electric power setpoint",
        )
        self.add_input(
            "rated_capacity",
            val=self.config.rated_capacity,
            units=self.commodity_rate_units,
            desc="Available reactor electrical capacity",
        )
        self.add_input(
            "high_pressure_electrical_efficiency",
            val=self.config.high_pressure_electrical_efficiency,
            units="unitless",
        )
        self.add_input(
            "low_pressure_electrical_efficiency",
            val=self.config.low_pressure_electrical_efficiency,
            units="unitless",
        )
        self.add_input(
            "minimum_heat_extract",
            val=self.config.minimum_heat_extract,
            units="MW",
            desc="Minimum thermal output reserved for process heat extraction",
        )
        self.add_input(
            "heat_command_value",
            val=6400,
            shape=self.n_timesteps,
            units="MW",
            desc="Requested process heat demand from downstream technologies",
        )

        self.add_output(
            "high_pressure_heat_demanded",
            val=0.0,
            shape=self.n_timesteps,
            units=self.commodity_rate_units,
        )
        self.add_output(
            "high_pressure_heat", val=0.0, shape=self.n_timesteps, units=self.commodity_rate_units
        )
        self.add_output(
            "low_pressure_heat", val=0.0, shape=self.n_timesteps, units=self.commodity_rate_units
        )
        self.add_output(
            "heat_out", val=0.0, shape=self.n_timesteps, units=self.commodity_rate_units
        )

    def compute(self, inputs, outputs, discrete_inputs, discrete_outputs):
        operating_mode = discrete_inputs["operating_mode"]
        hp_eff = float(inputs["high_pressure_electrical_efficiency"][0])
        lp_eff = float(inputs["low_pressure_electrical_efficiency"][0])
        electric_capacity_mw = float(inputs["rated_capacity"][0])
        minimum_heat_extract_mw = np.maximum(
            inputs["minimum_heat_extract"], 0.0
        )  # maintain MW rating
        requested_power_mw = np.maximum(inputs["electricity_command_value"], 0.0)  # fix >0
        external_heat_demand_mw = np.maximum(inputs["heat_command_value"], 0.0)

        combined_efficiency = hp_eff + (1.0 - hp_eff) * lp_eff
        if combined_efficiency <= 0.0:
            raise ValueError("Combined nuclear electric efficiency must be greater than zero")
        if lp_eff <= 0.0:
            raise ValueError("Low-pressure electrical efficiency must be greater than zero")

        thermal_capacity_mw = electric_capacity_mw / combined_efficiency
        high_pressure_electricity_mw = thermal_capacity_mw * hp_eff
        available_process_heat_mw = thermal_capacity_mw * (1.0 - hp_eff)
        heat_demand_mw = np.maximum(external_heat_demand_mw, minimum_heat_extract_mw)

        if operating_mode == "heat":
            heat_out_mw = np.minimum(heat_demand_mw, available_process_heat_mw)
            electricity_out_mw = (
                high_pressure_electricity_mw + (available_process_heat_mw - heat_out_mw) * lp_eff
            )
        elif operating_mode == "electricity":
            electricity_out_mw = np.minimum(requested_power_mw, electric_capacity_mw)
            heat_out_mw = (
                available_process_heat_mw
                - (electricity_out_mw - high_pressure_electricity_mw) / lp_eff
            )
            heat_out_mw = np.clip(heat_out_mw, 0.0, available_process_heat_mw)
        else:
            raise NotImplementedError(
                "The nuclear operating_mode must be either 'heat' or 'electricity'"
            )

        electricity_out_mw = np.clip(electricity_out_mw, 0.0, electric_capacity_mw)
        low_pressure_heat_remaining_mw = available_process_heat_mw - heat_out_mw

        high_pressure_heat_mw = np.full(self.n_timesteps, available_process_heat_mw)
        low_pressure_heat_mw = low_pressure_heat_remaining_mw
        heat_out_mw = heat_out_mw

        outputs["high_pressure_heat_demanded"] = heat_demand_mw
        outputs["high_pressure_heat"] = high_pressure_heat_mw
        outputs["low_pressure_heat"] = low_pressure_heat_mw
        outputs["heat_out"] = heat_out_mw
        outputs["electricity_out"] = electricity_out_mw
        outputs["rated_electricity_production"] = electric_capacity_mw

        total_electricity = np.sum(electricity_out_mw) * (self.dt / 3600.0)
        outputs["total_electricity_produced"] = total_electricity
        annual_electricity = total_electricity / self.fraction_of_year_simulated
        outputs["annual_electricity_produced"] = np.full(self.plant_life, annual_electricity)

        avg_electricity_out_mw = float(np.mean(electricity_out_mw))
        capacity_factor = (
            avg_electricity_out_mw / electric_capacity_mw if electric_capacity_mw > 0.0 else 0.0
        )
        outputs["capacity_factor"] = np.full(self.plant_life, capacity_factor)
        outputs["replacement_schedule"] = np.zeros(self.plant_life)


@define(kw_only=True)
class SimpleThermalNuclearReactorCostConfig(CostModelBaseConfig):
    """Configuration class for the thermal nuclear reactor cost model.

    Args:
        rated_capacity (float): Rated capacity used for cost calculations in kW.
        upfront_cost (float): Capital cost per kW in USD/kW.
        fixed_om_cost (float): Fixed annual O&M in USD/(kW*year).
        variable_om_cost (float): Variable O&M applied to the simulated
            electricity production in USD/(kW*h).
        cost_year (int): Dollar year corresponding to the input costs. Defaults to ``2025``.
    """

    rated_capacity: float = field(validator=validators.gt(0))
    upfront_cost: float = field(validator=validators.gt(0))
    fixed_om_cost: float = field(validator=validators.gt(0))
    variable_om_cost: float = field(validator=validators.gt(0))
    cost_year: int = field(default=2025, converter=int)


class SimpleThermalNuclearReactorCostModel(CostModelBaseClass):
    """Simple cost model for the thermal nuclear reactor.

    The model applies capacity-based capital and fixed O&M costs and computes variable O&M
    from the delivered electricity:

    - ``CapEx`` from ``rated_capacity * upfront_cost``
    - ``OpEx`` from ``rated_capacity * fixed_om_cost``
    - ``VarOpEx`` from ``variable_om_cost`` applied to the simulated
      electricity output, repeated across the plant life.
    """

    _time_step_bounds = (3600, 3600)

    def setup(self) -> None:
        self.dt = self.options["plant_config"]["plant"]["simulation"]["dt"]
        self.plant_life = int(self.options["plant_config"]["plant"]["plant_life"])
        n_timesteps = int(self.options["plant_config"]["plant"]["simulation"]["n_timesteps"])
        self.fraction_of_year_simulated = (self.dt * n_timesteps / 3600.0) / 8760.0
        self.config = SimpleThermalNuclearReactorCostConfig.from_dict(
            merge_shared_inputs(self.options["tech_config"]["model_inputs"], "cost"),
            strict=False,
            additional_cls_name=self.__class__.__name__,
        )
        super().setup()

        self.add_input(
            "rated_capacity",
            val=self.config.rated_capacity,
            units="MW",
        )
        self.add_input(
            "upfront_cost",
            val=self.config.upfront_cost,
            units="USD/MW",
        )
        self.add_input(
            "fixed_om_cost",
            val=self.config.fixed_om_cost,
            units="USD/(MW*year)",
        )
        self.add_input(
            "variable_om_cost",
            val=self.config.variable_om_cost,
            units="USD/(MW*h)",
        )
        self.add_input("electricity_out", val=0.0, shape=n_timesteps, units="kW")

    def compute(self, inputs, outputs, discrete_inputs, discrete_outputs):
        rated_capacity_mw = float(inputs["rated_capacity"][0])
        upfront_cost_per_mw = float(inputs["upfront_cost"][0])
        fixed_om_per_kw_year = float(inputs["fixed_om_cost"][0])
        variable_om_per_mwh = float(inputs["variable_om_cost"][0])

        outputs["CapEx"] = rated_capacity_mw * upfront_cost_per_mw
        outputs["OpEx"] = fixed_om_per_kw_year * rated_capacity_mw

        delivered_electricity_mwh = np.sum(inputs["electricity_out"]) * (self.dt / 3600.0)
        annual_variable_om = (
            variable_om_per_mwh * delivered_electricity_mwh / (self.fraction_of_year_simulated)
        )
        outputs["VarOpEx"] = np.full(self.plant_life, annual_variable_om)
