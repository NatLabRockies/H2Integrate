"""
Example 33: Peak load management dispatch

This example demonstrates:
1. Peak load management dispatch open loop control
2. Battery charging without an input stream, assuming purchase from the grid

"""

import numpy as np
import matplotlib.pyplot as plt

from h2integrate.core.utilities import build_time_series_from_plant_config
from h2integrate.core.h2integrate_model import H2IntegrateModel


# Create and setup the H2Integrate model
model = H2IntegrateModel("33_peak_load_management.yaml")

model.setup()

model.run()

supervisor_demand = np.array(
    model.technology_config["technologies"]["battery"]["model_inputs"]["control_parameters"][
        "demand_profile_supervisor"
    ]
)
secondary_demand = model.prob.get_val("battery.electricity_demand")

time_series = build_time_series_from_plant_config(model.plant_config)

n_plot = 24 * 7
time_plot = time_series[:n_plot]

fig, ax = plt.subplots(4, 1, sharex=True)
ax[0].plot(time_plot, supervisor_demand[:n_plot] * 1e-3, label="Supervisory demand (MW)")
ax[0].plot(time_plot, secondary_demand[:n_plot] * 1e-3, label="Secondary demand (MW)")
ax[0].set_ylabel("Power (MW)")
ax[0].legend(loc="upper right")

ax[1].plot(time_plot, model.prob.get_val("battery.SOC", units="percent")[:n_plot])
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
    model.prob.get_val("battery.unmet_electricity_demand_out", units="MW")[:n_plot],
    label="New demand profile",
)
ax[3].set(ylabel="Power (MW)")
ax[3].legend()
ax[3].tick_params(axis="x", labelrotation=90)

plt.tight_layout()
plt.show()
