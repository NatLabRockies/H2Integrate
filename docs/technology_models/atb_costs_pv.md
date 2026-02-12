# Solar-PV Cost Models based on ATB-Formatted Cost Data

NREL's [Annual Technology Baseline (ATB)](https://atb.nrel.gov) is commonly referenced for technology costs such as overnight capital cost, fixed operations and maintenance costs, and capital expenditures. Two solar-PV cost models are available in H2I that are intended to be easily used with cost values pulled from [NREL's ATB Excel workbook](https://atb.nrel.gov/electricity/2024/data).

```{note}
The Annual Technology Baseline (ATB) is updated annually. While we do our best to update our documentation regularly, be sure that you're using the most recent version of the ATB in case our links are pointing to an older version.
```

As mentioned on the [Utility-Scale PV ATB page](https://atb.nrel.gov/electricity/2024/utility-scale_pv), the costs for utility-scale PV have been published in `$/kW-AC` since 2020. The costs for [Commercial PV](https://atb.nrel.gov/electricity/2024/commercial_pv) and [Residential PV](https://atb.nrel.gov/electricity/2024/residential_pv) are published in `$/kW-DC`. The only difference between the two cost models in H2I are whether costs are input in `$/kW-AC` or `$/kW-DC`.

- The `"ATBUtilityPVCostModel"` model has costs input in `$/kW-AC` to match the ATB and the outputted capacity in kW-AC from the PV performance model. Example usage of this cost model in the `tech_config.yaml` file is shown [in the first section below](#utility-scale-pv-cost-model).
- The `"ATBResComPVCostModel"` model has costs input in `$/kW-DC` and the PV capacity is input in kW-DC from the **shared input parameter** of the PV performance model. Example usage of this cost model in the `tech_config.yaml` file is shown [in the second section below](#commercial-and-residential-pv-cost-model).

(utility-scale-pv-cost-model)=
## Utility-Scale PV Cost Model

The inputs for `cost_parameters` are `capex_per_kWac` and `opex_per_kWac_per_year`. From the ATB workbook, a value for `capex_per_kWac` can be found on the `Solar - Utility PV` sheet under the "Overnight Capital Cost" section or the "CAPEX" section. The values in the "CAPEX" section include overnight capital costs, construction finance factor, and grid connection costs. A value for `opex_per_kWac_per_year` can be found on the `Solar - Utility PV` sheet under the "Fixed Operation and Maintenance Expenses" section.

Here is an example of how to use the `ATBUtilityPVCostModel` model in the `tech_config.yaml` file:

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
```

(commercial-and-residential-pv-cost-model)=
## Commercial and Residential PV Cost Model

The inputs for `cost_parameters` are `capex_per_kWdc` and `opex_per_kWdc_per_year`. From the ATB workbook, a value for `capex_per_kWdc` can be found on the `Solar - PV Dist. Comm` or `Solar - PV Dist. Res` sheet under the "Overnight Capital Cost" section or the "CAPEX" section. The values in the "CAPEX" section include overnight capital costs, construction finance factor, and grid connection costs. A value for `opex_per_kWdc_per_year` can be found on the `Solar - PV Dist. Comm` or `Solar - PV Dist. Res` sheet under the "Fixed Operation and Maintenance Expenses" section.

```{note}
Since the commercial and residential PV values in the ATB are in kW-DC the parameter `pv_capacity_kWdc` should be included in the `shared_parameters` when using the `PYSAMSolarPlantPerformanceModel` and `ATBResComPVCostModel` models.
```

Here is an example of how to use the `ATBResComPVCostModel` model in the `tech_config.yaml` file:

```yaml
technologies:
  solar:
    performance_model:
      model: "PYSAMSolarPlantPerformanceModel"
    cost_model:
      model: "ATBResComPVCostModel"
    model_inputs:
        shared_parameters:
            pv_capacity_kWdc: 200
        performance_parameters:
            dc_ac_ratio: 1.23
            create_model_from: "default"
            config_name: "PVWattsCommercial"
        cost_parameters:
            capex_per_kWdc: 1439
            opex_per_kWdc_per_year: 16
```
