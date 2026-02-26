
(finance:overview)=
# Finance Models Overview

**General finance models** compute finance metrics and are not specific to individual technologies.
These models live in the `h2integrate/finances/` folder and accept `driver_config`, `tech_config`, `plant_config`, `commodity_type`, and a `description` as the inputs and options.

- `driver_config` (dict): the `folder_outputs` specified here may be used by the finance model if the finance model outputs data to a file.
- `tech_config` (dict): the technology configs for the technologies to include in the finance calculations
- `plant_config` (dict): contains the `finance_parameters` for the finance model (see [Finance Parameters](financeparameters:specifiyingfinanceparameters)).
- `commodity_type` (str): the name of the commodity to use in the finance calculation.
- `description` (str, optional): an additional description to use for naming outputs of the finance model.

```{note}
The `commodity_type` and `description` are used in the finance model naming convention. Specifics on the output naming convention for each finance model can be found in their docs.
```

(finance:supportedmodels)=
## Currently supported general finance models

- [``ProFastLCO``](profastcomp:profastcompmodel): calculates levelized cost of commodity using [ProFAST](https://github.com/NREL/ProFAST).
- [``ProFastNPV``](profastnpv:profastnpvmodel): calculates the net present value of a commodity using [ProFAST](https://github.com/NREL/ProFAST).
- [``NumpyFinancialNPV``](numpyfinancialnpvfinance:numpyfinancialnpvmodel): calculates the net present value of a commodity using the [NumPy Financial npv](https://numpy.org/numpy-financial/latest/npv.html#numpy_financial.npv) method.

## Custom finance models

A general finance model can be defined similarly to a custom technology model. A custom finance model should be defined in the plant configuration file within the `finance_groups` section under `finance_parameters`.

Below shows an example, similar to the [Wind Electrolyzer Example](https://github.com/NREL/H2Integrate/tree/develop/examples/08_wind_electrolyzer/) of how to define a custom finance model within the `plant_config.yaml` file:
```yaml
finance_parameters:
  finance_groups:
    my_finance_model:
      finance_model: simple_lco_finance #this is the key to give it in for supported models
      finance_model_class_name: SimpleLCOFinance #name of the finance class
      finance_model_location: user_finance_model/simple_lco.py #filepath of the finance model relative to the plant_config.yaml file
      model_inputs: #inputs for the finance model
        discount_rate: 0.09
```
