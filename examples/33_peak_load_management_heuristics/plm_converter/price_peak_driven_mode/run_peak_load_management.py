"""
Example 33: Peak load management converter heuristic dispatch (price-driven mode)

This example demonstrates peak load management dispatch open-loop control of a converter
driven by an upstream *price* signal instead of an upstream demand profile.

The fuel-cell converter command is determined by a simple open-loop threshold heuristic
that uses:

1. demand_profile (local set-point, in kW)
2. demand_profile_upstream (a supervisory upstream *price* signal, in USD/kWh)

In price-driven mode, fuel-cell dispatch is only *enabled* on timesteps where the upstream
price exceeds ``demand_profile_upstream_peak_cutoff``. On those enabled hours, the commanded
dispatch is the local demand's exceedance above ``demand_profile_peak_cutoff``, limited by
both the instantaneous local demand and the converter capacity. This shaves local peaks
only when it is economically attractive to do so (i.e. when grid prices are high).

The upstream price profile is ``library/demand_profiles/pjm_wh_rt_peak_hourly_2025.yaml``,
an 8760 hourly profile derived from ICE "PJM WH Real Time Peak" daily prices.

The output figure compares the local demand and its cutoff against the upstream price and
its cutoff, the resulting converter output, and the unmet demand and grid purchases.

"""

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt

from h2integrate import H2IntegrateModel
from h2integrate.core.utilities import build_time_series_from_plant_config


# Create, setup, and run the H2Integrate model
model = H2IntegrateModel("33_plm_converter_heuristic.yaml")

model.setup()
# om.n2(model.prob)
model.run()
model.post_process()


# --- Plot window selection --------------------------------------------------
# Choose the date the plot window starts on and how many days to show. The start
# date is clamped to the simulated period (the plant starts 2025-07-01). Set
# PLOT_START_DATE to None to start at the beginning of the simulation.
PLOT_START_DATE = "2025-07-05"
PLOT_DAYS = 21

demand_profile = model.prob.get_val("fuel_cell.electricity_set_point", units="kW")

# In price-driven mode the upstream signal is a price time series (USD/kWh).
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

# Resolve the requested start date to an index into the 8760 arrays and build a
# slice for the plot window.
time_index = pd.DatetimeIndex(time_series)
if PLOT_START_DATE is None:
    start_idx = 0
else:
    start_ts = pd.Timestamp(PLOT_START_DATE)
    if time_index.tz is not None and start_ts.tz is None:
        start_ts = start_ts.tz_localize(time_index.tz)
    start_idx = int(time_index.searchsorted(start_ts))
start_idx = min(max(start_idx, 0), len(time_index) - 1)

n_plot = 24 * PLOT_DAYS
end_idx = min(start_idx + n_plot, len(time_index))
window = slice(start_idx, end_idx)
time_plot = time_series[window]

fig, ax = plt.subplots(3, 1, sharex=True, figsize=(10, 5))

# Panel 0: local demand (MW, left axis) vs. upstream price (USD/kWh, right axis).
ax[0].plot(time_plot, demand_profile[window] * 1e-3, label="Original demand", color="tab:blue")
ax[0].axhline(
    demand_profile_peak_cutoff * 1e-3, label="Demand peak cutoff", color="tab:blue", linestyle="--"
)
ax[0].set(ylabel="Power (MW)", ylim=[-2, 2])
ax[0].legend(loc="upper left", frameon=True, ncol=2)

ax_price = ax[0].twinx()
ax_price.plot(
    time_plot, demand_profile_upstream[window], label="Upstream price", color="tab:red", alpha=0.7
)
ax_price.axhline(
    demand_profile_upstream_peak_cutoff,
    label="Upstream price cutoff",
    color="tab:red",
    linestyle=":",
)
ax_price.set(ylabel="Price ($/kWh)")
ax_price.legend(loc="upper right", frameon=True, ncol=2)

ax[1].plot(time_plot, demand_profile[window] * 1e-3, label="Original demand")
ax[1].plot(
    time_plot,
    model.prob.get_val("fuel_cell.electricity_out", units="MW")[window],
    label="fuel_cell dispatch",
)
ax[1].set(ylabel="Power (MW)", ylim=[-2, 2])
ax[1].legend(frameon=False, ncol=2)

ax[2].plot(time_plot, demand_profile[window] * 1e-3, label="Original demand")
ax[2].plot(
    time_plot,
    model.prob.get_val("electrical_load_demand.unmet_electricity_demand_out", units="MW")[window],
    label="New demand profile",
)
ax[2].plot(time_plot, grid_output[window], label="Grid purchase", linestyle=":")

ax[2].set(ylabel="Power (MW)", ylim=[-2, 2])
ax[2].legend(frameon=False, ncol=3)
ax[2].tick_params(axis="x", labelrotation=90)

for axis in ax:
    axis.minorticks_on()
    axis.grid(True, which="major", alpha=0.45, linewidth=0.8)
    axis.grid(True, which="minor", alpha=0.2, linewidth=0.5)

plt.tight_layout()
plt.savefig("example_peak_load_dispatch.png", transparent=False, dpi=300)
