# Grid Performance and Cost Models

This page documents the unified `grid_performance` and `grid_cost` models, which together represent a flexible, configurable grid interconnection point within an H2I simulation.
These components support both power flows and cost accounting for buying and selling electricity through a constrained interconnection.
This is a single model that can be configured to either sell electricity to the grid, buy electricity from the grid, or both.

See `example/24_solar_battery_grid` to see how to set up both buying and selling grid components.

## Grid Performance
`grid_performance` represents a grid interconnection point that can buy or sell electricity subject to a maximum throughput rating (interconnection_size).

It supports:
- Buying electricity from the grid to meet downstream demand.
- Selling electricity to the grid.
- Enforcing maximum allowed interconnection power.
- Computing unmet demand and unsold electricity due to constraints.

```{note}
Multiple grid instances may be used within the same plant to represent different interconnection nodes. For buying electricity from the grid, the technology name in the `tech_config` **must** start with `grid_buy` for the logic to work appropriately in financial calculations.
```

**Inputs**
| Name                     | Shape              | Units | Description                                                       |
| ------------------------ | ------------------ | ----- | ----------------------------------------------------------------- |
| `interconnection_size`   | scalar             | kW    | Maximum power capacity for grid connection.                       |
| `electricity_in`         | array[n_timesteps] | kW    | Electricity flowing into the grid (selling to grid).              |
| `electricity_demand`     | array[n_timesteps] | kW    | Electricity demand from downstream technologies.                  |

**Outputs**
| Name                       | Shape              | Units | Description                                                         |
| -------------------------- | ------------------ | ----- | ------------------------------------------------------------------- |
| `electricity_out`          | array[n_timesteps] | kW    | Electricity flowing *out of* the grid (buying).                     |
| `electricity_sold`         | array[n_timesteps] | kW    | Electricity successfully sold to the grid.                          |
| `electricity_unmet_demand` | array[n_timesteps] | kW    | Downstream technology demand not met due to interconnection limits. |
| `electricity_excess`     | array[n_timesteps] | kW    | Electricity that could not be sold due to limits.                   |

## Grid Cost
`grid_cost` computes all costs and revenues associated with the grid interconnection, including:
- Capital cost based on interconnection rating.
- Fixed annual O&M.
- Variable cost of electricity purchased.
- Revenue from electricity sold.

**Inputs**
| Name                            | Shape                        | Units     | Description                                                            |
| ------------------------------- | ---------------------------- | --------- | ---------------------------------------------------------------------- |
| `interconnection_size`          | scalar                       | kW        | Interconnection capacity for cost calculation.                         |
| `interconnection_capex_per_kw`  | scalar                       | $/kW      | Capital cost per kW of interconnection.                                |
| `interconnection_opex_per_kw`   | scalar                       | $/kW/year | Annual O&M cost per kW of interconnection.                             |
| `fixed_interconnection_cost`    | scalar                       | $         | One-time fixed cost regardless of size.                                |
| `electricity_out`               | array[n_timesteps]           | kW        | Electricity flowing out of grid (buying from grid).                    |
| `electricity_buy_price`         | scalar/array[n_timesteps]    | $/kWh     | Price to buy electricity from grid (optional, time-varying supported). |
| `electricity_sold`              | array[n_timesteps]           | kW        | Electricity flowing into grid (selling to grid).                       |
| `electricity_sell_price`        | scalar/array[n_timesteps]    | $/kWh     | Price to sell electricity to grid (optional, time-varying supported).  |

**Outputs**
| Name      | Description                                                                                                     |
| --------- | --------------------------------------------------------------------------------------------------------------- |
| `CapEx`   | Total capital expenditure.                                                                                      |
| `OpEx`    | Annual O&M cost.                                                                                                |
| `VarOpEx` | Variable operating expenses (buying), revenues (selling), or net of expenses and revenues (buying and selling). |

The **costs** of purchasing electricity from the grid are represented as a variable operating expense (`VarOpEx`) and are represented as a positive value. This allows it to be tracked as an expense in the financial models.

The **revenue** of selling electricity to the grid is represented as a variable operating expense (`VarOpEx`) and a represented as a negative value. This is allows it to be tracked as a coproduct in the financial models.

```{note}
If you're using a price-maker financial model (e.g., calculating the LCOE) and selling all of the electricity to the grid, then the `electricity_sell_price` should most likely be set to 0. since you want to know the breakeven price of selling that electricity.
```
