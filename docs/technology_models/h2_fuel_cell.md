# Hydrogen Fuel Cell Model

The {py:class}`~h2integrate.converters.hydrogen.h2_fuel_cell.LinearH2FuelCellPerformanceModel`
is a linearized model configured by
{py:class}`~h2integrate.converters.hydrogen.h2_fuel_cell.LinearH2FuelCellPerformanceConfig`.
It depends on `hydrogen_in`, `electricity_command_value`, `fuel_cell_efficiency`, and
`system_capacity` to calculate `electricity_out`. The model caps output at system capacity and
the command, and prevents negative production. It reports `hydrogen_consumed`, production
summaries, and a replacement schedule, and supports one-hour time steps.

There are no non-linear considerations in this model such as warm-up delays, degraded performance over operational life, etc.

The {py:class}`~h2integrate.converters.hydrogen.h2_fuel_cell.H2FuelCellCostModel`, configured by
{py:class}`~h2integrate.converters.hydrogen.h2_fuel_cell.H2FuelCellCostConfig`, uses system
capacity and annual electricity production to report `CapEx`, fixed `OpEx`, and `VarOpEx`.

```{note}
To ensure the hydrogen fuel cell is appropriately connected with other electricity producing technologies, the model name in the `tech_config["technologies]` needs to begin with `h2_fuel_cell`.
```

## Performance Model

```{eval-rst}
.. autoclass:: h2integrate.converters.hydrogen.h2_fuel_cell.LinearH2FuelCellPerformanceConfig
   :members:
   :undoc-members:
   :show-inheritance:
   :no-index:
```

```{eval-rst}
.. autoclass:: h2integrate.converters.hydrogen.h2_fuel_cell.LinearH2FuelCellPerformanceModel
   :members:
   :undoc-members:
   :show-inheritance:
   :no-index:
```

## Cost Model

```{eval-rst}
.. autoclass:: h2integrate.converters.hydrogen.h2_fuel_cell.H2FuelCellCostConfig
   :members:
   :undoc-members:
   :show-inheritance:
   :no-index:
```

```{eval-rst}
.. autoclass:: h2integrate.converters.hydrogen.h2_fuel_cell.H2FuelCellCostModel
   :members:
   :undoc-members:
   :show-inheritance:
   :no-index:
