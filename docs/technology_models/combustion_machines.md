# Thermodynamically-driven power plant models

In addition to heat-rate-based NG plant models, H2Integrate optionally provides fuel-generic, thermodynamic models of combustion machines.

Presently, only simple-cycle combustion turbine power plants are available.

## Simple-cycle combustion turbine models

The {py:class}`~h2integrate.converters.combustion_machines.turbine_simple_cycle.SimpleCycleTurbinePerformanceModel`
uses the surface-level resource data provided by the solar database, a specified turbine design, and (permitted fractional) turbine count to represent the performance of a simple-cycle combustion turbine plant.
Its {py:class}`~h2integrate.converters.combustion_machines.turbine_simple_cycle.SimpleCycleTurbinePerformanceModelConfig` requires
`turbine_capacity_mw`, `flowrate_max_fluid_cubic_m_per_s`, `pressure_ratio`, `firing_temp_C`, `isentropic_efficiency_compressor`, `isentropic_efficiency_turbine`, `generator_efficiency`, `generator_oversize_ratio`, and `fuel_source`;
optionally, `num_turbines` can also be provided.
In `examples/38_natural_gas_statistical`, users can find an example that highlights the impacts of the thermodynamically-aware modeling approach in terms of the variability of the output that can result.

The OpenMDAO inputs are `num_turbines`, `turbine_capacity` (MW), `generator_oversize_ratio` (-), `electricity_command_value` (MW, defaults to capacity), `flowrate_max_fluid` (m^3/s), and `{fuel_source}_in` (kJ/s);
the `solar_resource_data` discrete input is also required for surface level atmospheric conditions.
Output is limited by the command, maximum volumetric flowrate, and available generator capacity.
It reports `{fuel_source}_consumed` (kJ/s), `unmet_electricity_demand` (MW), `electricity_headroom` (MW), and `system_capacity` (MW), and the inherited production and lifetime outputs.
The model supports one-hour timesteps, although analyses should be possible down to ramp rate-limited operation, and optional [reliability modeling](../reliability/reliability_guide.md).

### Configuration

```{eval-rst}
.. autoclass:: h2integrate.converters.combustion_machines.turbine_simple_cycle.SimpleCycleTurbinePerformanceConfig
   :no-members:
   :no-index:
```
