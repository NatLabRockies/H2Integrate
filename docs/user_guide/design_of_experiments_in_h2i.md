---
jupytext:
  text_representation:
    extension: .md
    format_name: myst
    format_version: 0.13
    jupytext_version: 1.18.1
kernelspec:
  display_name: h2i-fork
  language: python
  name: python3
---

# Design of experiments in H2I

One of the key features of H2Integrate is the ability to perform a design of experiments (DOE) for hybrid energy systems.

The design of experiments process uses the `driver_config.yaml` file to define the design sweep, including the design variables, constraints, and objective functions.
Detailed information on setting up the `driver_config.yaml` file can be found in the
[user guide](https://h2integrate.readthedocs.io/en/latest/user_guide/design_optimization_in_h2i.html)

## Driver config file

The driver config file defines the analysis type and the optimization or design of experiments settings.
For completeness, here is an example of a driver config file for a design of experiments problem:

```yaml
name: "driver_config"
description: "Runs a design sweep"

general:
  folder_output: outputs

driver:
  design_of_experiments:
    flag: True
    generator: "csvgen" #type of generator to use
    filename: "" #this input is specific to the "csvgen" generator
    debug_print: False

design_variables:
  solar:
    system_capacity_DC:
      flag: true
      lower: 5000.0
      upper: 5000000.0
      units: "kW"
  electrolyzer:
    n_clusters:
      flag: true
      lower: 1
      upper: 25
      units: "unitless"

constraints: #constraints are not used within the design of experiments run
# but are accessible in the recorder file as constraint variables

objective: #the objective is not used within the design of experiments run
# but is accessible in the recorder file as the objective
  name: finance_subgroup_hydrogen.LCOH

recorder:
  file: "cases.sql"
  flag: True
  includes: ["*"]
  excludes: ['*_resource*']
```

## Types of Generators

H2Integrate currently supports the following types of generators:

- ["uniform"](#uniform): uses the `UniformGenerator` generator
- ["fullfact"](#fullfactorial): uses the `FullFactorialGenerator` generator
- ["plackettburman"](#plackettburman): uses the `PlackettBurmanGenerator` generator
- ["boxbehnken"](#boxbehnken): uses the `BoxBehnkenGenerator` generator
- ["latinhypercube"](#latinhypercube): uses the `LatinHypercubeGenerator` generator
- ["csvgen"](#csv): uses the `CSVGenerator` generator

Documentation for each generator type can be found on [OpenMDAO's documentation page](https://openmdao.org/newdocs/versions/latest/_srcdocs/packages/drivers/doe_generators.html).

### Uniform

```yaml
driver:
  design_of_experiments:
    flag: True
    generator: "uniform" #type of generator to use
    num_samples: 10 #input is specific to this generator
    seed: #input is specific to this generator
```

### FullFactorial

```yaml
driver:
  design_of_experiments:
    flag: True
    generator: "fullfact" #type of generator to use
    levels: 2 #input is specific to this generator
```

The **levels** input is the number of evenly spaced levels between each design variable lower and upper bound.

You can check the values that will be used for a specific design variable by running:

```python
import numpy as np

design_variable_values = np.linspace(lower_bound,upper_bound,levels)
```

### PlackettBurman

```yaml
driver:
  design_of_experiments:
    flag: True
    generator: "plackettburman" #type of generator to use
```

### BoxBehnken

```yaml
driver:
  design_of_experiments:
    flag: True
    generator: "boxbehnken" #type of generator to use
```

### LatinHypercube

```yaml
driver:
  design_of_experiments:
    flag: True
    generator: "latinhypercube" #type of generator to use
    num_samples:  10 #input is specific to this generator
    criterion: "center"  #input is specific to this generator
    seed: #input is specific to this generator
```

### CSV

This method is useful if there are specific combinations of designs variables that you want to sweep. An example is shown here:

```yaml
driver:
  design_of_experiments:
    flag: True
    generator: "csvgen" #type of generator to use
    filename: "cases_to_run.csv" #input is specific to this generator
```

The **filename** input is the filepath to the csv file to read cases from. The first row of the csv file should contain the names of the design variables. The rest of the rows should contain the values of that design variable you want to run (such as `solar.system_capacity_DC` or `electrolyzer.n_clusters`). **The values in the csv file are expected to be in the same units specified for that design variable**.

```{note}
You should check the csv file for potential formatting issues before running a simulation. This can be done using the `check_file_format_for_csv_generator` method in `h2integrate/core/utilities.py`. Usage of this method is shown in the `20_solar_electrolyzer_doe` example in the `examples` folder.
```

#### Demonstration Using Solar and Electrolyzer Capacities

This `csvgen` generator example reflects the work to produce the `examples/20_solar_electrolyzer_doe`
example.

We use the `examples/20_solar_electrolyzer_doe/driver_config.yaml` to run a design of experiments for
varying combinations of solar power and hydrogen electrolzer capacities.

```{literalinclude} ../../examples/20_solar_electrolyzer_doe/driver_config.yaml
:language: yaml
:lineno-start: 4
:linenos: true
:lines: 4-26
```

The different combinations of solar and electrolzyer capacities are listed in the csv file `examples/20_solar_electrolyzer_doe/csv_doe_cases.csv`:

```{literalinclude} ../../examples/20_solar_electrolyzer_doe/csv_doe_cases.csv
:language: csv
```

Next, we'll import the required models and functions to complete run a successful design of experiments.

```{code-cell} ipython3
# Import necessary methods and packages
from pathlib import Path

from hopp.utilities.utilities import load_yaml
from h2integrate.core.utilities import check_file_format_for_csv_generator, load_yaml
from h2integrate.core.dict_utils import update_defaults
from h2integrate.core.h2integrate_model import H2IntegrateModel
from h2integrate.core.inputs.validation import load_driver_yaml, write_yaml
```

##### Setup and first attempt

First, we need to update the relative file refrerences to ensure the demonstration works.

```{code-cell} ipython3
EXAMPLE_DIR = Path("../../examples/20_solar_electrolyzer_doe").resolve()

config = load_yaml(EXAMPLE_DIR / "20_solar_electrolyzer_doe.yaml")

driver_config = load_yaml(EXAMPLE_DIR / config["driver_config"])
csv_config_fn = EXAMPLE_DIR / driver_config["driver"]["design_of_experiments"]["filename"]
config["driver_config"] = driver_config
config["driver_config"]["driver"]["design_of_experiments"]["filename"] = csv_config_fn

config["technology_config"] = load_yaml(EXAMPLE_DIR / config["technology_config"])
config["plant_config"] = load_yaml(EXAMPLE_DIR / config["plant_config"])
```

As-is, the model produces a `UserWarning` that it will not successfully run with the existing
configuration, as shown below.

```{code-cell} ipython3
:tags: [raises-exception]

model = H2IntegrateModel(config)
model.run()
```

##### Fixing the bug

The UserWarning tells us that there may be an issue with our csv file. We will use the recommended method to create a new csv file that doesn't have formatting issues.

We'll take the following steps to try and fix the bug:

1. Run the `check_file_format_for_csv_generator` method mentioned in the UserWarning and create a new csv file that is hopefully free of errors
2. Make a new driver config file that has "filename" point to the new csv file created in Step 1.
3. Make a new top-level config file that points to the updated driver config file created in Step 2.

```{code-cell} ipython3
# Step 1
new_csv_filename = check_file_format_for_csv_generator(
    csv_config_fn,
    driver_config,
    check_only=False,
    overwrite_file=False,
)

new_csv_filename.name
```

Let's see the updates to combinations.

```{literalinclude} ../../examples/20_solar_electrolyzer_doe/csv_doe_cases0.csv
:language: csv
```

```{code-cell} ipython3
# Step 2
updated_driver = update_defaults(
  driver_config["driver"],
  "filename",
  EXAMPLE_DIR / new_csv_filename.name,
)
driver_config["driver"].update(updated_driver)

# Step 3
config["driver_config"] = driver_config
```

### Re-running

Now that we've completed the debugging and fixing steps, lets try to run the simulation again but with our new files.

```{code-cell} ipython3
model = H2IntegrateModel(config)
model.run()
```
