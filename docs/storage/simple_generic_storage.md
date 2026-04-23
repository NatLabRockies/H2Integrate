(simple-generic-storage-performance)=
# `StoragePerformanceModel` Model

The `StoragePerformanceModel` model provides a flexible framework for modeling various types of energy storage systems in H2Integrate. While particularly useful for battery storage, this model can be used to simulate the storage of different commodities including hydrogen, CO2, or any other commodity.

## Overview

The `StoragePerformanceModel` is a component that defines a simple storage performance model for any defined commodity. This model allows the storage system to work with any commodity type by simply configuring the commodity name and units, making it quite versatile.

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
