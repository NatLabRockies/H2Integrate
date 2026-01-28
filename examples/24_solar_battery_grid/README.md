# Example 23: Solar Battery Grid System

## Overview

This example demonstrates a solar + battery + grid system that showcases the unified grid component. The system can both buy electricity from the grid and sell excess electricity back to the grid using separate grid connection instances.

## System Description

### Technologies

1. **Solar PV** (200 MWdc)
   - Utility-scale solar with single-axis tracking
   - 1.34 DC/AC ratio
   - 65% bifacial panels
   - Ground coverage ratio: 0.3

2. **Battery Storage** (200 MWh, 25 MW charge/discharge rate)
   - Simple generic storage model
   - Demand-following control strategy (100 MW demand profile)
   - Min SOC: 10%, Max SOC: 100%
   - Charge/discharge efficiency: 100%

3. **Grid Buy** (1000 MW interconnection)
   - Buys electricity from grid to meet unmet demand
   - Purchase price: $0.10/kWh
   - No interconnection costs (set to $0)

4. **Grid Sell** (1000 MW interconnection)
   - Sells excess electricity back to grid
   - Sell price: $0.00/kWh (no revenue in this configuration)
   - No interconnection costs (set to $0)

```{note}
We use two separate grid instances here: one for buying electricity and one for selling electricity so that there is not a feedback loop in the execution order of the technologies. You could use a single grid instance in this case, but it would require resolving the circular coupling using a nonlinear solver on the model. We generally recommend using separate grid instances for buying and selling to avoid this complexity, though this may vary based on your plant architecture.
```

## Key Features Demonstrated

### Unified Grid Component

The grid component in this example is designed to handle both electricity purchases and sales within a single component. This allows for flexible configurations depending on the system's needs.

**Key Features:**
- Single component supports both buying and selling electricity
- Configure only the prices you need (buy, sell, or both)
- Optional interconnection sizing with associated costs
- Multiple grid instances in one plant for different purposes
- Enforces interconnection limits on both buying and selling
- Tracks unmet demand and electricity that couldn't be sold

**Performance Model:**
The grid performance model handles:
- `electricity_in`: Power flowing INTO the grid (selling to grid) - limited by interconnection size
- `electricity_out`: Power flowing OUT OF the grid (buying from grid) - limited by interconnection size
- `electricity_sold`: Actual electricity sold (up to interconnection limit)
- `electricity_unmet_demand`: Demand that couldn't be met due to interconnection limit
- `electricity_excess`: Electricity that couldn't be sold due to interconnection limit

**Cost Model:**
- CapEx: Based on interconnection size ($/kW) plus fixed costs
- OpEx: Annual O&M based on interconnection size ($/kW/year)
- VarOpEx:
  - Positive costs from electricity purchases (if `electricity_buy_price` is set)
  - Negative costs (revenue) from electricity sales (if `electricity_sell_price` is set)
  - Both prices can be scalar or time-varying arrays

### Energy Flow

```
Solar → Battery → [Grid Buy (purchases) | Grid Sell (sales)]
```

- Solar generates electricity
- Battery stores excess and follows 100 MW demand profile
- Grid Buy purchases electricity when battery cannot meet demand (via `electricity_unmet_demand` → `electricity_demand` connection)
- Grid Sell accepts excess electricity when battery has surplus (via `electricity_unused_commodity` → `electricity_in` connection)

### Technology Interconnections

```yaml
technology_interconnections: [
  ["solar", "battery", "electricity", "cable"],
  ["battery", "grid_buy", ["electricity_unmet_demand", "electricity_demand"]],
  ["battery", "grid_sell", ["electricity_unused_commodity", "electricity_in"]]
]
```

**Note:** Each grid instance specifies only the price relevant to its purpose:
- `grid_buy` only sets `electricity_buy_price` (the other is None by default)
- `grid_sell` only sets `electricity_sell_price` (the other is None by default)
- Both prices are optional - set only what you need
