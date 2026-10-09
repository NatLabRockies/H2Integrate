# Postprocessing results

When running H2Integrate, results from the simulation and individual technologies are generated automatically.
Additionally, the raw numerical results are available in the resulting Python object `prob` after a simulation.
This doc page will walk you through the steps to postprocess the results from a simulation.

```{note}
Streamlining the postprocessing of results is an ongoing effort in H2Integrate -- please expect this page to be updated as new features are added.
```

## Automatically generated results

At the conclusion of a simulation, H2Integrate automatically prints a list of model inputs and outputs to the terminal. The report groups results by technology and model. This illustrative excerpt shows the structure; exact model names, output counts, values, and units depend on the configuration:

```text
varname             val       units      prom_name
------------------  --------  ---------  ---------------------------
plant
  technology_name
    PerformanceModel
      commodity_out  |...|     units      technology_name.commodity_out
    CostModel
      CapEx          [...]     USD        technology_name.CapEx
```

Anywhere that the value is listed as a magnitude (e.g. `|85854400.89803042|`), this indicates that the value reported is the magnitude of the array.
Other values are reported as arrays (e.g. `[4.00631628e+09]`), which indicates that the value is a single element.
The units of the value are also reported, as well as the name of the variable in the model.
The name of the variable in the model is the last column in the table, and is used to access the value in the `prob` object.

```{note}
If the technologies you're modeling have been set up to generate results, the results will be printed or saved at this time as well.
```

## Manually postprocessing results

Once the simulation is complete, the results are available in the `prob` object.
This object is a dictionary-like object that contains all the inputs and outputs for the model.
The keys in the object are the names of the variables in the model, and the values are the values of the variables.

Here is an example of how to access the results from the `prob` object:

```python
from h2integrate import H2IntegrateModel
from h2integrate.postprocess.sql_timeseries_to_csv import save_case_timeseries_as_csv
from h2integrate.postprocess.sql_to_csv import convert_sql_to_csv_summary


# Create a H2Integrate model
model = H2IntegrateModel("top_level_config.yaml")

# Run the model
model.run()

model.post_process()

print(model.prob.get_val("electrolyzer.total_hydrogen_produced", units='kg'))
```

This will print the total hydrogen produced by the electrolyzer in kg.
The `get_val` method is used to access the value of the variable in the `prob` object.
The `units` argument is used to specify the units of the value to be returned.

### Saving outputs

The time series outputs can be saved to a csv output using the `save_case_timeseries_as_csv` function. If no variables are specified, then the function saves all time series variables in the simulation. Otherwise, the specified variables are saved.

The `vars_to_save` argument supports three different input formats:

1. **List of variable names** - saves variables with their default units
2. **Dictionary with units** - keys are variable names, values are the desired units
3. **Dictionary with options** - keys are variable names, values are dictionaries with `"units"` and/or `"alternative_name"` keys

#### Example 1: Save all timeseries data

```python
# Create and run a H2Integrate model
model = H2IntegrateModel("top_level_config.yaml")
model.run()
model.post_process()

# Save all timeseries data to a csv file
timeseries_data = save_case_timeseries_as_csv(model.recorder_path)
```

#### Example 2: Specify variables as a list

When providing a list of variable names, the function uses the default units for each variable.

```python
# Get a subset of timeseries data using a list of variable names
output_vars = [
    "electrolyzer.hydrogen_out",
  "wind.electricity_out",
    "ammonia.ammonia_out",
    "h2_storage.hydrogen_out",
]

# Don't save subset of timeseries to a csv file using save_to_file=False
timeseries_data = save_case_timeseries_as_csv(
    model.recorder_path, vars_to_save=output_vars, save_to_file=False
)
```

#### Example 3: Specify variables with custom units

When providing a dictionary with variable names as keys and unit strings as values, the function converts each variable to the specified units.

```python
# Specify variables with custom units
vars_with_units = {
    "ammonia.hydrogen_in": "kg/h",
    "h2_storage.hydrogen_in": "kg/h",
    "electrolyzer.electricity_in": "kW",
}

timeseries_data = save_case_timeseries_as_csv(
    model.recorder_path, vars_to_save=vars_with_units, save_to_file=False
)
```

#### Example 4: Specify variables with alternative column names

When providing a dictionary with variable names as keys and dictionaries as values, you can specify both custom units and alternative column names for the output DataFrame.

```python
# Specify variables with alternative names and/or units
vars_with_options = {
    "electrolyzer.hydrogen_out": {"alternative_name": "Electrolyzer Hydrogen Output"},
  "wind.electricity_out": {"units": "kW", "alternative_name": "Plant Electricity Output"},
    "ammonia.ammonia_out": {"alternative_name": None},  # Uses default variable name
    "h2_storage.hydrogen_out": {"alternative_name": "H2 Storage Hydrogen Output"},
}

timeseries_data = save_case_timeseries_as_csv(
    model.recorder_path, vars_to_save=vars_with_options, save_to_file=False
)
# Resulting columns: "Electrolyzer Hydrogen Output (kg/h)", "Plant Electricity Output (kW)", etc.
```

```{note}
The `electricity_base_unit` argument (default: `"MW"`) controls the units used for electricity-based variables when no specific units are provided. Valid options are `"W"`, `"kW"`, `"MW"`, or `"GW"`.
```

### Summarizing scalar results to CSV

While `save_case_timeseries_as_csv` exports time-series data, the `convert_sql_to_csv_summary` function extracts **scalar** results from one or more SQL recorder files and writes them to a single CSV summary.
This is especially useful when running parameter sweeps, where each row in the output corresponds to a different case.

The function:

- Collects every scalar output (single-element arrays) plus design variables.
- Reports VarOpEx values for the first year only.
- Averages capacity-factor and annual-production arrays over the project lifetime.
- Renames columns to include units, e.g. `plant.LCOH (USD/kg)`.
- When running in parallel, automatically aggregates results from all partitioned SQL files (e.g. `cases.sql_0`, `cases.sql_1`, ...) while skipping the `_meta` companion file.

#### Basic usage

```python
from h2integrate.postprocess.sql_to_csv import convert_sql_to_csv_summary

# Summarize scalar results and write a CSV next to the SQL file
df = convert_sql_to_csv_summary("path/to/cases.sql")  # creates path/to/cases.csv
```

#### Return only the DataFrame (no file written)

```python
df = convert_sql_to_csv_summary("path/to/cases.sql", save_to_file=False)
print(df.head())
```

#### Postprocessing the results of a completed H2Integrate model run

```python
model = H2IntegrateModel("top_level_config.yaml")
model.run()
model.post_process()

# Produce a one-row CSV summary of the scalar results
summary_df = convert_sql_to_csv_summary(model.recorder_path)
```

#### Summarizing parallel parameter sweep results

When a parameter sweep or parallel study is executed, H2Integrate writes one SQL file per process (e.g. `cases.sql_0`, `cases.sql_1`).
Pass the base name and the function handles the rest:

```python
# Aggregates cases.sql_0, cases.sql_1, ... into a single DataFrame
summary_df = convert_sql_to_csv_summary("output_dir/cases.sql")
```

## Printing model results

`print_results` prints a hierarchical summary of an OpenMDAO model's inputs and outputs and returns
a dictionary containing input, explicit-output, and implicit-output metadata. The `includes` and
`excludes` arguments accept OpenMDAO variable patterns; `show_units` controls whether units are
included in the report and returned metadata.

```python
from h2integrate.postprocess.reporting import print_results

model.run()
result_summary = print_results(
  model.prob.model,
  includes="*.hydrogen_out",
  excludes="*resource_data",
  show_units=True,
)
```

The returned mapping has `inputs`, `explicit_outputs`, and `implicit_outputs` entries.

```{eval-rst}
.. autofunction:: h2integrate.postprocess.reporting.print_results
   :no-index:
```

## Plotting energy and hydrogen flows

The plotting helpers in `h2integrate.tools.plot` read the production `energy_flows.csv` file. They
accept start and end datetimes, a save path, and flags to display or save the figure. The default
input path is `./output/data/production/energy_flows.csv`.

```python
import datetime as dt

from h2integrate.tools.plot import plot_energy_flows, plot_hydrogen_flows

plot_energy_flows(
  energy_flow_data_path="output/data/production/energy_flows.csv",
  start_date_time=dt.datetime(2024, 1, 5),
  end_date_time=dt.datetime(2024, 1, 10),
  show_fig=False,
)
plot_hydrogen_flows(
  energy_flow_data_path="output/data/production/energy_flows.csv",
  show_fig=False,
)
```

`plot_energy_flows` plots electricity generation and battery charge/discharge.
`plot_hydrogen_flows` plots hydrogen production, demand, and storage state of charge. The CSV must
contain the columns expected by the selected plotting function.

```{eval-rst}
.. autofunction:: h2integrate.tools.plot.plot_energy_flows
   :no-index:

.. autofunction:: h2integrate.tools.plot.plot_hydrogen_flows
   :no-index:
```

## ProFAST helpers

The ProFAST utilities create and populate a `ProFAST` object from a configuration mapping, run its
price solve, or convert an existing object back to configuration data. They are available from
`h2integrate.tools.profast_tools`.

- `create_and_populate_profast(pf_config)` builds a ProFAST instance from a configuration mapping.
- `run_profast(pf)` returns the solved price, summary values, and cost-breakdown DataFrame.
- `make_price_breakdown(price_breakdown, pf_config)` distributes non-component financial costs
  across primary cost items and returns a check against the solved levelized cost.
- `format_profast_price_breakdown_per_year(price_breakdown)` formats a ProFAST cost breakdown by
  year for reporting.
- `convert_pf_to_dict(pf)` converts a ProFAST instance into nested configuration data.

```python
from h2integrate.tools.profast_tools import create_and_populate_profast, run_profast

profast_model = create_and_populate_profast(pf_config)
solution, summary, price_breakdown = run_profast(profast_model)
```
