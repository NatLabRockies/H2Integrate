# Time-Marching Simulation

By default, H2Integrate simulates each technology in a linear fashion: each model computes its full time series before the next model in the plant runs.
In a time-marching simulation, the plant advances through the simulation one window of timesteps at a time.
Every model computes only its current window, then the next window is simulated, and so on until the end of the simulation.
Models that carry state between timesteps, such as storage, keep that state from one window to the next.

Time-marching is opt-in and does not change the results of a simulation that is supported.
Models must be flagged as steppable (see below) before they can be used in a time-marching simulation.

## Configuring a time-marching simulation

Set `n_timesteps_window`, the number of timesteps in each window, in the `plant.simulation` section of the plant config:

```yaml
plant:
  simulation:
    dt: 3600
    n_timesteps: 8760
    n_timesteps_window: 24
```

- Omit `n_timesteps_window`, or set it equal to `n_timesteps`, to simulate all timesteps at once (the default behavior).
- `n_timesteps_window` must be a positive integer that evenly divides `n_timesteps`.
- Cost and finance models are computed once, after the final window.

## Current limitations

- Time-marching is not supported together with system-level control or a technology interconnection graph that contains a cycle.
  H2Integrate raises a `NotImplementedError` in these cases.
- Every technology performance model and technology control strategy in the plant must be steppable.
  If any is not, H2Integrate raises an error that lists the unsupported models.
- Derivatives are not propagated through a time-marching simulation, so use gradient-free or finite-difference drivers.

## Steppable models

The following technology performance models and control strategies are currently steppable:

- `PYSAMSolarPlantPerformanceModel`
- `GridPerformanceModel`
- `GenericCombinerPerformanceModel`
- `GenericDemandComponent`
- `StoragePerformanceModel`
- `DemandOpenLoopStorageController`
- `PassthroughController`

## Example

[Example 38](https://github.com/NatLabRockies/H2Integrate/tree/develop/examples/38_time_marching_simulation) (`examples/38_time_marching_simulation`) simulates a solar, battery, and grid plant both
at once and in 24-timestep windows, and shows that the results match.
