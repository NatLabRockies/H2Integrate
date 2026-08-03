# High-Temperature Steam Electrolysis (HTSE) Model

The HTSE model in H2Integrate represents hydrogen production from high-temperature steam electrolysis using electricity and thermal input. In this model, HTSE is represented as a solid oxide electrolyzer cell (SOEC) process. It is implemented as two components:

- `HTSEPerformanceModel`
- `HTSECostModel`

The performance model converts electricity and heat into hydrogen, water demand, and operating signals for connected technologies. The cost model computes installed capital cost and fixed operating cost from installed HTSE size.

## Model Overview

This is a simplified HTSE representation with constant nominal specific energy requirements:

- `nominal_electricity_required` in `kWh/kg`
- `nominal_heat_required` in `kWh/kg`

At each timestep, hydrogen production is determined from:

- installed HTSE size
- available `electricity_in`
- available `heat_in`
- optional `hydrogen_command_value` when system-level control is enabled
- turndown behavior

The model also exposes internal operating signals that are useful for coupled systems, including:

- `heat_demand`
- `electricity_demand`
- `electricity_consumed`
- `water_demand`

```{note}
The current implementation uses `electricity_demand` to report installed electrical demand equal to nameplate size, while `electricity_consumed` reports the timestep electricity required by the energy balance. For coupled analyses, `electricity_consumed` is the more literal consumption signal.
```

## Performance Model

To use this model, within your `tech_config.yaml` file set:

- performance model: `HTSEPerformanceModel`

The HTSE performance model inherits from the electrolyzer base classes, so it is treated as a hydrogen-producing, dispatchable technology with an `electricity_in` input and a `hydrogen_out` output.

```{figure} images/HTSE.png
:alt: HTSE schematic
:width: 100%
:align: center
```

### Dispatch and sizing behavior

Installed size is first calculated as:

$$
\text{electrolyzer\_size\_mw} = n_\text{clusters} \times \text{cluster\_rating\_MW}
$$

The model supports additional sizing modes inherited from the resizeable performance base class:

- `normal`
- `resize_by_max_feedstock`
- `resize_by_max_commodity`

In the current implementation:

- `resize_by_max_feedstock` supports sizing from `electricity`
- `resize_by_max_commodity` supports sizing from `hydrogen`

When system-level control is enabled, hydrogen demand is taken from `hydrogen_command_value`. Otherwise, the model assumes demand equal to rated hydrogen production implied by installed electrical size.

### Energy balance behavior

The model forms:

$$
\text{total\_specific\_energy} = \text{nominal\_heat\_required} + \text{nominal\_electricity\_required}
$$

and computes a nominal heat-to-electricity ratio:

$$
\text{ratio\_heat\_elec\_nom} = \frac{\text{nominal\_heat\_required}}{\text{nominal\_electricity\_required}}
$$

Available heat is used first up to the requested `heat_demand`. The remaining required energy is supplied electrically when possible. Hydrogen production is then limited by the combined energy available and by the turndown threshold.

```{note}
The current implementation is intentionally simple and should be interpreted as a reduced-order plant representation, not a detailed SOEC stack model with thermal transients, degradation coupling, startup dynamics, or detailed balance-of-plant behavior.
```

### API details
For API details, see the [`HTSEPerformanceModel` and `HTSECostModel` API documentation](../_autosummary/h2integrate.converters.hydrogen.htse_electrolyzer).

## Cost Model

To use this model, in your `tech_config.yaml` file, set:

- cost model: `HTSECostModel`

The cost model is size-based and currently depends only on installed HTSE size.

### API details
For API details, see the [`HTSEPerformanceModel` and `HTSECostModel` API documentation](../_autosummary/h2integrate.converters.hydrogen.htse_electrolyzer).
