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

(slc-demand-following)=
# Demand Following System Level Controller

The demand following controller, `DemandFollowingControl`, aims to fully meet the demand and does not have any inputs related to cost.

The N2 diagram below shows an example system using the demand following controller with wind, natural gas, and battery storage technologies.

```{code-cell} ipython3
:tags: [remove-input]

from h2integrate.core.h2integrate_model import H2IntegrateModel
import openmdao.api as om
import os

import html
from pathlib import Path
from h2integrate import EXAMPLE_DIR
from IPython.display import HTML, display

os.chdir(EXAMPLE_DIR / "35_system_level_control/battery_with_controller/")

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

The demand is satisfied in a fixed three-step priority order, and each step's shortfall or surplus is passed to the next:

1. **Curtailable techs** run at their available capacity. Their total output is subtracted from the demand, which may drive the residual demand negative (surplus).

2. **Storage techs** receive the residual demand (which may be positive or negative). When residual demand is positive the storage is commanded to discharge; when negative it is commanded to charge. If multiple storage techs produce the demanded commodity, the residual demand is
split **evenly** across them (each receives ``demand / n_storage``).

3. **Dispatchable techs** cover any remaining positive demand after storage. The remaining demand (floored at zero) is split **evenly** across all dispatchable techs that produce the demanded commodity (each receives ``remaining_demand / n_dispatchable``).

### Example Configuration

```yaml
system_level_control:
  control_strategy: DemandFollowingControl
  solver_options: # solver options for resolving feedback
    solver_name: gauss_seidel
    max_iter: 20
    convergence_tolerance: 1.0e-6
```

## Inputs and Outputs

The inputs for technologies classified as `curtailable`, `dispatchable`, and `storage` are:

- `f"{tech_name}_{tech_output_commodity}_out"`
- `f"{tech_name}_rated_{tech_output_commodity}_production"`
- `f"{tech_name}_{tech_output_commodity}_demand"`

The inputs for technologies classified as `feedstock` are:
- `f"{tech_name}_{commodity}_out"`

## Systems with Heterogeneous Commodities

The `DemandFollowingControl` controller can be used in hybrid systems where technologies produce different commodities.
For example, in a system where an electrolyzer produces hydrogen and the demand commodity is hydrogen, the controller can set the electricity-generating *curtailable* technologies' set-points to meet the hydrogen demand.

This framework provides a starting point for hybrid energy system control but is intended to be extended with more sophisticated strategies for complex multi-commodity systems.

## Limitations

- No cost awareness: The controller dispatches technologies purely to meet demand without considering operational costs, commodity prices, or economic optimization.
- Even splitting across storage: When multiple storage technologies produce the demanded commodity, the residual demand is divided evenly among them (`demand / n_storage`), regardless of differences in capacity, state of charge, or efficiency.
- Even splitting across dispatchable technologies: Similarly, any remaining demand after storage dispatch is split evenly across all dispatchable technologies (`remaining_demand / n_dispatchable`), without accounting for marginal costs or capacity constraints.
- Fixed priority order: The dispatch order (curtailable → storage → dispatchable) is fixed in the current implementation.
