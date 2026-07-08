# Nuclear power plant models

H2Integrate currently includes two nuclear converter options:

- `QuinnNuclearPerformanceModel` with `QuinnNuclearCostModel` for a simple electricity-only nuclear plant
- `SimpleThermalNuclearReactorPerformanceModel` with `SimpleThermalNuclearReactorCostModel` for a thermal reactor that can trade off electricity production and process heat delivery

## Simple thermal nuclear reactor model

Use this model by setting:

- performance model: `SimpleThermalNuclearReactorPerformanceModel`
- cost model: `SimpleThermalNuclearReactorCostModel`

This model represents a reactor with:

- a high-pressure electric conversion stage
- a low-pressure electric conversion stage
- an extractable process heat stream, extracted upstream of the low-pressure turbine stages

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
| `electricity_out` | array[n_timesteps] | kW | Electrical output after mode-specific dispatch and clipping. |
| `heat_out` | array[n_timesteps] | kW | Delivered process heat. |
| `high_pressure_heat_demanded` | array[n_timesteps] | kW | Requested heat after applying `minimum_heat_extract`. |
| `high_pressure_heat` | array[n_timesteps] | kW | Available process heat stream before low-pressure electric conversion. |
| `low_pressure_heat` | array[n_timesteps] | kW | Remaining unused low-pressure heat after dispatch. |
| `rated_electricity_production` | scalar | kW | Rated electrical production. |
| `total_electricity_produced` | scalar | kW*h | Electricity produced over the simulated period. |
| `annual_electricity_produced` | array[plant_life] | kW*h/year | Annualized electricity production repeated across plant life. |
| `capacity_factor` | array[plant_life] | unitless | Average electrical output divided by rated electrical capacity. |
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

### Example `tech_config`

This matches the current HTSE example structure and naming.

```yaml
technologies:
  nuclear:
    performance_model:
      model: SimpleThermalNuclearReactorPerformanceModel
    cost_model:
      model: SimpleThermalNuclearReactorCostModel
    model_inputs:
      performance_parameters:
        operating_mode: heat
        electricity_command_value: 500000  # kW
        high_pressure_electrical_efficiency: 0.12
        low_pressure_electrical_efficiency: 0.22
        minimum_heat_extract: 1000  # kW
      cost_parameters:
        nuclear_reactor_upfront_cost: 5750.0
        nuclear_reactor_fixed_om_cost: 2.64
        nuclear_reactor_variable_om_cost: 0.0145
      shared_parameters:
        rated_capacity: 1000000.0
```

For a full coupled example, see [examples/99_nuclear_reactor_htse/tech_config.yaml](../../examples/99_nuclear_reactor_htse/tech_config.yaml).
