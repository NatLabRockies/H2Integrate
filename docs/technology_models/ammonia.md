# Ammonia model

Ammonia is a common fertilizer, and also has the potential to serve as a lower-cost form of hydrogen storage than compressed hydrogen gas. This is typically an energy-intensive process, with the ammonia reactor requiring electricity connected from an electric generator. The primary inputs are hydrogen and air, with the air fed into an air separator to produce nitrogen in an intermediate step, and oxygen as a co-product that is sold to offset opex costs. The ammonia synthesis is highly exothermic, and future versions of this model are planned to connect the generated heat (in the form of steam) to other converters requiring thermal energy as an input. Currently, H2I has two ammonia production models:

1. The simple ammonia model calculates production from configured capacity and capacity factor;
   its cost model uses feedstock-to-ammonia ratios. Its registered models are
   `SimpleAmmoniaPerformanceModel` and `SimpleAmmoniaCostModel`, both defined in
   `h2integrate/converters/ammonia/simple_ammonia_model.py`. This model is based on ASPEN
   modeling performed at Argonne National Lab (ANL) by [Lee et al.](https://doi.org/10.1039/d2gc00843b),
   and was originally developed for H2I by [Reznicek et al.](https://doi.org/10.1016/j.crsus.2025.100338).
   The cost modeling follows these studies. One of the plants included in the Reznicek et al.
   study is shown in `examples/02_texas_ammonia/`.

2. The synloop ammonia model accepts stream-table measurements (or modeled values) from an ammonia synthesis loop as performance parameters. Its registered models are `AmmoniaSynLoopPerformanceModel` in `h2integrate/converters/ammonia/ammonia_synloop_performance.py` and `AmmoniaSynLoopCostModel` in `h2integrate/converters/ammonia/ammonia_synloop_cost.py`. The example in `examples/12_ammonia_synloop/` uses mostly the same parameters as those used by Reznicek et al., but with updated capital costs for the air separator and synthesis loop derived from an NETL baseline study of ammonia production by [Brasington et al.](https://doi.org/10.2172/1515254).

## Simple ammonia configuration

The {py:class}`~h2integrate.converters.ammonia.simple_ammonia_model.SimpleAmmoniaPerformanceModel`
uses the annual plant capacity and capacity factor in
{py:class}`~h2integrate.converters.ammonia.simple_ammonia_model.SimpleAmmoniaPerformanceModelConfig`.
It accepts a `hydrogen_in` profile, but its production calculation does **not** use or limit
production by that profile. It assigns `plant_capacity_kgpy * plant_capacity_factor` to
`total_ammonia_produced`, divides that quantity evenly across the simulated hourly timesteps for
`ammonia_out`, and sets `rated_ammonia_production` to `plant_capacity_kgpy / 8760`. It reports
the configured `capacity_factor` and scales the total by the simulated fraction of a year for
`annual_ammonia_produced`. Consequently, for simulations shorter than a year, the total is still
the configured annual capacity times the capacity factor, not a prorated amount.

The {py:class}`~h2integrate.converters.ammonia.simple_ammonia_model.SimpleAmmoniaCostModel`
uses {py:class}`~h2integrate.converters.ammonia.simple_ammonia_model.SimpleAmmoniaCostModelConfig`
to estimate capital and fixed operating costs. It reports `CapEx`, `OpEx`, component-level costs,
startup-year feedstock and energy costs, and oxygen by-product credits. The `LCOH` input determines
the reported hydrogen startup cost, and `capex_scaling_exponent` determines equipment scaling.
The component also declares `plant_capacity_kgpy` and `plant_capacity_factor` inputs, but its
calculations use the configuration values instead. The startup costs and credits are reported
separately, rather than included in `VarOpEx`.

Both models use one-hour time steps and are demonstrated in
[Example 02: Texas Ammonia](https://github.com/NatLabRockies/H2Integrate/tree/develop/examples/02_texas_ammonia).

```{eval-rst}
.. autoclass:: h2integrate.converters.ammonia.simple_ammonia_model.SimpleAmmoniaPerformanceModelConfig
  :no-members:
  :no-index:

.. autoclass:: h2integrate.converters.ammonia.simple_ammonia_model.SimpleAmmoniaCostModelConfig
  :no-members:
  :no-index:
```

## Synloop configuration and interface

The {py:class}`~h2integrate.converters.ammonia.ammonia_synloop_performance.AmmoniaSynLoopPerformanceModel`
uses {py:class}`~h2integrate.converters.ammonia.ammonia_synloop_performance.AmmoniaSynLoopPerformanceConfig`
to describe capacity, energy and feed requirements, purge gas composition, and optional operating
constraints. Hydrogen and nitrogen are supplied in kg/h and electricity in kW. The model reports
ammonia production, unused feeds, electricity, heat, feed consumption, limiting input, catalyst
mass and aggregate production and consumption. An ammonia command input is present when
system-level control is configured. See the [dynamic operating constraints](ammonia_synloop_dynamics.md)
guide for turndown, ramping and startup behavior.

The per-timestep `hydrogen_consumed`, `nitrogen_consumed`, and `electricity_consumed` outputs
track actual consumption, but the corresponding `total_*_consumed` outputs currently sum the
supplied inputs, including any unused feed. The `heat_out` value is production multiplied by
the configured heat output, although its declared OpenMDAO unit is `kW*h/kg`.

The {py:class}`~h2integrate.converters.ammonia.ammonia_synloop_cost.AmmoniaSynLoopCostModel`
uses {py:class}`~h2integrate.converters.ammonia.ammonia_synloop_cost.AmmoniaSynLoopCostConfig`
to scale baseline capital and operating costs to the rated capacity and target dollar year. Its
OpenMDAO inputs are `rated_ammonia_production` and `annual_ammonia_produced`; it reports `CapEx`,
`OpEx` and detailed cost components. Both synloop models use one-hour time steps.

```{eval-rst}
.. autoclass:: h2integrate.converters.ammonia.ammonia_synloop_performance.AmmoniaSynLoopPerformanceConfig
   :no-members:
   :no-index:

.. autoclass:: h2integrate.converters.ammonia.ammonia_synloop_cost.AmmoniaSynLoopCostConfig
   :no-members:
   :no-index:
```

## Synloop purge gas output

The Synloop Ammonia Model exposes the purge gas exiting the synthesis loop as a **multivariable stream** called `process_gas_mixture`. This is a general-purpose stream type for process gas mixtures that can be reused by other components. It bundles seven constituent variables into a single connection type:

| Variable | Units | Description |
|---|---|---|
| `mass_flow` | kg/h | Total gas mass flow rate |
| `hydrogen_mass_fraction` | unitless | Mass fraction of hydrogen in the gas stream |
| `nitrogen_mass_fraction` | unitless | Mass fraction of nitrogen in the gas stream |
| `argon_mass_fraction` | unitless | Mass fraction of argon in the gas stream |
| `ammonia_mass_fraction` | unitless | Mass fraction of ammonia in the gas stream |
| `temperature` | K | Gas stream temperature |
| `pressure` | bar | Gas stream pressure |

The purge gas composition is determined by the `purge_gas_x_h2`, `purge_gas_x_n2`, `purge_gas_x_ar`, and `purge_gas_x_nh3` molar fractions in the performance config, which are converted to mass fractions using the molecular weights of all species. The total purge gas mass flow is `purge_gas_mass_ratio × ammonia_produced`.

The `hydrogen_out` and `nitrogen_out` outputs of the synloop model represent only the **unused feedstock** that was available but not consumed. Purge gas hydrogen and nitrogen are reported separately through the `process_gas_mixture` stream. This separation allows downstream components (such as a hydrogen recovery unit or a recycle loop) to receive the purge gas as a distinct physical stream with its own temperature, pressure, and composition.

To connect the purge gas to a downstream consumer at the plant level, add a single interconnection line:

```yaml
technology_interconnections:
  - [ammonia, purge_gas_consumer, process_gas_mixture]
```

The framework handles connecting all constituent variables automatically. See `examples/32_multivariable_streams/` for a general example of multivariable stream connections.
