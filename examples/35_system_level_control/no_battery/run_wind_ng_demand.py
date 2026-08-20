import numpy as np
import matplotlib.pyplot as plt

from h2integrate.core.h2integrate_model import H2IntegrateModel


##################################
# Create an H2I model with a fixed electricity load demand
h2i = H2IntegrateModel("wind_ng_demand.yaml")

# Run the model
h2i.run()

# Post-process the results
h2i.post_process()

# Plot the first 100 hours
n_hours = 100
hours = np.arange(n_hours)

demand = h2i.prob.get_val("plant.electrical_load_demand.electricity_demand")[:n_hours]
wind_out = h2i.prob.get_val("plant.wind.electricity_out")[:n_hours]
ng_out = h2i.prob.get_val("plant.natural_gas_plant.electricity_out", units="kW")[:n_hours]
curtailed = h2i.prob.get_val("plant.electrical_load_demand.unused_electricity_out")[:n_hours]

fig, axes = plt.subplots(2, 1, figsize=(12, 8), sharex=True)

# Stacked bar chart of supply per hour with demand overlay
axes[0].bar(hours, wind_out, width=1.0, color="tab:blue", label="Wind", align="edge")
axes[0].bar(
    hours,
    ng_out,
    width=1.0,
    bottom=wind_out,
    color="tab:orange",
    label="Natural Gas",
    align="edge",
)
axes[0].plot(hours, demand, color="black", linewidth=1.5, linestyle="--", label="Demand")
axes[0].set_ylabel("Power (kW)")
axes[0].set_title("System-Level Control: First 100 Hours")
axes[0].legend(loc="upper right")

axes[1].bar(hours, curtailed, width=1.0, color="tab:red", align="edge")
axes[1].set_ylabel("Curtailed (kW)")
axes[1].set_xlabel("Hour")

for ax in axes:
    ax.grid(True, alpha=0.3)

plt.tight_layout()
plt.savefig("slc_results.png", dpi=150)
plt.show()
