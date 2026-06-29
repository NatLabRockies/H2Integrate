import numpy as np
from attrs import field, define

from h2integrate.core.utilities import BaseConfig, merge_shared_inputs
from h2integrate.core.validators import gt_zero, contains
from h2integrate.core.model_baseclasses import (
    CostModelBaseClass,
    CostModelBaseConfig,
    PerformanceModelBaseClass,
)


@define(kw_only=True)
class SimpleThermalNuclearReactorConfig(BaseConfig):
    operating_mode: str = field(validator=contains(["heat", "electricity"]))
    electricity_command_value: float = field(validator=gt_zero)
    high_pressure_electrical_efficiency: float = field(validator=gt_zero)
    low_pressure_electrical_efficiency: float = field(validator=gt_zero)
    rated_capacity: float = field(validator=gt_zero)
    minimum_heat_extract: float = field(default=0.0)


class SimpleThermalNuclearReactorPerformanceModel(PerformanceModelBaseClass):
    """Simple thermal nuclear reactor model with heat and electricity outputs."""

    _time_step_bounds = (3600, 3600)

    def initialize(self):
        super().initialize()
        self.commodity = "electricity"
        self.commodity_rate_units = "kW"
        self.commodity_amount_units = "kW*h"


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
            desc="Available reactor thermal capacity",
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
            units="kW",
            desc="Minimum thermal output reserved for process heat extraction",
        )
        self.add_input(
            "heat_command_value",
            val=6400,
            shape=self.n_timesteps,
            units="kW",
            desc="Requested process heat demand from downstream technologies",
        )

        self.add_output("high_pressure_heat_demanded", val=0.0, shape=self.n_timesteps, units="kW")
        self.add_output("high_pressure_heat", val=0.0, shape=self.n_timesteps, units="kW")
        self.add_output("low_pressure_heat", val=0.0, shape=self.n_timesteps, units="kW")
        self.add_output("heat_out", val=0.0, shape=self.n_timesteps, units="kW")
 
    def compute(self, inputs, outputs, discrete_inputs, discrete_outputs):
        operating_mode = discrete_inputs["operating_mode"]
        hp_eff = float(inputs["high_pressure_electrical_efficiency"][0])
        lp_eff = float(inputs["low_pressure_electrical_efficiency"][0])
        electric_capacity_mw = float(inputs["rated_capacity"][0]) * 1e-3  # convert kW to MW
        minimum_heat_extract_kw = np.maximum(inputs["minimum_heat_extract"], 0.0)  #maintain kW rating
        requested_power_mw = np.maximum(inputs["electricity_command_value"], 0.0) * 1e-3 #convert kW to MW, fix >0
        external_heat_demand_kw = np.maximum(inputs["heat_command_value"], 0.0) #maintaining kW rating
      
        combined_efficiency = hp_eff + (1.0 - hp_eff) * lp_eff
        if combined_efficiency <= 0.0:
            raise ValueError("Combined nuclear electric efficiency must be greater than zero")
        if lp_eff <= 0.0:
            raise ValueError("Low-pressure electrical efficiency must be greater than zero")

        thermal_capacity_mw = electric_capacity_mw / combined_efficiency
        high_pressure_electricity_mw = thermal_capacity_mw * hp_eff
        available_process_heat_mw = thermal_capacity_mw * (1.0 - hp_eff)
        heat_demand_mw = np.maximum(external_heat_demand_kw, minimum_heat_extract_kw) * 1e-3 #convert to MW from kW
        
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

        high_pressure_heat_kw = np.full(self.n_timesteps, available_process_heat_mw * 1000.0)
        low_pressure_heat_kw = low_pressure_heat_remaining_mw * 1000.0
        electricity_out_kw = electricity_out_mw * 1000.0
        heat_out_kw = heat_out_mw * 1000.0

        outputs["high_pressure_heat_demanded"] = heat_demand_mw * 1000.0
        outputs["high_pressure_heat"] = high_pressure_heat_kw
        outputs["low_pressure_heat"] = low_pressure_heat_kw
        outputs["heat_out"] = heat_out_kw
        outputs["electricity_out"] = electricity_out_kw
        outputs["rated_electricity_production"] = electric_capacity_mw * 1000.0

        total_electricity = np.sum(electricity_out_kw) * (self.dt / 3600.0)
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
    rated_capacity: float = field(validator=gt_zero)
    nuclear_reactor_upfront_cost: float = field(validator=gt_zero)
    nuclear_reactor_fixed_om_cost: float = field(validator=gt_zero)
    nuclear_reactor_variable_om_cost: float = field(validator=gt_zero)
    cost_year: int = field(default=2025, converter=int)


class SimpleThermalNuclearReactorCostModel(CostModelBaseClass):
    """Simple cost model for the thermal nuclear reactor."""

    _time_step_bounds = (3600, 3600)

    def setup(self):
        self.dt = self.options["plant_config"]["plant"]["simulation"]["dt"]
        self.plant_life = int(self.options["plant_config"]["plant"]["plant_life"])
        n_timesteps = int(self.options["plant_config"]["plant"]["simulation"]["n_timesteps"])
        self.config = SimpleThermalNuclearReactorCostConfig.from_dict(
            merge_shared_inputs(self.options["tech_config"]["model_inputs"], "cost"),
            strict=False,
            additional_cls_name=self.__class__.__name__,
        )
        super().setup()

        self.add_input(
            "rated_capacity",
            val=self.config.rated_capacity,
            units="kW",
        )
        self.add_input(
            "nuclear_reactor_upfront_cost",
            val=self.config.nuclear_reactor_upfront_cost,
            units="USD/kW",
        )
        self.add_input(
            "nuclear_reactor_fixed_om_cost",
            val=self.config.nuclear_reactor_fixed_om_cost,
            units="USD/(kW*year)",
        )
        self.add_input(
            "nuclear_reactor_variable_om_cost",
            val=self.config.nuclear_reactor_variable_om_cost,
            units="USD/(kW*h)",
        )
        self.add_input("electricity_out", val=0.0, shape=n_timesteps, units="kW")

    def compute(self, inputs, outputs, discrete_inputs, discrete_outputs):
        rated_capacity_kw = float(inputs["rated_capacity"][0])
        upfront_cost_per_kw = float(inputs["nuclear_reactor_upfront_cost"][0])
        fixed_om_per_kw_year = float(inputs["nuclear_reactor_fixed_om_cost"][0])
        variable_om_per_kwh = float(inputs["nuclear_reactor_variable_om_cost"][0])

        outputs["CapEx"] = rated_capacity_kw * upfront_cost_per_kw
        outputs["OpEx"] = fixed_om_per_kw_year * rated_capacity_kw

        delivered_electricity_kwh = np.sum(inputs["electricity_out"]) * (self.dt / 3600.0)
        annual_variable_om = variable_om_per_kwh * delivered_electricity_kwh
        outputs["VarOpEx"] = np.full(self.plant_life, annual_variable_om)
