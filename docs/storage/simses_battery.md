(simses-battery-performance)=
# SimSES Battery Model

H2Integrate's `SimSESBatteryPerformanceModel` wraps the stateful battery and converter models from [SimSES](https://github.com/SimSES/SimSES). It adds H2I integration for container thermal behavior, HVAC control, ambient solar-resource data, safety interlocks, and battery degradation.

Use `SimSESBatteryPerformanceModel` as the battery `performance_model` in a technology configuration. Example 38 demonstrates a complete H2I setup with the optimized Pyomo storage controller and Exclusive Control Months:

[`examples/38_battery_degradation`](../../examples/38_battery_degradation/38_battery_degradation.yaml)

## H2I additions

The model builds a large-format LFP cell by scaling SimSES's `SonyLFP` model, then configures the SimSES battery pack and fixed-efficiency converter. H2I also supplies:

- Calendar and cyclic degradation models with a configurable `deg_scale`.
- A layered container thermal model coupled to the battery as a thermal node.
- A variable-COP HVAC heat pump model and thermostat with configurable setpoint, deadband, and power limit.
- Solar heat gain from site latitude, longitude, container azimuth, and global horizontal irradiance.
- A battery-temperature interlock that commands zero power outside the configured safe battery temperature range.
- A stateful `simulate()` callback so Pyomo controllers can dispatch the battery over rolling windows while preserving SimSES state between windows.

Container geometry and layer properties are currently fixed in the component. HVAC settings, battery-safe temperature limits, converter settings, pack topology, and degradation parameters are configurable through `model_inputs.performance_parameters`.

## Resource and dispatch inputs

Connect a solar resource to the battery's `solar_resource_data` input. The resource dictionary must contain time series for:

- `temperature`: ambient dry-bulb temperature in degrees Celsius.
- `ghi`: global horizontal irradiance in watts per square metre.

Connect site latitude and longitude to the battery as well; they are used to calculate solar heat gain.

For open-loop dispatch, the storage command uses H2I sign convention: positive values discharge the battery and negative values charge it. With a feedback controller, H2I invokes the battery's stateful simulation callback once per controller window. Charging commands are limited by battery rate, state-of-charge headroom, and available `electricity_in`.

The component supports plant timesteps from 60 to 3600 seconds. However, the underlying SimSES model required timesteps <= 60 seconds. Its thermal solver internally substeps to maintain stability at larger plant timesteps.

When capacity SOH reaches `eol_soh_capacity`, the performance model replaces the SimSES battery
with a fresh instance using the configured initial SOC and temperature. Capacity SOH,
resistance SOH, and SOC at that sample describe the fresh battery; callback SOC and output
SOC agree. Power, losses, heat, voltage, current, and temperature still describe the executed
timestep on the outgoing battery. The container thermal state is retained, including across
controller windows.

The shared annualization helper detects replacement events from upward capacity-SOH jumps
greater than `1e-9`, at elapsed offsets `sample_index * dt`. These offsets are sample
conventions, not interpolated physical threshold-crossing times. SOH alone cannot reliably
identify a first-sample replacement or a reset without an upward jump, including replacement
at every sample with constant fresh SOH. Such invisible events are not separately counted.

The H2I `replacement_schedule` contains integer-valued event counts in fixed 365-day plant-year
bins `[year, year + 1)`, excluding initial installation and plant retirement. Multiple
observable replacements within a year are counted separately. Annual capacity-factor means
retain their elapsed durations, including partial simulated years, on the same cycle clock
as replacement events. The trailing cycle uses the last two post-reset SOH samples to
project annual degradation. Projected EOL occurs at the end of the first full projected
annual interval reaching the threshold, not at an interpolated fractional-year crossing.
Fewer than two post-reset samples or stalled degradation do not imply a projected EOL.
ProFAST applies the configured `replacement_cost_percent` to this schedule when calculating
replacement capital costs; initial ATB battery capital costs are unchanged.

## Outputs

In addition to standard H2I storage outputs (`electricity_out`, charge/discharge streams, SOC, capacity factors, and replacement schedule), the model exposes diagnostic time series for voltage, current, cell temperature, capacity and resistance SOH, AC/DC power, battery loss and heat, converter loss, container temperatures, solar heat gain, HVAC thermal/electrical power, and thermal derating.
