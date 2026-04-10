"""
Example 33: Peak load management dispatch

This example demonstrates:
1. Peak load management dispatch open loop control with two demand profiles of interest
2. Battery charging without an input stream, assuming purchase from the grid

In this example, two load profiles are provided. It is assumed that demand_profile is a
subset of demand_profile_2, where demand_profile_2 may represent the total demand of a
larger/upstream system. In this case, the upstream system reserves the right to choose
when to dispatch the battery up to three times per week. The remaining days the sub-system
may choose when and how to dispatch the battery. The subsystem has certain expected peak
windows that may be critical in terms of their cost structure, grid limits, or some other
reason and so they will only dispatch the battery for peaks in the chosen range. The top-
level system does not have such a requirement and will simply dispatch to reduce the highest
peaks. Perfect a priori demand knowledge is assumed. The battery is only allowed to discharge
once per day and is further restricted to not charge during the expected peak windows defined
by the sub-system operator.

"""

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from matplotlib.patches import Patch

from h2integrate.core.utilities import build_time_series_from_plant_config
from h2integrate.core.h2integrate_model import H2IntegrateModel


# Create, setup, and run the H2Integrate model
model = H2IntegrateModel("33_peak_load_management.yaml")

model.setup()
model.run()

# plot the results for the first week
supervisor_demand = np.array(
    model.technology_config["technologies"]["battery"]["model_inputs"]["control_parameters"][
        "demand_profile_2"
    ]
)

secondary_demand = model.prob.get_val("battery.electricity_demand")

time_series = build_time_series_from_plant_config(model.plant_config)

n_plot = 24 * 7
time_plot = time_series[:n_plot]

# Shade peak window on every plotted day
peak_patch = Patch(facecolor="orange", alpha=0.12, label="Expected peak window (12pm to 7pm)")

fig, ax = plt.subplots(4, 1, sharex=True, figsize=(10, 5))
ax[0].plot(time_plot, secondary_demand[:n_plot] * 1e-3, label="Original demand (MW)")
ax[0].plot(time_plot, supervisor_demand[:n_plot] * 1e-3, label="Overriding demand (MW)")
ax[0].set(ylabel="Power (MW)", ylim=[-2, 2])
ax[0].legend(handles=[*ax[0].get_legend_handles_labels()[0], peak_patch], frameon=True, ncol=3)

ax[1].plot(time_plot, model.prob.get_val("battery.SOC", units="percent")[:n_plot])
ax[1].set(ylabel="SOC", ylim=[0, 100])
ax[1].legend(handles=[*ax[1].get_legend_handles_labels()[0]], frameon=False, ncol=2)

ax[2].plot(time_plot, secondary_demand[:n_plot] * 1e-3, label="Original demand (MW)")
ax[2].plot(
    time_plot,
    model.prob.get_val("battery.electricity_out", units="MW")[:n_plot],
    label="Battery charge/discharge",
)
ax[2].set(ylabel="Power (MW)", ylim=[-2, 2])
ax[2].legend(handles=[*ax[2].get_legend_handles_labels()[0]], frameon=False, ncol=2)

ax[3].plot(time_plot, secondary_demand[:n_plot] * 1e-3, label="Original demand (MW)")
ax[3].plot(
    time_plot,
    model.prob.get_val("battery.unmet_electricity_demand_out", units="MW")[:n_plot],
    label="New demand profile",
)
ax[3].set(ylabel="Power (MW)", ylim=[-2, 2])
ax[3].legend(handles=[*ax[3].get_legend_handles_labels()[0]], frameon=False, ncol=2)
ax[3].tick_params(axis="x", labelrotation=90)

days = pd.to_datetime(np.unique(pd.DatetimeIndex(time_plot).normalize()))
for axis in ax:
    for day in days:
        axis.axvspan(
            day + pd.Timedelta(hours=12),
            day + pd.Timedelta(hours=19),
            color="orange",
            alpha=0.12,
            linewidth=0,
            zorder=0,
        )

for axis in ax:
    axis.minorticks_on()
    axis.grid(True, which="major", alpha=0.45, linewidth=0.8)
    axis.grid(True, which="minor", alpha=0.2, linewidth=0.5)

plt.tight_layout()
plt.savefig("example_peak_load_dispatch.png", transparent=False)
