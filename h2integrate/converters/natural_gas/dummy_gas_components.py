"""
Dummy components for demonstrating multivariable streams.

These components are used in example 29 to showcase the multivariable stream
connection feature. They produce and consume wellhead_gas streams with
5 constituent variables.
"""

import numpy as np
import openmdao.api as om


# Define wellhead_gas stream locally to avoid circular import
# This mirrors the definition in supported_models.py
WELLHEAD_GAS_STREAM = {
    "gas_flow": {
        "units": "kg/h",
        "desc": "Total mass flow rate of gas in the stream",
    },
    "hydrogen_fraction": {
        "units": "unitless",
        "desc": "Fraction of hydrogen in the gas stream",
    },
    "oxygen_fraction": {
        "units": "unitless",
        "desc": "Fraction of oxygen in the gas stream",
    },
    "gas_temperature": {
        "units": "K",
        "desc": "Temperature of the gas stream",
    },
    "gas_pressure": {
        "units": "bar",
        "desc": "Pressure of the gas stream",
    },
}


class DummyGasProducerPerformance(om.ExplicitComponent):
    """
    A dummy gas producer component that outputs a 'wellhead_gas' multivariable stream.

    This component produces time-varying outputs for each constituent variable
    of the wellhead_gas stream (gas_flow, hydrogen_fraction, oxygen_fraction,
    gas_temperature, gas_pressure).

    The outputs are sinusoidal variations to demonstrate time-varying behavior.
    """

    def initialize(self):
        self.options.declare("driver_config", types=dict)
        self.options.declare("plant_config", types=dict)
        self.options.declare("tech_config", types=dict)

    def setup(self):
        n_timesteps = self.options["plant_config"]["plant"]["simulation"]["n_timesteps"]

        # Add all wellhead_gas stream outputs
        for var_name, var_props in WELLHEAD_GAS_STREAM.items():
            units = var_props.get("units")
            if units == "unitless":
                units = None
            self.add_output(
                f"{var_name}_out",
                val=0.0,
                shape=n_timesteps,
                units=units,
                desc=var_props.get("desc", ""),
            )

        # Add some configuration inputs
        self.add_input("base_flow_rate", val=100.0, units="kg/h", desc="Base gas flow rate")
        self.add_input("base_temperature", val=300.0, units="K", desc="Base gas temperature")
        self.add_input("base_pressure", val=10.0, units="bar", desc="Base gas pressure")

    def compute(self, inputs, outputs):
        n_timesteps = self.options["plant_config"]["plant"]["simulation"]["n_timesteps"]

        # Create time array for sinusoidal variations
        t = np.linspace(0, 2 * np.pi * 365, n_timesteps)  # One year of hourly data

        # Generate varied outputs for each stream variable
        base_flow = inputs["base_flow_rate"][0]
        base_temp = inputs["base_temperature"][0]
        base_pressure = inputs["base_pressure"][0]

        # Gas flow varies ±20% sinusoidally (daily pattern)
        outputs["gas_flow_out"] = base_flow * (1.0 + 0.2 * np.sin(t * 24))

        # Hydrogen fraction: 0.7 to 0.9 (varies slowly over the year)
        outputs["hydrogen_fraction_out"] = 0.8 + 0.1 * np.sin(t)

        # Oxygen fraction: 0.0 to 0.05 (inverse of hydrogen somewhat)
        outputs["oxygen_fraction_out"] = 0.025 + 0.025 * np.cos(t)

        # Temperature varies ±10K with daily and seasonal patterns
        outputs["gas_temperature_out"] = base_temp + 5 * np.sin(t * 24) + 5 * np.sin(t)

        # Pressure varies ±1 bar (weekly pattern)
        outputs["gas_pressure_out"] = base_pressure + 1.0 * np.sin(t * 7)


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
        for var_name, var_props in WELLHEAD_GAS_STREAM.items():
            units = var_props.get("units")
            if units == "unitless":
                units = None
            self.add_input(
                f"{var_name}_in",
                val=0.0,
                shape=n_timesteps,
                units=units,
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


class DummyGasProducerCost(om.ExplicitComponent):
    """
    Simple cost model for the dummy gas producer.

    This is a placeholder cost model that returns fixed CapEx/OpEx values.
    """

    def initialize(self):
        self.options.declare("driver_config", types=dict)
        self.options.declare("plant_config", types=dict)
        self.options.declare("tech_config", types=dict)

    def setup(self):
        plant_life = int(self.options["plant_config"]["plant"]["plant_life"])

        self.add_output("CapEx", val=0.0, units="USD", desc="Capital expenditure")
        self.add_output("OpEx", val=0.0, units="USD/year", desc="Fixed operational expenditure")
        self.add_output(
            "VarOpEx",
            val=0.0,
            shape=plant_life,
            units="USD/year",
            desc="Variable operational expenditure",
        )
        self.add_discrete_output("cost_year", val=2024, desc="Dollar year for costs")

    def compute(self, inputs, outputs, discrete_inputs=None, discrete_outputs=None):
        # Fixed cost values for demonstration
        outputs["CapEx"] = 1_000_000.0  # $1M
        outputs["OpEx"] = 50_000.0  # $50k/year


class DummyGasConsumerCost(om.ExplicitComponent):
    """
    Simple cost model for the dummy gas consumer.

    This is a placeholder cost model that returns fixed CapEx/OpEx values.
    """

    def initialize(self):
        self.options.declare("driver_config", types=dict)
        self.options.declare("plant_config", types=dict)
        self.options.declare("tech_config", types=dict)

    def setup(self):
        plant_life = int(self.options["plant_config"]["plant"]["plant_life"])

        self.add_output("CapEx", val=0.0, units="USD", desc="Capital expenditure")
        self.add_output("OpEx", val=0.0, units="USD/year", desc="Fixed operational expenditure")
        self.add_output(
            "VarOpEx",
            val=0.0,
            shape=plant_life,
            units="USD/year",
            desc="Variable operational expenditure",
        )
        self.add_discrete_output("cost_year", val=2024, desc="Dollar year for costs")

    def compute(self, inputs, outputs, discrete_inputs=None, discrete_outputs=None):
        # Fixed cost values for demonstration
        outputs["CapEx"] = 2_000_000.0  # $2M
        outputs["OpEx"] = 100_000.0  # $100k/year
