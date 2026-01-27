"""
Example 29: Multivariable Streams

This example demonstrates the multivariable streams feature in H2Integrate.

Multivariable streams allow users to connect multiple related variables
(like gas characterization) with a single connection in the plant_config.yaml.
Behind the scenes, H2Integrate automatically expands this into individual
connections for each constituent variable.

In this example, we use a 'wellhead_gas' stream that includes:
- gas_flow (kg/hr): Total mass flow rate
- hydrogen_fraction (unitless): Fraction of hydrogen
- oxygen_fraction (unitless): Fraction of oxygen
- gas_temperature (K): Temperature
- gas_pressure (bar): Pressure

The plant_config.yaml specifies just:
    ["gas_producer", "gas_consumer", "wellhead_gas"]

And H2Integrate expands this to 5 individual connections:
    gas_producer.gas_flow_out -> gas_consumer.gas_flow_in
    gas_producer.hydrogen_fraction_out -> gas_consumer.hydrogen_fraction_in
    gas_producer.oxygen_fraction_out -> gas_consumer.oxygen_fraction_in
    gas_producer.gas_temperature_out -> gas_consumer.gas_temperature_in
    gas_producer.gas_pressure_out -> gas_consumer.gas_pressure_in

The dummy components use the utility functions:
- add_multivariable_stream_output() in the producer
- add_multivariable_stream_input() in the consumer

These functions automatically add all constituent variables with their
proper units and descriptions.
"""

from h2integrate.core.h2integrate_model import H2IntegrateModel


# Create and setup the H2Integrate model
print("Creating H2Integrate model with multivariable streams...")
model = H2IntegrateModel("29_multivariable_streams.yaml")

model.setup()

print("\nRunning the model...")
model.run()

# Access and print some results
print("\n" + "=" * 60)
print("RESULTS")
print("=" * 60)

# Get outputs from gas_producer (the multivariable stream values)
gas_flow = model.prob.get_val("gas_producer.gas_flow_out", units="kg/h")
h2_fraction = model.prob.get_val("gas_producer.hydrogen_fraction_out")
o2_fraction = model.prob.get_val("gas_producer.oxygen_fraction_out")
temperature = model.prob.get_val("gas_producer.gas_temperature_out", units="K")
pressure = model.prob.get_val("gas_producer.gas_pressure_out", units="bar")

print("\nGas Producer Outputs (wellhead_gas stream):")
print(
    f"  Gas Flow: min={gas_flow.min():.2f}, "
    f"max={gas_flow.max():.2f}, mean={gas_flow.mean():.2f} kg/h"
)
print(
    f"  H2 Fraction: min={h2_fraction.min():.3f}, "
    f"max={h2_fraction.max():.3f}, mean={h2_fraction.mean():.3f}"
)
print(
    f"  O2 Fraction: min={o2_fraction.min():.4f}, "
    f"max={o2_fraction.max():.4f}, mean={o2_fraction.mean():.4f}"
)
print(
    f"  Temperature: min={temperature.min():.1f}, "
    f"max={temperature.max():.1f}, mean={temperature.mean():.1f} K"
)
print(
    f"  Pressure: min={pressure.min():.2f}, "
    f"max={pressure.max():.2f}, mean={pressure.mean():.2f} bar"
)

# Get derived outputs from gas_consumer
h2_mass_flow = model.prob.get_val("gas_consumer.hydrogen_mass_flow", units="kg/h")
total_consumed = model.prob.get_val("gas_consumer.total_gas_consumed", units="kg")
avg_temp = model.prob.get_val("gas_consumer.avg_temperature", units="K")
avg_pressure = model.prob.get_val("gas_consumer.avg_pressure", units="bar")

print("\nGas Consumer Derived Outputs:")
print(
    f"  H2 Mass Flow: min={h2_mass_flow.min():.2f}, "
    f"max={h2_mass_flow.max():.2f}, mean={h2_mass_flow.mean():.2f} kg/h"
)
print(f"  Total Gas Consumed: {total_consumed[0]:,.0f} kg")
print(f"  Avg Temperature:    {avg_temp[0]:.1f} K")
print(f"  Avg Pressure:       {avg_pressure[0]:.2f} bar")

print("\n" + "=" * 60)
print("SUCCESS: Multivariable stream connection worked!")
print("=" * 60)
print("\nThe wellhead_gas multivariable stream was successfully connected")
print("from gas_producer to gas_consumer with a single line in plant_config.yaml")
