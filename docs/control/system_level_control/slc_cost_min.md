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

(slc-cost-min)=
# Cost Minimization System Level Controller

The cost minimization controller, `CostMinimizationControl`, meets demand at minimum variable cost using merit-order dispatch.
Unlike the {ref}`demand following controller <slc-demand-following>`, which splits demand evenly across dispatchable technologies, this controller dispatches the cheapest technologies first.

## Dispatch Logic

The controller follows a three-step dispatch process:

1. **Flexible technologies** run at their available capacity (assumed zero marginal cost). Their output is subtracted from the demand.
2. **Storage technologies** absorb any surplus (charging) or provide the deficit (discharging). Residual demand is split evenly across storage technologies producing the demanded commodity.
3. **Dispatchable technologies** are dispatched by cheapest marginal cost first, each up to its rated capacity, until the remaining demand is met.

## Marginal Cost Configuration

Marginal costs are specified per dispatchable technology in the `cost_per_tech` dictionary under `system_level_control.control_parameters` in the plant config. Each entry can be:

| Value | Description |
| --- | --- |
| Numeric (e.g. `0.05`) | Constant marginal cost in `$/(commodity_amount_units)` |
| `"buy_price"` | Uses the technology's configured purchase price |
| `"VarOpEx"` | Derives marginal cost from the technology's variable operating expenditure divided by total production |
| `"feedstock"` | Sums upstream feedstock `VarOpEx` values and divides by the technology's total production |

```{note}
The dispatch order is determined by sorting dispatchable technologies by their **mean** marginal cost across all timesteps (cheapest first).
```

### Example Configuration

```yaml
system_level_control:
  control_strategy: CostMinimizationControl
  control_parameters:
    cost_per_tech:
      natural_gas_plant: feedstock
```

## Inputs and Outputs

In addition to the standard inputs inherited from `SystemLevelControlBase`, the cost minimization controller adds marginal cost inputs based on the `cost_per_tech` configuration (see above).

The base inputs for technologies classified as `flexible`, `dispatchable`, and `storage` are:

- `f"{tech_name}_{tech_output_commodity}_out"`
- `f"{tech_name}_rated_{tech_output_commodity}_production"`
- `f"{tech_name}_{tech_output_commodity}_demand"`

## Limitations

- Greedy dispatch: The merit-order approach is greedy - it does not look ahead across timesteps to optimize total cost over the simulation horizon.
- Even splitting across storage: Residual demand is split evenly across storage technologies regardless of capacity or state of charge.
- Demand is always met: Unlike the {ref}`profit maximization controller <slc-profit-max>`, this controller always attempts to meet demand regardless of cost.
