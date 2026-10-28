(simple-generic-storage-performance)=
# `StoragePerformanceModel` Model

The `StoragePerformanceModel` model provides a flexible framework for modeling various types of energy storage systems in H2Integrate. While particularly useful for battery storage, this model can be used to simulate the storage of different commodities including hydrogen, CO2, or any other commodity.

## Overview

The `StoragePerformanceModel` is a component that defines a simple storage performance model for any defined commodity. This model allows the storage system to work with any commodity type by simply configuring the commodity name and units, making it quite versatile.

## Configuration and operation

The performance model is
{py:class}`~h2integrate.storage.storage_performance_model.StoragePerformanceModel`, configured by
{py:class}`~h2integrate.storage.storage_performance_model.StoragePerformanceModelConfig`.
It supports time steps from 1 second to 1 hour and can be used in time-marching simulations.
The configuration reference is embedded below:

```{eval-rst}
.. autoclass:: h2integrate.storage.storage_performance_model.StoragePerformanceModelConfig
   :members:
   :no-index:
```

The model receives `{commodity}_in`, `max_charge_rate`, `storage_capacity`, and, when rates
differ, `max_discharge_rate`. With open-loop control it also receives
`{commodity}_command_value`; negative commands request charging and positive commands request
discharging. With feedback dispatch it instead receives `{commodity}_set_point` and a discrete
`pyomo_dispatch_solver`. Actual flows are limited by the command, storage limits and available
commodity for charging, with efficiency losses applied.

In addition to the {ref}`common storage outputs <storage-performance-outputs>`,
the model reports `{commodity}_charge_demand` and `{commodity}_headroom`, estimates of the
available charge and discharge rates based on the state of charge at the end of each timestep.
`SOC` is reported as a percentage.

The optional {py:class}`~h2integrate.storage.generic_storage_cost.GenericStorageCostModel` uses
{py:class}`~h2integrate.storage.generic_storage_cost.GenericStorageCostConfig`. It accepts
`storage_capacity`, `max_charge_rate`, `capacity_capex`, `charge_capex`, and `opex_fraction`
as OpenMDAO inputs and reports `CapEx` and annual `OpEx`. It computes storage duration in hours
as capacity divided by charge rate, then calculates
`CapEx = (duration * capacity_capex + charge_capex) * max_charge_rate` and
`OpEx = opex_fraction * CapEx`. Its supported time step is one hour. Cost rate units are
restricted to the units listed in its configuration reference.

```{eval-rst}
.. autoclass:: h2integrate.storage.generic_storage_cost.GenericStorageCostConfig
   :members:
   :no-index:
```

## Example Applications

### Battery Storage (Example 19)

Example 19 demonstrates a wind-battery dispatch system that showcases the `StoragePerformanceModel` model in action. This example:

- Models a wind farm providing variable electricity generation
- Uses battery storage with defined capacity and charge/discharge rates
- Implements demand-based control with a constant electricity demand
- Demonstrates realistic battery operations including state of charge management and curtailment

The example produces detailed plots showing:
- Battery state of charge over time
- Electricity flows (input, output)
- How the storage system balances variable wind generation with constant demand

### Hydrogen Storage

The model can be configured for hydrogen storage systems by setting:
```yaml
commodity: "hydrogen"
commodity_rate_units: "kg/h"
max_capacity: 1000.0  # kg
commodity_amount_units: "kg"
```

This is useful for modeling hydrogen production from electrolyzers with variable renewable input and steady hydrogen demand for industrial processes.

### CO2 Storage

For carbon capture and utilization systems:
```yaml
commodity: "co2"
commodity_rate_units: "kg/h"
commodity_amount_units: "kg"
max_capacity: 50000.0  # kg
```

This enables modeling of CO2 capture systems with temporary storage before utilization or permanent sequestration.
