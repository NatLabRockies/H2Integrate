# Nitrogen Air Separation Unit

`SimpleASUPerformanceModel` is a linear model for producing nitrogen from air. It can size from a
configured nitrogen demand, or use a rated nitrogen production or electrical power input. It also
calculates air feed, oxygen and argon co-products, and electricity use. Its `efficiency_kWh_pr_kg_N2`
is expressed in kWh per kg of nitrogen; the model documentation gives representative values of
0.119 for cryogenic separation and 0.29 for pressure swing adsorption.

With `size_from_N2_demand: true`, connect `nitrogen_in` as the demand profile and the model reports
the required `electricity_in`. With it set to `false`, provide `electricity_in` and specify either
`rated_N2_kg_pr_hr` or `ASU_rated_power_kW`. The model supports one-hour time steps.

`SimpleASUCostModel` calculates capital and operating expenses using a cost per nitrogen capacity
or a cost per power capacity. `capex_unit` must identify the basis; when `opex_usd_per_unit_per_year`
is nonzero, set `opex_unit` as well.

```{eval-rst}
.. autoclass:: h2integrate.converters.nitrogen.simple_ASU.SimpleASUPerformanceConfig
   :members:
   :no-index:

.. autoclass:: h2integrate.converters.nitrogen.simple_ASU.SimpleASUCostConfig
   :members:
   :no-index:
```
