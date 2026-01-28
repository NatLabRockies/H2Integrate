(cost:cost_years)=
# Cost year of Cost Models
Some cost models are derived from literature and output costs (CapEx and OpEx) in a specific dollar-year.
Some cost models require users to input the key cost information and the output costs are in the same cost year as the user-provided costs.
For [cost models with a built-in cost year](#cost-models-with-inherent-cost-year), the cost year is not required as an input for the cost model.
For [cost models based on user-provided costs](#cost-models-with-user-input-cost-year), the `cost_year` should be included in the tech_config for that technology.

(cost-models-with-inherent-cost-year)=
## Cost models with inherent cost year

### Summary of cost models that are based around a cost year
| Cost Model              | Cost Year  |
| :---------------------- | :---------------: |
| `basic_electrolyzer_cost`|  2016    |
| `pem_electrolyzer_cost`|  2021    |
| `singlitico_electrolyzer_cost`|  2021    |
| `h2_storage`  with `'mch'` storage type  |  2024    |
| `h2_storage` for geologic storage or buried pipe | 2018 |
| `simple_ammonia_cost`   |  2022    |
| `direct_ocean_capture_cost` | 2023 |
| `ocean_alkalinity_enhancement_cost` | 2024 |
| `ocean_alkalinity_enhancement_cost_financial` | 2024 |
| `steel_cost`            |  2022    |
| `reverse_osmosis_desalination_cost` | 2013 |
| `synloop_ammonia_cost`  |  N/A (adjusts costs to `target_dollar_year` within cost model)  |

(cost-models-with-user-input-cost-year)=
## Cost models with user input cost year

### Summary of cost models that have user-input cost year
| Cost Model              |
| :---------------------- |
| `wind_plant_cost` |
| `atb_utility_pv_cost` |
| `atb_comm_res_pv_cost` |
| `simple_ASU_cost` |
| `hopp`            |
| `run_of_river_hydro_cost` |
| `smr_methanol_plant_cost` |
| `stimulated_geoh2_cost` |
| `natural_geoh2_cost`    |
| `wombat`                |
| `custom_electrolyzer_cost` |

### Example tech_config input for user-input cost year
```yaml
technologies:
  solar:
    performance_model:
      model: "pysam_solar_plant_performance"
    cost_model:
      model: "atb_utility_pv_cost"
    model_inputs:
        performance_parameters:
            pv_capacity_kWdc: 100000
            dc_ac_ratio: 1.34
            ...
        cost_parameters:
            capex_per_kWac: 1044
            opex_per_kWac_per_year: 18
            cost_year: 2022
```
