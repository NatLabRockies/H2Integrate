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

fig, axes = plt.subplots(4, 1, figsize=(12, 10), sharex=True)

axes[0].plot(hours, demand, color="black")
axes[0].set_ylabel("Demand (kW)")
axes[0].set_title("System-Level Control: First 100 Hours")

axes[1].plot(hours, wind_out, color="tab:blue")
axes[1].set_ylabel("Wind (kW)")

axes[2].plot(hours, ng_out, color="tab:orange")
axes[2].set_ylabel("Natural Gas (kW)")

axes[3].plot(hours, curtailed, color="tab:red")
axes[3].set_ylabel("Curtailed (kW)")
axes[3].set_xlabel("Hour")

for ax in axes:
    ax.grid(True, alpha=0.3)

plt.tight_layout()
plt.savefig("slc_results.png", dpi=150)
plt.show()
