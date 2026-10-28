# Wind Cost Model based on ATB-Formatted Cost Data

NLR's [Annual Technology Baseline (ATB)](https://atb.nlr.gov) is commonly referenced for technology costs such as overnight capital cost, fixed operations and maintenance costs, and capital expenditures. The `ATBWindPlantCostModel` cost model available in H2I that is intended to be easily used with cost values pulled from [NLR's ATB Excel workbook](https://atb.nlr.gov/electricity/2024/data).

```{note}
The Annual Technology Baseline (ATB) is updated annually. While we do our best to update our documentation regularly, be sure that you're using the most recent version of the ATB in case our links are pointing to an older version.
```

There are specific costs and performance specifications in the ATB for:
- [Land-Based Wind](https://atb.nlr.gov/electricity/2024/land-based_wind)
- [Offshore Wind](https://atb.nlr.gov/electricity/2024/offshore_wind)
- [Distributed Wind](https://atb.nlr.gov/electricity/2024/distributed_wind)

Example usage of this cost model in the `tech_config.yaml` file is shown [in the first section below](#atb-wind-cost-model).
See {py:class}`~h2integrate.converters.wind.atb_wind_cost.ATBWindPlantCostModel` and
{py:class}`~h2integrate.converters.wind.atb_wind_cost.ATBWindPlantCostModelConfig`.
The model multiplies `rated_electricity_production` by the configured rates to produce `CapEx`
and annual `OpEx`, and supports one-hour time steps.

(atb-wind-cost-model)=
## ATB Wind Cost Model

Capital and fixed operating costs can be found on the wind-specific ATB workbook sheets under
"Overnight Capital Cost" or "CAPEX" and "Fixed Operation and Maintenance Expenses". The "CAPEX"
values include overnight capital costs, construction finance factor, and grid connection costs.
Configure the model using:

```{eval-rst}
.. autoclass:: h2integrate.converters.wind.atb_wind_cost.ATBWindPlantCostModelConfig
   :members:
   :no-index:
```

Here is an example of how to use the `ATBWindPlantCostModel` model in the `tech_config.yaml` file:

```yaml
technologies:
  wind:
    performance_model:
      model: "PYSAMWindPlantPerformanceModel"
    cost_model:
      model: "ATBWindPlantCostModel"
    model_inputs:
      shared_parameters:
        num_turbines: 20
        turbine_rating_kw: 6000
      performance_parameters:
        hub_height: 115
        rotor_diameter: 170
            ...
      cost_parameters:
          capex_per_kW: 1044
          opex_per_kW_per_year: 18
```
