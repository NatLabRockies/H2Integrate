"""
Profit-maximization example with simple electricity price profiles.

The controller dispatches the NG plant only during hours when the sell price
exceeds the marginal cost, demonstrating profit-driven curtailment of
dispatchable generation.
"""

import numpy as np
import matplotlib.pyplot as plt

from h2integrate.core.h2integrate_model import H2IntegrateModel


# -- Create and run model --
h2i = H2IntegrateModel("wind_ng_demand.yaml")

# Setup first so we can set values
h2i.setup()

h2i.run()
h2i.post_process()

# -- Extract results --
n_hours = 168  # first week
hours = np.arange(n_hours)

wind_out = h2i.prob.get_val("plant.wind.electricity_out")[:n_hours]
ng_out = h2i.prob.get_val("plant.natural_gas_plant.electricity_out", units="kW")[:n_hours]
batt_discharge = h2i.prob.get_val("plant.battery.storage_electricity_discharge")[:n_hours]
batt_soc = h2i.prob.get_val("plant.battery.SOC")[:n_hours]
demand = h2i.prob.get_val("plant.electrical_load_demand.electricity_demand")[:n_hours]
curtailed = h2i.prob.get_val("plant.electrical_load_demand.unused_electricity_out")[:n_hours]
price = h2i.prob.get_val("system_level_controller.commodity_sell_price")[:n_hours]

# -- Plot --
fig, axes = plt.subplots(4, 1, figsize=(14, 12), sharex=True)

# Panel 1: stacked supply vs demand
axes[0].fill_between(hours, 0, ng_out, alpha=0.7, color="tab:orange", label="Natural Gas")
axes[0].fill_between(
    hours,
    ng_out,
    ng_out + batt_discharge,
    alpha=0.7,
    color="tab:purple",
    label="Battery Discharge",
)
axes[0].fill_between(
    hours,
    ng_out + batt_discharge,
    ng_out + batt_discharge + wind_out,
    alpha=0.7,
    color="tab:blue",
    label="Wind",
)
axes[0].plot(hours, demand, "k--", linewidth=1.5, label="Demand")
axes[0].set_ylabel("Power (kW)")
axes[0].set_title("Profit Maximization: First 168 Hours")
axes[0].legend(loc="upper right")

# Panel 2: battery SOC
axes[1].plot(hours, batt_soc, color="tab:green")
axes[1].set_ylabel("SOC (kWh)")
axes[1].set_title("Battery State of Charge")

# Panel 3: sell price vs NG marginal cost
axes[2].plot(hours, price * 100, color="tab:red", label="Sell Price")
axes[2].axhline(y=5.0, color="tab:orange", linestyle="--", label="NG Marginal Cost (5 ¢/kWh)")
axes[2].set_ylabel("Price (¢/kWh)")
axes[2].set_title("Electricity Sell Price vs NG Marginal Cost")
axes[2].legend(loc="upper right")

# Panel 4: curtailed energy
axes[3].plot(hours, curtailed, color="tab:gray")
axes[3].set_ylabel("Curtailed (kW)")
axes[3].set_xlabel("Hour")
axes[3].set_title("Curtailed Electricity")

plt.tight_layout()
plt.savefig("profit_max_results.png", dpi=150)
print("Plot saved to profit_max_results.png")
# plt.show()
