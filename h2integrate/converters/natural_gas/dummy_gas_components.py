"""
Dummy components for demonstrating multivariable streams.

These components are used in example 29 to showcase the multivariable stream
connection feature. They produce and consume wellhead_gas streams with
5 constituent variables.
"""

import numpy as np
import openmdao.api as om
from attrs import field, define

from h2integrate.core.utilities import BaseConfig, merge_shared_inputs
from h2integrate.core.validators import gt_zero, gte_zero
from h2integrate.core.model_baseclasses import CostModelBaseClass, CostModelBaseConfig
from h2integrate.core.commodity_stream_definitions import multivariable_streams


@define(kw_only=True)
class DummyGasProducerPerformanceConfig(BaseConfig):
    """
    Configuration class for dummy gas producer performance model.

    Attributes:
        base_flow_rate: Base gas flow rate in kg/h
        base_temperature: Base gas temperature in K
        base_pressure: Base gas pressure in bar
        flow_variation: Fractional variation in flow rate (0-1)
        temp_variation: Variation in temperature in K
        pressure_variation: Variation in pressure in bar
        random_seed: Seed for random number generator (for reproducibility)
    """

    base_flow_rate: float = field(default=100.0, validator=gt_zero)
    base_temperature: float = field(default=300.0, validator=gt_zero)
    base_pressure: float = field(default=10.0, validator=gt_zero)
    flow_variation: float = field(default=0.2, validator=gte_zero)
    temp_variation: float = field(default=10.0, validator=gte_zero)
    pressure_variation: float = field(default=1.0, validator=gte_zero)
    random_seed: int | None = field(default=None)


class DummyGasProducerPerformance(om.ExplicitComponent):
    """
    A dummy gas producer component that outputs a 'wellhead_gas' multivariable stream.

    This component produces time-varying outputs for each constituent variable
    of the wellhead_gas stream (gas_flow, hydrogen_fraction, oxygen_fraction,
    gas_temperature, gas_pressure).

    The outputs use random variations around base values.
    """

    def initialize(self):
        self.options.declare("driver_config", types=dict)
        self.options.declare("plant_config", types=dict)
        self.options.declare("tech_config", types=dict)

    def setup(self):
        self.config = DummyGasProducerPerformanceConfig.from_dict(
            merge_shared_inputs(self.options["tech_config"]["model_inputs"], "performance")
        )
        n_timesteps = self.options["plant_config"]["plant"]["simulation"]["n_timesteps"]

        # Add all wellhead_gas stream outputs
        for var_name, var_props in multivariable_streams["wellhead_gas"].items():
            self.add_output(
                f"{var_name}_out",
                val=0.0,
                shape=n_timesteps,
                units=var_props.get("units"),
                desc=var_props.get("desc", ""),
            )

    def compute(self, inputs, outputs):
        n_timesteps = self.options["plant_config"]["plant"]["simulation"]["n_timesteps"]

        # Set random seed for reproducibility if specified
        rng = np.random.default_rng(self.config.random_seed)

        # Generate random variations around base values
        base_flow = self.config.base_flow_rate
        base_temp = self.config.base_temperature
        base_pressure = self.config.base_pressure

        # Gas flow varies randomly within ±variation fraction
        flow_noise = rng.uniform(
            -self.config.flow_variation, self.config.flow_variation, n_timesteps
        )
        outputs["gas_flow_out"] = base_flow * (1.0 + flow_noise)

        # Hydrogen fraction: 0.7 to 0.9 (random)
        outputs["hydrogen_fraction_out"] = rng.uniform(0.7, 0.9, n_timesteps)

        # Oxygen fraction: 0.0 to 0.05 (random)
        outputs["oxygen_fraction_out"] = rng.uniform(0.0, 0.05, n_timesteps)

        # Temperature varies randomly within ±temp_variation K
        temp_noise = rng.uniform(
            -self.config.temp_variation, self.config.temp_variation, n_timesteps
        )
        outputs["gas_temperature_out"] = base_temp + temp_noise

        # Pressure varies randomly within ±pressure_variation bar
        pres_noise = rng.uniform(
            -self.config.pressure_variation, self.config.pressure_variation, n_timesteps
        )
        outputs["gas_pressure_out"] = base_pressure + pres_noise


class DummyGasConsumerPerformance(om.ExplicitComponent):
    """
    A dummy gas consumer component that takes in a 'wellhead_gas' multivariable stream.

    This component demonstrates receiving all constituent variables of a
    wellhead_gas stream (gas_flow, hydrogen_fraction, oxygen_fraction,
    gas_temperature, gas_pressure) and performing simple calculations.

    The component calculates some derived quantities from the input stream.
    """

    def initialize(self):
        self.options.declare("driver_config", types=dict)
        self.options.declare("plant_config", types=dict)
        self.options.declare("tech_config", types=dict)

    def setup(self):
        n_timesteps = self.options["plant_config"]["plant"]["simulation"]["n_timesteps"]

        # Add all wellhead_gas stream inputs
        for var_name, var_props in multivariable_streams["wellhead_gas"].items():
            self.add_input(
                f"{var_name}_in",
                val=0.0,
                shape=n_timesteps,
                units=var_props.get("units"),
                desc=var_props.get("desc", ""),
            )

        # Add some derived outputs
        self.add_output(
            "hydrogen_mass_flow",
            val=0.0,
            shape=n_timesteps,
            units="kg/h",
            desc="Mass flow rate of hydrogen component",
        )
        self.add_output(
            "total_gas_consumed", val=0.0, units="kg", desc="Total gas consumed over the simulation"
        )
        self.add_output("avg_temperature", val=0.0, units="K", desc="Average gas temperature")
        self.add_output("avg_pressure", val=0.0, units="bar", desc="Average gas pressure")

    def compute(self, inputs, outputs):
        # Calculate derived quantities from the stream inputs
        gas_flow = inputs["gas_flow_in"]
        h2_fraction = inputs["hydrogen_fraction_in"]
        temperature = inputs["gas_temperature_in"]
        pressure = inputs["gas_pressure_in"]

        # Hydrogen mass flow is total flow times hydrogen fraction
        outputs["hydrogen_mass_flow"] = gas_flow * h2_fraction

        # Total gas consumed (assuming hourly data, sum all flow rates)
        outputs["total_gas_consumed"] = np.sum(gas_flow)

        # Average temperature and pressure
        outputs["avg_temperature"] = np.mean(temperature)
        outputs["avg_pressure"] = np.mean(pressure)


@define(kw_only=True)
class DummyGasProducerCostConfig(CostModelBaseConfig):
    """
    Configuration class for dummy gas producer cost model.

    Attributes:
        capex: Capital expenditure in USD
        opex: Fixed operational expenditure in USD/year
    """

    capex: float = field(default=1_000_000.0, validator=gte_zero)
    opex: float = field(default=50_000.0, validator=gte_zero)


class DummyGasProducerCost(CostModelBaseClass):
    """
    Simple cost model for the dummy gas producer.
    """

    def setup(self):
        self.config = DummyGasProducerCostConfig.from_dict(
            merge_shared_inputs(self.options["tech_config"]["model_inputs"], "cost")
        )

        super().setup()

    def compute(self, inputs, outputs, discrete_inputs=None, discrete_outputs=None):
        outputs["CapEx"] = self.config.capex
        outputs["OpEx"] = self.config.opex


@define(kw_only=True)
class DummyGasConsumerCostConfig(CostModelBaseConfig):
    """
    Configuration class for dummy gas consumer cost model.

    Attributes:
        capex: Capital expenditure in USD
        opex: Fixed operational expenditure in USD/year
    """

    capex: float = field(default=2_000_000.0, validator=gte_zero)
    opex: float = field(default=100_000.0, validator=gte_zero)


class DummyGasConsumerCost(CostModelBaseClass):
    """
    Simple cost model for the dummy gas consumer.
    """

    def setup(self):
        self.config = DummyGasConsumerCostConfig.from_dict(
            merge_shared_inputs(self.options["tech_config"]["model_inputs"], "cost")
        )

        super().setup()

    def compute(self, inputs, outputs, discrete_inputs=None, discrete_outputs=None):
        outputs["CapEx"] = self.config.capex
        outputs["OpEx"] = self.config.opex
