"""
Example 33: Peak load management dispatch

This example demonstrates:
1. Peak load management dispatch open loop control
2. Battery charging without an input stream, assuming purchase from the grid

"""

import numpy as np
import matplotlib.pyplot as plt

from h2integrate.core.utilities import build_time_series_from_plant_config
from h2integrate.core.file_utils import load_yaml
from h2integrate.core.h2integrate_model import H2IntegrateModel


# Create and setup the H2Integrate model
model = H2IntegrateModel("33_peak_load_management.yaml")

model.setup()

model.run()

plant_config = load_yaml("plant_config.yaml")
supervisor_demand = np.asarray(
    load_yaml("demand_profiles/demand_profile_supervisor.yaml"), dtype=float
)
secondary_demand = np.asarray(
    load_yaml("demand_profiles/demand_profile_secondary.yaml"), dtype=float
)

time_series = build_time_series_from_plant_config(plant_config)

# Example profiles may be shorter than the simulation horizon; plot over shared length.
n_plot = min(len(time_series), len(supervisor_demand), len(secondary_demand))
time_plot = time_series[:n_plot]

fig, ax = plt.subplots(4, 1, sharex=True)

ax[0].plot(time_plot, supervisor_demand[:n_plot] * 1e-3, label="Supervisory demand (MW)")
ax[0].plot(time_plot, secondary_demand[:n_plot] * 1e-3, label="Secondary demand (MW)")
ax[0].set_ylabel("Power (MW)")
ax[0].legend(loc="upper right")

ax[1].plot(time_plot, model.prob.get_val("battery.SOC", units="percent"))
ax[1].set(ylabel="SOC")

ax[2].plot(time_plot, secondary_demand[:n_plot] * 1e-3, label="Original demand (MW)")
ax[2].plot(
    time_plot,
    model.prob.get_val("battery.electricity_out", units="MW"),
    label="Battery charge/discharge",
)
ax[2].set(ylabel="Power (MW)")
ax[2].legend()

ax[3].plot(time_plot, secondary_demand[:n_plot] * 1e-3, label="Original demand (MW)")
ax[3].plot(
    time_plot,
    model.prob.get_val("battery.unmet_electricity_demand_out", units="MW"),
    label="New demand profile",
)
ax[3].set(ylabel="Power (MW)")
ax[3].legend()


ax[3].tick_params(axis="x", labelrotation=90)

# import pdb; pdb.set_trace()
plt.tight_layout()
plt.show()
