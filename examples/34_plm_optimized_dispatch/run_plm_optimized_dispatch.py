"""
This example simulates a Battery Energy Storage system controller
to demonstrate demand-response and peak-load management dispatch
using a rolling-horizon MILP controller.
The battery is scheduled to discharge during high-LMP peak hours
to maximize incentives and during off-peak hours to minimize the
operation cost.
"""

from pathlib import Path

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt

from h2integrate.core.utilities import build_time_series_from_plant_config
from h2integrate.core.h2integrate_model import H2IntegrateModel


EXAMPLE_DIR = Path(__file__).parent


# Run H2Ingegrate
model = H2IntegrateModel(EXAMPLE_DIR / "34_plm_optimized_dispatch.yaml")
model.setup()
model.run()

# Read inputs from config
control_params = model.technology_config["technologies"]["battery"]["model_inputs"][
    "control_parameters"
]
n_timesteps = int(model.plant_config["plant"]["simulation"]["n_timesteps"])
lmp = np.array(control_params["lmp_signal"])[:n_timesteps]
demand = np.array(control_params["demand_signal"])[:n_timesteps]
dt_seconds = int(model.plant_config["plant"]["simulation"]["dt"])
time_index = pd.DatetimeIndex(build_time_series_from_plant_config(model.plant_config))

event_dur_cfg = control_params.get("event_duration")
half_td = None
if event_dur_cfg is not None:
    half_td = pd.Timedelta(value=event_dur_cfg["val"], unit=event_dur_cfg["units"]) / 2

# Read H2Integrate output
battery_power = model.prob.get_val("battery.storage_electricity_discharge", units="kW")
soc_pct = model.prob.get_val("battery.SOC", units="percent")

# Read controller output
controller = model.control_strategies[0]
pw_start, pw_end = controller._parse_peak_window()
pw_start_h = pw_start.hour
pw_end_h = pw_end.hour

# Intermediate MILP decision variables
u_discharge_gt = controller.discharge_gt_bin_history
u_discharge_coop = controller.discharge_coop_bin_history
v_charge = controller.charge_bin_history
p_discharge_gt = controller.p_discharge_gt_history
p_discharge_coop = controller.p_discharge_coop_history
p_charge = controller.p_charge_history
p_tocoop = controller.p_tocoop_history

# Plot outputs
plotdays = 10
plt.rcParams.update({"axes.spines.top": False, "axes.spines.right": False})
fig, axes = plt.subplots(4, 1, sharex=True, figsize=(8, 6))
days = pd.date_range(time_index[0].normalize(), periods=plotdays, freq="D", tz=time_index.tz)
plot_time_window = min(n_timesteps, int(plotdays * 24 * 3600 / dt_seconds))  # 14 days
eventlogmask = [False] * n_timesteps
for i in range(n_timesteps):
    if i == 0:
        eventlogmask[i] = False
    elif u_discharge_gt[i] == 1 and u_discharge_gt[i - 1] == 0:
        eventlogmask[i] = True


def shade_peaks(ax):
    for day in days:
        ax.axvspan(
            day + pd.Timedelta(hours=pw_start_h),
            day + pd.Timedelta(hours=pw_end_h),
            color="orange",
            alpha=0.20,
            linewidth=0,
            zorder=0,
        )
        if half_td is None:
            continue
        pw_start_ts = day + pd.Timedelta(hours=pw_start_h)
        pw_end_ts = day + pd.Timedelta(hours=pw_end_h)
        in_pw = (time_index >= pw_start_ts) & (time_index <= pw_end_ts)
        if not in_pw.any():
            continue
        peak_idx = np.where(in_pw)[0][np.argmax(lmp[in_pw])]
        peak_ts = time_index[peak_idx]
        ax.axvspan(
            peak_ts - half_td,
            peak_ts + half_td,
            color="darkorange",
            alpha=0.30,
            linewidth=0,
            zorder=0,
        )


# Plot LMP
ax = axes[0]
shade_peaks(ax)
ax.plot(
    time_index[:plot_time_window],
    lmp[:plot_time_window],
    color="steelblue",
    linewidth=1.0,
    label="LMP ($/kWh)",
)
ax.set_ylabel("LMP ($/kWh)", fontsize=8)
ax.set_ylim(bottom=0)
ax.legend(fontsize=7, loc="upper left", frameon=True)

# Plot SOC
ax = axes[1]
shade_peaks(ax)
ax.plot(
    time_index[:plot_time_window],
    soc_pct[:plot_time_window],
    linewidth=1.0,
    label="Battery SOC (%)",
)
ax.axhline(90, color="gray", linestyle=":", linewidth=0.7)
ax.axhline(10, color="gray", linestyle=":", linewidth=0.7)
ax.set_ylabel("Battery SOC (%)", fontsize=8)
ax.legend(fontsize=7, loc="lower left", frameon=True)
ax.set_ylim([0, 105])

# Plot battery discharges and charges
ax = axes[2]
shade_peaks(ax)
ax.plot(
    time_index[:plot_time_window],
    p_discharge_gt[:plot_time_window],
    color="green",
    label="Discharging for G&T",
    linewidth=1.0,
)
ax.plot(
    time_index[:plot_time_window],
    p_discharge_coop[:plot_time_window],
    color="darkorange",
    label="Discharging for Co-Op",
    linewidth=1.0,
)
ax.plot(
    time_index[:plot_time_window],
    -p_charge[:plot_time_window],
    color="orange",
    linestyle="--",
    label="Charging",
    linewidth=1.0,
)
ax.axhline(0, color="k", linewidth=0.5)
ax.set_ylabel("Battery power (kW)", fontsize=8)
# ax.legend(fontsize=7, loc="lower left", frameon=True)
ax.legend(
    fontsize=7,
    loc="upper center",
    bbox_to_anchor=(0.5, 1.25),  # x, y position
    ncol=3,  # arrange legend entries horizontally
)

# Plot demand and power supply from G&T to Co-Op
ax = axes[3]
shade_peaks(ax)
ax.plot(
    time_index[:plot_time_window],
    demand[:plot_time_window],
    color="k",
    label="Demand",
    linewidth=1.0,
)
ax.plot(
    time_index[:plot_time_window],
    p_tocoop[:plot_time_window],
    color="teal",
    label="G&T to Co-Op",
    linewidth=1.0,
    linestyle="--",
)
ax.set_ylabel("Demand (kW)", fontsize=8)
ax.set_xlabel("Time")
ax.set_ylim([2300, 6500])
ax.legend(fontsize=7, loc="lower left", frameon=True)

plt.tight_layout()
plt.savefig(EXAMPLE_DIR / "plm_optimized_dispatch.png", dpi=150, bbox_inches="tight")
