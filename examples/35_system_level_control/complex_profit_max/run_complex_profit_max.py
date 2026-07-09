"""
Complex profit-maximization example with wind, solar, battery, NG, and grid.

This example demonstrates profit-driven dispatch with:
  - Wind + solar (flexible) combined into a single renewable stream
  - Battery storage (200 MWh) for renewable energy shifting
  - Natural gas turbine with marginal cost of $0.05/kWh (dispatchable)
  - Grid buying with time-varying marginal cost (dispatchable)
  - Non-constant demand (commercial load profile with seasonal variation)
  - Realistic wholesale electricity sell prices (ERCOT-like diurnal + seasonal)

The controller dispatches NG and grid only during hours when the sell price
exceeds each source's marginal cost, preferring the cheaper source first
(merit-order dispatch). Renewables run at full capacity (zero marginal cost)
and the battery shifts energy toward high-price hours.
"""

import numpy as np
import matplotlib.pyplot as plt

from h2integrate.core.h2integrate_model import H2IntegrateModel


# ---------------------------------------------------------------------------
# Build realistic time-varying profiles
# ---------------------------------------------------------------------------
n_timesteps = 8760
hours_of_day = np.tile(np.arange(24), 365)
day_of_year = np.repeat(np.arange(365), 24)

# --- Non-constant demand (commercial/industrial load) ---
# Base: 50 MW, business-hours bump to ~80 MW, summer cooling adds ~20 MW
base_demand = 50_000  # kW
daytime_bump = np.where((hours_of_day >= 7) & (hours_of_day < 21), 30_000, 0)
# Seasonal factor: 1.0 in winter, peaks at 1.4 in summer (day ~172 = June 21)
seasonal_demand = 1.0 + 0.4 * np.sin(2 * np.pi * (day_of_year - 172) / 365)
demand_profile = (base_demand + daytime_bump) * seasonal_demand

# --- Realistic ERCOT-like wholesale sell price ($/kWh) ---
sell_price = np.zeros(n_timesteps)
for h in range(n_timesteps):
    hour = hours_of_day[h]
    day = day_of_year[h // 24] if h // 24 < 365 else day_of_year[-1]
    # Seasonal base: higher in summer
    season = 1.0 + 0.35 * np.sin(2 * np.pi * (day - 172) / 365)

    # Diurnal wholesale price shape (duck curve)
    if hour < 6:
        price = 0.025  # overnight trough
    elif hour < 10:
        price = 0.025 + (hour - 6) * 0.008  # morning ramp
    elif hour < 15:
        price = 0.035  # midday dip (solar flood)
    elif hour < 20:
        price = 0.035 + (hour - 15) * 0.018  # evening ramp to peak
    else:
        price = 0.125 - (hour - 20) * 0.025  # evening decline

    sell_price[h] = price * season

# Add summer evening price spikes (simulate heat-wave scarcity)
for h in range(n_timesteps):
    day = day_of_year[h // 24] if h // 24 < 365 else day_of_year[-1]
    hour = hours_of_day[h]
    if 150 <= day <= 250 and 17 <= hour <= 20 and day % 5 == 0:
        sell_price[h] = max(sell_price[h], 0.20)

# --- Grid buy marginal cost: tracks wholesale price + retail markup ---
grid_buy_price = sell_price + 0.02  # grid is always more expensive than selling

# ---------------------------------------------------------------------------
# Create and run model
# ---------------------------------------------------------------------------
h2i = H2IntegrateModel("complex_profit_max.yaml")
h2i.setup()

# Override demand profile
h2i.prob.set_val(
    "plant.electrical_load_demand.electricity_demand",
    demand_profile,
)

# Override sell price with time-varying profile
h2i.prob.set_val(
    "plant.system_level_controller.commodity_sell_price",
    sell_price,
    units="USD/(kW*h)",
)

# Override grid buy price with time-varying profile
h2i.prob.set_val(
    "plant.grid_buy.electricity_buy_price",
    grid_buy_price,
    units="USD/(kW*h)",
)

h2i.run()
h2i.post_process()

# ---------------------------------------------------------------------------
# Extract results
# ---------------------------------------------------------------------------
n_hours = 336  # two weeks for clearer patterns
hours = np.arange(n_hours)

wind_out = h2i.prob.get_val("plant.wind.electricity_out")[:n_hours]
solar_out = h2i.prob.get_val("plant.solar.electricity_out")[:n_hours]
ng_out = h2i.prob.get_val("plant.natural_gas_plant.electricity_out", units="kW")[:n_hours]
grid_out = h2i.prob.get_val("plant.grid_buy.electricity_out")[:n_hours]
batt_discharge = h2i.prob.get_val("plant.battery.storage_electricity_discharge")[:n_hours]
batt_soc = h2i.prob.get_val("plant.battery.SOC")[:n_hours]
demand = demand_profile[:n_hours]
price = sell_price[:n_hours]

# ---------------------------------------------------------------------------
# Plot
# ---------------------------------------------------------------------------
fig, axes = plt.subplots(5, 1, figsize=(16, 16), sharex=True)

# Panel 1: stacked bar supply vs demand
axes[0].bar(hours, wind_out, width=1.0, color="tab:blue", label="Wind", align="edge")
axes[0].bar(
    hours,
    solar_out,
    width=1.0,
    bottom=wind_out,
    color="gold",
    label="Solar",
    align="edge",
)
axes[0].bar(
    hours,
    batt_discharge,
    width=1.0,
    bottom=wind_out + solar_out,
    color="tab:purple",
    label="Battery",
    align="edge",
)
axes[0].bar(
    hours,
    ng_out,
    width=1.0,
    bottom=wind_out + solar_out + batt_discharge,
    color="tab:orange",
    label="Natural Gas",
    align="edge",
)
axes[0].bar(
    hours,
    grid_out,
    width=1.0,
    bottom=wind_out + solar_out + batt_discharge + ng_out,
    color="tab:gray",
    label="Grid Buy",
    align="edge",
)
axes[0].plot(hours, demand, "k--", linewidth=1.5, label="Demand")
axes[0].set_ylabel("Power (kW)")
axes[0].set_title("Complex Profit Maximization: First Two Weeks")
axes[0].legend(loc="upper right", ncol=3)

# Panel 2: battery state of charge
axes[1].plot(hours, batt_soc, color="tab:green")
axes[1].set_ylabel("SOC (kWh)")
axes[1].set_title("Battery State of Charge")

# Panel 3: sell price vs marginal costs
axes[2].plot(hours, price * 100, color="tab:red", linewidth=0.8, label="Sell Price")
axes[2].axhline(
    y=5.0, color="tab:orange", linestyle="--", alpha=0.8, label="NG Marginal Cost (5 ¢/kWh)"
)
axes[2].plot(
    hours, (price + 0.02) * 100, color="tab:gray", linewidth=0.6, alpha=0.7, label="Grid Buy Cost"
)
axes[2].set_ylabel("Price (¢/kWh)")
axes[2].set_title("Electricity Prices vs Dispatch Costs")
axes[2].legend(loc="upper right")

# Panel 4: individual dispatch decisions
axes[3].plot(hours, ng_out / 1000, color="tab:orange", label="NG (MW)")
axes[3].plot(hours, grid_out / 1000, color="tab:gray", label="Grid Buy (MW)")
axes[3].set_ylabel("Power (MW)")
axes[3].set_title("Dispatchable Generation Decisions")
axes[3].legend(loc="upper right")

# Panel 5: renewable generation
axes[4].plot(hours, wind_out / 1000, color="tab:blue", label="Wind (MW)")
axes[4].plot(hours, solar_out / 1000, color="gold", label="Solar (MW)")
axes[4].set_ylabel("Power (MW)")
axes[4].set_xlabel("Hour")
axes[4].set_title("Flexible Renewable Generation")
axes[4].legend(loc="upper right")

for ax in axes:
    ax.grid(True, alpha=0.3)

plt.tight_layout()
plt.savefig("complex_profit_max_results.png", dpi=150)
print("Plot saved to complex_profit_max_results.png")
# plt.show()
