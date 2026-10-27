"""Demand-following system-level control with and without battery storage.

The same wind and natural gas plant meets a fixed electrical load demand in three configurations:

- `wind_ng_demand.yaml`: wind and natural gas only.
- `wind_ng_battery_demand.yaml`: adds a battery that the system-level controller dispatches.
- `wind_ng_battery_controller_demand.yaml`: the battery also has its own open-loop controller.

Each case is run, post-processed, and plotted for the first week of the year.
"""

import numpy as np
import matplotlib.pyplot as plt

from h2integrate.core.h2integrate_model import H2IntegrateModel


cases = {
    "no_battery": "wind_ng_demand.yaml",
    "battery": "wind_ng_battery_demand.yaml",
    "battery_with_controller": "wind_ng_battery_controller_demand.yaml",
}

# Plot the first 168 hours (1 week)
n_hours = 168
hours = np.arange(n_hours)

for case, config_file in cases.items():
    h2i = H2IntegrateModel(config_file)
    h2i.run()
    h2i.post_process()

    has_battery = "battery" in h2i.technology_config["technologies"]

    wind_out = h2i.prob.get_val("plant.wind.electricity_out")[:n_hours]
    ng_out = h2i.prob.get_val("plant.natural_gas_plant.electricity_out", units="kW")[:n_hours]
    demand = h2i.prob.get_val("plant.electrical_load_demand.electricity_demand")[:n_hours]
    curtailed = h2i.prob.get_val("plant.electrical_load_demand.unused_electricity_out")[:n_hours]
    if has_battery:
        batt_discharge = h2i.prob.get_val("plant.battery.storage_electricity_discharge")[:n_hours]
        batt_soc = h2i.prob.get_val("plant.battery.SOC")[:n_hours]
    else:
        batt_discharge = np.zeros(n_hours)

    n_rows = 3 if has_battery else 2
    fig, axes = plt.subplots(n_rows, 1, figsize=(12, 2 + 8 * n_rows / 3), sharex=True)

    # Stacked bar chart: wind + battery discharge + NG = total supply
    axes[0].bar(hours, wind_out, width=1.0, color="tab:blue", label="Wind", align="edge")
    if has_battery:
        axes[0].bar(
            hours,
            batt_discharge,
            width=1.0,
            bottom=wind_out,
            color="tab:purple",
            label="Battery Discharge",
            align="edge",
        )
    axes[0].bar(
        hours,
        ng_out,
        width=1.0,
        bottom=wind_out + batt_discharge,
        color="tab:orange",
        label="Natural Gas",
        align="edge",
    )
    axes[0].plot(hours, demand, color="black", linewidth=1.5, linestyle="--", label="Demand")
    axes[0].set_ylabel("Power (kW)")
    axes[0].set_title(f"System-Level Control ({case.replace('_', ' ')}): First 168 Hours")
    axes[0].legend(loc="upper right")

    if has_battery:
        axes[1].plot(hours, batt_soc, color="tab:cyan")
        axes[1].set_ylabel("Battery SOC (%)")

    axes[-1].bar(hours, curtailed, width=1.0, color="tab:red", align="edge")
    axes[-1].set_ylabel("Curtailed (kW)")
    axes[-1].set_xlabel("Hour")

    for ax in axes:
        ax.grid(True, alpha=0.3)

    fig.tight_layout()
    fig.savefig(f"slc_results_{case}.png", dpi=150)

plt.show()
