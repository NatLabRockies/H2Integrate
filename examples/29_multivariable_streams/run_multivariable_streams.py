"""
Example 29: Multivariable Streams with Gas Combiner

This example demonstrates:
1. Multivariable streams - connecting multiple related variables with a single connection
2. Gas stream combiner - combining multiple gas streams with mass-weighted averaging

Two gas producers with different properties feed into a combiner, which outputs
a single combined stream to a consumer. The combiner can operate in two modes:
- "weighted_average": Simple mass-weighted averaging of properties
- "thermodynamic": Uses CoolProp for proper enthalpy-based mixing

The wellhead_gas stream includes:
- gas_flow (kg/h): Total mass flow rate
- hydrogen_fraction: Fraction of hydrogen
- oxygen_fraction: Fraction of oxygen
- gas_temperature (K): Temperature
- gas_pressure (bar): Pressure

The 4-element connection format for combiners:
    ["gas_producer_1", "gas_combiner", "wellhead_gas", 1]
connects all stream variables to indexed inputs (e.g., gas_flow_in1, gas_temperature_in1).
"""

from h2integrate.core.h2integrate_model import H2IntegrateModel


# Create and setup the H2Integrate model
print("Creating H2Integrate model with gas stream combiner...")
model = H2IntegrateModel("29_multivariable_streams.yaml")

model.setup()

print("\nRunning the model...")
model.run()

# Access and print some results
print("\n" + "=" * 60)
print("RESULTS")
print("=" * 60)

# Get outputs from gas producers
print("\nGas Producer 1 Outputs:")
flow1 = model.prob.get_val("gas_producer_1.gas_flow_out", units="kg/h")
temp1 = model.prob.get_val("gas_producer_1.gas_temperature_out", units="K")
pres1 = model.prob.get_val("gas_producer_1.gas_pressure_out", units="bar")
print(f"  Flow: mean={flow1.mean():.2f} kg/h")
print(f"  Temperature: mean={temp1.mean():.1f} K")
print(f"  Pressure: mean={pres1.mean():.2f} bar")

print("\nGas Producer 2 Outputs:")
flow2 = model.prob.get_val("gas_producer_2.gas_flow_out", units="kg/h")
temp2 = model.prob.get_val("gas_producer_2.gas_temperature_out", units="K")
pres2 = model.prob.get_val("gas_producer_2.gas_pressure_out", units="bar")
print(f"  Flow: mean={flow2.mean():.2f} kg/h")
print(f"  Temperature: mean={temp2.mean():.1f} K")
print(f"  Pressure: mean={pres2.mean():.2f} bar")

# Get outputs from combiner
print("\nGas Combiner Outputs (mass-weighted average):")
flow_out = model.prob.get_val("gas_combiner.gas_flow_out", units="kg/h")
temp_out = model.prob.get_val("gas_combiner.gas_temperature_out", units="K")
pres_out = model.prob.get_val("gas_combiner.gas_pressure_out", units="bar")
h2_out = model.prob.get_val("gas_combiner.hydrogen_fraction_out")
print(f"  Total Flow: mean={flow_out.mean():.2f} kg/h (sum of inputs)")
print(f"  Temperature: mean={temp_out.mean():.1f} K (weighted avg)")
print(f"  Pressure: mean={pres_out.mean():.2f} bar (weighted avg)")
print(f"  H2 Fraction: mean={h2_out.mean():.3f} (weighted avg)")

# Get derived outputs from gas_consumer
print("\nGas Consumer Derived Outputs:")
h2_mass_flow = model.prob.get_val("gas_consumer.hydrogen_mass_flow", units="kg/h")
total_consumed = model.prob.get_val("gas_consumer.total_gas_consumed", units="kg")
avg_temp = model.prob.get_val("gas_consumer.avg_temperature", units="K")
avg_pressure = model.prob.get_val("gas_consumer.avg_pressure", units="bar")
print(f"  H2 Mass Flow: mean={h2_mass_flow.mean():.2f} kg/h")
print(f"  Total Gas Consumed: {total_consumed[0]:,.0f} kg")
print(f"  Avg Temperature: {avg_temp[0]:.1f} K")
print(f"  Avg Pressure: {avg_pressure[0]:.2f} bar")

print("\n" + "=" * 60)
print("SUCCESS: Gas stream combiner with multivariable streams worked!")
print("=" * 60)
