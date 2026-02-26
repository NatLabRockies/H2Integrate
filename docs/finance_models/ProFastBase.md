(profastmodel:profastmodel)=
# ProFAST Financial Model
The Production Financial Analysis Scenario Tool or (ProFAST)[https://www.nrel.gov/hydrogen/profast-access] is a financial modeling tool developed at the NREL based on General Accepted Accounting Principles (GAAP) methodology. The model provides a quick and convenient way to conduct in-depth financial analysis for production system and services.

Currently there are two ProFAST models that can be used:
- [``ProFastLCO``](profastcomp:profastcompmodel): A price-taker model that calculates levelized cost of commodity (or breakeven price) using [ProFAST](https://github.com/NREL/ProFAST).
- [``ProFastNPV``](profastnpv:profastnpvmodel): A price-setter model that calculates the net present value of a commodity using [ProFAST](https://github.com/NREL/ProFAST).

(profast:overview)=
## Finance parameters overview
To set up the ProFast models correctly there are several financial parameters that need to be set. There are several ways of setting the information both within the `plant_config` and the `tech_config` for technology specific information.

Here is the information for setting the parameters:
- required: financial parameters (`params` section). These can be input in the `ProFastBase` format or the `ProFAST` format. These two formats are described in the following sections:
  - [ProFastBase format](profast:direct_opt)
  - [ProFAST format](profast:pf_params_opt)
- required: default capital item parameters (`capital_items` section). These parameters can be overridden for specific technologies if specified in the `tech_config`. Example usage of overriding values in the `tech_config` is outlined [here](profast:tech_specific_finance)

(profast:direct_opt)=
## Providing Finance Parameters: ProFastBase Format
Below is an example inputting financial parameters directly in the `finance_parameters` section of `plant_config`:

```yaml
finance_parameters:
  finance_model: "ProFastLCO" #finance model
    model_inputs: #inputs for finance_model
      params: #Financing parameters
        analysis_start_year: 2032 #year that financial analysis starts
        installation_time: 36 #installation period in months
        # Inflation parameters
        inflation_rate: 0.0 # 0 for nominal analysis
        # Finance parameters
        discount_rate: 0.09
        debt_equity_ratio: 2.62
        property_tax_and_insurance: 0.03
        total_income_tax_rate: 0.257
        capital_gains_tax_rate: 0.15
        sales_tax_rate: 0.07375
        debt_interest_rate: 0.07
        debt_type: "Revolving debt" #"Revolving debt" or "One time loan"
        loan_period_if_used: 0 #loan period if debt_type is 'One time loan'
        cash_onhand_months: 1
        admin_expense: 0.00 #administrative expense as a fraction of sales
    #default parameters for capital items unless specified in tech_config
    capital_items:
      depr_type: "MACRS" #depreciation method for capital items, can be "MACRS" or "Straight line"
      depr_period: 5 #depreciation period for capital items in years.
      refurb: [0.] #refurbishment schedule, values represent the replacement cost as a fraction of the CapEx

  # To adjust costs for technologies to target_dollar_year
  cost_adjustment_parameters:
    target_dollar_year: 2022
    cost_year_adjustment_inflation: 0.025
```

This approach also relies on data from `plant_config`:
- `plant_life`: used as the `operating life` ProFAST parameter


```{note}
`inflation_rate` is used to populate the escalation and inflation rates in ProFAST entries with a value of 0 corresponding to a *nominal analysis*.
```

(profast:pf_params_opt)=
## Providing Finance Parameters: ProFAST format

```{note}
To avoid errors, please check that `plant_config['plant']['plant_life']` is equal to `plant_config['finance_parameters']['model_inputs']['params']['operating life']`. Or remove `operating life` from the finance parameter inputs.`


| plant config parameter | equivalent `params` parameter |
| -------- | ------- |
| `plant['plant']['plant_life']` | `operating life` |
```

Below is an example of the `finance_parameters` section of `plant_config` if using ProFAST input format to specify financial parameters:

```yaml
finance_parameters:
  finance_model: "ProFastLCO"
  model_inputs:
    params: !include  "profast_params.yaml" #Finance information
    capital_items: #default parameters for capital items unless specified in tech_config
      depr_type: "MACRS" ##depreciation method for capital items, can be "MACRS" or "Straight line"
      depr_period: 5 #depreciation period for capital items
      refurb: [0.]
  cost_adjustment_parameters:
    target_dollar_year: 2022
    cost_year_adjustment_inflation: 0.025 # used to adjust costs for technologies to target_dollar_year
```

Below is an example of a valid ProFAST params config that may be specified in the `finance_parameters['model_inputs']['params]` section of `plant_config`:
```yaml
# Installation information
maintenance:
  value: 0.0
  escalation: 0.0
non depr assets: 250000 #such as land cost
end of proj sale non depr assets: 250000 #such as land cost
installation cost:
  value: 0.0
  depr type: "Straight line"
  depr period: 4
  depreciable: False
# Incentives information
incidental revenue:
  value: 0.0
  escalation: 0.0
annual operating incentive:
  value: 0.0
  decay: 0.0
  sunset years: 0
  taxable: true
one time cap inct:
  value: 0.0
  depr type: "MACRS"
  depr period: 5
  depreciable: True
# Sales information
analysis start year: 2032
operating life: 30 #if included, should equal plant_config['plant']['plant_life']
installation months: 36
demand rampup: 0
# Take or pay specification
TOPC:
  unit price: 0.0
  decay: 0.0
  support utilization: 0.0
  sunset years: 0
# Other operating expenses
credit card fees: 0.0
sales tax: 0.0
road tax:
  value: 0.0
  escalation: 0.0
labor:
  value: 0.0
  rate: 0.0
  escalation: 0.0
rent:
  value: 0.0
  escalation: 0.0
license and permit:
  value: 0.0
  escalation: 0.0
admin expense: 0.0
property tax and insurance: 0.015
# Financing information
sell undepreciated cap: True
capital gains tax rate: 0.15
total income tax rate: 0.2574
leverage after tax nominal discount rate: 0.0948
debt equity ratio of initial financing: 1.72
debt interest rate: 0.046
debt type: "Revolving debt"
general inflation rate: 0.0
cash onhand: 1 # number of months with cash on-hand
tax loss carry forward years: 0
tax losses monetized: True
loan period if used: 0
```

(profast:tech_specific_finance)=
## Override defaults for specific technologies

Capital item entries can be overridden for individual technologies.
This means that specific technologies can have different financial parameters defined in `tech_config` than the defaults set in the `plant_config`.

### **Override depreciation period:**

Suppose the default depreciation period for capital items is 5 years (set in the `plant_config['finance_parameters']['model_inputs]['capital_items']['depr_period']`), but we want the depreciation period for the electrolyzer to be 7 years. This can be done in the `tech_config` as shown below:
```yaml
technologies:
  electrolyzer:
    model_inputs:
      finance_parameters:
        capital_items:
          depr_period: 7
```


### **Custom refurbishment period:**

Suppose the default refurbishment schedule for capital items is `[0.]` (set in the `plant_config['finance_parameters']['model_inputs]['capital_items']['refurb']`), but we want our battery to be replaced in 15-years and the replacement cost is equal to the capital cost. This can be accomplished in the tech_config as shown below:
```yaml
technologies:
  battery:
    model_inputs:
      finance_parameters:
        capital_items:
          refurbishment_period_years: 15
          replacement_cost_percent: 1.0
```
