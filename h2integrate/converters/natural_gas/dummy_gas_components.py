"""
Dummy components for demonstrating multivariable streams, nominally based
on wellhead gas mixtures. These components are not meant to represent any real
physical processes or technologies, but simply to provide a realistic example
of producing and consuming a multivariable stream with multiple constituent
variables.

These components are used in example 32 to showcase the multivariable stream
connection feature. They produce and consume wellhead_gas_mixture streams with
5 constituent variables.
"""

import numpy as np
from attrs import field, define

from h2integrate.core.utilities import BaseConfig, merge_shared_inputs
from h2integrate.core.validators import gt_zero, gte_zero
from h2integrate.core.model_baseclasses import (
    CostModelBaseClass,
    CostModelBaseConfig,
    PerformanceModelBaseClass,
)
from h2integrate.core.commodity_stream_definitions import (
    add_multivariable_input,
    add_multivariable_output,
)


@define(kw_only=True)
class SimpleGasProducerPerformanceConfig(BaseConfig):
    """
    Configuration class for dummy gas producer performance model.

    Attributes:
        base_flow_rate: Base gas flow rate in kg/h
        base_temperature: Base gas temperature in K
        base_pressure: Base gas pressure in bar
        flow_variation: Absolute variation in flow rate in kg/h
        temp_variation: Variation in temperature in K
        pressure_variation: Variation in pressure in bar
        random_seed: Seed for random number generator (for reproducibility)
    """

    base_flow_rate: float = field(default=100.0, validator=gt_zero)
    base_temperature: float = field(default=300.0, validator=gt_zero)
    base_pressure: float = field(default=10.0, validator=gt_zero)
    flow_variation: float = field(default=20.0, validator=gte_zero)
    temp_variation: float = field(default=10.0, validator=gte_zero)
    pressure_variation: float = field(default=1.0, validator=gte_zero)
    random_seed: int | None = field(default=None)


class SimpleGasProducerPerformance(PerformanceModelBaseClass):
    """
    A dummy gas producer component that outputs a 'wellhead_gas_mixture' multivariable stream.

    This component produces time-varying outputs for each constituent variable
    of the wellhead_gas_mixture stream (mass_flow, hydrogen_mass_fraction, oxygen_mass_fraction,
    temperature, pressure).

    The outputs use random variations around base values.
    """

    _time_step_bounds = (
        3600,
        3600,
    )  # (min, max) time step lengths (in seconds) compatible with this model

    def initialize(self):
        super().initialize()
        self.commodity = "gas"
        self.commodity_rate_units = "kg/h"
        self.commodity_amount_units = "kg"

    def setup(self):
        self.config = SimpleGasProducerPerformanceConfig.from_dict(
            merge_shared_inputs(self.options["tech_config"]["model_inputs"], "performance")
        )
        super().setup()

        # Add all wellhead_gas_mixture stream outputs
        add_multivariable_output(self, "wellhead_gas_mixture", self.n_timesteps)

    def compute(self, inputs, outputs):
        # Set random seed for reproducibility if specified
        rng = np.random.default_rng(self.config.random_seed)

        base_flow = self.config.base_flow_rate
        base_temp = self.config.base_temperature
        base_pressure = self.config.base_pressure

        # Gas flow varies randomly within ±flow_variation (absolute, kg/h)
        flow_noise = rng.uniform(
            -self.config.flow_variation, self.config.flow_variation, self.n_timesteps
        )
        outputs["wellhead_gas_mixture:mass_flow_out"] = base_flow + flow_noise

        # Hydrogen fraction: 0.7 to 0.9 (random)
        outputs["wellhead_gas_mixture:hydrogen_mass_fraction_out"] = rng.uniform(
            0.7, 0.9, self.n_timesteps
        )

        # Oxygen mass fraction: 0.0 to 0.05 (random)
        outputs["wellhead_gas_mixture:oxygen_mass_fraction_out"] = rng.uniform(
            0.0, 0.05, self.n_timesteps
        )

        # Temperature varies randomly within ±temp_variation K
        temp_noise = rng.uniform(
            -self.config.temp_variation, self.config.temp_variation, self.n_timesteps
        )
        outputs["wellhead_gas_mixture:temperature_out"] = base_temp + temp_noise

        # Pressure varies randomly within ±pressure_variation bar
        pres_noise = rng.uniform(
            -self.config.pressure_variation, self.config.pressure_variation, self.n_timesteps
        )
        outputs["wellhead_gas_mixture:pressure_out"] = base_pressure + pres_noise

        # Standardized outputs from PerformanceModelBaseClass
        rated_production = base_flow + self.config.flow_variation
        outputs["gas_out"] = outputs["wellhead_gas_mixture:mass_flow_out"]
        outputs["total_gas_produced"] = np.sum(outputs["wellhead_gas_mixture:mass_flow_out"]) * (
            self.dt / 3600
        )
        outputs["rated_gas_production"] = rated_production
        outputs["annual_gas_produced"] = (
            outputs["total_gas_produced"] / self.fraction_of_year_simulated
        )
        outputs["capacity_factor"] = outputs["total_gas_produced"] / (
            rated_production * self.n_timesteps * (self.dt / 3600)
        )


class SimpleGasConsumerPerformance(PerformanceModelBaseClass):
    """
    A dummy gas consumer component that takes in a 'wellhead_gas_mixture' multivariable stream.

    This component demonstrates receiving all constituent variables of a
    wellhead_gas_mixture stream (mass_flow, hydrogen_mass_fraction, oxygen_mass_fraction,
    temperature, pressure) and performing simple calculations.

    The component calculates some derived quantities from the input stream.
    The primary commodity output is hydrogen (extracted from the gas stream).
    """

    _time_step_bounds = (
        3600,
        3600,
    )  # (min, max) time step lengths (in seconds) compatible with this model

    def initialize(self):
        super().initialize()
        self.commodity = "hydrogen"
        self.commodity_rate_units = "kg/h"
        self.commodity_amount_units = "kg"

    def setup(self):
        super().setup()

        # Add all wellhead_gas_mixture stream inputs
        add_multivariable_input(self, "wellhead_gas_mixture", self.n_timesteps)

        # Add some derived outputs
        self.add_output(
            "total_gas_consumed", val=0.0, units="kg", desc="Total gas consumed over the simulation"
        )
        self.add_output("avg_temperature", val=0.0, units="K", desc="Average gas temperature")
        self.add_output("avg_pressure", val=0.0, units="bar", desc="Average gas pressure")

    def compute(self, inputs, outputs):
        # Calculate derived quantities from the stream inputs
        gas_flow = inputs["wellhead_gas_mixture:mass_flow_in"]
        h2_fraction = inputs["wellhead_gas_mixture:hydrogen_mass_fraction_in"]
        temperature = inputs["wellhead_gas_mixture:temperature_in"]
        pressure = inputs["wellhead_gas_mixture:pressure_in"]

        # Hydrogen mass flow is total flow times hydrogen fraction
        hydrogen_mass_flow = gas_flow * h2_fraction

        # Total gas consumed (assuming hourly data, sum all flow rates)
        outputs["total_gas_consumed"] = np.sum(gas_flow) * (self.dt / 3600)

        # Average temperature and pressure
        outputs["avg_temperature"] = np.mean(temperature)
        outputs["avg_pressure"] = np.mean(pressure)

        # Standardized outputs from PerformanceModelBaseClass
        outputs["hydrogen_out"] = hydrogen_mass_flow
        outputs["total_hydrogen_produced"] = np.sum(hydrogen_mass_flow) * (self.dt / 3600)
        outputs["rated_hydrogen_production"] = np.max(hydrogen_mass_flow)
        outputs["annual_hydrogen_produced"] = (
            outputs["total_hydrogen_produced"] / self.fraction_of_year_simulated
        )
        max_possible = np.max(hydrogen_mass_flow) * self.n_timesteps * (self.dt / 3600)
        outputs["capacity_factor"] = (
            outputs["total_hydrogen_produced"] / max_possible if max_possible > 0 else 0.0
        )


@define(kw_only=True)
class SimpleGasProducerCostConfig(CostModelBaseConfig):
    """
    Configuration class for dummy gas producer cost model.

    Attributes:
        capex: Capital expenditure in USD
        opex: Fixed operational expenditure in USD/year
    """

    capex: float = field(default=1_000_000.0, validator=gte_zero)
    opex: float = field(default=50_000.0, validator=gte_zero)


class SimpleGasProducerCost(CostModelBaseClass):
    """
    Simple cost model for the dummy gas producer.
    """

    _time_step_bounds = (
        3600,
        3600,
    )  # (min, max) time step lengths (in seconds) compatible with this model

    def setup(self):
        self.config = SimpleGasProducerCostConfig.from_dict(
            merge_shared_inputs(self.options["tech_config"]["model_inputs"], "cost")
        )

        super().setup()

    def compute(self, inputs, outputs, discrete_inputs=None, discrete_outputs=None):
        outputs["CapEx"] = self.config.capex
        outputs["OpEx"] = self.config.opex


@define(kw_only=True)
class SimpleGasConsumerCostConfig(CostModelBaseConfig):
    """
    Configuration class for dummy gas consumer cost model.

    Attributes:
        capex: Capital expenditure in USD
        opex: Fixed operational expenditure in USD/year
    """

    capex: float = field(default=2_000_000.0, validator=gte_zero)
    opex: float = field(default=100_000.0, validator=gte_zero)


class SimpleGasConsumerCost(CostModelBaseClass):
    """
    Simple cost model for the dummy gas consumer.
    """

    _time_step_bounds = (
        3600,
        3600,
    )  # (min, max) time step lengths (in seconds) compatible with this model

    def setup(self):
        self.config = SimpleGasConsumerCostConfig.from_dict(
            merge_shared_inputs(self.options["tech_config"]["model_inputs"], "cost")
        )

        super().setup()

    def compute(self, inputs, outputs, discrete_inputs=None, discrete_outputs=None):
        outputs["CapEx"] = self.config.capex
        outputs["OpEx"] = self.config.opex
