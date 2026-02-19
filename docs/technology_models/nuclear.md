# Nuclear power plant model

The nuclear power plant model provides a simple, size-based performance model and a type-based cost model.
Cost defaults are intended to be populated from literature, such as Quinn et al. (2023) on SMR LWR techno-economic analysis.
See the paper here: https://doi.org/10.1016/j.apenergy.2023.120669.

To use this model, set the performance model to `NuclearPerformanceModel` and the cost model to `NuclearCostModel` in your `tech_config`.

## Performance model

The performance model limits electricity production by the rated capacity and an optional demand signal.
A capacity factor parameter is accepted in the config but is not currently applied in the calculation.

**Inputs**
| Name | Shape | Units | Description |
| --- | --- | --- | --- |
| `system_capacity` | scalar | MW | Rated electrical capacity. |
| `electricity_demand` | array[n_timesteps] | MW | Optional demand profile; defaults to rated capacity. |

**Outputs**
| Name | Shape | Units | Description |
| --- | --- | --- | --- |
| `electricity_out` | array[n_timesteps] | MW | Electricity produced, capped at `system_capacity`. |
| `rated_electricity_production` | scalar | MW | Rated production (capacity). |
| `total_electricity_produced` | scalar | MW*h | Sum of production over the simulation. |
| `annual_electricity_produced` | array[plant_life] | MW*h/year | Annualized production. |
| `capacity_factor` | array[plant_life] | unitless | Ratio of actual to maximum production. |
| `replacement_schedule` | array[plant_life] | unitless | Placeholder replacement schedule (zeros). |
| `operational_life` | scalar | yr | Operational life (defaults to plant life). |

## Cost model

The cost model uses a reactor type selector and a `type_costs` mapping to compute capital and operating costs.
It supports optional scaling of capex with size using a reference capacity and scaling exponent.

**Inputs**
| Name | Shape | Units | Description |
| --- | --- | --- | --- |
| `system_capacity` | scalar | MW | Plant capacity used for cost scaling. |
| `electricity_out` | array[n_timesteps] | MW | Output from performance model. |

**Cost parameters (tech_config)**
| Key | Type | Description |
| --- | --- | --- |
| `system_capacity_mw` | float | Rated electrical capacity (MW). |
| `reactor_type` | str | Key to select a reactor type in `type_costs`. |
| `type_costs` | dict | Mapping of reactor type to cost values. |
| `cost_year` | int | Dollar year for the input costs. |

**type_costs schema**
| Key | Type | Required | Description |
| --- | --- | --- | --- |
| `capex_per_kw` | float | yes | Capital cost per kW. |
| `fixed_opex_per_kw_year` | float | yes | Fixed O&M per kW per year. |
| `variable_opex_per_mwh` | float | yes | Variable O&M per MWh. |
| `reference_capacity_mw` | float | no | Reference capacity for capex scaling (defaults to `system_capacity_mw`). |
| `capex_scaling_exponent` | float | no | Capex scaling exponent (defaults to 1.0). |

The capex calculation follows:

$$
C_{\text{capex}} = (c_{\text{capex}} \cdot (P / P_{\text{ref}})^{(e-1)}) \cdot P
$$

Where $c_{\text{capex}}$ is `capex_per_kw`, $P$ is plant capacity (kW), $P_{\text{ref}}$ is `reference_capacity_mw`, and $e$ is `capex_scaling_exponent`.

**Outputs**
| Name | Shape | Units | Description |
| --- | --- | --- | --- |
| `CapEx` | scalar | USD | Total capital expenditure. |
| `OpEx` | scalar | USD/year | Fixed plus variable O&M. |
| `VarOpEx` | array[plant_life] | USD/year | Variable O&M (repeated each year). |
| `cost_year` | scalar | year | Dollar year of costs. |

## Example tech_config

```yaml
technologies:
  nuclear:
    performance_model:
      model: "NuclearPerformanceModel"
    cost_model:
      model: "NuclearCostModel"
    model_inputs:
      performance_parameters:
        system_capacity_mw: 300.0
        capacity_factor: 0.9
      cost_parameters:
        system_capacity_mw: 450.0
        reactor_type: smr_lwr
        type_costs:
          smr_lwr:
            capex_per_kw: 6000.0
            fixed_opex_per_kw_year: 120.0
            variable_opex_per_mwh: 2.5
            reference_capacity_mw: 300.0
            capex_scaling_exponent: 0.9
          lwr:
            capex_per_kw: 4500.0
            fixed_opex_per_kw_year: 95.0
            variable_opex_per_mwh: 2.0
            reference_capacity_mw: 1000.0
            capex_scaling_exponent: 0.95
        cost_year: 2023
```

## References

- Quinn, J. et al., 2023. Small modular reactor light water reactor techno-economic analysis. Applied Energy 120669. https://doi.org/10.1016/j.apenergy.2023.120669
