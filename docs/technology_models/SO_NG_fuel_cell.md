# Solid Oxide Natural Gas Fuel Cell Model

The solid oxide natural gas (SO NG) fuel cell performance model implemented in H2Integrate is an electrochemical model that simulates the conversion of natural gas (assumed to be methane in the chemical reaction equations), steam, and oxygen into electricity, water, and carbon dioxide. The model uses a polynomial fit of an I-V (current-voltage) curve to determine the operating point of each cell based on the input `electricity_set_point`, then computes `natural_gas_consumed`, `oxygen_consumed`, `water_out`, `carbon_dioxide_out`, and `electricity_out` as the outputs of the system for each timestep.

The model is sized by `system_capacity_kw` and `n_stacks`. The number of cells per stack is calculated from the stack size, a fixed cell active area (400 cm²), and a maximum cell power density. Natural gas and oxygen consumption are computed from the cell current via Faraday's law assuming complete electrochemical oxidation of methane. The model uses the methane-reforming equation rather than a direct electrochemical methan-combusting reaction. This assumes that the methane is broken down in a steam-reforming process before the feedstock enteres the fuel cell ([1](https://www.sciencedirect.com/science/article/pii/S0360319906005726)). Electricity output is clipped to the system capacity.

There are no non-linear operational considerations in this model such as warm-up delays, degraded performance over operational life, or thermal dynamics beyond a constant stack temperature input.

```{note}
The I-V curve is currently internally defined in the model and not adjustable.
```

## Performance Model

```{eval-rst}
.. autoclass:: h2integrate.converters.natural_gas.SO_NG_fuel_cell.SONGFuelCellPerformanceConfig
   :members:
   :undoc-members:
   :show-inheritance:
   :no-index:
```

```{eval-rst}
.. autoclass:: h2integrate.converters.natural_gas.SO_NG_fuel_cell.SONGFuelCellPerformanceModel
   :members:
   :undoc-members:
   :show-inheritance:
   :no-index:
```
