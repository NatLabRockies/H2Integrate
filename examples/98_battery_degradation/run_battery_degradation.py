"""
Example 98: Battery degradation through the standard H2Integrate interface.

This example runs the SimSES-backed ``BatteryPerformanceModel`` through the standard
``H2IntegrateModel`` interface (YAML-configured plant/tech/driver). The battery has no
control strategy, so a passthrough controller forwards the ``electricity_set_point``
profile to the battery as its dispatch command (positive = discharge, negative = charge).

A repeating daily charge/discharge cycle is applied for the full simulation horizon and
the battery internal timeseries (voltage, temperature, state-of-health, losses) are read
from ``BatteryPerformanceModel.results`` to produce the reference plots:

  1. AC and DC power (first 7 days)
  2. State of charge (hourly mean)
  3. Battery temperature (first 7 days)
  4. Terminal voltage (first 7 days and daily mean)
  5. Capacity fade and resistance growth over the horizon
  6. Battery/converter losses and heat (daily mean)

H2Integrate constrains a single simulation to exactly one year
(``n_timesteps * dt == 31_536_000 s``), so this example runs a 1-year degradation
study. The battery pack topology and degradation scaling live in ``tech_config.yaml``.
"""

from pathlib import Path

import numpy as np
import pandas as pd
import matplotlib


matplotlib.use("Agg")
import matplotlib.pyplot as plt

from h2integrate import H2IntegrateModel
from h2integrate.storage.battery.battery_performance import BatteryPerformanceModel


HERE = Path(__file__).parent

# ---------------------------------------------------------------------------
# Build and set up the H2Integrate model (standard interface)
# ---------------------------------------------------------------------------
model = H2IntegrateModel(HERE / "98_battery_degradation.yaml")
model.setup()

# Simulation horizon (read from the plant config)
sim = model.plant_config["plant"]["simulation"]
dt = float(sim["dt"])
n_steps = int(sim["n_timesteps"])
steps_per_day = round(86400 / dt)

# Fixed Megapack-style pack (read from the tech config)
shared = model.technology_config["technologies"]["battery"]["model_inputs"]["shared_parameters"]
series_count = shared["series_count"]
parallel_count = shared["parallel_count"]
cell_nominal_voltage = 3.2  # V
cell_capacity_ah = 280.0  # Ah
usable_fraction = shared["max_soc_fraction"] - shared["min_soc_fraction"]

nominal_energy_kwh = series_count * parallel_count * cell_nominal_voltage * cell_capacity_ah / 1e3
usable_energy_kwh = nominal_energy_kwh * usable_fraction

# ---------------------------------------------------------------------------
# Daily set-point profile (H2I convention: + = discharge, - = charge, kW)
#   0 - 2 h    discharge at C/2 of usable energy
#   2 - 12 h   charge    at C/10 of usable energy
#   12 - 24 h  rest
# Defined in continuous time so it is independent of the timestep.
# ---------------------------------------------------------------------------
p_discharge = 0.5 * usable_energy_kwh  # kW, + = discharge
p_charge = -0.1 * usable_energy_kwh  # kW, - = charge

t_mid = (np.arange(n_steps) + 0.5) * dt  # midpoint time [s] from sim start
t_day = t_mid % 86400  # position within the current day
set_point = np.where(
    t_day < 2 * 3600,
    p_discharge,
    np.where(t_day < 12 * 3600, p_charge, 0.0),
)

n_years = n_steps / (365 * steps_per_day)
print(f"Simulation: {n_years:.2f} years, {n_steps:,} steps, dt={int(dt)} s")
print(f"Nominal energy: {nominal_energy_kwh:.0f} kWh, usable: {usable_energy_kwh:.0f} kWh")
print(f"Discharge: {p_discharge / 1e3:.3f} MW (C/2)   Charge: {p_charge / 1e3:.3f} MW (C/10)")

# ---------------------------------------------------------------------------
# Drive the battery via its set-point (passthrough controller -> command value)
# and run the model.
# ---------------------------------------------------------------------------
model.prob.set_val("battery.electricity_set_point", set_point, units="kW")
model.run()

# ---------------------------------------------------------------------------
# Retrieve the battery internal timeseries and assemble a DataFrame
# ---------------------------------------------------------------------------
battery = next(model.prob.model.system_iter(typ=BatteryPerformanceModel))
res = battery.results

index = pd.date_range("2026-01-01", periods=n_steps, freq=f"{int(dt)}s")
df = pd.DataFrame(
    {
        "soc": res["soc"],
        "v": res["voltage"],
        "T": res["temperature"],
        "loss": res["battery_loss"],
        "heat": res["battery_heat"],
        "soh_Q": res["soh_capacity"],
        "soh_R": res["soh_resistance"],
        "power_ac": res["power_ac"],
        "power_dc": res["power_dc"],
        "conv_loss": res["converter_loss"],
    },
    index=index,
)

fade_pct = (1 - df["soh_Q"].iloc[-1]) * 100
growth_pct = (df["soh_R"].iloc[-1] - 1) * 100
print(f"Final capacity fade: {fade_pct:.2f} %   resistance growth: {growth_pct:.2f} %")

week = 7 * steps_per_day

# ---------------------------------------------------------------------------
# Plot 1: AC & DC power (first 7 days)
# ---------------------------------------------------------------------------
fig, ax = plt.subplots(figsize=(12, 3))
df[["power_ac", "power_dc"]].iloc[:week].plot(ax=ax)
ax.set_title("AC and DC power -- first 7 days")
ax.set_ylabel("Power [MW]")
ax.axhline(0, color="gray", linewidth=0.5)
ax.yaxis.set_major_formatter(plt.FuncFormatter(lambda x, _: f"{x / 1e6:.2f}"))
fig.tight_layout()
fig.savefig(HERE / "plot_power.png", dpi=150)
print("Saved plot_power.png")

# ---------------------------------------------------------------------------
# Plot 2: SOC (hourly mean)
# ---------------------------------------------------------------------------
fig, ax = plt.subplots(figsize=(12, 3))
df["soc"].resample("1h").mean().plot(ax=ax, title="State of charge -- hourly mean")
ax.set_ylabel("SOC [p.u.]")
fig.tight_layout()
fig.savefig(HERE / "plot_soc.png", dpi=150)
print("Saved plot_soc.png")

# ---------------------------------------------------------------------------
# Plot 3: Battery temperature (first 7 days)
# ---------------------------------------------------------------------------
fig, ax = plt.subplots(figsize=(12, 3))
df["T"].iloc[:week].plot(ax=ax, title="Battery temperature -- first 7 days")
ax.set_ylabel("Temperature [degC]")
ax.axhline(25.0, color="gray", linewidth=0.8, linestyle="--", label="T_ambient = 25 degC")
ax.legend()
fig.tight_layout()
fig.savefig(HERE / "plot_temperature_7days.png", dpi=150)
print("Saved plot_temperature_7days.png")

# ---------------------------------------------------------------------------
# Plot 4a: Terminal voltage (first 7 days)
# ---------------------------------------------------------------------------
fig, ax = plt.subplots(figsize=(12, 3))
df["v"].iloc[:week].plot(ax=ax, title="Terminal voltage -- first 7 days [V]")
ax.set_ylabel("Voltage [V]")
fig.tight_layout()
fig.savefig(HERE / "plot_voltage_7days.png", dpi=150)
print("Saved plot_voltage_7days.png")

# ---------------------------------------------------------------------------
# Plot 4b: Terminal voltage (daily mean)
# ---------------------------------------------------------------------------
fig, ax = plt.subplots(figsize=(12, 3))
df["v"].resample("1D").mean().plot(ax=ax, title="Terminal voltage -- daily mean [V]")
ax.set_ylabel("Voltage [V]")
fig.tight_layout()
fig.savefig(HERE / "plot_voltage.png", dpi=150)
print("Saved plot_voltage.png")

# ---------------------------------------------------------------------------
# Plot 5: Degradation over the simulation horizon
# ---------------------------------------------------------------------------
df_monthly = df[["soh_Q", "soh_R"]].resample("ME").last()
capacity_fade_pct = (1 - df_monthly["soh_Q"]) * 100
resistance_growth_pct = (df_monthly["soh_R"] - 1) * 100

fig, ax1 = plt.subplots(figsize=(12, 4))
ax2 = ax1.twinx()
ax1.plot(
    capacity_fade_pct.index,
    capacity_fade_pct.values,
    color="steelblue",
    label="Capacity fade [%]",
)
ax2.plot(
    resistance_growth_pct.index,
    resistance_growth_pct.values,
    color="darkorange",
    label="Resistance growth [%]",
)
ax1.set_ylabel("Capacity fade [%]", color="steelblue")
ax2.set_ylabel("Resistance growth [%]", color="darkorange")
ax1.tick_params(axis="y", labelcolor="steelblue")
ax2.tick_params(axis="y", labelcolor="darkorange")
ax1.axhline(20, color="steelblue", linewidth=0.8, linestyle="--", alpha=0.6)
ax1.set_title(
    f"Battery degradation over {n_years:.1f} years "
    f"(final: {capacity_fade_pct.iloc[-1]:.1f} % fade, "
    f"{resistance_growth_pct.iloc[-1]:.1f} % resistance growth)"
)
ax1.set_xlabel("Date")
lines1, labels1 = ax1.get_legend_handles_labels()
lines2, labels2 = ax2.get_legend_handles_labels()
ax1.legend(lines1 + lines2, labels1 + labels2, loc="upper left")
fig.tight_layout()
fig.savefig(HERE / "plot_degradation.png", dpi=150)
print("Saved plot_degradation.png")

# ---------------------------------------------------------------------------
# Plot 6: Losses and heat (daily mean)
# ---------------------------------------------------------------------------
fig, ax = plt.subplots(figsize=(12, 3))
df[["loss", "heat", "conv_loss"]].resample("1D").mean().plot(
    ax=ax, title="Battery losses, heat and converter losses -- daily mean [W]"
)
ax.set_ylabel("Power [W]")
fig.tight_layout()
fig.savefig(HERE / "plot_losses.png", dpi=150)
print("Saved plot_losses.png")
