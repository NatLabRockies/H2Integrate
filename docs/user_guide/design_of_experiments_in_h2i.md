# Design of experiments in H2I

One of the key features of H2Integrate is the ability to perform a design of experiments (DOE) for hybrid energy systems.

The design of experiments process uses the `driver_config.yaml` file to define the design sweep, including the design variables, constraints, and objective functions.
Detailed information on setting up the `driver_config.yaml` file can be found [here](https://h2integrate.readthedocs.io/en/latest/user_guide/design_optimization_in_h2i.html)

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
