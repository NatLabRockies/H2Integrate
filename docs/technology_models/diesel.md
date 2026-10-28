# Diesel Generator Model

The {py:class}`~h2integrate.converters.diesel.diesel_generator.DieselGeneratorPerformanceModel`
converts diesel fuel to electricity, bounded by the generator rating and requested output. The
{py:class}`~h2integrate.converters.diesel.diesel_generator.DieselGeneratorCostModel` calculates
capital and operating costs. Both models support one-hour time steps.

## Performance

{py:class}`~h2integrate.converters.diesel.diesel_generator.DieselGeneratorPerformanceConfig`
requires `system_capacity_kw` (kW) and `heat_rate_gal_per_mwh` (US gallons/MWh). These are also
OpenMDAO inputs. The other inputs are `diesel_in` (US gallons/hour) and
`electricity_command_value` (kW), which defaults to the configured capacity. The model caps the
requested electricity and available fuel at the generator rating, then converts the smaller
available fuel amount to electricity using the heat rate.

The primary outputs are `electricity_out` and `unmet_electricity_demand` (kW), and
`diesel_consumed` (US gallons/hour). Inherited outputs include rated, total and annual electricity
production, capacity factor, operational life, and replacement schedule.

## Cost

{py:class}`~h2integrate.converters.diesel.diesel_generator.DieselGeneratorCostModelConfig`
requires `system_capacity_kw`, `capex_per_kw`, `capex_battery_total`,
`fixed_opex_per_kw_per_year`, `variable_opex_per_kwh`, and `cost_year`. The capacity and per-unit
costs are also OpenMDAO inputs, along with the performance model's `electricity_out` profile.
The cost model reports `CapEx` as generator capacity times `capex_per_kw`, plus the configured
`capex_battery_total`. It reports `OpEx` as fixed O&M plus variable O&M on electricity generated
during the simulation; it does not annualize that variable term for partial-year simulations.
Fuel costs are supplied separately by a diesel feedstock component.
