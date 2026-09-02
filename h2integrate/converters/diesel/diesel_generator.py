import numpy as np
from attrs import field, define, validators
from openmdao.utils import units

from h2integrate.core.utilities import BaseConfig, merge_shared_inputs
from h2integrate.core.model_baseclasses import (
    CostModelBaseClass,
    CostModelBaseConfig,
    PerformanceModelBaseClass,
)


@define(kw_only=True)
class DieselGeneratorPerformanceConfig(BaseConfig):
    """
    Configuration class for diesel generator performance model.

    Attributes:
        system_capacity_kw (float): Rated capacity of the diesel generator in kW.
        heat_rate_gal_per_mwh (float): Heat rate of the diesel generator in gal/MWh.
            This represents the volume of diesel fuel required to produce one MWh of
            electricity. Lower values indicate higher efficiency. Typical values for
            modern diesel generators are 65-85 gal/MWh (roughly 30-40% efficient at HHV).
    """

    system_capacity_kw: float = field(validator=validators.ge(0))
    heat_rate_gal_per_mwh: float = field(validator=validators.gt(0))


class DieselGeneratorPerformanceModel(PerformanceModelBaseClass):
    """
    Performance model for diesel generators.

    This model calculates electricity output from diesel fuel input based on the
    generator's heat rate. It follows the same structure as the natural gas model,
    dispatching against an electricity command value while being limited by fuel
    availability and rated capacity.

    The model implements the relationship:
        electricity_out = diesel_consumed / heat_rate_gal_per_mwh

    Inputs:
        system_capacity_kw (float): Diesel generator rated capacity in kW
        diesel_in (array): Diesel fuel input in galUS/h
        heat_rate_gal_per_mwh (float): Generator heat rate in galUS/MWh
        electricity_command_value (array): Electricity command value in MW for each timestep

    Outputs:
        electricity_out (array): Electricity output in MW for each timestep
        diesel_consumed (array): Diesel fuel consumed in galUS/h
        unmet_electricity_demand (array): Unmet portion of the electricity command in MW
    """

    _time_step_bounds = (
        3600,
        3600,
    )  # (min, max) time step lengths (in seconds) compatible with this model
    _control_classifier = "dispatchable"

    def initialize(self):
        super().initialize()
        self.commodity = "electricity"
        self.commodity_rate_units = "kW"
        self.commodity_amount_units = "kW*h"

    def setup(self):
        super().setup()

        self.config = DieselGeneratorPerformanceConfig.from_dict(
            merge_shared_inputs(self.options["tech_config"]["model_inputs"], "performance"),
            additional_cls_name=self.__class__.__name__,
        )

        self.add_output(
            "diesel_consumed",
            val=0.0,
            shape=self.n_timesteps,
            units="galUS/h",
            desc="Diesel fuel consumed by the generator",
        )

        self.add_input(
            "heat_rate_gal_per_mwh",
            val=self.config.heat_rate_gal_per_mwh,
            units="galUS/(MW*h)",
            desc="Generator heat rate in galUS/MWh",
        )

        self.add_input(
            "system_capacity_kw",
            val=self.config.system_capacity_kw,
            units="kW",
            desc="Diesel generator rated capacity in kW",
        )

        self.add_input(
            f"{self.commodity}_command_value",
            val=self.config.system_capacity_kw,
            shape=self.n_timesteps,
            units=self.commodity_rate_units,
            desc="Electricity command value for diesel generator",
        )

        self.add_input(
            "diesel_in",
            val=0.0,
            shape=self.n_timesteps,
            units="galUS/h",
            desc="Diesel fuel input",
        )

        self.add_output(
            "unmet_electricity_demand",
            val=0.0,
            shape=self.n_timesteps,
            units=self.commodity_rate_units,
            desc="Unmet electricity demand for diesel generator",
        )

    def compute(self, inputs, outputs):
        """
        Compute electricity output from diesel fuel input.

        Args:
            inputs: OpenMDAO inputs object containing diesel_in, heat_rate_gal_per_mwh,
                system_capacity, and electricity_command_value.
            outputs: OpenMDAO outputs object for electricity_out, diesel_consumed,
                and unmet_electricity_demand.
        """

        system_capacity = inputs["system_capacity_kw"]  # generator capacity in kW
        heat_rate_gal_per_kwh = units.convert_units(
            inputs["heat_rate_gal_per_mwh"], "galUS/(MW*h)", "galUS/(kW*h)"
        )  # Convert heat rate to gal/(kW*h) for consistency with kW units
        max_diesel_consumption = system_capacity * heat_rate_gal_per_kwh

        # electrical command value, saturated at rated system capacity
        electricity_command_value = np.where(
            inputs["electricity_command_value"] > system_capacity,
            system_capacity,
            inputs["electricity_command_value"],
        )
        diesel_demand = electricity_command_value * heat_rate_gal_per_kwh

        # available fuel, saturated at maximum system fuel consumption
        diesel_available = np.where(
            inputs["diesel_in"] > max_diesel_consumption,
            max_diesel_consumption,
            inputs["diesel_in"],
        )

        # diesel consumed is minimum between available fuel and output demand
        diesel_consumed = np.minimum.reduce([diesel_demand, diesel_available])

        # Convert diesel consumption to electricity output using heat rate
        electricity_out = diesel_consumed / heat_rate_gal_per_kwh

        outputs["electricity_out"] = electricity_out
        outputs["diesel_consumed"] = diesel_consumed

        outputs["rated_electricity_production"] = inputs["system_capacity_kw"]

        max_production = inputs["system_capacity_kw"] * len(electricity_out) * (self.dt / 3600)

        outputs["total_electricity_produced"] = np.sum(electricity_out) * (self.dt / 3600)
        outputs["capacity_factor"] = outputs["total_electricity_produced"].sum() / max_production
        outputs["annual_electricity_produced"] = outputs["total_electricity_produced"] * (
            1 / self.fraction_of_year_simulated
        )
        outputs["unmet_electricity_demand"] = inputs["electricity_command_value"] - electricity_out


@define(kw_only=True)
class DieselGeneratorCostModelConfig(CostModelBaseConfig):
    """
    Configuration class for diesel generator cost model.

    Attributes:
        system_capacity_kw (float | int): Generator capacity in kW.
        capex_per_kw (float | int): Capital cost per unit capacity in $/kW.
            Typical values: 500-1500 $/kW.
        fixed_opex_per_kw_per_year (float | int): Fixed operating expenses per unit
            capacity in $/kW/year. Typical values: 15-35 $/kW/year.
        variable_opex_per_kwh (float | int): Variable operating expenses per unit
            generation in $/kWh (excluding fuel). Typical values: 0.005-0.015 $/kWh.
        cost_year (int): Dollar year corresponding to input costs.
    """

    system_capacity_kw: float | int = field(validator=validators.ge(0))
    capex_per_kw: float | int = field(validator=validators.ge(0))
    capex_battery_total: float | int = field(validator=validators.ge(0))
    fixed_opex_per_kw_per_year: float | int = field(validator=validators.ge(0))
    variable_opex_per_kwh: float | int = field(validator=validators.ge(0))


class DieselGeneratorCostModel(CostModelBaseClass):
    """
    Cost model for diesel generators.

    Calculates:
        - CapEx: capex_per_kw * generator_capacity_kW
        - OpEx: fixed_opex_per_kw_per_year * generator_capacity_kW
            + variable_opex_per_kwh * delivered_electricity_kWh

    Fuel costs are handled externally through the diesel feedstock component.

    Inputs:
        system_capacity_kw (float): Diesel generator capacity in kW
        electricity_out (array): Hourly electricity output in kW from performance model
        capex_per_kw (float): Capital cost per unit capacity in $/kW
        fixed_opex_per_kw_per_year (float): Fixed operating expenses in $/kW/year
        variable_opex_per_kwh (float): Variable operating expenses in $/kWh

    Outputs:
        CapEx (float): Total capital expenditure in USD
        OpEx (float): Total operating expenditure in USD/year
        cost_year (int): Dollar year for the costs
    """

    _time_step_bounds = (
        3600,
        3600,
    )  # (min, max) time step lengths (in seconds) compatible with this model

    def setup(self):
        self.config = DieselGeneratorCostModelConfig.from_dict(
            merge_shared_inputs(self.options["tech_config"]["model_inputs"], "cost"),
            additional_cls_name=self.__class__.__name__,
        )

        super().setup()

        self.add_input(
            "system_capacity_kw",
            val=self.config.system_capacity_kw,
            units="kW",
            desc="Diesel generator capacity",
        )
        self.add_input(
            "electricity_out",
            val=0.0,
            shape=self.n_timesteps,
            units="kW",
            desc="Hourly electricity output from performance model",
        )
        self.add_input(
            "capex_per_kw",
            val=self.config.capex_per_kw,
            units="USD/kW",
            desc="Capital cost per unit capacity",
        )
        self.add_input(
            "fixed_opex_per_kw_per_year",
            val=self.config.fixed_opex_per_kw_per_year,
            units="USD/(kW*year)",
            desc="Fixed operating expenses per unit capacity per year",
        )
        self.add_input(
            "variable_opex_per_kwh",
            val=self.config.variable_opex_per_kwh,
            units="USD/(kW*h)",
            desc="Variable operating expenses per unit generation",
        )

    def compute(self, inputs, outputs, discrete_inputs, discrete_outputs):
        """Compute capital and operating costs for the diesel generator."""
        generator_capacity_kw = inputs["system_capacity_kw"]  # kW system definition
        electricity_out = inputs["electricity_out"]  # kW hourly profile
        capex_per_kw = inputs["capex_per_kw"]
        fixed_opex_per_kw_per_year = inputs["fixed_opex_per_kw_per_year"]
        variable_opex_per_kwh = inputs["variable_opex_per_kwh"]

        delivered_electricity_kWdt = electricity_out.sum()
        delivered_electricity_kWh = delivered_electricity_kWdt * self.dt / 3600

        capex = capex_per_kw * generator_capacity_kw + self.config.capex_battery_total
        fixed_om = fixed_opex_per_kw_per_year * generator_capacity_kw
        variable_om = variable_opex_per_kwh * delivered_electricity_kWh
        opex = fixed_om + variable_om

        outputs["CapEx"] = capex
        outputs["OpEx"] = opex
