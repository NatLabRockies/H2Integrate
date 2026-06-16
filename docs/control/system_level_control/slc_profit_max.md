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

(slc-profit-max)=
# Profit Maximization System Level Controller

The profit maximization controller, `ProfitMaximizationControl`, dispatches technologies only when the revenue from selling the commodity exceeds the marginal cost of production. This means demand may go **unmet** if dispatch is unprofitable.

The N2 diagram below shows an example system using the profit maximization controller with wind, natural gas, and battery storage technologies.

```{code-cell} ipython3
:tags: [remove-input]

from h2integrate.core.h2integrate_model import H2IntegrateModel
import openmdao.api as om
import os

import html
from pathlib import Path
from IPython.display import HTML, display

os.chdir("../../../examples/35_system_level_control/profit_maximization/")

h2i_model = H2IntegrateModel("wind_ng_demand.yaml")
h2i_model.setup()

om.n2(
    h2i_model.prob,
    outfile="h2i_n2.html",
    display_in_notebook=False,
    show_browser=False,
)

n2_html = "h2i_n2.html"
n2_srcdoc = html.escape(Path(n2_html).read_text(encoding="utf-8"))
display(
    HTML(
        f'<div style="width:100%; height:600px; overflow:auto; margin:0; padding:0; border:0;">'
        f'<iframe srcdoc="{n2_srcdoc}" '
        'style="display:block; width:200%; height:600px; border:0; margin:0; padding:0; background:transparent;" '
        'loading="lazy"></iframe>'
        '</div>'
    )
)
```

## Dispatch Logic

The controller follows a three-step dispatch process:

1. **Flexible technologies** run at available capacity - they are always profitable to produce (zero marginal cost).
2. **Storage technologies** absorb any surplus (charging) or provide the deficit (discharging), split evenly across storage technologies producing the demanded commodity.
3. **Dispatchable technologies** are dispatched in merit order (cheapest first), but **only at timesteps where their marginal cost is below the sell price**. At each timestep, the dispatch is the minimum of the remaining demand and the rated capacity, gated by the profitability check.

```{note}
This is the key difference from the {ref}`cost minimization controller <slc-cost-min>`: unprofitable dispatch is skipped entirely, so demand may go unmet.
```

## Commodity Sell Price

The sell price can be configured in two ways in `system_level_control.control_parameters`:

| Value | Description |
| --- | --- |
| Numeric (e.g. `0.06`) | Constant sell price in `$/(commodity_amount_units)` |
| String (e.g. `"profast_npv"`) | Name of a finance group in `finance_parameters.finance_groups` whose `model_inputs.commodity_sell_price` will be used |

## Marginal Cost Configuration

Marginal costs are configured identically to the {ref}`cost minimization controller <slc-cost-min>` via `cost_per_tech`. Each dispatchable technology's entry can be:

| Value | Description |
| --- | --- |
| Numeric (e.g. `0.05`) | Constant marginal cost in `$/(commodity_amount_units)` |
| `"buy_price"` | Uses the technology's configured purchase price |
| `"VarOpEx"` | Derives cost from VarOpEx / total production |
| `"feedstock"` | Sums upstream feedstock VarOpEx / total production |

### Example Configuration

```yaml
system_level_control:
  control_strategy: ProfitMaximizationControl
  control_parameters:
    commodity_sell_price: profast_npv  # look up from finance group
    cost_per_tech:
      natural_gas_plant: feedstock     # use upstream feedstock VarOpEx
```

## Inputs and Outputs

In addition to the standard inputs inherited from `SystemLevelControlBase`, this controller adds:

- `commodity_sell_price` - the sell price per unit of the demanded commodity, shape `(n_timesteps,)`
- Marginal cost inputs per dispatchable technology based on `cost_per_tech` configuration

The base inputs for technologies classified as `flexible`, `dispatchable`, and `storage` are:

- `f"{tech_name}_{tech_output_commodity}_out"`
- `f"{tech_name}_rated_{tech_output_commodity}_production"`
- `f"{tech_name}_{tech_output_commodity}_demand"`

## Limitations

- Demand may go unmet: If no dispatchable technology is profitable at a given timestep, the remaining demand is not served.
- Even splitting across storage: Residual demand is split evenly across storage technologies regardless of capacity or state of charge.
