# Solar-PV Cost Models based on ATB-Formatted Cost Data

NLR's [Annual Technology Baseline (ATB)](https://atb.nlr.gov) is commonly referenced for technology costs such as overnight capital cost, fixed operations and maintenance costs, and capital expenditures. Two solar-PV cost models are available in H2I that are intended to be easily used with cost values pulled from [NLR's ATB Excel workbook](https://atb.nlr.gov/electricity/2024/data).

```{note}
The Annual Technology Baseline (ATB) is updated annually. While we do our best to update our documentation regularly, be sure that you're using the most recent version of the ATB in case our links are pointing to an older version.
```

As mentioned on the [Utility-Scale PV ATB page](https://atb.nlr.gov/electricity/2024/utility-scale_pv), the costs for utility-scale PV have been published in `$/kW-AC` since 2020. The costs for [Commercial PV](https://atb.nlr.gov/electricity/2024/commercial_pv) and [Residential PV](https://atb.nlr.gov/electricity/2024/residential_pv) are published in `$/kW-DC`. The only difference between the two cost models in H2I are whether costs are input in `$/kW-AC` or `$/kW-DC`.

- The `"ATBUtilityPVCostModel"` model has costs input in `$/kW-AC` to match the ATB and the outputted capacity in kW-AC from the PV performance model. Example usage of this cost model in the `tech_config.yaml` file is shown [in the first section below](#utility-scale-pv-cost-model).
- The `"ATBResComPVCostModel"` model has costs input in `$/kW-DC` and the PV capacity is input in kW-DC from the **shared input parameter** of the PV performance model. Example usage of this cost model in the `tech_config.yaml` file is shown [in the second section below](#commercial-and-residential-pv-cost-model).

The APIs are {py:class}`~h2integrate.converters.solar.atb_utility_pv_cost.ATBUtilityPVCostModel`
and {py:class}`~h2integrate.converters.solar.atb_utility_pv_cost.ATBUtilityPVCostModelConfig`, and
{py:class}`~h2integrate.converters.solar.atb_res_com_pv_cost.ATBResComPVCostModel` and
{py:class}`~h2integrate.converters.solar.atb_res_com_pv_cost.ATBResComPVCostModelConfig`.
Both support one-hour time steps and multiply their capacity input by the configured cost rates to
produce `CapEx` and annual `OpEx`. The inputs are `system_capacity_AC` for utility PV and
`system_capacity_DC` for residential and commercial PV.

(utility-scale-pv-cost-model)=
## Utility-Scale PV Cost Model

From the ATB workbook, capital and fixed operating costs can be found on the `Solar - Utility PV`
sheet under the "Overnight Capital Cost" or "CAPEX" and "Fixed Operation and Maintenance
Expenses" sections. The "CAPEX" values include overnight capital costs, construction finance
factor, and grid connection costs. The model accepts these costs through:

```{eval-rst}
.. autoclass:: h2integrate.converters.solar.atb_utility_pv_cost.ATBUtilityPVCostModelConfig
   :no-members:
   :no-index:
```

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

The corresponding ATB workbook sheets are `Solar - PV Dist. Comm` and `Solar - PV Dist. Res`;
the cost categories are the same as for utility PV. Configure the model using:

```{eval-rst}
.. autoclass:: h2integrate.converters.solar.atb_res_com_pv_cost.ATBResComPVCostModelConfig
   :no-members:
   :no-index:
```

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
