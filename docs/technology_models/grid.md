# Grid Performance and Cost Models

This page documents the unified `GridPerformanceModel` and `GridCostModel` models, which together represent a flexible, configurable grid interconnection point within an H2I simulation.
These components support both power flows and cost accounting for buying and selling electricity through a constrained interconnection.
This is a single model that can be configured to either sell electricity to the grid, buy electricity from the grid, or both.

See `example/24_solar_battery_grid` to see how to set up both buying and selling grid components.

## Grid Performance
`GridPerformanceModel` represents a grid interconnection point that can buy or sell electricity subject to a maximum throughput rating (`interconnection_size`).

It supports:
- Buying electricity from the grid to meet downstream demand.
- Selling electricity to the grid.
- Enforcing maximum allowed interconnection power.
- Computing unmet demand, unsold electricity, and remaining usable headroom due to constraints.

The model exposes two headroom outputs that are useful for dispatch logic and controller tuning:
- `electricity_headroom` is the remaining grid import capacity available for meeting downstream demand.
- `electricity_sell_headroom` is the remaining grid export capacity available for selling excess generation.

```{note}
Multiple grid instances may be used within the same plant to represent different interconnection nodes. For buying electricity from the grid, the technology name in the `tech_config` **must** start with `grid_buy` for the logic to work appropriately in financial calculations.
```

## Grid Cost
`GridCostModel` computes all costs and revenues associated with the grid interconnection, including:
- Capital cost based on interconnection rating.
- Fixed annual O&M.
- Variable cost of electricity purchased.
- Revenue from electricity sold.

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

## Performance Model

```{eval-rst}
.. autoclass:: h2integrate.converters.grid.grid.GridPerformanceModelConfig
   :members:
   :undoc-members:
   :show-inheritance:
   :no-index:
```

```{eval-rst}
.. autoclass:: h2integrate.converters.grid.grid.GridPerformanceModel
   :members:
   :undoc-members:
   :show-inheritance:
   :no-index:
```

## Cost Model

```{eval-rst}
.. autoclass:: h2integrate.converters.grid.grid.GridCostModelConfig
   :members:
   :undoc-members:
   :show-inheritance:
   :no-index:
```

```{eval-rst}
.. autoclass:: h2integrate.converters.grid.grid.GridCostModel
   :members:
   :undoc-members:
   :show-inheritance:
   :no-index:
```
