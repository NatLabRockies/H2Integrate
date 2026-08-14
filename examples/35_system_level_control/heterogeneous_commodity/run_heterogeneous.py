import os
from pathlib import Path

import numpy as np
import matplotlib


# Use a non-interactive backend so the figures render when the script is run headless.
matplotlib.use("Agg")
import matplotlib.pyplot as plt

from h2integrate import EXAMPLE_DIR
from h2integrate.core.h2integrate_model import H2IntegrateModel


EXAMPLE_FOLDER = EXAMPLE_DIR / "35_system_level_control" / "heterogeneous_commodity"
os.chdir(EXAMPLE_FOLDER)

##################################
# Create an H2I model with an ammonia demand served by a heterogeneous commodity chain.
# The profit-maximizing system-level controller translates ammonia demand backward into
# hydrogen demand (across the synthesis loop) and then into electricity demand (across the
# electrolyzer). Wind runs whenever it is available, the battery charges on wind surplus and
# discharges to cover short deficits, and the grid is only dispatched to backfill the
# electricity that wind and the battery cannot supply.
h2i = H2IntegrateModel("heterogeneous_commodity.yaml")

h2i.setup()

# Run the model
h2i.run()

# Post-process the results
h2i.post_process()


##################################
# Plot the resulting dispatch, backward demand propagation, and the dynamic
# conversion ratios that the controller uses to translate demand across commodities.
def _get(name, units=None):
    """Return a flattened numpy array for a promoted model output."""
    return np.asarray(h2i.prob.get_val(name, units=units)).flatten()


def make_plots(figure_dir):
    figure_dir = Path(figure_dir)
    figure_dir.mkdir(parents=True, exist_ok=True)

    n_timesteps = h2i.prob.get_val("ammonia.ammonia_out", units="kg/h").size
    hours = np.arange(n_timesteps)

    # A representative week (7 days) chosen to show variable wind and grid backup.
    week_start = 3000
    week = slice(week_start, week_start + 168)
    week_hours = hours[week] - week_start

    # Electricity streams (MW).
    wind_mw = _get("wind.electricity_out", "MW")
    grid_mw = _get("grid.electricity_out", "MW")
    battery_mw = _get("battery.electricity_out", "MW")
    electrolyzer_load_mw = _get("electrolyzer.electricity_consumed", "MW")
    synloop_load_mw = _get("ammonia.electricity_consumed", "MW")

    # Hydrogen streams (kg/h).
    h2_produced = _get("electrolyzer.hydrogen_out", "kg/h")
    h2_to_synloop = _get("ammonia.hydrogen_consumed", "kg/h")

    # Ammonia streams (kg/h).
    ammonia_out = _get("ammonia.ammonia_out", "kg/h")
    ammonia_demand = _get("ammonia_load_demand.ammonia_demand_out", "kg/h")

    # Controller set points that show backward propagation of demand.
    ammonia_set_point = _get("system_level_controller.ammonia_ammonia_set_point", "kg/h")
    hydrogen_set_point = _get("system_level_controller.electrolyzer_hydrogen_set_point", "kg/h")
    total_electricity_load_mw = electrolyzer_load_mw + synloop_load_mw

    # Measured (dynamic) conversion ratios the controller derives per timestep.
    electrolyzer_load_kw = _get("electrolyzer.electricity_consumed", "kW")
    synloop_load_kw = _get("ammonia.electricity_consumed", "kW")
    with np.errstate(divide="ignore", invalid="ignore"):
        electricity_per_hydrogen = np.where(
            h2_produced > 1e-6, electrolyzer_load_kw / h2_produced, np.nan
        )
        hydrogen_per_ammonia = np.where(ammonia_out > 1e-6, h2_to_synloop / ammonia_out, np.nan)
        electricity_per_ammonia = np.where(
            ammonia_out > 1e-6, synloop_load_kw / ammonia_out, np.nan
        )

    # -----------------------------------------------------------------
    # Figure 1: the commodity cascade over a representative week.
    # Electricity (wind + grid) drives hydrogen, which drives ammonia.
    # -----------------------------------------------------------------
    fig, axes = plt.subplots(3, 1, figsize=(10, 9), sharex=True)

    axes[0].stackplot(
        week_hours,
        wind_mw[week],
        np.clip(battery_mw[week], 0.0, None),
        grid_mw[week],
        labels=["Wind", "Battery discharge", "Grid (firm)"],
        colors=["#4C9F70", "#F2C14E", "#8C8C8C"],
    )
    axes[0].plot(
        week_hours,
        total_electricity_load_mw[week],
        color="black",
        lw=1.5,
        label="Electrolyzer + synloop load",
    )
    axes[0].set_ylabel("Electricity (MW)")
    axes[0].set_title("Electricity supply: wind prioritized, grid provides firm backup")
    axes[0].legend(loc="upper right", ncol=2, fontsize=8)

    axes[1].plot(week_hours, h2_produced[week], color="#3B7DD8", label="Electrolyzer output")
    axes[1].plot(
        week_hours, h2_to_synloop[week], color="#D8663B", ls="--", label="Synloop consumption"
    )
    axes[1].set_ylabel("Hydrogen (kg/h)")
    axes[1].set_title("Hydrogen: electrolyzer output feeds the ammonia synthesis loop")
    axes[1].legend(loc="upper right", fontsize=8)

    axes[2].plot(week_hours, ammonia_out[week], color="#7B4FA3", label="Ammonia production")
    axes[2].plot(week_hours, ammonia_demand[week], color="black", ls="--", label="Ammonia demand")
    axes[2].set_ylabel("Ammonia (kg/h)")
    axes[2].set_xlabel("Hour of representative week")
    axes[2].set_title("Ammonia: production tracks the demand that drives the whole chain")
    axes[2].legend(loc="lower right", fontsize=8)

    fig.suptitle("Heterogeneous-commodity dispatch: electricity -> hydrogen -> ammonia", y=0.995)
    fig.tight_layout()
    fig.savefig(figure_dir / "dispatch_cascade.png", dpi=150)
    plt.close(fig)

    # -----------------------------------------------------------------
    # Figure 2: backward demand propagation. A firm ammonia demand is
    # translated into a firm hydrogen demand and then a firm electricity
    # load. The demands are near-constant, so we show their magnitudes and
    # annotate the conversion ratios that connect them.
    # -----------------------------------------------------------------
    fig, ax_left = plt.subplots(figsize=(10, 5))
    ax_left.plot(
        week_hours, ammonia_set_point[week], color="#7B4FA3", label="Ammonia set point (kg/h)"
    )
    ax_left.plot(
        week_hours, hydrogen_set_point[week], color="#D8663B", label="Hydrogen set point (kg/h)"
    )
    ax_left.set_xlabel("Hour of representative week")
    ax_left.set_ylabel("Commodity set point (kg/h)")
    ax_left.set_ylim(0.0, 1.15 * float(ammonia_set_point[week].max()))

    ax_right = ax_left.twinx()
    ax_right.plot(
        week_hours,
        total_electricity_load_mw[week],
        color="#3B7DD8",
        ls="--",
        label="Derived electricity load (MW)",
    )
    ax_right.set_ylabel("Electricity load (MW)")
    ax_right.set_ylim(0.0, 1.15 * float(total_electricity_load_mw[week].max()))

    # Annotate the conversion ratios that link the three firm demand levels.
    mean_hydrogen_per_ammonia = float(np.nanmean(hydrogen_per_ammonia))
    mean_electricity_per_ammonia_mw = float(total_electricity_load_mw.mean() / ammonia_out.mean())
    ax_left.annotate(
        f"x {mean_hydrogen_per_ammonia:0.3f} kg H2 / kg NH3",
        xy=(0.5, 0.62),
        xycoords="axes fraction",
        color="#D8663B",
        fontsize=9,
        ha="center",
    )
    ax_left.annotate(
        f"x {mean_electricity_per_ammonia_mw * 1000:0.2f} kWh / kg NH3 (total)",
        xy=(0.5, 0.12),
        xycoords="axes fraction",
        color="#3B7DD8",
        fontsize=9,
        ha="center",
    )

    lines_left, labels_left = ax_left.get_legend_handles_labels()
    lines_right, labels_right = ax_right.get_legend_handles_labels()
    ax_left.legend(
        lines_left + lines_right, labels_left + labels_right, loc="center right", fontsize=8
    )
    ax_left.set_title("Backward demand propagation: ammonia -> hydrogen -> electricity")
    fig.tight_layout()
    fig.savefig(figure_dir / "demand_propagation.png", dpi=150)
    plt.close(fig)

    # -----------------------------------------------------------------
    # Figure 3: dynamic conversion ratios across the year. The controller
    # prefers these measured ratios over the static seed values. The
    # electrolyzer ratio drifts up as the stack degrades over the year.
    # -----------------------------------------------------------------
    fig, axes = plt.subplots(3, 1, figsize=(10, 9), sharex=True)

    axes[0].plot(hours, electricity_per_hydrogen, color="#3B7DD8", lw=0.8)
    # axes[0].axhline(51.0, color="black", ls=":", lw=1.0, label="Static seed (51 kWh/kg)")
    axes[0].set_ylabel("kWh / kg H2")
    axes[0].set_title(
        "Electrolyzer measured ratio (electricity per hydrogen) drifts up with degradation"
    )
    axes[0].legend(loc="upper left", fontsize=8)

    axes[1].plot(hours, hydrogen_per_ammonia, color="#D8663B", lw=0.8)
    axes[1].axhline(0.2, color="black", ls=":", lw=1.0, label="Static seed (0.2 kg/kg)")
    axes[1].set_ylabel("kg H2 / kg NH3")
    axes[1].set_title("Synloop measured ratio (hydrogen per ammonia)")
    axes[1].legend(loc="upper left", fontsize=8)

    axes[2].plot(hours, electricity_per_ammonia, color="#7B4FA3", lw=0.8)
    axes[2].axhline(0.530645243, color="black", ls=":", lw=1.0, label="Static seed (0.53 kWh/kg)")
    axes[2].set_ylabel("kWh / kg NH3")
    axes[2].set_xlabel("Hour of year")
    axes[2].set_title("Synloop measured ratio (electricity per ammonia)")
    axes[2].legend(loc="upper left", fontsize=8)

    fig.suptitle("Dynamic conversion ratios used to translate demand across converters", y=0.995)
    fig.tight_layout()
    fig.savefig(figure_dir / "conversion_ratios.png", dpi=150)
    plt.close(fig)

    # -----------------------------------------------------------------
    # Figure 4: annual electricity source mix and the resulting LCOA.
    # -----------------------------------------------------------------
    wind_energy = wind_mw.sum()
    grid_energy = grid_mw.sum()
    battery_energy = np.clip(battery_mw, 0.0, None).sum()
    lcoa = float(h2i.prob.get_val("finance_subgroup_ammonia.LCOA", units="USD/kg")[0])

    fig, ax = plt.subplots(figsize=(6, 6))
    ax.pie(
        [wind_energy, battery_energy, grid_energy],
        labels=["Wind", "Battery", "Grid (firm)"],
        colors=["#4C9F70", "#F2C14E", "#8C8C8C"],
        autopct="%1.1f%%",
        startangle=90,
    )
    ax.set_title(
        f"Annual electricity supplied to the chain\nAmmonia LCOA = ${lcoa:0.2f}/kg", fontsize=11
    )
    fig.tight_layout()
    fig.savefig(figure_dir / "electricity_source_mix.png", dpi=150)
    plt.close(fig)

    return figure_dir


figures = make_plots(EXAMPLE_FOLDER / "outputs")
print(f"Saved dispatch and conversion-ratio figures to {figures}")
