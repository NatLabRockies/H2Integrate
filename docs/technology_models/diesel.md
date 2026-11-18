# Diesel Generator Model

The {py:class}`~h2integrate.converters.diesel.diesel_generator.DieselGeneratorPerformanceModel`
converts diesel fuel to electricity, bounded by the generator rating and requested output. The
{py:class}`~h2integrate.converters.diesel.diesel_generator.DieselGeneratorCostModel` calculates
capital and operating costs. Both models support one-hour time steps.

## Performance

{py:class}`~h2integrate.converters.diesel.diesel_generator.DieselGeneratorPerformanceConfig`
provides the defaults for the capacity and heat-rate OpenMDAO inputs. The other inputs are
`diesel_in` (US gallons/hour) and
`electricity_command_value` (kW), which defaults to the configured capacity. The model caps the
requested electricity and available fuel at the generator rating, then converts the smaller
available fuel amount to electricity using the heat rate.

The primary outputs are `electricity_out` and `unmet_electricity_demand` (kW), and
`diesel_consumed` (US gallons/hour). Inherited outputs include rated, total and annual electricity
production, capacity factor, operational life, and replacement schedule.

```{eval-rst}
.. autoclass:: h2integrate.converters.diesel.diesel_generator.DieselGeneratorPerformanceConfig
   :no-members:
   :no-index:
```

## Cost

{py:class}`~h2integrate.converters.diesel.diesel_generator.DieselGeneratorCostModelConfig`
provides capacity and per-unit costs as defaults for OpenMDAO inputs, alongside the performance
model's `electricity_out` profile.
The cost model reports `CapEx` as generator capacity times `capex_per_kw`, plus the configured
`capex_battery_total`. It reports `OpEx` as fixed O&M plus variable O&M on electricity generated
during the simulation; it does not annualize that variable term for partial-year simulations.
Fuel costs are supplied separately by a diesel feedstock component.

```{eval-rst}
.. autoclass:: h2integrate.converters.diesel.diesel_generator.DieselGeneratorCostModelConfig
   :no-members:
   :no-index:
```
