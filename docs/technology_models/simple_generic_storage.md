# Simple Generic Storage Model

The Simple Generic Storage model provides a flexible framework for modeling various types of energy storage systems in H2Integrate. While particularly useful for battery storage, this model can be used to simulate the storage of different resources including hydrogen, CO2, or any other commodity.

## Overview

The Simple Generic Storage model consists of two main components:

1. **SimpleGenericStorage**: A minimal component that defines the input interface for the storage system
2. **DemandOpenLoopStorageController**: The core logic component that handles storage operations, state of charge calculations, and resource management

This architecture allows the storage system to work with any resource type by simply configuring the resource name and units, making it quite versatile.

## Example Applications

### Battery Storage (Example 19)

Example 19 demonstrates a wind-battery dispatch system that showcases the Simple Generic Storage model in action. This example:

- Models a wind farm providing variable electricity generation
- Uses battery storage with defined capacity and charge/discharge rates
- Implements demand-based control with a constant electricity demand
- Demonstrates realistic battery operations including state of charge management and curtailment

The example produces detailed plots showing:
- Battery state of charge over time
- Electricity flows (input, output, curtailed, missed load)
- How the storage system balances variable wind generation with constant demand

### Hydrogen Storage

The model can be configured for hydrogen storage systems by setting:
```yaml
commodity_name: "hydrogen"
commodity_units: "kg/h" # commodity_units must by a rate
max_capacity: 1000.0  # kg
```

This is useful for modeling hydrogen production from electrolyzers with variable renewable input and steady hydrogen demand for industrial processes.

### CO2 Storage

For carbon capture and utilization systems:
```yaml
commodity_name: "co2"
commodity_units: "kg/h"
max_capacity: 50000.0  # kg
```

This enables modeling of CO2 capture systems with temporary storage before utilization or permanent sequestration.
