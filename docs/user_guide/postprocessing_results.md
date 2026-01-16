# Postprocessing results

When running H2Integrate, results from the simulation and individual technologies are generated automatically.
Additionally, the raw numerical results are available in the resulting Python object `prob` after a simulation.
This doc page will walk you through the steps to postprocess the results from a simulation.

```{note}
Streamlining the postprocessing of results is an ongoing effort in H2Integrate -- please expect this page to be updated as new features are added.
```

## Automatically generated results

At the conclusion of a simulation, H2Integrate automatically prints a list of all the inputs and outputs for the model to the terminal.
Here is a snippet of the output from a simulation:

```text
37 Explicit Output(s) in 'model'

varname                               val                  units     prom_name
------------------------------------  -------------------  --------  -----------------------------------------------
plant
  hopp
    hopp
      electricity_out                 |85694382.72934064|   kW         hopp.electricity_out
      CapEx                           [4.00631628e+09]      USD        hopp.CapEx
      OpEx                            [70417369.71000001]   USD/year   hopp.OpEx
  hopp_to_steel_cable
    electricity_out                   |85694382.72934064|   kW         hopp_to_steel_cable.electricity_out
  hopp_to_electrolyzer_cable
    electricity_out                   |85694382.72934064|   kW         hopp_to_electrolyzer_cable.electricity_out
  electrolyzer
    eco_pem_electrolyzer_performance
      hydrogen_out                    |1100221.2561732|     kg/h       electrolyzer.hydrogen_out
      time_until_replacement          [47705.10433122]      h          electrolyzer.time_until_replacement
      total_hydrogen_produced         [89334697.48304178]   kg/year    electrolyzer.total_hydrogen_produced
      efficiency                      [0.54540813]          None       electrolyzer.efficiency
      rated_h2_production_kg_pr_hr    [14118.38052482]      kg/h       electrolyzer.rated_h2_production_kg_pr_hr
    eco_pem_electrolyzer_cost
      CapEx                           [6.75464089e+08]      USD        electrolyzer.CapEx
      OpEx                            [16541049.81608545]   USD/year   electrolyzer.OpEx
<...>
  finance_subgroup_default
    ProFastComp_0
      LCOH                            [7.47944016]          USD/kg     finance_subgroup_default.LCOH
    ProFastComp_1
      LCOE                            [0.09795931]          USD/(kW*h)   finance_subgroup_default.LCOE
  steel
    steel_performance
      steel                           |9615.91147134|       t/year     steel.steel
    steel_cost
      CapEx                           [5.78060014e+08]      USD        steel.CapEx
      OpEx                            [1.0129052e+08]       USD/year   steel.OpEx
      LCOS                            [1213.87728644]       USD/t      steel.LCOS
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
from h2integrate.core.h2integrate_model import H2IntegrateModel


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

The time series outputs can be saved to a csv output using the `save_case_timeseries_as_csv` function. If no variables are specified, then the function saves all time series variables in the simulation. Otherwise, the specified variables are saves.
Here is an example of how to save time series results:
```python
from h2integrate.postprocess.sql_timeseries_to_csv import save_case_timeseries_as_csv

# Create a H2Integrate model
model = H2IntegrateModel("top_level_config.yaml")

# Run the model
model.run()

model.post_process()

# Save all timeseries data to a csv file
timeseries_data = save_case_timeseries_as_csv(h2i.recorder_path)

# Get a subset of timeseries data
output_vars = [
    "electrolyzer.hydrogen_out",
    "hopp.electricity_out",
    "ammonia.ammonia_out",
    "h2_storage.hydrogen_out",
]

# Don't save subset of timeseries to a csv file using save_to_file=False
timeseries_data = save_case_timeseries_as_csv(
    h2i.recorder_path, vars_to_save=output_vars, save_to_file=False
)

```
This example starts by saving all time series outputs to a csv file. Then, it specifies specific variables to pull out and outputs them as a dictionary (not a csv) when `save_to_file=False`

