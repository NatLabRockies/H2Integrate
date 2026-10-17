---
jupytext:
  text_representation:
    extension: .md
    format_name: myst
    format_version: 0.13
    jupytext_version: 1.18.1
kernelspec:
  display_name: Python 3.11.13 ('h2i_env')
  language: python
  name: python3
---

(slc-heterogeneous-commodity)=
# Heterogeneous-Commodity System-Level Control

This walkthrough runs the wind, solar, and battery powered ammonia example. The system-level
controller (SLC) starts with ammonia demand, then propagates the required hydrogen and electricity
backward through the Haber-Bosch loop and electrolyzer. The physical flows still move forward:

```text
wind + solar -> generation combiner -> battery / electricity bus -> splitter
  splitter out1 -> electrolyzer -> hydrogen -> Haber-Bosch -> ammonia demand
  splitter out2 ---------------------------> Haber-Bosch
n2 feedstock --------------------------------> Haber-Bosch
```

The example uses `ProfitMaximizationControl`. Wind and solar are flexible, the battery follows the
electricity surplus or deficit, and the ammonia sell-price gate applies at the demand bus. There is
no grid backup or hydrogen storage.

## Run the Example

The code runs an isolated copy, keeping generated reports and outputs out of the source example.

```{code-cell} ipython3
import os
import shutil
import tempfile
from pathlib import Path

import numpy as np
import matplotlib.pyplot as plt
from IPython.display import display

from h2integrate import EXAMPLE_DIR
from h2integrate.core.h2integrate_model import H2IntegrateModel

_example_tmp = tempfile.TemporaryDirectory(prefix="h2i-heterogeneous-")
_example_dir = Path(_example_tmp.name) / "heterogeneous_commodity"
shutil.copytree(
    EXAMPLE_DIR / "35_system_level_control" / "heterogeneous_commodity",
    _example_dir,
)
_original_cwd = Path.cwd()
os.chdir(_example_dir)

model = H2IntegrateModel("heterogeneous_commodity.yaml")
model.run()
```

## Conversion Ratios

`dispatch_trace["ratios"]` contains the ratio used at each converter link. For a representative
operating period where both converters are producing, the measured ratios show how one kilogram
per hour of ammonia demand translates into upstream flows:

```{code-cell} ipython3
trace = model.prob.model.plant.system_level_controller.dispatch_trace
ammonia_out = np.asarray(model.prob.get_val("haber_bosch.ammonia_out", units="kg/h"))
hydrogen_out = np.asarray(model.prob.get_val("electrolyzer.hydrogen_out", units="kg/h"))
fully_measured = (ammonia_out > 1e-6) & (hydrogen_out > 1e-6)

ratio_descriptions = [
    (("electricity", "electrolyzer", "hydrogen"), "Electrolyzer electricity / hydrogen", "kWh/kg H2"),
    (("hydrogen", "haber_bosch", "ammonia"), "Haber-Bosch hydrogen / ammonia", "kg H2/kg NH3"),
    (("electricity", "haber_bosch", "ammonia"), "Haber-Bosch direct electricity / ammonia", "kWh/kg NH3"),
]

for key, label, units in ratio_descriptions:
    ratio = trace["ratios"][key]
    valid = fully_measured & (ratio["source"] == "measured")
    print(f"{label}: {np.mean(ratio['value'][valid]):.3f} {units}")

plant_ratios = trace["demand_ratios"]
print(
    "Plant-wide requirement per kg NH3: "
    f"{np.mean(plant_ratios['electricity'][fully_measured]):.3f} kWh electricity, "
    f"{np.mean(plant_ratios['hydrogen'][fully_measured]):.4f} kg hydrogen"
)
```

The plant-wide electricity ratio includes both the electrolyzer load and the Haber-Bosch loop's
direct electricity use. The trace is overwritten on each model compute and is intended for
inspection; it is not an OpenMDAO output or a public API.

The plot below shows how the ratios used by the SLC change over the year. Zero-output hours use
the mean of valid measured ratios once measurements exist; the capacity-based ratio seeds the
first iteration and is used throughout only when no valid measurements are available.

```{code-cell} ipython3
hours = np.arange(ammonia_out.size)
ratio_plot_data = [
    (("electricity", "electrolyzer", "hydrogen"), "kWh/kg H2"),
    (("hydrogen", "haber_bosch", "ammonia"), "kg H2/kg NH3"),
    (("electricity", "haber_bosch", "ammonia"), "kWh/kg NH3"),
]

fig, axes = plt.subplots(3, 1, figsize=(10, 7), sharex=True)
for axis, (key, units) in zip(axes, ratio_plot_data, strict=True):
    ratio = trace["ratios"][key]
    axis.plot(hours, ratio["value"], linewidth=0.8)
    axis.set_ylabel(units)
    axis.grid(alpha=0.25)
    axis.set_title(f"{key[1]}: {key[0]} per {key[2]}")
axes[-1].set_xlabel("Hour of year")
fig.tight_layout()
display(fig)
plt.close(fig)
```

## Commodity Histories

These panels follow physical flows through a representative week: generation and the shared
electricity bus, splitter allocations and consumer loads, hydrogen production and consumption,
ammonia production and demand, then battery state of charge.

```{code-cell} ipython3
def _get(name, units):
    return np.asarray(model.prob.get_val(name, units=units)).reshape(-1)


week_start = 3000
week = slice(week_start, week_start + 168)
week_hours = np.arange(168)

wind_mw = _get("wind.electricity_out", "MW")
solar_mw = _get("solar.electricity_out", "MW")
battery_mw = _get("battery.electricity_out", "MW")
electricity_bus_mw = _get("elec_combiner.electricity_out", "MW")
split_out1_mw = _get("electricity_splitter.electricity_out1", "MW")
split_out2_mw = _get("electricity_splitter.electricity_out2", "MW")
electrolyzer_load_mw = _get("electrolyzer.electricity_consumed", "MW")
haber_bosch_load_mw = _get("haber_bosch.electricity_consumed", "MW")
hydrogen_set_point = _get(
    "system_level_controller.electrolyzer_hydrogen_set_point", "kg/h"
)
hydrogen_consumed = _get("haber_bosch.hydrogen_consumed", "kg/h")
ammonia_demand = _get("ammonia_load_demand.ammonia_demand", "kg/h")
battery_soc = _get("battery.SOC", "unitless")

fig, axes = plt.subplots(5, 1, figsize=(11, 12), sharex=True)

axes[0].plot(week_hours, wind_mw[week], label="Wind")
axes[0].plot(week_hours, solar_mw[week], label="Solar PV")
axes[0].plot(week_hours, battery_mw[week], label="Battery net output")
axes[0].plot(week_hours, electricity_bus_mw[week], color="black", label="Electricity bus")
axes[0].set_ylabel("MW")
axes[0].set_title("Electricity generation and storage feed the shared bus")
axes[0].legend(ncol=2)

axes[1].plot(week_hours, split_out1_mw[week], label="Splitter out1 -> electrolyzer")
axes[1].plot(week_hours, electrolyzer_load_mw[week], "--", label="Electrolyzer consumed")
axes[1].plot(week_hours, split_out2_mw[week], label="Splitter out2 -> Haber-Bosch")
axes[1].plot(week_hours, haber_bosch_load_mw[week], "--", label="Haber-Bosch consumed")
axes[1].set_ylabel("MW")
axes[1].set_title("The splitter divides electricity between both converter loads")
axes[1].legend(ncol=2)

axes[2].plot(week_hours, hydrogen_out[week], label="Electrolyzer hydrogen out")
axes[2].plot(week_hours, hydrogen_set_point[week], "--", label="SLC hydrogen set point")
axes[2].plot(week_hours, hydrogen_consumed[week], ":", label="Haber-Bosch hydrogen consumed")
axes[2].set_ylabel("kg/h")
axes[2].set_title("Hydrogen connects the electrolyzer to the synthesis loop")
axes[2].legend(ncol=2)

axes[3].plot(week_hours, ammonia_out[week], label="Haber-Bosch ammonia out")
axes[3].plot(week_hours, ammonia_demand[week], "--", color="black", label="Ammonia demand")
axes[3].set_ylabel("kg/h")
axes[3].set_title("Ammonia production follows the demand that drives the chain")
axes[3].legend()

axes[4].plot(week_hours, battery_soc[week] * 100.0, color="#C78B14")
axes[4].set_ylabel("SOC (%)")
axes[4].set_xlabel("Hour of representative week")
axes[4].set_ylim(0, 100)
axes[4].set_title("Battery state of charge")

fig.tight_layout()
display(fig)
plt.close(fig)
```

The full-year arrays remain available in the notebook kernel. For example,
`model.prob.get_val("electricity_splitter.electricity_out1", units="kW")` returns the hourly
priority flow to the electrolyzer, while `electricity_out2` is the corresponding flow to
Haber-Bosch.

```{code-cell} ipython3
os.chdir(_original_cwd)
_example_tmp.cleanup()
```
