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
- Cost and finance models are skipped until the final window. They may compute more than once as that window converges.


To maintain the default behavior, omit `n_timesteps_window`, or set it equal to `n_timesteps`, and all subsystem models will simulate their full time series individually and separately.


In the standard simulation configuration, the plant solver loops over all the models in the plant, computing the full output time series (length `n_timesteps`) for each. If necessary, the models are iteratively simulated repeatedly using the nonlinear block Gauss-Seidel (NLBGS) method until their inputs and outputs converge to stable values that satisfy the convergence criteria of the default plant group nonlinear solver.

```{figure} figures/standard_solver.png
:width: 85%
:align: center

Default plant group nonlinear solver.
```

When `n_timesteps_window` is smaller than `n_timesteps`, H2Integrate uses nonlinear block
Gauss-Seidel to solve each window before advancing. If a window fails to converge, the solver
stops and reports its starting timestep. Time marching honors the Gauss-Seidel settings in
`system_level_control.solver_options`, but does not support other solver types, zero solver
iterations, or disabling errors on non-convergence.


```{figure} figures/time_marching_solver.png
:width: 85%
:align: center

Time-marching plant group nonlinear solver.
```

## Current limitations

- Every technology performance model, technology control strategy, and system-level controller  in the plant must be steppable.
  If any is not, H2Integrate raises an error that lists the unsupported models.
- For cost-aware system-level controllers, use a numeric marginal cost or `buy_price` in `cost_per_tech`. Time marching does not support `VarOpEx` or `feedstock` pricing because the required cost outputs are unavailable in earlier windows.
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
