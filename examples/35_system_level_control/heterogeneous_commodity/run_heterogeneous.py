import os
from pathlib import Path

import yaml
import numpy as np
import matplotlib


# Use a non-interactive backend so the figures render when the script is run headless.
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Patch, FancyBboxPatch

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
    _get("system_level_controller.ammonia_ammonia_set_point", "kg/h")
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
    # Figure 2: dynamic conversion ratios across the year. The controller
    # prefers these measured ratios over the static seed values. The
    # electrolyzer ratio drifts up as the stack degrades over the year.
    # -----------------------------------------------------------------
    fig, axes = plt.subplots(3, 1, figsize=(10, 9), sharex=True)

    axes[0].plot(hours, electricity_per_hydrogen, color="#3B7DD8", lw=0.8)
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
    # Figure 3: system block diagram. Technologies are colored by their
    # control classification, arrows show the commodity flows, and the two
    # converters (electrolyzer and ammonia synloop) carry the conversion
    # ratios that the controller multiplies to propagate demand upstream.
    # -----------------------------------------------------------------
    # The static seed ratios now live in plant_config under
    # system_level_control -> control_parameters -> conversion_parameters,
    # so read them straight from there to keep the diagram in sync with the config.
    with Path("plant_config.yaml").open() as f:
        plant_cfg = yaml.safe_load(f)
    conv = plant_cfg["system_level_control"]["control_parameters"]["conversion_parameters"]
    seed_elec_per_h2 = float(conv["electrolyzer"]["electricity_per_hydrogen"])
    seed_h2_per_nh3 = float(conv["ammonia"]["hydrogen_per_ammonia"])
    seed_elec_per_nh3 = float(conv["ammonia"]["electricity_per_ammonia"])

    # Measured (dynamic) ratios that the controller actually used, averaged over the year.
    m_elec_per_h2 = float(np.nanmean(electricity_per_hydrogen))
    m_h2_per_nh3 = float(np.nanmean(hydrogen_per_ammonia))
    m_elec_per_nh3 = float(np.nanmean(electricity_per_ammonia))

    # Representative demand magnitudes used to annotate the propagation band.
    nh3_rate = float(ammonia_demand.mean())
    h2_rate = float(hydrogen_set_point.mean())
    electrolyzer_rate_mw = float(electrolyzer_load_mw.mean())
    synloop_rate_mw = float(synloop_load_mw.mean())

    fig, ax = plt.subplots(figsize=(16, 9))
    ax.set_xlim(0, 100)
    ax.set_ylim(0, 100)
    ax.axis("off")

    color_class = _CLASS_COLORS
    color_flow = _COMMODITY_COLORS

    # Technology boxes, laid out left to right along the forward commodity flow.
    _box(ax, (9, 86), "Wind\n(flexible)\n120 MW", color_class["flexible"])
    _box(ax, (9, 68), "Battery\n(storage)\n10 MW / 40 MWh", color_class["storage"])
    _box(ax, (9, 50), "Grid\n(dispatchable)\n50 MW", color_class["dispatchable"])
    _box(ax, (26, 68), "Electricity\ncombiner", color_class["combiner"], width=11, height=7)
    _box(
        ax,
        (44, 68),
        "Electrolyzer\n(dispatchable)\nconverter: elec -> H2",
        color_class["dispatchable"],
        width=15,
        height=11,
    )
    _box(ax, (62, 88), "H2 storage\n(storage)", color_class["storage"], width=11, height=7)
    _box(ax, (62, 68), "H2\ncombiner", color_class["combiner"], width=11, height=7)
    _box(ax, (80, 90), "N2 feedstock\n(feedstock)", color_class["feedstock"], width=12, height=7)
    _box(
        ax,
        (80, 68),
        "Ammonia synloop\n(dispatchable)\nconverter: H2 -> NH3\n(+ direct electricity)",
        color_class["dispatchable"],
        width=16,
        height=13,
    )
    _box(
        ax,
        (80, 48),
        "Electricity feedstock\n(feedstock)",
        color_class["feedstock"],
        width=13,
        height=7,
    )
    _box(ax, (95, 68), "Ammonia\ndemand\n4000 kg/h", color_class["demand"], width=10, height=9)

    # Electricity flows (blue).
    _flow_arrow(ax, (14.5, 84), (20.5, 70), color_flow["electricity"])
    _flow_arrow(ax, (14.5, 68), (20.5, 68), color_flow["electricity"], label="electricity")
    _flow_arrow(ax, (14.5, 52), (20.5, 66), color_flow["electricity"])
    _flow_arrow(ax, (31.5, 68), (36.5, 68), color_flow["electricity"], label="electricity")
    _flow_arrow(ax, (80, 51.5), (80, 61.5), color_flow["electricity"], label="direct", label_dy=0)
    _flow_arrow(ax, (5, 82), (5, 72), color_flow["electricity"], lw=1.6, label="charge", label_dy=0)

    # Hydrogen flows (orange).
    _flow_arrow(ax, (51.5, 71), (56.5, 86), color_flow["hydrogen"], rad=0.25)
    _flow_arrow(ax, (51.5, 68), (56.5, 68), color_flow["hydrogen"], label="hydrogen")
    _flow_arrow(ax, (62, 84.5), (62, 71.5), color_flow["hydrogen"])
    _flow_arrow(ax, (67.5, 68), (72, 68), color_flow["hydrogen"], label="hydrogen")

    # Nitrogen feedstock and the final ammonia product.
    _flow_arrow(ax, (80, 86.5), (80, 74.5), color_flow["nitrogen"], label="nitrogen", label_dy=0)
    _flow_arrow(ax, (88, 68), (90, 68), color_flow["ammonia"], label="ammonia")

    # Conversion-ratio callouts on the two converters (seed and measured values).
    ax.text(
        44,
        60.5,
        f"x {seed_elec_per_h2:0.1f} kWh/kg H2 (seed)\nmeasured ~{m_elec_per_h2:0.1f}",
        ha="center",
        va="top",
        fontsize=7.5,
        color=color_flow["electricity"],
    )
    ax.text(
        80,
        60.0,
        f"x {seed_h2_per_nh3:0.2f} kg H2/kg NH3 (seed)\n"
        f"+ {seed_elec_per_nh3:0.3f} kWh/kg NH3 direct",
        ha="center",
        va="top",
        fontsize=7.5,
        color=color_flow["hydrogen"],
    )

    # Backward demand-propagation band along the bottom.
    band = FancyBboxPatch(
        (4, 6),
        92,
        22,
        boxstyle="round,pad=0.4,rounding_size=1.5",
        linewidth=1.0,
        edgecolor="#999999",
        facecolor="#F5F5F5",
        zorder=1,
    )
    ax.add_patch(band)
    ax.text(
        50,
        25.5,
        "System-level controller: backward demand propagation "
        "(measured consumed/produced ratios override the plant_config seeds)",
        ha="center",
        va="center",
        fontsize=9.5,
        weight="bold",
    )
    _box(ax, (16, 15), f"NH3 demand\n{nh3_rate:,.0f} kg/h", "#EDE3F7", width=15, height=8)
    _box(ax, (42, 15), f"H2 demand\n{h2_rate:,.0f} kg/h", "#FBE3D6", width=15, height=8)
    _box(
        ax,
        (72, 19),
        f"Electrolyzer load\n{electrolyzer_rate_mw:,.1f} MW",
        "#DCE8F8",
        width=17,
        height=7,
    )
    _box(ax, (72, 10), f"Synloop direct\n{synloop_rate_mw:,.1f} MW", "#DCE8F8", width=17, height=7)
    _flow_arrow(
        ax,
        (23.5, 15),
        (34.5, 15),
        color_flow["hydrogen"],
        label=f"x {seed_h2_per_nh3:0.2f}",
        label_dy=1.4,
    )
    _flow_arrow(
        ax,
        (49.5, 15),
        (63.5, 19),
        color_flow["electricity"],
        label=f"x {seed_elec_per_h2:0.1f}",
        label_dy=1.4,
    )
    _flow_arrow(
        ax,
        (23.5, 13),
        (63.5, 10),
        color_flow["electricity"],
        rad=0.1,
        label=f"x {seed_elec_per_nh3:0.3f} (direct)",
        label_dy=-1.8,
    )

    legend_handles = [
        Patch(
            facecolor=color_class["flexible"], edgecolor="#2F2F2F", label="flexible (curtailable)"
        ),
        Patch(facecolor=color_class["storage"], edgecolor="#2F2F2F", label="storage"),
        Patch(facecolor=color_class["dispatchable"], edgecolor="#2F2F2F", label="dispatchable"),
        Patch(facecolor=color_class["feedstock"], edgecolor="#2F2F2F", label="feedstock"),
        Patch(facecolor=color_class["combiner"], edgecolor="#2F2F2F", label="combiner"),
        Patch(facecolor=color_class["demand"], edgecolor="#2F2F2F", label="demand"),
    ]
    ax.legend(
        handles=legend_handles,
        loc="upper center",
        ncol=6,
        fontsize=8,
        frameon=False,
        bbox_to_anchor=(0.5, 1.03),
    )
    ax.set_title(
        "Heterogeneous-commodity system: technologies, conversion ratios, and demand propagation",
        fontsize=13,
        pad=22,
    )
    fig.tight_layout()
    fig.savefig(figure_dir / "system_block_diagram.png", dpi=150)
    plt.close(fig)

    # -----------------------------------------------------------------
    # Figure 4: how the conversion ratios multiply along the chain to set
    # the electricity intensity of one kilogram of ammonia. Seeds come from
    # plant_config; the measured values are what the controller actually used.
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
        ax_chain, (12, 60), "1 kg\nammonia", color_class["demand"], width=14, height=16, fontsize=10
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
        f"{m_elec_per_nh3:0.3f} kWh\n(synloop direct)",
        "#DCE8F8",
        width=17,
        height=15,
    )

    _flow_arrow(
        ax_chain,
        (19, 64),
        (37.5, 78),
        color_flow["hydrogen"],
        label=f"x {m_h2_per_nh3:0.3f}\n(H2 per NH3)",
        label_dy=3.5,
    )
    _flow_arrow(
        ax_chain,
        (52.5, 78),
        (71.5, 78),
        color_flow["electricity"],
        label=f"x {m_elec_per_h2:0.1f}\n(elec per H2)",
        label_dy=3.5,
    )
    _flow_arrow(
        ax_chain,
        (19, 56),
        (71.5, 40),
        color_flow["electricity"],
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
        [0], [elec_via_electrolysis], color=color_flow["electricity"], label="via electrolysis"
    )
    ax_bar.barh(
        [0],
        [m_elec_per_nh3],
        left=[elec_via_electrolysis],
        color="#9AA0A6",
        label="synloop direct",
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

    return figure_dir


figures = make_plots(EXAMPLE_FOLDER / "outputs")
print(f"Saved dispatch, block-diagram, and conversion-ratio figures to {figures}")
