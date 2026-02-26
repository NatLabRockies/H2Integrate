# Wind Cost Model based on ATB-Formatted Cost Data

NREL's [Annual Technology Baseline (ATB)](https://atb.nrel.gov) is commonly referenced for technology costs such as overnight capital cost, fixed operations and maintenance costs, and capital expenditures. The `ATBWindPlantCostModel` cost model available in H2I that is intended to be easily used with cost values pulled from [NREL's ATB Excel workbook](https://atb.nrel.gov/electricity/2024/data).

```{note}
The Annual Technology Baseline (ATB) is updated annually. While we do our best to update our documentation regularly, be sure that you're using the most recent version of the ATB in case our links are pointing to an older version.
```

There are specific costs and performance specifications in the ATB for:
- [Land-Based Wind](https://atb.nrel.gov/electricity/2024/land-based_wind)
- [Offshore Wind](https://atb.nrel.gov/electricity/2024/offshore_wind)
- [Distributed Wind](https://atb.nrel.gov/electricity/2024/distributed_wind)

Example usage of this cost model in the `tech_config.yaml` file is shown [in the first section below](#atb-wind-cost-model).

(atb-wind-cost-model)=
## ATB Wind Cost Model

The inputs for `cost_parameters` are `capex_per_kW` and `opex_per_kW_per_year`. From the ATB workbook, a value for `capex_per_kW` can be found on any of the wind-specific tabs in the Excel Workbook under the "Overnight Capital Cost" section or the "CAPEX" section. The values in the "CAPEX" section include overnight capital costs, construction finance factor, and grid connection costs. A value for `opex_per_kW_per_year` can be found on any of the wind-specific tabs in the Excel Workbook under the "Fixed Operation and Maintenance Expenses" section.

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
