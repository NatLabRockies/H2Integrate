import os
from pathlib import Path

import numpy as np
import matplotlib


# Use a non-interactive backend so the figures render when the script is run headless.
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch

from h2integrate import EXAMPLE_DIR
from h2integrate.core.h2integrate_model import H2IntegrateModel


# Technology fill colors keyed by control classification and arrow colors keyed by commodity.
# These are shared by the block diagrams so the same legend applies everywhere.
_CLASS_COLORS = {
    "flexible": "#4C9F70",
    "storage": "#F2C14E",
    "dispatchable": "#9AA0A6",
    "feedstock": "#6FA8DC",
    "combiner": "#D9D9D9",
    "splitter": "#CBD8EE",
    "demand": "#B39DDB",
}
_COMMODITY_COLORS = {
    "electricity": "#3B7DD8",
    "hydrogen": "#D8663B",
    "ammonia": "#7B4FA3",
    "nitrogen": "#4C9F70",
}


def _box(ax, xy, text, facecolor, width=12.0, height=8.0, fontsize=9, text_color="black"):
    """Draw a rounded technology box centered at ``xy`` and return its center."""
    x, y = xy
    patch = FancyBboxPatch(
        (x - width / 2, y - height / 2),
        width,
        height,
        boxstyle="round,pad=0.2,rounding_size=1.2",
        linewidth=1.3,
        edgecolor="#2F2F2F",
        facecolor=facecolor,
        zorder=3,
    )
    ax.add_patch(patch)
    ax.text(x, y, text, ha="center", va="center", fontsize=fontsize, color=text_color, zorder=5)
    return x, y


def _flow_arrow(ax, start, end, color, label=None, lw=2.2, rad=0.0, label_dy=1.6):
    """Draw a commodity flow arrow from ``start`` to ``end`` with an optional label."""
    ax.annotate(
        "",
        xy=end,
        xytext=start,
        arrowprops={
            "arrowstyle": "-|>",
            "color": color,
            "lw": lw,
            "shrinkA": 6,
            "shrinkB": 6,
            "connectionstyle": f"arc3,rad={rad}",
        },
        zorder=2,
    )
    if label:
        mx = (start[0] + end[0]) / 2
        my = (start[1] + end[1]) / 2 + label_dy
        ax.text(mx, my, label, ha="center", va="center", fontsize=7.5, color=color, zorder=6)


EXAMPLE_FOLDER = EXAMPLE_DIR / "35_system_level_control" / "heterogeneous_commodity"
os.chdir(EXAMPLE_FOLDER)

##################################
# Create an H2I model with an ammonia demand served by a heterogeneous commodity chain.
# The profit-maximizing system-level controller translates ammonia demand backward into
# hydrogen demand (across the synthesis loop) and then into electricity demand (across the
# electrolyzer). Wind and solar run whenever they are available; their combined generation
# charges the battery, which discharges to cover short deficits. There is no grid backup, so
# the ammonia demand is only met when wind, solar, and the battery can supply enough electricity.
h2i = H2IntegrateModel("heterogeneous_commodity.yaml")

h2i.setup()

# Run the model
h2i.run()

# Post-process the results
h2i.post_process()

# Plant-wide conversion read-out: upstream commodity required per kg/h of ammonia demand,
# summed across the electrolyzer and the Haber-Bosch loop's direct electricity draw.
# Hours where a converter produced nothing are excluded so the summary reflects operating hours.
trace = h2i.prob.model.plant.system_level_controller.dispatch_trace
measured_hours = (np.asarray(h2i.prob.get_val("haber_bosch.ammonia_out")).flatten() > 0.0) & (
    np.asarray(h2i.prob.get_val("electrolyzer.hydrogen_out")).flatten() > 0.0
)
demand_ratios = trace["demand_ratios"]
print(
    f"Over {measured_hours.sum()} operating hours: "
    f"{demand_ratios['electricity'][measured_hours].mean():.3f} kWh electricity and "
    f"{demand_ratios['hydrogen'][measured_hours].mean():.4f} kg hydrogen per kg ammonia"
)


##################################
# Plot the resulting dispatch, backward demand propagation, and the dynamic
# conversion ratios that the controller uses to translate demand across commodities.
def _get(name, units=None):
    """Return a flattened numpy array for a promoted model output."""
    return np.asarray(h2i.prob.get_val(name, units=units)).flatten()


def make_plots(figure_dir):
    figure_dir = Path(figure_dir)
    figure_dir.mkdir(parents=True, exist_ok=True)

    n_timesteps = h2i.prob.get_val("haber_bosch.ammonia_out", units="kg/h").size
    hours = np.arange(n_timesteps)

    # A representative week (7 days) chosen to show variable solar and battery dispatch.
    week_start = 3000
    week = slice(week_start, week_start + 168)
    week_hours = hours[week] - week_start

    # Electricity streams (MW).
    wind_mw = _get("wind.electricity_out", "MW")
    solar_mw = _get("solar.electricity_out", "MW")
    battery_mw = _get("battery.electricity_out", "MW")
    electrolyzer_load_mw = _get("electrolyzer.electricity_consumed", "MW")
    haber_bosch_load_mw = _get("haber_bosch.electricity_consumed", "MW")

    # Splitter streams (MW): the combined bus feeds a literal splitter whose
    # priority output (out1) supplies the electrolyzer and whose second output
    # (out2) supplies the Haber-Bosch loop. The controller sets the prescribed priority
    # allocation each hour from the two consumers' backpropagated demand.
    bus_mw = _get("elec_combiner.electricity_out", "MW")
    split_out1_mw = _get("electricity_splitter.electricity_out1", "MW")
    split_out2_mw = _get("electricity_splitter.electricity_out2", "MW")
    prescribed_mw = _get("system_level_controller.electricity_splitter_electricity_set_point", "MW")

    # Hydrogen streams (kg/h).
    h2_produced = _get("electrolyzer.hydrogen_out", "kg/h")
    h2_to_haber_bosch = _get("haber_bosch.hydrogen_consumed", "kg/h")

    # Ammonia streams (kg/h).
    ammonia_out = _get("haber_bosch.ammonia_out", "kg/h")
    ammonia_demand = _get("ammonia_load_demand.ammonia_demand", "kg/h")

    # Battery state of charge (fraction of capacity).
    battery_soc = _get("battery.SOC", "unitless")

    # Controller set point that shows backward propagation of demand.
    _get("system_level_controller.electrolyzer_hydrogen_set_point", "kg/h")
    total_electricity_load_mw = electrolyzer_load_mw + haber_bosch_load_mw

    # Hourly measured conversion ratios; the controller uses their production-weighted aggregate.
    electrolyzer_load_kw = _get("electrolyzer.electricity_consumed", "kW")
    haber_bosch_load_kw = _get("haber_bosch.electricity_consumed", "kW")
    with np.errstate(divide="ignore", invalid="ignore"):
        electricity_per_hydrogen = np.where(
            h2_produced > 1e-6, electrolyzer_load_kw / h2_produced, np.nan
        )
        hydrogen_per_ammonia = np.where(ammonia_out > 1e-6, h2_to_haber_bosch / ammonia_out, np.nan)
        electricity_per_ammonia = np.where(
            ammonia_out > 1e-6, haber_bosch_load_kw / ammonia_out, np.nan
        )

    # -----------------------------------------------------------------
    # Figure 1: the commodity cascade over a representative week.
    # Electricity (wind + solar + battery) drives hydrogen, which drives ammonia.
    # -----------------------------------------------------------------
    fig, axes = plt.subplots(3, 1, figsize=(10, 9), sharex=True)

    axes[0].stackplot(
        week_hours,
        wind_mw[week],
        solar_mw[week],
        np.clip(battery_mw[week], 0.0, None),
        labels=["Wind", "Solar PV", "Battery discharge"],
        colors=["#4C9F70", "#EF8A17", "#F2C14E"],
    )
    axes[0].plot(
        week_hours,
        total_electricity_load_mw[week],
        color="black",
        lw=1.5,
        label="Electrolyzer + Haber-Bosch load",
    )
    axes[0].set_ylabel("Electricity (MW)")
    axes[0].set_title(
        "Electricity supply: wind and solar prioritized, battery smooths short deficits"
    )
    axes[0].legend(loc="upper right", ncol=3, fontsize=8)

    axes[1].plot(week_hours, h2_produced[week], color="#3B7DD8", label="Electrolyzer output")
    axes[1].plot(
        week_hours,
        h2_to_haber_bosch[week],
        color="#D8663B",
        ls="--",
        label="Haber-Bosch consumption",
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

    # Measured (dynamic) conversion ratios the controller actually used, averaged over the
    # year. These feed the block diagram and conversion-ratio-chain figures below.
    m_elec_per_h2 = float(np.nanmean(electricity_per_hydrogen))
    m_h2_per_nh3 = float(np.nanmean(hydrogen_per_ammonia))
    m_elec_per_nh3 = float(np.nanmean(electricity_per_ammonia))

    # -----------------------------------------------------------------
    # Figure 2: how the conversion ratios multiply along the chain to set
    # the electricity intensity of one kilogram of ammonia, using the measured
    # yearly-mean ratios the controller actually used.
    # -----------------------------------------------------------------
    elec_via_electrolysis = m_h2_per_nh3 * m_elec_per_h2  # kWh electricity per kg NH3 through H2
    total_elec_per_nh3 = elec_via_electrolysis + m_elec_per_nh3

    fig, (ax_chain, ax_bar) = plt.subplots(
        2, 1, figsize=(12, 8), gridspec_kw={"height_ratios": [3, 1]}
    )
    ax_chain.set_xlim(0, 100)
    ax_chain.set_ylim(0, 100)
    ax_chain.axis("off")

    _box(
        ax_chain,
        (12, 60),
        "1 kg\nammonia",
        _CLASS_COLORS["demand"],
        width=14,
        height=16,
        fontsize=10,
    )
    _box(ax_chain, (45, 78), f"{m_h2_per_nh3:0.3f} kg\nhydrogen", "#FBE3D6", width=15, height=15)
    _box(
        ax_chain,
        (80, 78),
        f"{elec_via_electrolysis:0.2f} kWh\n(electrolysis)",
        "#DCE8F8",
        width=17,
        height=15,
    )
    _box(
        ax_chain,
        (80, 40),
        f"{m_elec_per_nh3:0.3f} kWh\n(Haber-Bosch direct)",
        "#DCE8F8",
        width=17,
        height=15,
    )

    _flow_arrow(
        ax_chain,
        (19, 64),
        (37.5, 78),
        _COMMODITY_COLORS["hydrogen"],
        label=f"x {m_h2_per_nh3:0.3f}\n(H2 per NH3)",
        label_dy=3.5,
    )
    _flow_arrow(
        ax_chain,
        (52.5, 78),
        (71.5, 78),
        _COMMODITY_COLORS["electricity"],
        label=f"x {m_elec_per_h2:0.1f}\n(elec per H2)",
        label_dy=3.5,
    )
    _flow_arrow(
        ax_chain,
        (19, 56),
        (71.5, 40),
        _COMMODITY_COLORS["electricity"],
        rad=0.1,
        label=f"x {m_elec_per_nh3:0.3f}  (direct elec per NH3)",
        label_dy=-3.5,
    )

    ax_chain.text(
        50,
        10,
        f"Total electricity intensity = {elec_via_electrolysis:0.2f} + {m_elec_per_nh3:0.3f}"
        f" = {total_elec_per_nh3:0.2f} kWh per kg NH3",
        ha="center",
        va="center",
        fontsize=9.5,
    )
    ax_chain.set_title(
        "Conversion ratios multiply along the chain: NH3 -> H2 -> electricity", fontsize=12
    )

    ax_bar.barh(
        [0],
        [elec_via_electrolysis],
        color=_COMMODITY_COLORS["electricity"],
        label="via electrolysis",
    )
    ax_bar.barh(
        [0],
        [m_elec_per_nh3],
        left=[elec_via_electrolysis],
        color="#9AA0A6",
        label="Haber-Bosch direct",
    )
    ax_bar.set_yticks([])
    ax_bar.set_xlabel("Electricity per kg ammonia (kWh/kg)")
    ax_bar.legend(loc="lower right", fontsize=8, ncol=2)
    ax_bar.set_xlim(0, total_elec_per_nh3 * 1.15)
    ax_bar.text(
        total_elec_per_nh3, 0, f"  {total_elec_per_nh3:0.2f} kWh/kg", va="center", fontsize=9
    )

    fig.tight_layout()
    fig.savefig(figure_dir / "conversion_ratio_chain.png", dpi=150)
    plt.close(fig)

    # -----------------------------------------------------------------
    # Figure 3: hourly time histories of the commodity signals that pass
    # between components over a representative week. The top panels show how
    # the literal electricity splitter divides the combined bus: the priority
    # output (out1) tracks the electrolyzer's demand while the second output
    # (out2) carries the remainder to the Haber-Bosch loop, so both loads are served
    # from a single physical stream. The lower panels follow the hydrogen and
    # ammonia signals along the rest of the chain, and the final panel shows the
    # battery state of charge over the same week.
    # -----------------------------------------------------------------
    fig, axes = plt.subplots(5, 1, figsize=(10, 14), sharex=True)

    # Panel 1: the split of the combined electricity bus at the splitter.
    axes[0].stackplot(
        week_hours,
        split_out1_mw[week],
        split_out2_mw[week],
        labels=["out1 -> electrolyzer", "out2 -> Haber-Bosch"],
        colors=["#3B7DD8", "#9AC4F0"],
    )
    axes[0].plot(
        week_hours, bus_mw[week], color="black", lw=1.4, label="combined bus (combiner out)"
    )
    axes[0].plot(
        week_hours,
        prescribed_mw[week],
        color="#D8663B",
        lw=1.2,
        ls=":",
        label="controller prescribed priority allocation",
    )
    axes[0].set_ylabel("Electricity (MW)")
    axes[0].set_title("Electricity splitter: controller divides the combined bus between two loads")
    axes[0].legend(loc="upper right", ncol=2, fontsize=8)

    # Panel 2: each split output vs the load it serves (no starvation of either).
    axes[1].plot(week_hours, split_out1_mw[week], color="#3B7DD8", lw=1.4, label="out1 (priority)")
    axes[1].plot(
        week_hours,
        electrolyzer_load_mw[week],
        color="#1F3F66",
        ls="--",
        lw=1.2,
        label="electrolyzer consumed",
    )
    axes[1].plot(week_hours, split_out2_mw[week], color="#9AC4F0", lw=1.4, label="out2")
    axes[1].plot(
        week_hours,
        haber_bosch_load_mw[week],
        color="#7B4FA3",
        ls="--",
        lw=1.2,
        label="Haber-Bosch consumed",
    )
    axes[1].set_ylabel("Electricity (MW)")
    axes[1].set_title("Split allocations track each consumer's load")
    axes[1].legend(loc="upper right", ncol=2, fontsize=8)

    # Panel 3: hydrogen signals between the electrolyzer and the Haber-Bosch loop.
    axes[2].plot(week_hours, h2_produced[week], color="#D8663B", lw=1.4, label="electrolyzer out")
    axes[2].plot(
        week_hours,
        h2_to_haber_bosch[week],
        color="black",
        ls=":",
        lw=1.2,
        label="Haber-Bosch consumed",
    )
    axes[2].set_ylabel("Hydrogen (kg/h)")
    axes[2].set_title("Hydrogen: electrolyzer output feeds the ammonia synthesis loop")
    axes[2].legend(loc="upper right", ncol=2, fontsize=8)

    # Panel 4: the ammonia product signal that drives the whole chain.
    axes[3].plot(week_hours, ammonia_out[week], color="#7B4FA3", lw=1.4, label="ammonia production")
    axes[3].plot(
        week_hours, ammonia_demand[week], color="black", ls="--", lw=1.2, label="ammonia demand"
    )
    axes[3].set_ylabel("Ammonia (kg/h)")
    axes[3].set_title("Ammonia production tracks the demand that drives the chain")
    axes[3].legend(loc="lower right", fontsize=8)

    # Panel 5: battery state of charge over the week.
    axes[4].plot(
        week_hours, battery_soc[week] * 100.0, color="#F2C14E", lw=1.4, label="battery SOC"
    )
    axes[4].set_ylabel("State of charge (%)")
    axes[4].set_ylim(0, 100)
    axes[4].set_xlabel("Hour of representative week")
    axes[4].set_title("Battery state of charge")
    axes[4].legend(loc="upper right", fontsize=8)

    fig.suptitle("Hourly commodity signals between components (representative week)", y=0.997)
    fig.tight_layout()
    fig.savefig(figure_dir / "commodity_time_histories.png", dpi=150)
    plt.close(fig)

    return figure_dir


figures = make_plots(EXAMPLE_FOLDER / "outputs")
print(
    "Saved dispatch, block-diagram, conversion-ratio, and commodity time-history "
    f"figures to {figures}"
)
