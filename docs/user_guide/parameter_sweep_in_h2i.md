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

# Parameter sweeps in H2I

One of the key features of H2Integrate is the ability to perform **parameter sweeps** across hybrid energy systems.
A parameter sweep systematically varies one or more design variables across a range of values and evaluates the system at each combination, making it easy to explore the design space.

```{note}
Under the hood, H2Integrate uses OpenMDAO's [Design of Experiments (DOE) Driver](https://openmdao.org/newdocs/versions/latest/_srcdocs/packages/drivers/doe_generators.html) to perform parameter sweeps.
We use the term **parameter sweep** in H2Integrate to avoid confusion with the U.S. Department of Energy (DOE), which is frequently referenced in our domain.
If you see "DOE" or "Design of Experiments" in OpenMDAO documentation, it refers to the same capability called "parameter sweep" here.
```

The parameter sweep is configured through the `driver_config.yaml` file, which defines the sweep settings, design variables, constraints, and objective functions.
Detailed information on setting up the `driver_config.yaml` file can be found in the
[user guide](https://h2integrate.readthedocs.io/en/latest/user_guide/design_optimization_in_h2i.html).

```{tip}
Parameter sweeps are the **recommended way** to run multiple cases with different design variable values.
If you need to change technology configuration values (not just design variables), see the
[advanced for-loop approach](how_to_run_several_cases_in_sequence.md) instead.
```

## Driver config file

The driver config file defines the analysis type and the parameter sweep settings.
For completeness, here is an example of a driver config file for a parameter sweep:

```{literalinclude} ../../examples/22_site_doe/driver_config.yaml
:language: yaml
:linenos: true
```

## Types of Generators

H2Integrate supports the following generator types to create the set of cases for a parameter sweep.
Each generator produces combinations of design variable values using a different sampling strategy.

- ["uniform"](#uniform): uses the `UniformGenerator` generator
- ["fullfact"](#fullfactorial): uses the `FullFactorialGenerator` generator
- ["plackettburman"](#plackettburman): uses the `PlackettBurmanGenerator` generator
- ["boxbehnken"](#boxbehnken): uses the `BoxBehnkenGenerator` generator
- ["latinhypercube"](#latinhypercube): uses the `LatinHypercubeGenerator` generator
- ["csvgen"](#csv): uses the `CSVGenerator` generator

Documentation for each generator type can be found on [OpenMDAO's documentation page](https://openmdao.org/newdocs/versions/latest/_srcdocs/packages/drivers/doe_generators.html).

(uniform)=
### Uniform

Generates random samples drawn uniformly between the lower and upper bounds of each design variable. Good for initial exploration when you have no prior knowledge of the design space.

```yaml
driver:
  parameter_sweep:
    flag: True
    generator: "uniform" #type of generator to use
    num_samples: 10 #input is specific to this generator
    seed: #input is specific to this generator
```

(fullfactorial)=
### FullFactorial

Evaluates **every combination** of evenly spaced levels for each design variable. Provides complete coverage of the design space but grows exponentially with the number of variables (e.g., 3 variables with 4 levels = 64 cases).

```yaml
driver:
  parameter_sweep:
    flag: True
    generator: "fullfact" #type of generator to use
    levels: 2 #input is specific to this generator
```

The **levels** input is the number of evenly spaced levels between each design variable lower and upper bound, inclusive.

(plackettburman)=
### PlackettBurman

A screening method that uses a fractional factorial approach to identify which design variables have the **largest effect** on the outputs. Requires far fewer runs than a full factorial sweep, making it useful for narrowing down which variables matter most before performing a more detailed study.

```yaml
driver:
  parameter_sweep:
    flag: True
    generator: "plackettburman" #type of generator to use
```

(boxbehnken)=
### BoxBehnken

A response surface method that samples at the **midpoints of edges** and the center of the design space (never at the corners). Useful for fitting quadratic response surface models with fewer runs than a full factorial at three levels. Best suited for 3 or more design variables.

```yaml
driver:
  parameter_sweep:
    flag: True
    generator: "boxbehnken" #type of generator to use
```

(latinhypercube)=
### LatinHypercube

A space-filling method that divides each variable's range into equal-probability intervals and samples exactly once from each interval. Provides good coverage of the design space with fewer samples than a full factorial.

```yaml
driver:
  parameter_sweep:
    flag: True
    generator: "latinhypercube" #type of generator to use
    num_samples:  10 #input is specific to this generator
    criterion: "center"  #input is specific to this generator
    seed: #input is specific to this generator
```

(csv)=
### CSV

Allows you to specify **exact combinations** of design variable values in a CSV file. This is useful when you have specific scenarios you want to evaluate rather than a systematic sampling of the design space.

```yaml
driver:
  parameter_sweep:
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

We use the `examples/20_solar_electrolyzer_doe/driver_config.yaml` to run a parameter sweep for
varying combinations of solar power and hydrogen electrolyzer capacities.

```{literalinclude} ../../examples/20_solar_electrolyzer_doe/driver_config.yaml
:language: yaml
:lineno-start: 4
:linenos: true
:lines: 4-26
```

The different combinations of solar and electrolyzer capacities are listed in the csv file `examples/20_solar_electrolyzer_doe/csv_doe_cases.csv`:

```{literalinclude} ../../examples/20_solar_electrolyzer_doe/csv_doe_cases.csv
:language: text
```

Next, we'll import the required models and functions to run a parameter sweep.

```{code-cell} ipython3
# Import necessary methods and packages
from pathlib import Path

from h2integrate import H2IntegrateModel, load_driver_yaml, write_yaml
from h2integrate.core.file_utils import check_file_format_for_csv_generator, load_yaml
from h2integrate.core.dict_utils import update_defaults
```

##### Setup and first attempt

First, we need to update the relative file references to ensure the demonstration works.

```{code-cell} ipython3
EXAMPLE_DIR = Path("../../examples/20_solar_electrolyzer_doe").resolve()

config = load_yaml(EXAMPLE_DIR / "20_solar_electrolyzer_doe.yaml")

driver_config = load_yaml(EXAMPLE_DIR / config["driver_config"])
csv_config_fn = EXAMPLE_DIR / driver_config["driver"]["parameter_sweep"]["filename"]
config["driver_config"] = driver_config
config["driver_config"]["driver"]["parameter_sweep"]["filename"] = csv_config_fn

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
:language: text
```

```{code-cell} ipython3
# Step 2
updated_driver = update_defaults(
  driver_config["driver"],
  "filename",
  str(EXAMPLE_DIR / new_csv_filename.name),
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
