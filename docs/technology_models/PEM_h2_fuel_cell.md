# PEM Hydrogen Fuel Cell Model

The PEM hydrogen fuel cell performance model implemented in H2Integrate is an electrochemical model that simulates the conversion of hydrogen and oxygen into electricity and water. The model uses a polynomial fit of an I-V (current-voltage) curve to determine the operating point of each cell based on the input `electricity_set_point`, then computes `hydrogen_consumed`, `oxygen_consumed`, `water_out`,  and `electricity_out` as the outputs of the system for each timestep.

The IV curve was extracted from the data in this GitHub repository [1](https://github.com/ECSIM/pem-dataset1). The model uses chemical reaction equations to calculate the consumed and produced commodities from the fuel cell reaction ([3](https://www.sciencedirect.com/science/article/pii/S0360319906005726), [4](https://www.sciencedirect.com/science/article/pii/S0360319924051577)).

The model is sized by `system_capacity_kw` and `n_stacks`. The number of cells per stack is calculated from the stack size, a fixed cell active area (400 cm²)([2](https://www.energy.gov/sites/prod/files/2018/02/f49/fcto_battelle_mfg_cost_analysis_1%20_to_25kw_pp_chp_fc_systems_jan2017_0.pdf)), and a maximum cell power density. Hydrogen and oxygen availability is checked against the demand at each timestep. If the available oxygen or hydrogen is insuffucient for the requested power, the operating current is reduced to match the lowest available feedstock.  Electricity output is clipped to the system capacity.

There are no non-linear operational considerations in this model such as warm-up delays, degraded performance over operational life, voltage recalculation after current adjustment for limited feedstock supply, or thermal dynamics beyond a constant stack temperature input.


```{note}
The I-V curve is currently internally defined in the model and not adjustable.
```

## Performance Model

```{eval-rst}
.. autoclass:: h2integrate.converters.hydrogen.PEM_h2_fuel_cell.PEMH2FuelCellPerformanceConfig
   :members:
   :undoc-members:
   :show-inheritance:
   :no-index:
```

```{eval-rst}
.. autoclass:: h2integrate.converters.hydrogen.PEM_h2_fuel_cell.PEMH2FuelCellPerformanceModel
   :members:
   :undoc-members:
   :show-inheritance:
   :no-index:
```
