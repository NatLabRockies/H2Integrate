(numpyfinancialnpvfinance:numpyfinancialnpvmodel)=
# NumPy Financial NPV Finance Model
The `NumpyFinancialNPV` component calculates the Net Present Value (NPV) of a commodity-producing plant or technology over its operational lifetime using the [NumPy Financial npv](https://numpy.org/numpy-financial/latest/npv.html#numpy_financial.npv) method.
It is implemented as an OpenMDAO `ExplicitComponent` and integrates with system-level technoeconomic optimization workflows.

The component evaluates profitability by discounting future cash flows — including capital expenditures (CAPEX), operating expenses (OPEX), refurbishments, and revenues — based on user-defined financial parameters.

By convention:
- Investments and costs (CAPEX, OPEX, refurbishments) are negative cash flows.
- Revenues (commodity sales) are positive cash flows.

## Model Inputs
### `NumpyFinancialNPVFinanceConfig`
**Description**
Configuration class defining financial parameters for the NPV calculation.
Implements validation and default handling using the `attrs` library.
| Attribute                         | Type             | Description                                           | Default     |
| --------------------------------- | ---------------- | ----------------------------------------------------- | ----------- |
| `plant_life`                      | `int`            | Operating life of the plant in years. Must be ≥ 0.    | —           |
| `real_discount_rate`              | `float`          | Discount rate (0-1). Can be either a real or nominal rate depending on how `inflation_rate` is specified. | -           |
| `inflation_rate`                  | `float`          | Inflation rate (0-1). Combined with `real_discount_rate` via the Fisher equation `(1 + r_eff) = (1 + real_discount_rate) * (1 + inflation_rate)` to form the effective discount rate. Set to 0 if `real_discount_rate` is already a nominal rate. This matches how ProFAST combines its real discount rate and `general_inflation` inputs. | `0.0`       |
| `commodity_sell_price`            | `int` or `float` | Sale price of the commodity (USD/unit).               | `0.0`       |
| `commodity_sell_price_units`      | `str`            | OpenMDAO unit string for `commodity_sell_price` (e.g. `"USD/(kW*h)"` for electricity or `"USD/kg"` for hydrogen). | —           |
| `save_cost_breakdown`             | `bool`           | Whether to save annual cost breakdowns to CSV.        | `False`     |
| `save_npv_breakdown`              | `bool`           | Whether to save per-technology NPV breakdowns to CSV. | `False`     |
| `cost_breakdown_file_description` | `str`            | Descriptor appended to output filenames.              | `'default'` |


An example of what to include in the `plant_config` to use the `NPVFinance` model. This is included in `["finance_parameters"]["finance_groups"]`, where `npv` is the specific `finance_group` name.

```yaml
npv:
  finance_model: "NumpyFinancialNPV"
  model_inputs:
    real_discount_rate: 0.09 # each period is discounted at a rate of `(1 + real_discount_rate) * (1 + inflation_rate) - 1`
    inflation_rate: 0.0 # optional, defaults to 0; provide e.g. 0.025 if `real_discount_rate` is a real rate
    commodity_sell_price: 0.078 # if commodity is electricity $/kwh
    commodity_sell_price_units: "USD/(kW*h)" # OpenMDAO unit string for the sell price
    save_cost_breakdown: True
    save_npv_breakdown: True
```

```{note}
`plant_life` is included in the `plant` section of the `plant_config` yaml.
```

## Model Outputs
| Name              | Units | Description                                        |
| ----------------- | ----- | -------------------------------------------------- |
| `NPV_<commodity>_<optional_description>` | `USD` | Total discounted Net Present Value for the system. |

### Output Files (if enabled)

| File                   | Description                                              |
| ---------------------- | -------------------------------------------------------- |
| `*_cost_breakdown.csv` | Annual time series of costs and revenues per technology. |
| `*_NPV_breakdown.csv`  | Discounted NPV summary by cost/revenue category.         |



## Calculation Methodology

1. Assemble Cash Flows
    - CAPEX (negative) at year 0
    - OPEX (negative) and revenue (positive) for years 1–`plant_life`

2. Refurbishments
    - Technologies with `replacement_cost_percent` and a refurbishment period incur periodic capital costs.

3. Discounting
    - Each series of cash flows is discounted using NumPy Financial’s `npf.npv(effective_rate, values)`, where `effective_rate = (1 + real_discount_rate) * (1 + inflation_rate) - 1` is the Fisher-equation combination of `real_discount_rate` and `inflation_rate`. When `inflation_rate` is left at its default of 0, `effective_rate` reduces to `real_discount_rate`, so the value passed as `real_discount_rate` is used directly as the (nominal) discount rate. To model inflation explicitly, supply a real `real_discount_rate` together with a nonzero `inflation_rate`. The multiplicative (Fisher) form matches the way ProFAST combines its real discount rate and `general_inflation` inputs.

4. Summation
   - Total NPV = sum of all discounted cash flows.

5. Optional Output Files
   - `*_cost_breakdown.csv`: Annual cash flow time series
   - `*_NPV_breakdown.csv`: Discounted NPV breakdown per item
