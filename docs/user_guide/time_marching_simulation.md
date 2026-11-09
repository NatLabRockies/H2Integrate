# Time-Marching Simulation

By default, H2Integrate simulates each technology in a linear fashion: each model computes its full time series before the next model in the plant runs.
In a time-marching simulation, the plant advances through the simulation one window of timesteps at a time.
Every model computes only its current window, then the next window is simulated, and so on until the end of the simulation.
Models that carry state between timesteps, such as storage, keep that state from one window to the next.

```{figure} figures/sequential_cartoon.png
:width: 85%
:align: center

Default simulation: Each model computes its full time series before the next model in the plant runs.
```


```{figure} figures/time_marching_cartoon.png
:width: 85%
:align: center

Time-marching simulation: All models compute one window of the simulation at a time before moving on to the next one.
```

Time-marching is opt-in and does not change the results of a simulation that is supported.
Models must be flagged as steppable (see below) before they can be used in a time-marching simulation.

## Configuring a time-marching simulation

To run a time-marching simulation in H2Integrate, specify `n_timesteps_window`, the number of timesteps in each window, in the `plant.simulation` section of the plant config:

```yaml
plant:
  simulation:
    dt: 3600
    n_timesteps: 8760
    n_timesteps_window: 24
```

- `n_timesteps_window` must be a positive integer that evenly divides `n_timesteps`.
- Cost and finance models are computed once, after the final window.



To maintain the default behavior, omit `n_timesteps_window`, or set it equal to `n_timesteps`, and all subsystem models will simulate their full time series individually and separately.


In the standard simulation configuration, the plant solver loops over all the models in the plant, computing the full output time series (length `n_timesteps`) for each. If necessary, the models are iteratively simulated repeatedly using the nonlinear block Gauss-Seidel (NLBGS) method until their inputs and outputs converge to stable values that satisfy the convergence criteria of the default plant group nonlinear solver.

```{figure} figures/standard_solver.png
:width: 85%
:align: center

Default plant group nonlinear solver.
```

When `n_timesteps_window` is specified in the configuration files, H2Integrate assigns a custom time-marching nonlinear solver to the plant group to manage the time-marching simulation. The time-marching nonlinear solver differs from from the default nonlinear solver in one important aspect. The time-marching solver loops over each simulation window in the time-marching simulation, and within any given simulation window, loops over the performance and control models in the plant, computing a slice of the output time series (length `n_timesteps_window`) for each. If necessary, the models are iteratively simulated repeatedly using the NLBGS method until their inputs and outputs in the current simulation window converge.


The cost and finance models are ran once, after all the control and performance models have been simulated and converged for all simulation windows in the time-marching simulation.


```{figure} figures/time_marching_solver.png
:width: 85%
:align: center

Time-marching plant group nonlinear solver.
```

## Current limitations

- Every technology performance model and technology control strategy in the plant must be steppable.
  If any is not, H2Integrate raises an error that lists the unsupported models.
- Derivatives are not propagated through a time-marching simulation, so use gradient-free or finite-difference drivers.

## Steppable models

The following technology performance models and control strategies are currently steppable:

- `PYSAMSolarPlantPerformanceModel`
- `PYSAMWindPlantPerformanceModel`
- `NaturalGasPerformanceModel`
- `GridPerformanceModel`
- `GenericCombinerPerformanceModel`
- `GenericDemandComponent`

- `StoragePerformanceModel`
- `DemandOpenLoopStorageController`
- `PassthroughController`

- `DemandFollowingControl`
- `CostMinimizationControl`
- `ProfitMaximizationControl`


## Examples

- [Example 24](https://github.com/NatLabRockies/H2Integrate/tree/develop/examples/24_solar_battery_grid) (`examples/24_solar_battery_grid/run_time_marching.py`) simulates a solar, battery, and grid plant both
at once and in 24-timestep windows, and shows that the results match.
- [Example 35](https://github.com/NatLabRockies/H2Integrate/tree/develop/examples/35_system_level_control/time_marching_system_level_control) (`examples/35_system_level_control/time_marching_system_level_control/run_time_marching_SLC.py`) simulates a plant with wind, battery, and a natural gas plant using three rule-based system level control strategies: demand following control, cost minimization control, and profit maximization control.
