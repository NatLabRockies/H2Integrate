# Feedstock Models

Feedstock models in H2Integrate represent any resource input that is consumed by technologies in your plant that comes from outside your designed system boundary (and not generated internally), such as natural gas, water, electricity from the grid, or any other material input.
The feedstock modeling approach provides a flexible way to track resource consumption and calculate associated costs for any type of input material or energy source.
Please see the example `16_natural_gas` in the `examples` directory for a complete setup using natural gas as a feedstock.

## How Feedstock Models Work

### Two-Component Architecture

Each feedstock type requires two model components:

1. **Performance Model** (`FeedstockPerformanceModel`):
   - Generates the feedstock supply profile
   - Outputs `{commodity}_out` variable
   - Located at the beginning of the technology chain

2. **Cost Model** (`FeedstockCostModel`):
   - Calculates consumption costs based on actual usage
   - Takes `{commodity}_consumed` as input
   - Located after all consuming technologies in the chain
   - Calculates the capacity factor of the consumed feedstock

### Technology Interconnections

Feedstocks connect to consuming technologies through the `technology_interconnections` in your plant configuration. The connection pattern is:

```yaml
technology_interconnections: [
    ["name_of_feedstock_source", "consuming_technology", "commodity", "connection_type"],
]
```

Where:
- `name_of_feedstock_source`: Name of your feedstock source
- `consuming_technology`: Technology that uses the feedstock
- `commodity`: Type identifier (e.g., "natural_gas", "water", "electricity")
- `connection_type`: Name for the connection (e.g., "pipe", "cable")

## Configuration

To use the feedstock performance and cost models, add an entry to your `tech_config.yaml` like this:

```yaml
ng_feedstock:
    performance_model:
        model: "FeedstockPerformanceModel"
    cost_model:
        model: "FeedstockCostModel"
    model_inputs:
        shared_parameters:
            commodity: "natural_gas"
            commodity_rate_units: "MMBtu/h"
        performance_parameters:
            rated_capacity: 100.
        cost_parameters:
            commodity_amount_units: "MMBtu" # optional, if not specified defaults to `commodity_rate_units*h`
            cost_year: 2023
            price: 4.2 # cost in USD/commodity_amount_units
            annual_cost: 0. #cost in USD/year
            start_up_cost: 100000. #cost in USD
```

### Performance Model Parameters

- `commodity` (str): Identifier for the feedstock type (e.g., "natural_gas", "water", "electricity")
- `commodity_rate_units` (str): commodity_rate_units for feedstock consumption (e.g., "MMBtu/h", "kg/h", "galUS/h", or "MW")
- `rated_capacity` (float): Maximum feedstock supply rate in `commodity_rate_units`

### Cost Model Parameters

- `commodity` (str): Must match the performance model identifier
- `commodity_rate_units` (str): Must match the performance model commodity_rate_units
- `price` (float, int, or list): Cost per unit in `USD/commodity_amount_units`. Can be:
  - Scalar: Constant price for all timesteps and years
  - List: Price per timestep
- `annual_cost` (float, optional): Fixed cost per year in USD/year. Defaults to 0.0
- `start_up_cost` (float, optional): One-time capital cost in USD. Defaults to 0.0
- `cost_year` (int): Dollar year for cost inputs
- `commodity_amount_units` (str | None, optional): the amount units of the commodity (i.e., "MMBtu", "kg", "galUS" or "kW*h"). If None, will be set as `commodity_rate_units*h`

```{tip}
The `price` parameter is flexible - you can specify constant pricing with a single value or time-varying pricing with an array of values matching the number of simulation timesteps.
```

### Consumed Feedstock Outputs
The feedstock model outputs cost and performance information about the consumed feedstock. The most notable outputs are:
- `VarOpEx`: cost of the feedstock consumed (in `USD/yr`)
- `total_{commodity}_consumed`: total feedstock consumed over simulation (in `commodity_amount_units`)
- `annual_{commodity}_consumed`: annual feedstock consumed (in `commodity_amount_units/yr`)
- `rated_{commodity}_production`: this is equal to the the `rated_capacity` of the feedstock model (in `commodity_rate_units`)
- `capacity_factor`: ratio of the feedstock consumed to the maximum feedstock available
