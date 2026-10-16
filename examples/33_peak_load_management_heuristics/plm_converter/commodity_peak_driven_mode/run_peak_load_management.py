"""
Example 33: Peak load management converter heuristic dispatch

This example demonstrates peak load management dispatch open loop control of a converter
with two demand profiles of interest

In this example, the fuel-cell converter command is determined by a simple open-loop
threshold heuristic that uses two profiles:

1. demand_profile (local set-point)
2. demand_profile_upstream (supervisory or upstream signal)

At each time step, dispatch is only considered when either profile exceeds its configured
cutoff. For electricity-mode upstream control, the commanded dispatch is based on the
larger exceedance of the two profiles and is then limited by both the instantaneous local
demand and converter capacity. This creates a peak-shaving command profile for the
converter without storage state-of-charge dynamics or optimization.

The output figure compares the original local demand, upstream demand, cutoff thresholds,
converter output, resulting unmet demand, and grid purchases.

"""

import numpy as np
import matplotlib.pyplot as plt

from h2integrate import H2IntegrateModel
from h2integrate.core.utilities import build_time_series_from_plant_config


# Create, setup, and run the H2Integrate model
model = H2IntegrateModel("33_plm_converter_heuristic.yaml")

model.setup()
# om.n2(model.prob)
model.run()
model.post_process()

demand_profile = model.prob.get_val("fuel_cell.electricity_set_point", units="kW")
# plot the results for the first week
demand_profile_upstream = np.array(
    model.technology_config["technologies"]["fuel_cell"]["model_inputs"]["control_parameters"][
        "demand_profile_upstream"
    ]
)
demand_profile_peak_cutoff = model.technology_config["technologies"]["fuel_cell"]["model_inputs"][
    "control_parameters"
]["demand_profile_peak_cutoff"]
demand_profile_upstream_peak_cutoff = model.technology_config["technologies"]["fuel_cell"][
    "model_inputs"
]["control_parameters"]["demand_profile_upstream_peak_cutoff"]
grid_output = model.prob.get_val("grid_buy.electricity_out", units="MW")

time_series = build_time_series_from_plant_config(model.plant_config)

n_plot = 24 * 7
time_plot = time_series[:n_plot]

fig, ax = plt.subplots(3, 1, sharex=True, figsize=(10, 5))
ax[0].plot(time_plot, demand_profile_upstream[:n_plot] * 1e-3, label="Upstream demand")
ax[0].plot(time_plot, demand_profile[:n_plot] * 1e-3, label="Original demand")
ax[0].axhline(
    demand_profile_peak_cutoff * 1e-3, label="Demand peak cutoff", color="k", linestyle="--"
)
ax[0].axhline(
    demand_profile_upstream_peak_cutoff * 1e-3,
    label="Upstream demand peak cutoff",
    color="k",
    linestyle=":",
)
ax[0].set(ylabel="Power (MW)", ylim=[-2, 2])
ax[0].legend(frameon=True, ncol=3)

ax[1].plot(time_plot, demand_profile[:n_plot] * 1e-3, label="Original demand")
ax[1].plot(
    time_plot,
    model.prob.get_val("fuel_cell.electricity_out", units="MW")[:n_plot],
    label="fuel_cell dispatch",
)
ax[1].set(ylabel="Power (MW)", ylim=[-2, 2])
ax[1].legend(frameon=False, ncol=2)

ax[2].plot(time_plot, demand_profile[:n_plot] * 1e-3, label="Original demand")
ax[2].plot(
    time_plot,
    model.prob.get_val("electrical_load_demand.unmet_electricity_demand_out", units="MW")[:n_plot],
    label="New demand profile",
)
ax[2].plot(time_plot, grid_output[:n_plot], label="Grid purchase", linestyle=":")

ax[2].set(ylabel="Power (MW)", ylim=[-2, 2])
ax[2].legend(frameon=False, ncol=3)
ax[2].tick_params(axis="x", labelrotation=90)

for axis in ax:
    axis.minorticks_on()
    axis.grid(True, which="major", alpha=0.45, linewidth=0.8)
    axis.grid(True, which="minor", alpha=0.2, linewidth=0.5)

plt.tight_layout()
plt.savefig("example_peak_load_dispatch.png", transparent=False, dpi=300)
