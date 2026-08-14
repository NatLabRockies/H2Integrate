"""
Example 98: Battery degradation through the standard H2Integrate interface.

This example reproduces the SimSES battery-degradation reference study using the standard
``H2IntegrateModel`` interface (YAML-configured plant/tech/driver). The battery has no
control strategy, so a passthrough controller forwards the ``electricity_set_point``
profile to the battery as its dispatch command (positive = discharge, negative = charge).

A repeating daily charge/discharge cycle is applied for the full simulation horizon and
the battery internal timeseries (voltage, temperature, state-of-health, losses) are read
from the battery component's OpenMDAO outputs (via ``model.prob.get_val``) to produce the
reference plots:

  1. AC and DC power (first 7 days)
  2. State of charge (hourly mean)
  3. Battery temperature (first 7 days)
  4. Terminal voltage (first 7 days and daily mean)
  5. Capacity fade and resistance growth over the horizon
  6. Battery/converter losses and heat (daily mean)

Matching the partner reference, this runs a 15-year degradation study at 15-minute
resolution (``n_timesteps = 525600``, ``dt = 900`` s in ``plant_config.yaml``). The
horizon is fully configurable: ``n_timesteps * dt`` may cover any positive duration up to
the plant life. The battery pack topology and degradation scaling live in
``tech_config.yaml``.
"""

from pathlib import Path

import numpy as np
import pandas as pd
import matplotlib


matplotlib.use("Agg")
import matplotlib.pyplot as plt

from h2integrate import H2IntegrateModel


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
# Retrieve the battery internal timeseries and assemble a DataFrame.
# Each SimSES timeseries is exposed as an OpenMDAO output of the battery
# component and is read through the standard H2Integrate ``get_val`` interface
# (outputs are promoted to the "battery" tech group), so the model class does
# not need to be imported into this script.
# ---------------------------------------------------------------------------
index = pd.date_range("2026-01-01", periods=n_steps, freq=f"{int(dt)}s")
df = pd.DataFrame(
    {
        "soc": model.prob.get_val("battery.SOC", units="unitless"),
        "v": model.prob.get_val("battery.voltage", units="V"),
        "T": model.prob.get_val("battery.temperature", units="degC"),
        "loss": model.prob.get_val("battery.battery_loss", units="W"),
        "heat": model.prob.get_val("battery.battery_heat", units="W"),
        "soh_Q": model.prob.get_val("battery.soh_capacity"),
        "soh_R": model.prob.get_val("battery.soh_resistance"),
        "power_ac": model.prob.get_val("battery.power_ac", units="W"),
        "power_dc": model.prob.get_val("battery.power_dc", units="W"),
        "conv_loss": model.prob.get_val("battery.converter_loss", units="W"),
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

# ---------------------------------------------------------------------------
# Finance results (ProFAST LCOE).
# The battery's per-year, degradation-aware capacity factor feeds ProFAST's
# multi-year cash-flow analysis over the full 30-year plant life. When the
# simulated capacity SOH reaches the end-of-life threshold (``eol_soh_capacity``
# in tech_config.yaml), the battery is replaced and the capacity-factor cycle
# repeats from a fresh unit; each replacement is charged as new CapEx in ProFAST.
# ---------------------------------------------------------------------------
lcoe = model.prob.get_val("finance_subgroup_battery.LCOE", units="USD/(MW*h)")[0]
capacity_factor_by_year = model.prob.get_val("battery.capacity_factor")
replacement_schedule = model.prob.get_val("battery.replacement_schedule")
replacement_years = [int(y) for y in np.flatnonzero(replacement_schedule) + 1]
print(f"LCOE (levelized cost of storage): {lcoe:.2f} $/MWh")
print(
    "Discharge capacity factor - year 1: "
    f"{capacity_factor_by_year[0] * 100:.2f} %, "
    f"year 15: {capacity_factor_by_year[14] * 100:.2f} %, "
    f"year 30: {capacity_factor_by_year[29] * 100:.2f} %"
)
if replacement_years:
    print(f"Battery reaches EOL SOH and is replaced in plant year(s): {replacement_years}")
else:
    print("Battery does not reach EOL SOH within the plant life (no replacement scheduled).")

# ---------------------------------------------------------------------------
# Plot 7: Per-year capacity factor used by the finance model (ProFAST)
# This is the exact per-year capacity factor fed to ProFAST: actual values over
# the simulated years, scaled with the projected SOH beyond the simulation, and
# reset to a fresh battery at each end-of-life replacement.
# ---------------------------------------------------------------------------
plant_years = np.arange(1, len(capacity_factor_by_year) + 1)
fig, ax = plt.subplots(figsize=(12, 3))
ax.step(plant_years, capacity_factor_by_year * 100, where="mid", color="teal")
for i, yr in enumerate(replacement_years):
    ax.axvline(
        yr,
        color="firebrick",
        linestyle="--",
        linewidth=0.8,
        label="Battery replacement" if i == 0 else None,
    )
ax.set_title("Per-year discharge capacity factor used by ProFAST")
ax.set_xlabel("Plant year")
ax.set_ylabel("Capacity factor [%]")
ax.set_xlim(1, len(capacity_factor_by_year))
if replacement_years:
    ax.legend(loc="lower left")
fig.tight_layout()
fig.savefig(HERE / "plot_capacity_factor.png", dpi=150)
print("Saved plot_capacity_factor.png")

# ---------------------------------------------------------------------------
# Plot 8: State of health over the full simulation
# ---------------------------------------------------------------------------
perf_params = model.technology_config["technologies"]["battery"]["model_inputs"][
    "performance_parameters"
]
eol_soh = float(perf_params.get("eol_soh_capacity", 0.8))

fig, ax1 = plt.subplots(figsize=(12, 3))
ax2 = ax1.twinx()
ax1.plot(df.index, df["soh_Q"] * 100, color="steelblue", label="Capacity SOH [%]")
ax2.plot(df.index, df["soh_R"], color="darkorange", label="Resistance SOH [x nominal]")
ax1.axhline(
    eol_soh * 100,
    color="firebrick",
    linestyle="--",
    linewidth=0.8,
    label=f"EOL SOH = {eol_soh * 100:.0f} %",
)
ax1.set_ylabel("Capacity SOH [%]", color="steelblue")
ax2.set_ylabel("Resistance SOH [x nominal]", color="darkorange")
ax1.tick_params(axis="y", labelcolor="steelblue")
ax2.tick_params(axis="y", labelcolor="darkorange")
ax1.set_xlabel("Date")
ax1.set_title("Battery state of health over the full simulation")
lines1, labels1 = ax1.get_legend_handles_labels()
lines2, labels2 = ax2.get_legend_handles_labels()
ax1.legend(lines1 + lines2, labels1 + labels2, loc="lower left")
fig.tight_layout()
fig.savefig(HERE / "plot_soh.png", dpi=150)
print("Saved plot_soh.png")
