(profastnpv:profastnpvmodel)=
# ProFastNPV
The `ProFastNPV` finance model calculates the net present value (NPV) of a commodity using [ProFAST](https://github.com/NatLabRockies/ProFAST).

`ProFastNPV` inherits from `ProFastBase` so refer to the [`ProFastBase` documentation](profast:overview) for setting the finance parameters.

The only additional parameters that are required when using the `ProFastNPV` model are `commodity_sell_price` and `commodity_sell_price_units`. The latter is the OpenMDAO unit string for the sell price (e.g. `"USD/(kW*h)"` for electricity, `"USD/kg"` for hydrogen) and is required so that the NPV cash-flow calculation can convert between price and production-rate units without relying on a separate placeholder output.

Below is an example of how to set up the ProFast NPV model in the `plant_config`:

```yaml
finance_parameters:
  finance_model: "ProFastNPV"
  model_inputs:
    commodity_sell_price: 0.05 # USD/commodity
    commodity_sell_price_units: "USD/kg" # OpenMDAO unit string for commodity_sell_price
    params: !include  "profast_params.yaml" #Finance information
    capital_items: #default parameters for capital items unless specified in tech_config
      depr_type: "MACRS" ##depreciation method for capital items, can be "MACRS" or "Straight line"
      depr_period: 5 #depreciation period for capital items
      refurb: [0.]
  cost_adjustment_parameters:
    target_dollar_year: 2022
    cost_year_adjustment_inflation: 0.025 # used to adjust costs for technologies to target_dollar_year
```

```{note}
`commodity_sell_price` can be input as a scalar value (as shown above) or as a list that has the same length as the `plant_life` specified in the plant configuration file. Please refer to the documentation on [different types of financial analysis](https://h2integrate.readthedocs.io/en/latest/finance_models/financial_analyses.html) to determine how to input the `commodity_sell_price` across different years.
```

```{important}
ProFAST will apply the commodity escalation rate to the `commodity_sell_price` in its calculations. The commodity escalation rate will default to the general inflation rate (input under `model_inputs['params']['inflation_rate']`) unless explicity provided as `model_inputs['params']['commodity']['escalation']`
```

(profastnpv:outputs)=
## Output values and naming convention
``ProFastNPV`` outputs the following data following the naming convention detailed below:
- `NPV_<commodity_and_descriptor>`: net present value of commodity in USD.

**Naming convention**:
- `<commodity_and_descriptor>`:
  - if `commodity_desc` is **not** provided, then `<commodity_and_descriptor>` this is just `commodity`. For example, `NPV_hydrogen` if the `commodity` is `"hydrogen"`.
  - if `commodity_desc` is provided, then `<commodity_and_descriptor>` is `<commodity>_<commodity_desc>`. For example, `NPV_hydrogen_produced` if the `commodity` is `"hydrogen"` and `commodity_desc` is `"produced"`
