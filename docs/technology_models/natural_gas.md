# Natural gas power plant models

H2Integrate provides a heat-rate-based natural gas plant and a separate simple-cycle turbine
model. Both accept natural gas energy and produce electricity, but they use different
performance assumptions.

## Heat-rate-based plant

The {py:class}`~h2integrate.converters.natural_gas.natural_gas_cc_ct.NaturalGasPerformanceModel`
uses the configured capacity and heat rate to represent either a combustion turbine or a
combined-cycle plant. Its
{py:class}`~h2integrate.converters.natural_gas.natural_gas_cc_ct.NaturalGasPerformanceConfig`
requires `system_capacity_mw` and `heat_rate_mmbtu_per_mwh`.

The OpenMDAO inputs are `system_capacity` (MW), `heat_rate_mmbtu_per_mwh` (MMBtu/MWh),
`natural_gas_in` (MMBtu/h), and `electricity_command_value` (MW, defaulting to the configured
capacity). Output is limited by the command, fuel availability, and available capacity.
It reports `electricity_out`, `natural_gas_consumed`, `unmet_electricity_demand`,
`electricity_headroom_out`, and the inherited production and lifetime outputs. The model
supports one-hour time steps and optional [reliability modeling](../reliability/reliability_guide.md).

The {py:class}`~h2integrate.converters.natural_gas.natural_gas_cc_ct.NaturalGasCostModel` uses
{py:class}`~h2integrate.converters.natural_gas.natural_gas_cc_ct.NaturalGasCostModelConfig`.
It accepts `rated_electricity_production`, `electricity_out`, `capex_per_kw`,
`fixed_opex_per_kw_per_year`, and `variable_opex_per_mwh` as inputs, and reports `CapEx` and
`OpEx`. `OpEx` combines annual fixed O&M and variable O&M on electricity generated during the
simulation; the variable term is not annualized for a partial-year simulation. Fuel costs are
handled separately by a feedstock model. The cost model supports one-hour time steps.

### Configuration

```{eval-rst}
.. autoclass:: h2integrate.converters.natural_gas.natural_gas_cc_ct.NaturalGasPerformanceConfig
   :no-members:
   :no-index:

.. autoclass:: h2integrate.converters.natural_gas.natural_gas_cc_ct.NaturalGasCostModelConfig
   :no-members:
   :no-index:
```

## Simple-cycle turbine

The simple cycle turbine found in [combustion_machines.md](./combustion_machines.md) can be configured by setting `fuel_source` to `natural_gas`, and using the appropriate commodity supply.
