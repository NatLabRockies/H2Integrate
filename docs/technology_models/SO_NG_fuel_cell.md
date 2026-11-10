# Solid Oxide Natural Gas Fuel Cell Model

The {py:class}`~h2integrate.converters.natural_gas.SO_NG_fuel_cell.SONGFuelCellPerformanceModel`,
configured by {py:class}`~h2integrate.converters.natural_gas.SO_NG_fuel_cell.SONGFuelCellPerformanceConfig`,
is an electrochemical model that simulates natural gas (assumed to be methane) and oxygen conversion
to electricity, water, and carbon dioxide. It uses a polynomial I-V curve with
`electricity_command_value` and reports `natural_gas_consumed`, `oxygen_consumed`, `water_out`,
`co2_out`, `heat_out`, and `electricity_out` for each timestep.

The IV curve was extracted from the data in this GitHub repository [1](https://github.com/ECSIM/pem-dataset1). The model uses chemical reaction equations to calculate the consumed and produced commodities from the fuel cell reaction ([3](https://www.sciencedirect.com/science/article/pii/S0360319906005726), [4](https://www.sciencedirect.com/science/article/pii/S0360319924051577)).

The model is sized by `system_capacity_kw` and `n_stacks`. The number of cells per stack is calculated from the stack size, a fixed cell active area (400 cm²), and a maximum cell power density ([2](https://www.sciencedirect.com/science/article/pii/S0360319906005726)). Natural gas and oxygen availability limit current and consumption is computed using Faraday's law. Electricity output is clipped to the rating calculated from the rounded cell count. Steam consumption for reforming is not modeled.

The model does not include warm-up delays, degradation, or thermal dynamics; the declared
`stack_temperature` input is not used in the calculation. It supports one-hour time steps and
also reports rated outputs, capacity factor, and total and annual electricity production.

```{note}
The I-V curve is currently internally defined in the model and not adjustable.
```

## Performance Model

```{eval-rst}
.. autoclass:: h2integrate.converters.natural_gas.SO_NG_fuel_cell.SONGFuelCellPerformanceConfig
   :no-members:
   :no-index:
```
