(numpyfinancialnpvfinance:numpyfinancialnpvmodel)=
# NumPy Financial NPV Finance Model
The `NumpyFinancialNPV` component calculates the Net Present Value (NPV) of a commodity-producing plant or technology over its operational lifetime using the [NumPy Financial npv](https://numpy.org/numpy-financial/latest/npv.html#numpy_financial.npv) method.
It is implemented as an OpenMDAO `ExplicitComponent` and integrates with system-level technoeconomic optimization workflows.

The component evaluates profitability by discounting future cash flows — including capital expenditures (CAPEX), operating expenses (OPEX), refurbishments, and revenues — based on user-defined financial parameters.

Future cash flows are discounted using a nominal, **pre-tax** weighted average cost of capital (WACC) that blends the cost of equity and the cost of debt according to the plant's capital structure. Because the WACC is pre-tax and the cash flows are not tax-adjusted (no income tax, depreciation, or interest tax shield is modeled), the discount rate and cash flows are kept internally consistent. If a fully after-tax analysis is required, use the ProFAST-based finance model instead.

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
| `real_discount_rate`              | `float`          | Real equity rate / cost of equity (0-1). Can be either a real or nominal rate depending on how `inflation_rate` is specified. A pre-computed WACC can be supplied here directly by leaving `debt_equity_ratio` and `inflation_rate` at 0. | -           |
| `debt_rate`                       | `float`          | Real debt rate / cost of debt (0-1). Converted to nominal via the Fisher equation when `inflation_rate` is provided. | `0.0`       |
| `debt_equity_ratio`               | `float`          | Ratio of debt to equity (`D/E`, ≥ 0) used to weight the debt and equity contributions to the WACC. When 0, the WACC reduces to the equity rate. | `0.0`       |
| `inflation_rate`                  | `float`          | Inflation rate (0-1). Combined with the real equity and debt rates via the Fisher equation `(1 + nominal) = (1 + real) * (1 + inflation_rate)` before they are weighted into the WACC. Set to 0 if the rates are already nominal. This matches how ProFAST combines its real rates and `general_inflation` inputs. | `0.0`       |
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
    real_discount_rate: 0.09 # real equity rate (cost of equity); also the discount rate when no debt is specified
    debt_rate: 0.05 # optional, defaults to 0; real cost of debt
    debt_equity_ratio: 1.0 # optional, defaults to 0; D/E used to weight the pre-tax WACC
    inflation_rate: 0.0 # optional, defaults to 0; provide e.g. 0.025 if the rates above are real
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
    - Each series of cash flows is discounted using NumPy Financial’s `npf.npv(effective_rate, values)`, where `effective_rate` is the nominal, pre-tax WACC computed by `_compute_wacc`.
    - The real equity rate (`real_discount_rate`) and real debt rate (`debt_rate`) are first converted to nominal rates via the Fisher equation `(1 + nominal) = (1 + real) * (1 + inflation_rate)` (see `_real_to_nominal_rate`). When `inflation_rate` is left at its default of 0, this conversion is a no-op and the supplied rates are used directly (i.e., treated as nominal).
    - The nominal rates are then blended by capital structure:

      ```
      equity_weight = 1 / (1 + debt_equity_ratio)
      debt_weight   = debt_equity_ratio / (1 + debt_equity_ratio)
      WACC          = equity_weight * equity_rate + debt_weight * debt_rate
      ```

      No interest tax shield is applied to the debt leg, so the WACC is **pre-tax**, consistent with the pre-tax cash flows. When `debt_equity_ratio` is 0, the WACC reduces to the (nominal) equity rate, and a pre-computed WACC can be supplied directly through `real_discount_rate`. The multiplicative (Fisher) form matches the way ProFAST combines its real rates and `general_inflation` inputs.

4. Summation
   - Total NPV = sum of all discounted cash flows.

5. Optional Output Files
   - `*_cost_breakdown.csv`: Annual cash flow time series
   - `*_NPV_breakdown.csv`: Discounted NPV breakdown per item
