(cost:cost_years)=
# Cost year of cost models
Cost models report the dollar year associated with their cost outputs. Plant-level finance parameters can adjust these costs to a common `target_dollar_year`. Some models use fixed source years; others require a year alongside user-provided cost data.

(cost-models-with-inherent-cost-year)=
## Cost models with inherent cost year

Some cost models are built from published cost data in a single dollar year. These models set `cost_year` to that year by default, so you do not need to provide it in `model_inputs.cost_parameters`. If you do provide a `cost_year` that differs from the model's source year, the model raises an error when its configuration is validated. See each model's documentation for its source cost year.

(cost-models-with-user-input-cost-year)=
## Cost models with user input cost year

### Models with user-provided cost years
Most cost models use costs that you supply (for example, `capex_per_kW`), so the dollar year is defined by your inputs. For these models, you must provide `cost_year` in `model_inputs.cost_parameters` that matches the dollar year of your cost values. If it is missing, the model raises an error when its configuration is validated. Some models also restrict `cost_year` to a supported range and raise an error for values outside it. `AmmoniaSynLoopCostModel` uses the parameter `base_cost_year` for its source data.

A few models with user-provided costs also define a default `cost_year`, such as `HTSECostModel` and `SimpleThermalNuclearReactorCostModel`; confirm that the default matches the year of the costs you provide.

### Example tech_config input for user-input cost year
```yaml
technologies:
  solar:
    performance_model:
      model: "PYSAMSolarPlantPerformanceModel"
    cost_model:
      model: "ATBUtilityPVCostModel"
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
