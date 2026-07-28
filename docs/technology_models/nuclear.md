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


(references)=
## References

- Quinn, J. et al., 2023. Small modular reactor light water reactor techno-economic analysis. Applied Energy 120669. https://doi.org/10.1016/j.apenergy.2023.120669
