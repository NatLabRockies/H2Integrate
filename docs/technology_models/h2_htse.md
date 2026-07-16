# High-Temperature Steam Electrolysis (HTSE) Model

The HTSE model in H2Integrate represents hydrogen production from high-temperature steam electrolysis using electricity and thermal input. It is implemented as two components:

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

Use this model by setting:

- performance model: `HTSEPerformanceModel`

The HTSE performance model inherits from the electrolyzer base classes, so it is treated as a hydrogen-producing, dispatchable technology with an `electricity_in` input and a `hydrogen_out` output.

```{figure} images/HTSE.png
:alt: HTSE schematic
:width: 100%
:align: center
```

### Performance configuration parameters

These are read from `performance_parameters` and `shared_parameters`.

| Key | Type | Units | Description |
| --- | --- | --- | --- |
| `n_clusters` | int | unitless | Number of HTSE clusters. |
| `cluster_rating_MW` | float | MW | Nameplate electrical rating per cluster. |
| `nominal_heat_required` | float | kWh/kg | Nominal thermal energy required per kg of hydrogen. |
| `nominal_electricity_required` | float | kWh/kg | Nominal electrical energy required per kg of hydrogen. |
| `turndown_ratio` | float | unitless | Minimum fraction of rated hydrogen production required to stay on. |
| `location` | str | n/a | `onshore` or `offshore`. Present in config but not used directly in the current performance calculation. |
| `eol_eff_percent_loss` | float | percent | End-of-life efficiency loss setting. Present in config but not used directly in the current timestep energy balance. |
| `uptime_hours_until_eol` | int | h | Hours of operation between replacement events. |
| `include_degradation_penalty` | bool | n/a | Present in config but not used directly in the current timestep energy balance. |
| `pressure_H2` | float | n/a | Hydrogen pressure setting. Present in config but not used directly in the current timestep energy balance. |
| `size_mode` | str | n/a | Optional resizing mode inherited from the resizeable performance base class. |
| `flow_used_for_sizing` | str | n/a | Required for non-default sizing modes. |
| `max_feedstock_ratio` | float | unitless | Used when `size_mode = resize_by_max_feedstock`. |
| `max_commodity_ratio` | float | unitless | Used when `size_mode = resize_by_max_commodity`. |

### Performance inputs

| Name | Shape | Units | Description |
| --- | --- | --- | --- |
| `electricity_in` | array[n_timesteps] | kW | Available electrical input. Added by the electrolyzer base class. |
| `heat_in` | array[n_timesteps] | kW | Available thermal input. |
| `n_clusters` | scalar | unitless | Number of HTSE clusters used to determine installed size. |
| `cluster_size` | scalar | MW | Declared input in the component. Currently not used in the timestep calculation. |
| `max_hydrogen_capacity` | scalar | kg/h | Used in resize-by-commodity sizing mode. |
| `hydrogen_command_value` | array[n_timesteps] | kg/h | Optional hydrogen demand signal when `system_level_control` is enabled. |
| `max_feedstock_ratio` | scalar | unitless | Inherited optional resize input. |
| `max_commodity_ratio` | scalar | unitless | Inherited optional resize input. |

### Performance outputs

| Name | Shape | Units | Description |
| --- | --- | --- | --- |
| `hydrogen_out` | array[n_timesteps] | kg/h | Hydrogen production. |
| `rated_hydrogen_production` | scalar | kg/h | Rated hydrogen output based on installed electrical size and `nominal_electricity_required`. |
| `total_hydrogen_produced` | scalar | kg | Hydrogen produced over the simulated period. |
| `annual_hydrogen_produced` | array[plant_life] | kg/year | Annualized hydrogen production repeated across plant life. |
| `capacity_factor` | array[plant_life] | unitless | Simulated production relative to rated production. |
| `electrolyzer_size_mw` | scalar | MW | Installed HTSE electrical nameplate size. |
| `heat_demand` | array[n_timesteps] | kW | Requested HTSE thermal demand based on hydrogen demand. |
| `electricity_demand` | array[n_timesteps] | kW | Reported electrical demand signal. In the current implementation this is set to installed electrical size in kW. |
| `electricity_consumed` | array[n_timesteps] | kW | Electricity required by the current energy balance calculation. |
| `water_demand` | array[n_timesteps] | kg/h | Water consumption based on hydrogen production stoichiometry. |
| `efficiency` | scalar | unitless | Mean ratio of utilized input energy to available input energy over the simulation. |
| `replacement_schedule` | array[plant_life] | unitless | Replacement events derived from `uptime_hours_until_eol`. |
| `time_until_replacement` | scalar | h | Hours until replacement. |

### Dispatch and sizing behavior

Installed size is first inferred from:

$$
\text{electrolyzer\_size\_mw} = n_{clusters} \times cluster\_rating\_MW
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
\text{total\_specific\_energy} = nominal\_heat\_required + nominal\_electricity\_required
$$

and computes a nominal heat-to-electricity ratio:

$$
\text{ratio\_heat\_elec\_nom} = \frac{nominal\_heat\_required}{nominal\_electricity\_required}
$$

Available heat is used first up to the requested `heat_demand`. The remaining required energy is supplied electrically when possible. Hydrogen production is then limited by the combined energy available and by the turndown threshold.

```{note}
The current implementation is intentionally simple and should be interpreted as a reduced-order plant representation, not a detailed SOEC stack model with thermal transients, degradation coupling, startup dynamics, or detailed balance-of-plant behavior.
```

## Cost Model

Use this model by setting:

- cost model: `HTSECostModel`

The cost model is size-based and currently depends only on installed HTSE size.

### Cost configuration parameters

| Key | Type | Units | Description |
| --- | --- | --- | --- |
| `unit_capex` | float | USD/kW | Installed capital cost per kW of HTSE electrical size. |
| `fixed_opex` | float, optional | USD/(kW*year) | Fixed annual operating cost per kW. |
| `fixed_capex` | float, optional | USD/(kW*year) | Fallback value used to populate `fixed_opex` if `fixed_opex` is omitted. |
| `cost_year` | int | year | Dollar year of the cost inputs. Defaults to `2025`. |

### Cost inputs

| Name | Shape | Units | Description |
| --- | --- | --- | --- |
| `electrolyzer_size_mw` | scalar | MW | Installed HTSE size from the performance model. |
| `total_hydrogen_produced` | scalar | kg | Added by the electrolyzer cost base class, but not used directly in the current HTSE cost calculation. |
| `electricity_in` | array[n_timesteps] | kW | Added by the electrolyzer cost base class, but not used directly in the current HTSE cost calculation. |

### Cost outputs

| Name | Shape | Units | Description |
| --- | --- | --- | --- |
| `CapEx` | scalar | USD | `unit_capex * electrolyzer_size_kw` |
| `OpEx` | scalar | USD/year | `fixed_opex * electrolyzer_size_kw` |
| `VarOpEx` | array[plant_life] | USD/year | Inherited base output. The current model does not set a nonzero variable operating cost. |
| `cost_year` | scalar | year | Cost dollar year. |


