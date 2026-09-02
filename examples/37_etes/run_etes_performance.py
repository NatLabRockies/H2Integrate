"""
Example showcasing the ETESPerformanceModel.

This example simulates one week (168 hours) of an Electric Thermal Energy
Storage (ETES) system serving a steady industrial thermal load. The
charging electricity profile mimics a renewables-heavy grid: ample, cheap
electricity at night and midday (solar/wind), with a deficit during the
evening peak. The script runs both P-ETES (decoupled) and R-ETES
(integrated) configurations and produces a plot of state-of-charge,
charging / discharging rates, and heat delivered vs. demand.

Run with the h2integrate conda environment:

    conda run -n h2integrate python run_etes_performance.py
"""

from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import openmdao.api as om

from h2integrate.storage.heat.etes import ETESPerformanceModel


# ---------------------------------------------------------------------------
# Scenario setup
# ---------------------------------------------------------------------------
N_HOURS = 168  # 1 week
DT_S = 3600    # 1-hour timestep
HEAT_LOAD_KW = 10_000.0  # steady 10 MW_th industrial load


def build_electricity_profile(n: int) -> np.ndarray:
    """Synthetic available-electricity profile (kW_e) with diurnal cycles.

    - High at night (cheap wind)
    - Peak around midday (solar)
    - Low during evening ramp (no sun, low wind)
    """
    t = np.arange(n)
    hour_of_day = t % 24
    # Solar bump (Gaussian around hour 13)
    solar = 60_000.0 * np.exp(-0.5 * ((hour_of_day - 13) / 3.5) ** 2)
    # Wind: noisy baseline with a dip in the evening (hours 17-21)
    rng = np.random.default_rng(42)
    wind = 25_000.0 + 5_000.0 * np.sin(t / 7.0) + rng.normal(0, 2_000.0, n)
    evening_dip = np.where((hour_of_day >= 17) & (hour_of_day <= 21), -15_000.0, 0.0)
    profile = np.clip(solar + wind + evening_dip, 0.0, None)
    return profile


# ---------------------------------------------------------------------------
# Model configurations (parameter values from MILP ETES doc)
# ---------------------------------------------------------------------------
PETES_PARAMS = {
    "etes_type": "P-ETES",
    "S_TES_kWh": 600_000.0,   # 600 MWh thermal storage
    "S_ch_kW":   100_000.0,   # 100 MW electric charging unit
    "S_dis_kW":   20_000.0,   # 20 MW thermal discharging unit
    "eta_ch":  0.95,          # ENDURING particle heater
    "eta_dis": 0.73,          # MPBHX
    "f_loss":  0.0068,        # per-hour fractional loss
    "SOC_min": 0.05,
    "SOC_init": 0.5,
    "cost_year": 2026,
}

RETES_PARAMS = {
    "etes_type": "R-ETES",
    "S_TES_kWh": 600_000.0,
    "eta_ch":  0.98,          # refractory heater
    "eta_dis": 0.90,
    "f_loss":  0.0068,
    "f_ch_max": 0.3,
    "f_dis_max": 0.2,
    "SOC_min": 0.05,
    "SOC_init": 0.5,
    "cost_year": 2026,
}


def run_etes(perf_params: dict, electricity_in_kW: np.ndarray, heat_demand_kW: np.ndarray):
    """Build an OpenMDAO problem, run the ETES performance model, return the
    populated problem instance."""
    plant_config = {
        "plant": {
            "simulation": {"n_timesteps": N_HOURS, "dt": DT_S},
        }
    }
    tech_config = {"model_inputs": {"performance_parameters": perf_params}}

    prob = om.Problem()
    prob.model.add_subsystem(
        "etes",
        ETESPerformanceModel(
            tech_config=tech_config,
            plant_config=plant_config,
            driver_config={},
        ),
        promotes=["*"],
    )
    prob.setup()
    prob.set_val("electricity_in_kW", electricity_in_kW)
    prob.set_val("heat_demand_kW", heat_demand_kW)
    prob.run_model()
    return prob


def summarize(label: str, prob: om.Problem):
    heat_out = prob.get_val("heat_out_kW", units="kW")
    unmet = prob.get_val("unmet_heat_demand_kW", units="kW")
    elec_used = prob.get_val("electricity_consumed_kW", units="kW")
    rte = float(prob.get_val("round_trip_efficiency")[0])
    total_delivered = float(prob.get_val("E_total_delivered_kWh", units="kW*h")[0])

    print(f"\n--- {label} ---")
    print(f"  Total heat delivered : {total_delivered/1e3:,.1f} MWh_th")
    print(f"  Total unmet demand   : {np.sum(unmet)/1e3:,.1f} MWh_th  "
          f"({np.sum(unmet) / np.sum(heat_out + unmet) * 100:.2f}% of demand)")
    print(f"  Total electricity in : {np.sum(elec_used)/1e3:,.1f} MWh_e")
    print(f"  Round-trip efficiency: {rte * 100:.1f}%")


def plot_results(electricity_in: np.ndarray, heat_demand: np.ndarray,
                 petes_prob: om.Problem, retes_prob: om.Problem,
                 outfile: Path):
    fig, axes = plt.subplots(4, 1, figsize=(12, 11), sharex=True)
    t = np.arange(N_HOURS)

    # 1. Available electricity
    axes[0].plot(t, electricity_in / 1e3, color="tab:blue")
    axes[0].set_ylabel("Available\nelectricity (MW_e)")
    axes[0].set_title("Scenario: 1-week renewables-heavy electricity supply, 10 MW_th steady load")
    axes[0].grid(True, alpha=0.3)

    # 2. SOC
    for label, prob, color in [
        ("P-ETES", petes_prob, "tab:orange"),
        ("R-ETES", retes_prob, "tab:green"),
    ]:
        E_st = prob.get_val("E_st_kWh", units="kW*h")
        S_TES = (PETES_PARAMS if label == "P-ETES" else RETES_PARAMS)["S_TES_kWh"]
        axes[1].plot(t, E_st / S_TES * 100, label=label, color=color)
    axes[1].set_ylabel("State of charge (%)")
    axes[1].legend(loc="upper right")
    axes[1].grid(True, alpha=0.3)
    axes[1].set_ylim(0, 105)

    # 3. Charging / discharging rates
    for label, prob, color in [
        ("P-ETES", petes_prob, "tab:orange"),
        ("R-ETES", retes_prob, "tab:green"),
    ]:
        Q_ch = prob.get_val("Q_ch_kW", units="kW")
        Q_dis = prob.get_val("Q_dis_kW", units="kW")
        axes[2].plot(t, Q_ch / 1e3, label=f"{label} charge", color=color, linestyle="-")
        axes[2].plot(t, -Q_dis / 1e3, label=f"{label} discharge", color=color, linestyle="--")
    axes[2].axhline(0, color="black", linewidth=0.5)
    axes[2].set_ylabel("Storage flow\n(MW_th, +charge / -discharge)")
    axes[2].legend(loc="upper right", ncol=2, fontsize=8)
    axes[2].grid(True, alpha=0.3)

    # 4. Heat delivered vs. demand
    axes[3].plot(t, heat_demand / 1e3, color="black", linewidth=2, label="Demand")
    for label, prob, color in [
        ("P-ETES", petes_prob, "tab:orange"),
        ("R-ETES", retes_prob, "tab:green"),
    ]:
        heat_out = prob.get_val("heat_out_kW", units="kW")
        axes[3].plot(t, heat_out / 1e3, label=f"{label} delivered",
                     color=color, linestyle="--", alpha=0.85)
    axes[3].set_ylabel("Thermal power (MW_th)")
    axes[3].set_xlabel("Time (h)")
    axes[3].legend(loc="lower right", fontsize=8)
    axes[3].grid(True, alpha=0.3)

    fig.tight_layout()
    fig.savefig(outfile, dpi=120)
    print(f"\nWrote plot: {outfile}")


def main():
    electricity_in = build_electricity_profile(N_HOURS)
    heat_demand = np.full(N_HOURS, HEAT_LOAD_KW)

    petes_prob = run_etes(PETES_PARAMS, electricity_in, heat_demand)
    retes_prob = run_etes(RETES_PARAMS, electricity_in, heat_demand)

    summarize("P-ETES (decoupled)", petes_prob)
    summarize("R-ETES (integrated)", retes_prob)

    out = Path(__file__).parent / "etes_performance_results.png"
    plot_results(electricity_in, heat_demand, petes_prob, retes_prob, out)


if __name__ == "__main__":
    main()
