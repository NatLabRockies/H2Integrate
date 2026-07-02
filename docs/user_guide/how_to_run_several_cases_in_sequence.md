# Running several cases in sequence

## Overview

```{tip}
For most use cases where you want to sweep over different values of **design variables** (e.g., system capacities, number of clusters), we recommend using the built-in [parameter sweep capability](parameter_sweep_in_h2i.md).
It handles case generation, parallel execution, and result recording automatically.
```

The approach described on this page is intended for **advanced users** who need to modify **technology configuration** parameters between runs — values that are not exposed as design variables in the `driver_config.yaml`.
This is done using the functions in `h2integrate/tools/run_cases.py`.

```{warning}
The for-loop approach shown below does not automatically record results to a SQL file, does not support parallel execution, and requires manual post-processing.
Use the [parameter sweep](parameter_sweep_in_h2i.md) whenever possible.
```

## Setting up a variation of parameters in a .csv

To set up the inputs for each case, the input .csv should be set up like so:
|   Index 0    |    Index 1     |...|     Index N    | Type  | <Case #1 Name>  | <Case #2 Name>  |...| <Case #N Name>  |
|--------------|----------------|---|----------------|-------|-----------------|-----------------|---|-----------------|
| technologies | <param_1_tech> |...| <param_1_name> | float | <Case #1 value> | <Case #2 value> |...| <Case #N value> |
| technologies | <param_2_tech> |...| <param_2_name> | str   | <Case #1 value> | <Case #2 value> |...| <Case #N value> |
| ...          | ...            |...| ...            | ...   | ...             | ...             |...| ...             |
| technologies | <param_N_tech> |...| <param_N_name> | bool  | <Case #1 value> | <Case #2 value> |...| <Case #N value> |


## Example: Two different sizes of Haber Bosch ammonia plant

To demonstrate this capability, we include a short example that modifies the size and hydrogen storage type for a Haber Bosch ammonia plant in `examples/12_ammonia_synloop`.
The example spreadsheet `hb_inputs.csv` shows the format:

|Index 0|Index 1|Index 2|Index 3|Index 4|Index 5|Type|Haber Bosch Big|Haber Bosch Small
|---    |---    |---    |---    |---    |---    |---    |---    |---    |
technologies|ammonia|model_inputs|shared_parameters|production_capacity||float|100000|10000
technologies|h2_storage|model_inputs|performance_parameters|type||str|salt_cavern|lined_rock_cavern
technologies|electrolyzer|model_inputs|performance_parameters|n_clusters||int|16|2
technologies|electrolyzer|model_inputs|performance_parameters|include_degradation_penalty||bool|TRUE|FALSE
technologies|electrolyzer|model_inputs|financial_parameters|capital_items|replacement_cost_percent|float|0.15|0.25


### Things to note about this format

- The nested depth of the parameters in the `tech_config` can vary based on the parameter you're setting. If some parameters do not use as many levels, leave the unused levels blank (like the Index 5 level for most parameters in the above example)
- The currently available data types for each parameter are `float`, `str`, `int`, and `bool`. Be sure to specify the correct data type for each parameter.
- For parameters declared as `bool`, you can enter "0", "false", or "no" for `False`, and "1", "true", or "yes" for `True` (case insensitive). When making .csvs in Excel, the default "TRUE" and "FALSE" formatting will work.
- For all other parameters not included in the spreadsheet, their values will be kept the same as originally defined in the `tech_config.yaml`.

The variation of parameters can be run by first creating an H2I model (with a `tech_config.yaml`), then modifying only the `tech_config` values that need to change.
First, the spreadsheet with each case is loaded into a Pandas DataFrame using `load_tech_config_cases`.
Then, in a loop, individual cases are selected and the model is modified to use these parameters using `modify_tech_config`.
An example is shown in `run_ammonia_synloop.py`:

```
from pathlib import Path

from h2integrate.tools.run_cases import modify_tech_config, load_tech_config_cases
from h2integrate import H2IntegrateModel


# Create a H2Integrate model
model = H2IntegrateModel("12_ammonia_synloop.yaml")

# Load cases
case_file = Path("hb_inputs.csv")
cases = load_tech_config_cases(case_file)

# Modify and run the model for different cases
caselist = [
    "Haber Bosch Big",
    "Haber Bosch Small",
]
for casename in caselist:
    case = cases[casename]
    model = modify_tech_config(model, case)
    model.run()
    model.post_process()
```
