# Feedstock Models

Feedstock models in H2Integrate represent any resource input that is consumed by technologies in your plant, such as natural gas, water, electricity from the grid, or any other material input.
The feedstock modeling approach provides a flexible way to track resource consumption and calculate associated costs for any type of input material or energy source.
Please see the example `16_natural_gas` in the `examples` directory for a complete setup using natural gas as a feedstock.

## How Feedstock Models Work

### Two-Component Architecture

Each feedstock type requires two model components:

1. **Performance Model** (`feedstock_performance`):
   - Generates the feedstock supply profile
   - Outputs `{feedstock_type}_out` variable
   - Located at the beginning of the technology chain

2. **Cost Model** (`feedstock_cost`):
   - Calculates consumption costs based on actual usage
   - Takes `{feedstock_type}_consumed` as input
   - Located after all consuming technologies in the chain

### Technology Interconnections

Feedstocks connect to consuming technologies through the `technology_interconnections` in your plant configuration. The connection pattern is:

```yaml
technology_interconnections: [
    ["name_of_feedstock_source", "consuming_technology", "feedstock_type", "connection_type"],
]
```

Where:
- `name_of_feedstock_source`: Name of your feedstock source
- `consuming_technology`: Technology that uses the feedstock
- `feedstock_type`: Type identifier (e.g., "natural_gas", "water", "electricity")
- `connection_type`: Name for the connection (e.g., "pipe", "cable")

## Configuration

To use the feedstock performance and cost models, add an entry to your `tech_config.yaml` like this:

```yaml
ng_feedstock:
    performance_model:
        model: "feedstock_performance"
    cost_model:
        model: "feedstock_cost"
    model_inputs:
        shared_parameters:
        feedstock_type: "natural_gas"
        units: "MMBtu"
        performance_parameters:
        rated_capacity: 100.
        cost_parameters:
        cost_year: 2023
        price: 4.2
        annual_cost: 0.
        start_up_cost: 100000.
```

### Performance Model Parameters

- `feedstock_type` (str): Identifier for the feedstock type (e.g., "natural_gas", "water", "electricity")
- `units` (str): Units for feedstock consumption (e.g., "MMBtu", "kg", "galUS", "MWh")
- `rated_capacity` (float): Maximum feedstock supply rate in `units`/hour

### Cost Model Parameters

- `feedstock_type` (str): Must match the performance model identifier
- `units` (str): Must match the performance model units
- `price` (float, int, or list): Cost per unit in USD/`units`. Can be:
  - Scalar: Constant price for all timesteps and years
  - List: Price per timestep
- `annual_cost` (float, optional): Fixed cost per year in USD/year. Defaults to 0.0
- `start_up_cost` (float, optional): One-time capital cost in USD. Defaults to 0.0
- `cost_year` (int): Dollar year for cost inputs

```{tip}
The `price` parameter is flexible - you can specify constant pricing with a single value or time-varying pricing with an array of values matching the number of simulation timesteps.
```
