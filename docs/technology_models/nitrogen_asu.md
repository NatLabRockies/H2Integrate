# Nitrogen Air Separation Unit

{py:class}`~h2integrate.converters.nitrogen.simple_ASU.SimpleASUPerformanceModel`, configured
with {py:class}`~h2integrate.converters.nitrogen.simple_ASU.SimpleASUPerformanceConfig`, is a
linear model for producing nitrogen from air. It can size from a
configured nitrogen demand, or use a rated nitrogen production or electrical power input. It also
calculates air feed, oxygen and argon co-products, and electricity use. Its `efficiency_kWh_pr_kg_N2`
is expressed in kWh per kg of nitrogen; the model documentation gives representative values of
0.119 for cryogenic separation and 0.29 for pressure swing adsorption.

With `size_from_N2_demand: true`, connect `nitrogen_in` as the demand profile and the model reports
the required `electricity_in`. With it set to `false`, provide `electricity_in` and specify either
`rated_N2_kg_pr_hr` or `ASU_rated_power_kW`. The model supports one-hour time steps.

The performance outputs include `nitrogen_out`, `oxygen_out`, `argon_out`, `air_in`,
`rated_nitrogen_production`, `ASU_capacity_kW`, `capacity_factor`, and total and annual nitrogen
production. In the fixed-capacity mode nitrogen production is capped at the rated rate.
`annual_electricity_consumption` is the sum over the simulated period, even for partial-year
simulations, and is declared in kW despite its description referring to kWh/year.

{py:class}`~h2integrate.converters.nitrogen.simple_ASU.SimpleASUCostModel`, configured by
{py:class}`~h2integrate.converters.nitrogen.simple_ASU.SimpleASUCostConfig`, calculates capital
and operating expenses using a cost per nitrogen capacity or a cost per power capacity.
`capex_unit` must identify the basis; when `opex_usd_per_unit_per_year` is positive, set
`opex_unit` as well. The model takes `ASU_capacity_kW` and `rated_nitrogen_production` as inputs
and reports `CapEx` and `OpEx`.

```{eval-rst}
.. autoclass:: h2integrate.converters.nitrogen.simple_ASU.SimpleASUPerformanceConfig
   :members:
   :no-index:

.. autoclass:: h2integrate.converters.nitrogen.simple_ASU.SimpleASUCostConfig
   :members:
   :no-index:
```
