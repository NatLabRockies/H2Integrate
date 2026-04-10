import matplotlib.pyplot as plt
import numpy as np
from h2integrate.core.h2integrate_model import H2IntegrateModel

import pandas as pd
import yaml

# Load the CSV file
df = pd.read_csv("10mw_80per_compute_load.csv")

# Convert timestamp to datetime
df['timestamp'] = pd.to_datetime(df['timestamp'])

# Set timestamp as index
df.set_index('timestamp', inplace=True)

# Resample to hourly and take the mean
hourly_power = df['power_W'].resample('h').mean()

# Scale by 10 and convert from W to MW
hourly_power = (hourly_power * 10) / 1e6

# Drop the last value
hourly_power = hourly_power[:-1]

# fig, ax = plt.subplots(figsize=(10, 6))
# ax.plot(hourly_power.index, hourly_power.values, marker="o", label="Hourly Power Load (MW)", alpha=0.8)
# plt.show()
# lll


cases = [
    "data_center_advanced.yaml",
    "data_center_moderate.yaml",
    "data_center_conservative.yaml"
]

water_costs = []
electricity_costs = []
water_usages = []
electricity_usages = []

for case in cases:
    # Create an H2I model
    h2i = H2IntegrateModel(case)

    h2i.setup()
    h2i.prob.set_val("data_center.compute_load_demand", hourly_power.values, units="MW")

    # Run the model
    h2i.run()

    # Post-process the results
    h2i.post_process()

    water_cost = h2i.prob.get_val("water_feedstock.VarOpEx", units="USD/yr")[0]
    electricity_cost = h2i.prob.get_val("grid_buy.VarOpEx", units="USD/yr")[0]
    water_usage = h2i.prob.get_val("data_center.water_consumed", units="galUS/h")
    electricity_usage = h2i.prob.get_val("grid_buy.electricity_out", units="MW")

    water_costs.append(water_cost)
    electricity_costs.append(electricity_cost)
    water_usages.append(water_usage)
    electricity_usages.append(electricity_usage)

# Create a comparison plot
case_labels = ["Advanced", "Moderate", "Conservative"]
x = np.arange(len(case_labels))
width = 0.35

fig, ax = plt.subplots(figsize=(10, 6))
ax.bar(x - width/2, water_costs, width, label="Water Cost", alpha=0.8)
ax.bar(x + width/2, electricity_costs, width, label="Electricity Cost", alpha=0.8)

ax.set_xlabel("Case", fontsize=12)
ax.set_ylabel("Annual Cost (USD/yr)", fontsize=12)
ax.set_title("Water vs Electricity Costs by Case", fontsize=14, fontweight="bold")
ax.set_xticks(x)
ax.set_xticklabels(case_labels)
ax.legend()
ax.grid(axis="y", alpha=0.3)

plt.tight_layout()
plt.savefig("cost_comparison.png", dpi=300, bbox_inches="tight")

fig, ax = plt.subplots(figsize=(10, 6))
for i in range(len(cases)):
    ax.plot(water_usages[i], marker="o", label="Water Usage (galUS)", alpha=0.8)

ax.set_xlabel("Case", fontsize=12)
ax.set_ylabel("Water Usage (galUS)", fontsize=12)
ax.set_title("Water Usage by Case", fontsize=14, fontweight="bold")
ax.legend(case_labels)
ax.grid(alpha=0.3)

plt.tight_layout()
plt.savefig("water_usage.png", dpi=300, bbox_inches="tight")

fig, ax = plt.subplots(figsize=(10, 6))
for i in range(len(cases)):
    ax.plot(electricity_usages[i], marker="o", label="Electricity Usage (MW)", alpha=0.8)

ax.set_xlabel("Case", fontsize=12)
ax.set_ylabel("Electricity Usage (MW)", fontsize=12)
ax.set_title("Electricity Usage by Case", fontsize=14, fontweight="bold")
ax.legend(case_labels)
ax.grid(alpha=0.3)

plt.tight_layout()
plt.savefig("electricity_usage.png", dpi=300, bbox_inches="tight")

plt.show()
