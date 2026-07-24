"""
Example 33: Peak load management dispatch

This example demonstrates:
1. Peak load management dispatch open loop control with two demand profiles of interest
2. Battery charging without an input stream, assuming purchase from the grid

In this example, two load profiles are provided. It is assumed that demand_profile is a
subset of demand_profile_upstream, where demand_profile_upstream may represent the total demand of a
larger/upstream system. In this case, the upstream system reserves the right to choose
when to dispatch the battery up to three times per week. The remaining days the sub-system
may choose when and how to dispatch the battery. The subsystem has certain expected peak
windows that may be critical in terms of their cost structure, grid limits, or some other
reason and so they will only dispatch the battery for peaks in the chosen range. The top-
level system does not have such a requirement and will simply dispatch to reduce the highest
peaks. Perfect a priori demand knowledge is assumed. The battery is only allowed to discharge
once per day and is further restricted to not charge during the expected peak windows defined
by the sub-system operator.

The output figure indicates peaks from demand_profile_upstream that were selected to override the
peaks in demand_profile to demonstrate how the peak selection impacts dispatch.

"""

import numpy as np
import matplotlib.pyplot as plt

from h2integrate import H2IntegrateModel
from h2integrate.core.utilities import build_time_series_from_plant_config


# Create, setup, and run the H2Integrate model
model = H2IntegrateModel("33_peak_load_management.yaml")

model.setup()
# om.n2(model.prob)
model.run()
model.post_process()

demand_profile = model.prob.get_val("fuel_cell.electricity_command_value", units="kW")
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

ax[1].plot(time_plot, demand_profile[:n_plot] * 1e-3, label="Original demand (MW)")
ax[1].plot(
    time_plot,
    model.prob.get_val("fuel_cell.electricity_out", units="MW")[:n_plot],
    label="fuel_cell dispatch",
)
ax[1].set(ylabel="Power (MW)", ylim=[-2, 2])
ax[1].legend(frameon=False, ncol=2)

ax[2].plot(time_plot, demand_profile[:n_plot] * 1e-3, label="Original demand (MW)")
ax[2].plot(
    time_plot,
    model.prob.get_val("electrical_load_demand.unmet_electricity_demand_out", units="MW")[:n_plot],
    label="New demand profile",
)
ax[2].plot(time_plot, grid_output[:n_plot], label="Grid purchase (MW)", linestyle=":")

ax[2].set(ylabel="Power (MW)", ylim=[-2, 2])
ax[2].legend(frameon=False, ncol=3)
ax[2].tick_params(axis="x", labelrotation=90)

for axis in ax:
    axis.minorticks_on()
    axis.grid(True, which="major", alpha=0.45, linewidth=0.8)
    axis.grid(True, which="minor", alpha=0.2, linewidth=0.5)

############################## annotate override peaks ###########################

# Find top 3 daily peaks in supervisor demand (one per day in first week)
# supervisor_demand_first_week = supervisor_demand[:n_plot] * 1e-3
# days_first_week = pd.to_datetime(np.unique(pd.DatetimeIndex(time_plot).normalize()))

# daily_peaks = []
# for day in days_first_week:
#     day_start = day
#     day_end = day + pd.Timedelta(days=1)
#     day_mask = (time_plot >= day_start) & (time_plot < day_end)
#     if day_mask.any():
#         day_indices = np.where(day_mask)[0]
#         peak_idx = day_indices[np.argmax(supervisor_demand_first_week[day_indices])]
#         peak_time = time_plot[peak_idx]
#         peak_value = supervisor_demand_first_week[peak_idx]
#         daily_peaks.append((peak_time, peak_value))

# # Sort by peak value and get top 3
# top_3_peaks = sorted(daily_peaks, key=lambda x: x[1], reverse=True)[:3]
# top_3_peaks_sorted_by_time = sorted(top_3_peaks, key=lambda x: x[0])

# # Draw vertical dashed lines for top 3 daily peaks across all subplots
# colors = ["k", "k", "k"]
# for idx, (peak_time, _) in enumerate(top_3_peaks_sorted_by_time):
#     for axis in ax:
#         axis.axvline(peak_time, color=colors[idx], linestyle="--", linewidth=1.5, alpha=0.7)
#     # Add label on top subplot
#     ax[0].text(
#         peak_time,
#         ax[0].get_ylim()[1] + 0.3,
#         f"Peak override {idx + 1}",
#         fontsize=9,
#         ha="center",
#         color=colors[idx],
#         weight="bold",
#     )
###########################################################################################

plt.tight_layout()
plt.savefig("example_peak_load_dispatch.png", transparent=False)
