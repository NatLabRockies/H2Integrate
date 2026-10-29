# Hydrogen Steam Methane Reformer (SMR) Model

This module implements performance and cost models for a steam methane reformer (SMR) hydrogen production plant. The model converts natural gas and electricity inputs into hydrogen output subject to plant capacity constraints and feedstock availability.

The implementation consists of two components:
1. {py:class}`~h2integrate.converters.hydrogen.steam_methane_reformer.SteamMethaneReformerPerformanceModel`
   calculates hydrogen production and energy consumption over time, configured by
   {py:class}`~h2integrate.converters.hydrogen.steam_methane_reformer.SteamMethaneReformerPerformanceConfig`.
2. {py:class}`~h2integrate.converters.hydrogen.steam_methane_reformer.SteamMethaneReformerCostModel`
   computes capital and operating costs, configured by
   {py:class}`~h2integrate.converters.hydrogen.steam_methane_reformer.SteamMethaneReformerCostModelConfig`.

The model is designed to integrate with the `h2integrate` framework and follows the standard configuration and model structure used for performance and cost models.

## Model Overview

Steam methane reforming is a thermochemical process where methane reacts with steam to produce hydrogen and carbon monoxide, followed by water-gas shift reactions to increase hydrogen yield.

The simplified representation used in this model assumes:
- Hydrogen production is limited by:
    - SMR rated capacity
    - Natural gas availability
    - Electricity availability
- Energy consumption is modeled using constant intensity parameters:
    - Natural gas consumption per kg of hydrogen
    - Electricity consumption per kg of hydrogen
- Hydrogen demand may be specified and unmet demand is tracked.

## Interface and costs

The performance model takes `natural_gas_in`, `electricity_in`, and
`hydrogen_command_value` time series; the command defaults to configured rated capacity. Its
`system_capacity`, `natural_gas_usage_rate`, and `electricity_usage_rate` inputs default to
their configuration values. It reports `hydrogen_out`, feedstock consumption,
`unmet_hydrogen_demand`, rated and annual hydrogen production, capacity factor, and an equivalent
electrical capacity and energy conversion ratio. It supports one-hour time steps. Although the
configuration permits zero electricity intensity, the calculation divides by this value.

The cost model receives annual hydrogen production, the equivalent rated electrical capacity, and
the total energy conversion ratio. It reports `CapEx`, fixed annual `OpEx`, and annual `VarOpEx`;
the variable cost scales with hydrogen production converted to an energy-equivalent basis.

## Configuration

The performance and cost configurations are generated from their API documentation:

```{eval-rst}
.. autoclass:: h2integrate.converters.hydrogen.steam_methane_reformer.SteamMethaneReformerPerformanceConfig
   :no-members:
   :no-index:

.. autoclass:: h2integrate.converters.hydrogen.steam_methane_reformer.SteamMethaneReformerCostModelConfig
   :no-members:
   :no-index:
```
