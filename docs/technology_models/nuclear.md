# Nuclear power plant models

H2Integrate currently includes two nuclear converter options:

- `QuinnNuclearPerformanceModel` with `QuinnNuclearCostModel` for a simple electricity-only nuclear plant
- `SimpleThermalNuclearReactorPerformanceModel` with `SimpleThermalNuclearReactorCostModel` for a thermal reactor that can trade off electricity production and process heat delivery

The first model is based on Quinn et al. (2023). The second is a simplified thermal reactor representation intended for coupled workflows such as nuclear plus HTSE.

## Quinn electricity-only nuclear model

Use this model by setting:

- performance model: `QuinnNuclearPerformanceModel`
- cost model: `QuinnNuclearCostModel`

### Performance behavior

This model produces electricity only. It clips the commanded electricity output to the rated plant capacity and reports aggregate production metrics.

**Inputs**

| Name | Shape | Units | Description |
| --- | --- | --- | --- |
| `system_capacity` | scalar | kW | Rated electrical capacity. |
| `electricity_command_value` | array[n_timesteps] | kW | Requested electrical output profile. Defaults to `system_capacity`. |

**Outputs**

| Name | Shape | Units | Description |
| --- | --- | --- | --- |
| `electricity_out` | array[n_timesteps] | kW | Electricity output after clipping to capacity. |
| `rated_electricity_production` | scalar | kW | Rated plant capacity. |
| `total_electricity_produced` | scalar | kW*h | Electricity produced over the simulated period. |
| `annual_electricity_produced` | scalar | kW*h/year | Annualized electricity production. |
| `capacity_factor` | scalar | unitless | Simulated production divided by maximum possible production. |

### Cost behavior

The cost model applies:

- capital cost from `capex_per_kw`
- fixed O&M from `fixed_opex_per_kw_year`
- variable O&M from `variable_opex_per_mwh`
- optional capex scaling using `reference_capacity_kw` and `capex_scaling_exponent`

**Cost parameters**

| Key | Type | Description |
| --- | --- | --- |
| `system_capacity_kw` | float | Rated electrical capacity in kW. |
| `capex_per_kw` | float | Capital cost in USD/kW. |
| `fixed_opex_per_kw_year` | float | Fixed O&M in USD/(kW*year). |
| `variable_opex_per_mwh` | float | Variable O&M in USD/MWh. |
| `reference_capacity_kw` | float, optional | Reference capacity for capex scaling. Defaults to `system_capacity_kw`. |
| `capex_scaling_exponent` | float | Scaling exponent applied to capex. Defaults to `1.0`. |
| `cost_year` | int | Dollar year of the cost inputs. |

**Outputs**

| Name | Shape | Units | Description |
| --- | --- | --- | --- |
| `CapEx` | scalar | USD | Total capital cost. |
| `OpEx` | scalar | USD/year | Fixed annual O&M. |
| `VarOpEx` | array[plant_life] | USD/year | Variable annual O&M repeated across plant life. |

### Example `tech_config`

```yaml
technologies:
  nuclear:
    performance_model:
      model: QuinnNuclearPerformanceModel
    cost_model:
      model: QuinnNuclearCostModel
    model_inputs:
      performance_parameters:
        system_capacity_kw: 300000.0
      cost_parameters:
        system_capacity_kw: 450000.0
        capex_per_kw: 6000.0
        fixed_opex_per_kw_year: 120.0
        variable_opex_per_mwh: 2.5
        reference_capacity_kw: 300000.0
        capex_scaling_exponent: 0.9
        cost_year: 2023
```

### References
- Quinn, J. et al., 2023. Small modular reactor light water reactor techno-economic analysis. Applied Energy 120669. https://doi.org/10.1016/j.apenergy.2023.120669

## Simple thermal nuclear reactor model

Use this model by setting:

- performance model: `SimpleThermalNuclearReactorPerformanceModel`
- cost model: `SimpleThermalNuclearReactorCostModel`

This model represents a reactor with:

- a high-pressure electric conversion stage
- a low-pressure electric conversion stage
- an extractable process heat stream, extracted upstream of the low-pressure turbine stages (dashed red arrow in the figure)

It supports two operating modes:

- `heat`: satisfy heat demand first, then convert remaining low-pressure heat to electricity
- `electricity`: satisfy the electricity command first, then send the remaining available heat

```{figure} images/ThermalNucReactor-H2I.png
:alt: Thermal nuclear reactor schematic
:width: 100%
:align: center
```

### Performance inputs

The performance config is built from `performance_parameters` and shared inputs from `shared_parameters`.

| Name | Source | Units | Description |
| --- | --- | --- | --- |
| `operating_mode` | `performance_parameters` | n/a | Must be `heat` or `electricity`. |
| `electricity_command_value` | `performance_parameters` | kW | Requested electrical output. Added as a time-series input named `electricity_command_value`. |
| `high_pressure_electrical_efficiency` | `performance_parameters` | unitless | Fraction of total thermal input converted in the high-pressure stage. |
| `low_pressure_electrical_efficiency` | `performance_parameters` | unitless | Efficiency applied to remaining low-pressure heat when generating electricity. |
| `minimum_heat_extract` | `performance_parameters` | kW | Minimum process heat reserved for extraction. Defaults to `0.0`. |
| `rated_capacity` | `shared_parameters` | kW | Rated electrical capacity used to infer reactor thermal capacity. |
| `heat_command_value` | runtime input | kW | Downstream process heat request. Defaults to `6400` if not connected. |

### Performance outputs

| Name | Shape | Units | Description |
| --- | --- | --- | --- |
| `electricity_out` | array[n_timesteps] | kW | Electrical output of the nuclear system. |
| `heat_out` | array[n_timesteps] | kW | Delivered process heat. |
| `high_pressure_heat_demanded` | array[n_timesteps] | kW | Requested heat after applying `minimum_heat_extract`. |
| `high_pressure_heat` | array[n_timesteps] | kW | Available process heat stream before low-pressure electric conversion. |
| `low_pressure_heat` | array[n_timesteps] | kW | Remaining unused low-pressure heat after dispatch. |
| `rated_electricity_production` | scalar | kW | Rated electrical production. |
| `total_electricity_produced` | scalar | kW*h | Electricity produced over the simulated period. |
| `annual_electricity_produced` | array[plant_life] | kW*h/year | Annualized electricity production repeated across plant life. |
| `capacity_factor` | array[plant_life] | unitless | Electrical capacity factor, likely below nominal fleet values. |
| `replacement_schedule` | array[plant_life] | unitless | Currently zeros. |

### Thermal reactor dispatch logic

The model computes a combined electric efficiency:

$$
\eta_{combined} = \eta_{hp} + (1 - \eta_{hp}) \eta_{lp}
$$

Then infers thermal capacity from rated electrical capacity:

$$
P_{thermal} = \frac{P_{electric,rated}}{\eta_{combined}}
$$

In `heat` mode, delivered heat is limited by available process heat and the requested heat demand. Remaining low-pressure heat is converted to electricity.

In `electricity` mode, electricity is limited by the command value and rated capacity. Remaining process heat is then sent as `heat_out`.

### Thermal reactor cost model

The thermal reactor cost model uses direct capacity-based cost inputs and computes variable O&M from delivered electricity.

| Key | Source | Units | Description |
| --- | --- | --- | --- |
| `rated_capacity` | `shared_parameters` | kW | Rated capacity used for cost calculations. |
| `nuclear_reactor_upfront_cost` | `cost_parameters` | USD/kW | Capital cost per kW. |
| `nuclear_reactor_fixed_om_cost` | `cost_parameters` | USD/(kW*year) | Fixed annual O&M. |
| `nuclear_reactor_variable_om_cost` | `cost_parameters` | USD/(kW*h) | Variable O&M applied to simulated electricity production. |
| `cost_year` | `cost_parameters` | year | Optional cost year, default `2025`. |

**Outputs**

| Name | Shape | Units | Description |
| --- | --- | --- | --- |
| `CapEx` | scalar | USD | `rated_capacity * nuclear_reactor_upfront_cost` |
| `OpEx` | scalar | USD/year | `rated_capacity * nuclear_reactor_fixed_om_cost` |
| `VarOpEx` | array[plant_life] | USD/year | Variable O&M from simulated electricity output, repeated across plant life. |
