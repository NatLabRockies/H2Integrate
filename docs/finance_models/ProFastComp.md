
(profastcomp:profastcompmodel)=
# ProFastComp
The `ProFastLCO` finance model calculates levelized cost of a commodity using [ProFAST](https://github.com/NREL/ProFAST).

The inputs, outputs, and naming convention for the `ProFastLCO` model are outlined in this doc page.


(profastcomp:overview)=
## Finance parameters overview
The main inputs for `ProFastLCO` model include:
- required: financial parameters (`params` section). These can be input in the `ProFastBase` format or the `ProFAST` format. These two formats are described in the following sections:
  - [ProFastBase format](profast:direct_opt)
  - [ProFAST format](profast:pf_params_opt)
- required: default capital item parameters (`capital_items` section). These parameters can be overridden for specific technologies if specified in the `tech_config`. Example usage of overriding values in the `tech_config` is outlined [here](profast:tech_specific_finance)
- optional: information to export the ProFAST config or results to a .yaml file

```yaml
finance_parameters:
  finance_model: "ProFastLCO"
  model_inputs: #inputs for the finance_model
    save_profast_results: True #optional, will save ProFAST results to .yaml file in the folder specified in the driver_config (`driver_config["general"]["folder_output"]`)
    save_profast_config: True #optional, will save ProFAST the profast config to .yaml file in the folder specified in the driver_config (`driver_config["general"]["folder_output"]`)
    profast_output_description: "profast_config" #used to name the output file.
    params: #Financial parameters section
    capital_items: #Required: section for default parameters for capital items
      depr_type: "MACRS" #Required: depreciation method for capital items, can be "MACRS" or "Straight line"
      depr_period: 5 #Required: depreciation period for capital items
      refurb: [0.] #Optional: replacement schedule as a fraction of the capital cost. Defaults to [0.]
    fixed_costs: #Optional section for default parameters for fixed cost items
      escalation: #escalation rate for fixed costs, will default to `inflation_rate` specific in the params section
      unit: "$/year" #optional unit of the cost. Defaults to $/year
      usage: 1.0 #usage multiplier, most commonly is set to 1 and defaults to 1.0

```

```{note}
If you are setting `save_profast_results` to `True` and are using multiple finance subgroups, use the `commodity_desc` in each unique finance subgroup to ensure the output files get written correctly for each subgroup. See examples/19_simple_dispatch/plant_config.yaml for an example of this.
```

(profastcomp:outputs)=
## Output values and naming convention
``ProFastLCO`` outputs the following data following the naming convention detailed below:
- `LCO<x_and_descriptor>`: levelized cost of commodity in USD/commodity unit, e.g. `LCOH_produced` for hydrogen produced.
- `wacc_<commodity_and_descriptor>`: weighted average cost of capital as a fraction.
- `crf_<commodity_and_descriptor>`: capital recovery factor as a fraction.
- `irr_<commodity_and_descriptor>`: internal rate of return as a fraction.
- `profit_index_<commodity_and_descriptor>`
- `investor_payback_period_<commodity_and_descriptor>`: time until initial investment costs are recovered in years.
- `price_<commodity_and_descriptor>`: first year price of commodity in same units as levelized cost.

**Naming convention**:
- `<commodity_and_descriptor>`:
  - if `commodity_desc` is **not** provided, then `<commodity_and_descriptor>` this is just `commodity`. For example, `wacc_hydrogen` if the `commodity` is `"hydrogen"`.
  - if `commodity_desc` is provided, then `<commodity_and_descriptor>` is `<commodity>_<commodity_desc>`. For example, `wacc_hydrogen_produced` if the `commodity` is `"hydrogen"` and `commodity_desc` is `"produced"`
- `<x_and_descriptor>`:
  - if `commodity_desc` is **not** provided, then `<x_and_descriptor>` is the upper-case first letter of the `commodity`. For example, `LCOH` if the `commodity` is `"hydrogen"`
  - if `commodity_desc` is provided, then `<x_and_descriptor>` is the upper-case first letter of the `commodity` followed by the `commodity_desc` descriptor. For example, `LCOH_produced` if the `commodity` is `"hydrogen"` and the `commodity_desc` is `"produced"`.
