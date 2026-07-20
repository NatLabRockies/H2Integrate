import math

import matplotlib


matplotlib.use("Agg")
from pathlib import Path

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from tqdm import tqdm


HERE = Path(__file__).parent

from simses.degradation import DegradationModel
from simses.battery.state import BatteryState
from simses.battery.battery import Battery
from simses.thermal.ambient import AmbientThermalModel
from simses.degradation.state import DegradationState
from simses.model.cell.sony_lfp import SonyLFP
from simses.degradation.cycle_detector import HalfCycle
from simses.model.degradation.sony_lfp_cyclic import (
    A_RINC,
    B_RINC,
    C_RINC as CYC_C_RINC,
    D_RINC as CYC_D_RINC,
    A_QLOSS,
    B_QLOSS,
    C_QLOSS as CYC_C_QLOSS,
    D_QLOSS as CYC_D_QLOSS,
    SonyLFPCyclicDegradation,
)
from simses.model.degradation.sony_lfp_calendar import (
    T_REF,
    C_RINC as CAL_C_RINC,
    D_RINC as CAL_D_RINC,
    C_QLOSS as CAL_C_QLOSS,
    D_QLOSS as CAL_D_QLOSS,
    EA_RINC,
    EA_QLOSS,
    K_REF_RINC,
    K_REF_QLOSS,
    R,
    SonyLFPCalendarDegradation,
)


# ---------------------------------------------------------------------------
# Large-format 280 Ah LFP cell
# ---------------------------------------------------------------------------


class LFP280Ah(SonyLFP):
    """280 Ah / 3.2 V prismatic LFP cell scaled from the SonyLFP OCV/resistance curves."""

    _SCALE = 3.0 / 280.0  # resistance scales inversely with capacity

    def __init__(self):
        super().__init__()
        self.electrical.nominal_capacity = 280.0  # Ah
        # Thermal properties for a large-format prismatic cell (vs. the 70 g 26650 reference).
        # mass=1.5 kg, h=23 W/m²K gives C_th≈6.5 MJ/K, R_th≈1.73 mK/W, τ≈3.1 h
        # → ΔT ≈ 10 °C at end of 2-hour C/2 discharge.
        self.thermal.mass = 3.0  # kg per cell
        self.thermal.convection_coefficient = 23.0  # W/m²K

    def internal_resistance(self, state):
        return super().internal_resistance(state) * self._SCALE


# ---------------------------------------------------------------------------
# Scaled degradation models targeting ~1-2 % capacity fade over 365 days.
# The Sony LFP parametrization is for a 3 Ah cylindrical cell; large-format
# prismatic LFP cells degrade roughly 5x slower per calendar/cycle unit.
# A uniform scale factor of 0.2 brings the total fade into the 1-2 % range.
# ---------------------------------------------------------------------------
_DEG_SCALE = 0.4


class ScaledLFPCalendarDegradation(SonyLFPCalendarDegradation):
    def update_capacity(self, state: BatteryState, dt: float, accumulated_qloss: float) -> float:
        if dt == 0.0:
            return 0.0
        T_K = state.T + 273.15
        T_REF_K = T_REF + 273.15
        k_T_q = (K_REF_QLOSS * _DEG_SCALE) * math.exp(-EA_QLOSS / R * (1.0 / T_K - 1.0 / T_REF_K))
        k_soc_q = CAL_C_QLOSS * (state.soc - 0.5) ** 3 + CAL_D_QLOSS
        stress_q = k_T_q * k_soc_q
        if stress_q > 0.0:
            virtual_time = (accumulated_qloss / stress_q) ** 2
            delta_q = stress_q * math.sqrt(virtual_time + dt) - accumulated_qloss
        else:
            delta_q = 0.0
        return delta_q

    def update_resistance(self, state: BatteryState, dt: float) -> float:
        if dt == 0.0:
            return 0.0
        T_K = state.T + 273.15
        T_REF_K = T_REF + 273.15
        k_T_r = (K_REF_RINC * _DEG_SCALE) * math.exp(-EA_RINC / R * (1.0 / T_K - 1.0 / T_REF_K))
        k_soc_r = CAL_C_RINC * (state.soc - 0.5) ** 2 + CAL_D_RINC
        return k_T_r * k_soc_r * dt


class ScaledLFPCyclicDegradation(SonyLFPCyclicDegradation):
    def update_capacity(
        self, state: BatteryState, half_cycle: HalfCycle, accumulated_qloss: float
    ) -> float:
        delta_fec = half_cycle.full_equivalent_cycles
        if delta_fec == 0.0:
            return 0.0
        k_crate_q = (A_QLOSS * _DEG_SCALE) * half_cycle.c_rate + (B_QLOSS * _DEG_SCALE)
        k_dod_q = CYC_C_QLOSS * (half_cycle.depth_of_discharge - 0.6) ** 3 + CYC_D_QLOSS
        stress_q = k_crate_q * k_dod_q
        if stress_q > 0.0:
            virtual_fec = (accumulated_qloss * 100.0 / stress_q) ** 2
            delta_q = stress_q * math.sqrt(virtual_fec + delta_fec) / 100.0 - accumulated_qloss
        else:
            delta_q = 0.0
        return delta_q

    def update_resistance(self, state: BatteryState, half_cycle: HalfCycle) -> float:
        delta_fec = half_cycle.full_equivalent_cycles
        if delta_fec == 0.0:
            return 0.0
        k_crate_r = (A_RINC * _DEG_SCALE) * half_cycle.c_rate + (B_RINC * _DEG_SCALE)
        k_dod_r = CYC_C_RINC * (half_cycle.depth_of_discharge - 0.5) ** 3 + CYC_D_RINC
        return k_crate_r * k_dod_r * delta_fec / 100.0


# ---------------------------------------------------------------------------
# Battery pack: 239s x 18p  ->  764.8 V * 5040 Ah  ~  3855 kWh
# ---------------------------------------------------------------------------
cell = LFP280Ah()

battery = Battery(
    cell=cell,
    circuit=(239, 18),
    initial_states={"start_soc": 1.0, "start_T": 25.0},
    degradation=DegradationModel(
        calendar=ScaledLFPCalendarDegradation(),
        cyclic=ScaledLFPCyclicDegradation(),
        initial_soc=1.0,
        initial_state=DegradationState(qloss_cal=1e-4),
    ),
)

summary = pd.Series(
    {
        "nominal_capacity [Ah]": battery.nominal_capacity,
        "nominal_voltage [V]": battery.nominal_voltage,
        "nominal_energy [kWh]": battery.nominal_energy_capacity / 1e3,
        "max_charge_current [A]": battery.max_charge_current,
        "max_discharge_current [A]": battery.max_discharge_current,
        "thermal_capacity [kJ/K]": battery.thermal_capacity / 1e3,
    }
)
print("Battery summary:")
print(summary.to_string())
print()

# ---------------------------------------------------------------------------
# 15-year power demand profile (dt = 15 min = 900 s)
#
# Each day (96 steps):
#   8  steps  discharge at C/2   (~-1.927 MW)
#   40 steps  charge    at C/10  (~+385 kW)
#   48 steps  rest       0 W
# ---------------------------------------------------------------------------
dt = 900.0
STEPS_PER_DAY = 96
N_YEARS = 15
N_DAYS = N_YEARS * 365
n_steps = N_DAYS * STEPS_PER_DAY

P_nom = battery.nominal_energy_capacity  # Wh
P_disch = -0.5 * P_nom  # C/2 discharge
P_chg = +0.1 * P_nom  # C/10 charge

day_profile = np.concatenate(
    [
        np.full(8, P_disch),
        np.full(40, P_chg),
        np.full(48, 0.0),
    ]
)
power_profile = np.tile(day_profile, N_DAYS)

print(f"Simulation: {N_YEARS} years ({N_DAYS} days), {n_steps:,} steps, dt={int(dt)} s")
print(f"Discharge: {P_disch/1e6:.3f} MW (C/2)")
print(f"Charge:    {P_chg/1e3:.1f} kW (C/10)")
print()

# ---------------------------------------------------------------------------
# Thermal model: constant 25 °C ambient, battery registered as thermal node
# ---------------------------------------------------------------------------
thermal = AmbientThermalModel(T_ambient=25.0, components=[battery])

# ---------------------------------------------------------------------------
# Simulation loop
# ---------------------------------------------------------------------------
keys = ["soc", "v", "i", "T", "loss", "heat", "soh_Q", "soh_R", "power"]
log = {k: np.empty(n_steps) for k in keys}

for i, p in enumerate(tqdm(power_profile, desc=f"Simulating {N_YEARS} years")):
    battery.step(float(p), dt)
    thermal.step(dt)  # update battery temperature after each step
    for k in keys:
        log[k][i] = getattr(battery.state, k)

index = pd.date_range("2026-01-01", periods=n_steps, freq=f"{int(dt)}s")
df = pd.DataFrame(log, index=index)

print("\nFirst rows:")
print(df.head().to_string())
print(
    f"\nFinal SOH_Q : {df['soh_Q'].iloc[-1]:.4f} \
          ({(1 - df['soh_Q'].iloc[-1]) * 100:.2f} % capacity fade)"
)
print(f"Final SOH_R : {df['soh_R'].iloc[-1]:.4f}")

# ---------------------------------------------------------------------------
# Plots
# ---------------------------------------------------------------------------

# Plot 1: Power demand (first 7 days)
fig, ax = plt.subplots(figsize=(12, 3))
df["power"].iloc[: 7 * STEPS_PER_DAY].plot(ax=ax)
ax.set_title("Power demand profile -- first 7 days")
ax.set_ylabel("Power [W]")
ax.axhline(0, color="gray", linewidth=0.5)
ax.yaxis.set_major_formatter(plt.FuncFormatter(lambda x, _: f"{x/1e6:.2f} MW"))
fig.tight_layout()
fig.savefig(HERE / "plot_power.png", dpi=150)
print("Saved plot_power.png")

# Plot 2: SOC (hourly mean)
fig, ax = plt.subplots(figsize=(12, 3))
df["soc"].resample("1h").mean().plot(ax=ax, title="State of Charge -- hourly mean")
ax.set_ylabel("SOC [p.u.]")
fig.tight_layout()
fig.savefig(HERE / "plot_soc.png", dpi=150)
print("Saved plot_soc.png")

# Plot 2b: Battery temperature -- first 7 days (15-min resolution)
fig, ax = plt.subplots(figsize=(12, 3))
df["T"].iloc[: 7 * STEPS_PER_DAY].plot(ax=ax, title="Battery temperature -- first 7 days")
ax.set_ylabel("Temperature [°C]")
ax.axhline(25.0, color="gray", linewidth=0.8, linestyle="--", label="T_ambient = 25 °C")
ax.legend()
fig.tight_layout()
fig.savefig(HERE / "plot_temperature_7days.png", dpi=150)
print("Saved plot_temperature_7days.png")

# Plot 3a: Terminal voltage -- first 7 days (raw 15-min data)
fig, ax = plt.subplots(figsize=(12, 3))
df["v"].iloc[: 7 * STEPS_PER_DAY].plot(ax=ax, title="Terminal voltage -- first 7 days [V]")
ax.set_ylabel("Voltage [V]")
fig.tight_layout()
fig.savefig(HERE / "plot_voltage_7days.png", dpi=150)
print("Saved plot_voltage_7days.png")

# Plot 3b: Terminal voltage (daily mean, full year)
fig, ax = plt.subplots(figsize=(12, 3))
df["v"].resample("1D").mean().plot(ax=ax, title="Terminal voltage -- daily mean [V]")
ax.set_ylabel("Voltage [V]")
fig.tight_layout()
fig.savefig(HERE / "plot_voltage.png", dpi=150)
print("Saved plot_voltage.png")

# Plot 4: Degradation over 15 years
df_monthly = df[["soh_Q", "soh_R"]].resample("ME").last()
capacity_fade_pct = (1 - df_monthly["soh_Q"]) * 100
resistance_growth_pct = (df_monthly["soh_R"] - 1) * 100

fig, ax1 = plt.subplots(figsize=(12, 4))
ax2 = ax1.twinx()

ax1.plot(
    capacity_fade_pct.index, capacity_fade_pct.values, color="steelblue", label="Capacity fade [%]"
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
ax1.set_title(
    f"Battery degradation over {N_YEARS} years  "
    f"(final: {capacity_fade_pct.iloc[-1]:.1f} % capacity fade, "
    f"{resistance_growth_pct.iloc[-1]:.1f} % resistance growth)"
)
ax1.set_xlabel("Date")

lines1, labels1 = ax1.get_legend_handles_labels()
lines2, labels2 = ax2.get_legend_handles_labels()
ax1.legend(lines1 + lines2, labels1 + labels2, loc="upper left")

# Mark end-of-life reference (20 % capacity fade)
ax1.axhline(20, color="steelblue", linewidth=0.8, linestyle="--", alpha=0.6, label="EoL (20 %)")

fig.tight_layout()
fig.savefig(HERE / "plot_degradation_15yr.png", dpi=150)
print("Saved plot_degradation_15yr.png")

# Plot 5: Losses and heat (daily mean)
fig, ax = plt.subplots(figsize=(12, 3))
df[["loss", "heat"]].resample("1D").mean().plot(
    ax=ax, title="Battery losses and heat -- daily mean [W]"
)
ax.set_ylabel("Power [W]")
fig.tight_layout()
fig.savefig(HERE / "plot_losses.png", dpi=150)
print("Saved plot_losses.png")
