# Hydrogen Fuel Cell Model

The hydrogen fuel cell performance model implemented in H2Integrate is a linearized model that depends on the hydrogen inflow, `fuel_cell_efficiency_hhv` and `system_capacity_kw` to calculate the output electricity. The model will not allow negative electricity to be produced or more than the `system_capacity_kw`.

There are no non-linear considerations in this model such as warm-up delays, degraded performance over operational life, etc.

The hydrogen fuel cell cost model is implemented to uses cost values that are in dollars per kilowatt (or per kilowatt per year) because that's the typical reporting metric for hydrogen fuel cells.

```{note}
To ensure the hydrogen fuel cell is appropriately connected with other electricity producing technologies it needs to include `h2_fuel_cell` in the technology name in the `tech_config["technologies]`
```

## Performance Model

```{eval-rst}
.. autoclass:: h2integrate.converters.hydrogen.h2_fuel_cell.H2FuelCellPerformanceConfig
   :members:
   :undoc-members:
   :show-inheritance:
```

```{eval-rst}
.. autoclass:: h2integrate.converters.hydrogen.h2_fuel_cell.H2FuelCellPerformanceModel
   :members:
   :undoc-members:
   :show-inheritance:
```

## Cost Model

```{eval-rst}
.. autoclass:: h2integrate.converters.hydrogen.h2_fuel_cell.H2FuelCellCostConfig
   :members:
   :undoc-members:
   :show-inheritance:
```

```{eval-rst}
.. autoclass:: h2integrate.converters.hydrogen.h2_fuel_cell.H2FuelCellCostModel
   :members:
   :undoc-members:
   :sho
