"""
Example 29: Multivariable Streams with Gas Combiner

This example demonstrates:
1. Multivariable streams - connecting multiple related variables with a single connection
2. Gas stream combiner - combining multiple gas streams with mass-weighted averaging

Two gas producers with different properties feed into a combiner, which outputs
a single combined stream to a consumer.

The wellhead_gas stream includes:
- gas_flow (kg/h): Total mass flow rate
- hydrogen_fraction: Fraction of hydrogen
- oxygen_fraction: Fraction of oxygen
- gas_temperature (K): Temperature
- gas_pressure (bar): Pressure
"""

import numpy as np
import matplotlib.pyplot as plt

from h2integrate.core.h2integrate_model import H2IntegrateModel


# Create and setup the H2Integrate model
model = H2IntegrateModel("29_multivariable_streams.yaml")

model.setup()

model.run()


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


# Time axis in hours
n_timesteps = len(flow1)
time_hours = np.arange(n_timesteps)

# Create figure with 3 subplots sharing x-axis
fig, (ax1, ax2, ax3) = plt.subplots(3, 1, figsize=(12, 10), sharex=True)
fig.suptitle("Gas Stream Time History", fontsize=14, fontweight="bold")

# Colors for the two streams
color1 = "#1f77b4"  # Blue for stream 1
color2 = "#ff7f0e"  # Orange for stream 2
color_total = "#2ca02c"  # Green for total/combined

# ------------------------------------------------------------
# Plot 1: Mass Flow Rates (stacked area)
# ------------------------------------------------------------
# Stack the flows - stream 1 on bottom, stream 2 on top
ax1.fill_between(time_hours, 0, flow1, color=color1, alpha=0.7, label="Stream 1")
ax1.fill_between(time_hours, flow1, flow1 + flow2, color=color2, alpha=0.7, label="Stream 2")
ax1.plot(time_hours, flow_out, color=color_total, linewidth=2, label="Total (Combined)")

# Add in-area labels at the center of each region
mid_time = n_timesteps // 2
ax1.text(
    mid_time,
    flow1.mean() / 2,
    "Producer 1",
    ha="center",
    va="center",
    fontsize=10,
    fontweight="bold",
    color="white",
)
ax1.text(
    mid_time,
    flow1.mean() + flow2.mean() / 2,
    "Producer 2",
    ha="center",
    va="center",
    fontsize=10,
    fontweight="bold",
    color="white",
)

ax1.set_ylabel("Mass Flow Rate (kg/h)")
ax1.set_title("Mass Flow Rates")
ax1.legend(loc="upper right")
ax1.grid(True, alpha=0.3)
ax1.set_ylim(bottom=0)

# ------------------------------------------------------------
# Plot 2: Pressure
# ------------------------------------------------------------
ax2.plot(time_hours, pres1, color=color1, linewidth=1.5, label="Stream 1", linestyle="--")
ax2.plot(time_hours, pres2, color=color2, linewidth=1.5, label="Stream 2", linestyle="--")
ax2.plot(time_hours, pres_out, color=color_total, linewidth=2, label="Combined")

ax2.set_ylabel("Pressure (bar)")
ax2.set_title("Pressure")
ax2.legend(loc="upper right")
ax2.grid(True, alpha=0.3)

# ------------------------------------------------------------
# Plot 3: Temperature
# ------------------------------------------------------------
ax3.plot(time_hours, temp1, color=color1, linewidth=1.5, label="Stream 1", linestyle="--")
ax3.plot(time_hours, temp2, color=color2, linewidth=1.5, label="Stream 2", linestyle="--")
ax3.plot(time_hours, temp_out, color=color_total, linewidth=2, label="Combined")

ax3.set_xlabel("Time (hours)")
ax3.set_ylabel("Temperature (K)")
ax3.set_title("Temperature")
ax3.legend(loc="upper right")
ax3.grid(True, alpha=0.3)

# Adjust layout and save
plt.tight_layout()
plt.show()
