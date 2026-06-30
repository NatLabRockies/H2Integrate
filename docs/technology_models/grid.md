# Grid Performance and Cost Models

This page documents the unified `GridPerformanceModel` and `GridCostModel` models, which together represent a flexible, configurable grid interconnection point within an H2I simulation.
These components support both power flows and cost accounting for buying and selling electricity through a constrained interconnection.
This is a single model that can be configured to either sell electricity to the grid, buy electricity from the grid, or both.

See `example/24_solar_battery_grid` to see how to set up both buying and selling grid components.

## Grid Performance
`GridPerformanceModel` represents a grid interconnection point that can buy or sell electricity subject to a maximum throughput rating (interconnection_size).

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
| `electricity_set_point`     | array[n_timesteps] | kW    | Electricity set point from downstream technologies.                  |

**Outputs**
| Name                       | Shape              | Units | Description                                                         |
| -------------------------- | ------------------ | ----- | ------------------------------------------------------------------- |
| `electricity_out`          | array[n_timesteps] | kW    | Electricity flowing *out of* the grid (buying).                     |
| `electricity_sold`         | array[n_timesteps] | kW    | Electricity successfully sold to the grid.                          |
| `electricity_unmet_demand` | array[n_timesteps] | kW    | Downstream technology demand not met due to interconnection limits. |
| `electricity_excess`     | array[n_timesteps] | kW    | Electricity that could not be sold due to limits.                   |

## Grid Cost
`GridCostModel` computes all costs and revenues associated with the grid interconnection, including:
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
| `electricity_buy_price`         | scalar or array              | $/kWh     | Price to buy electricity from grid (optional). Shape is `n_timesteps` when `buy_price_mode` is `per_timestep`, or `plant_life` when `per_year`. |
| `buy_price_mode`                | string                       | —         | `"per_timestep"` or `"per_year"`. Controls the buy price input shape and cost calculation. |
| `electricity_out`               | array[n_timesteps]           | kW        | Electricity flowing out of grid (buying). Present when `buy_price_mode` is `per_timestep` (or buy price is not set). |
| `annual_electricity_out`        | array[plant_life]            | kWh/yr    | Annual electricity bought from grid. Present when `buy_price_mode` is `per_year`. |
| `electricity_sell_price`        | scalar or array              | $/kWh     | Price to sell electricity to grid (optional). Shape is `n_timesteps` when `sell_price_mode` is `per_timestep`, or `plant_life` when `per_year`. |
| `sell_price_mode`               | string                       | —         | `"per_timestep"` or `"per_year"`. Controls the sell price input shape and cost calculation. |
| `electricity_sold`              | array[n_timesteps]           | kW        | Electricity flowing into grid (selling). Present when `sell_price_mode` is `per_timestep` (or sell price is not set). |
| `annual_electricity_sold`       | array[plant_life]            | kWh/yr    | Annual electricity sold to grid. Present when `sell_price_mode` is `per_year`. |

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

```{note}
The grid components are currently compatible with 5-minute (300-second) to 1-hour (3600-second) time steps.
```

### Price Input Modes

The pricing mode is controlled explicitly via `buy_price_mode` and `sell_price_mode` in the grid cost configuration. Each can be set to:

- **`per_timestep`** (default): The price is a scalar or an array of length `n_timesteps`. The cost model uses the timestep-level `electricity_out` / `electricity_sold` inputs (in kW) and converts to energy using `dt`. The resulting `VarOpEx` is a single value applied uniformly across all years.
- **`per_year`**: The price is an array of length `plant_life`. The cost model uses `annual_electricity_out` / `annual_electricity_sold` inputs (in kWh/yr, shape `plant_life`) directly, producing a per-year `VarOpEx` array with no `dt` conversion needed in the cost model.
- **`constant`**: The price is a single scalar value applied uniformly to all timesteps. Behaves like `per_timestep` with a scalar price but makes the intent explicit in the configuration.

Example YAML configuration for per-year pricing:

```yaml
cost_parameters:
  electricity_buy_price: [0.05, 0.06, 0.07, ...]  # length = plant_life
  buy_price_mode: per_year
  electricity_sell_price: [0.03, 0.04, 0.05, ...]  # length = plant_life
  sell_price_mode: per_year
```

Example YAML configuration for constant pricing:

```yaml
cost_parameters:
  electricity_buy_price: 0.10
  buy_price_mode: constant
  electricity_sell_price: 0.05
  sell_price_mode: constant
```
