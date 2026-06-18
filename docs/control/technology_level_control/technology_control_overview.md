# Technology-Level Control

Every technology group in H2Integrate contains a controller subsystem. Its job is to translate a `{commodity}_set_point` signal into the `{commodity}_command_value` consumed by the technology's performance model. This convention keeps the framework consistent: every technology exposes the same set-point/command-value interface, regardless of whether a system-level controller (SLC) is present and regardless of how complex the underlying control logic is.

(implicit-passthrough-controller)=
## Implicit passthrough controller

If a technology does not define its own `control_strategy`, H2Integrate automatically inserts a `PassthroughController` into the technology group. This controller simply copies `{commodity}_set_point` to `{commodity}_command_value` so that:

- When an SLC is present, the SLC's per-tech set-point is fed straight to the performance model.
- When no SLC is present, the set-point input defaults to a large value so the performance model behaves as if unconstrained (the model typically saturates at its rated capacity).

If you add your own controller via `control_strategy` in the technology config, that controller is used instead of the passthrough. User-defined controllers must produce the same `{commodity}_command_value` output so the rest of the framework can connect to them in a uniform way.

## Control frameworks

There are two different systematic approaches, or frameworks, in H2Integrate for technology-level control: [open-loop](#open-loop-control) and [pyomo](#pyomo-control). These two frameworks are useful in different situations and have different impacts on the system and control strategies that can be implemented. Both control frameworks are focused on technology-level dispatching. The open-loop framework has logic that is applicable to both storage technologies and converter technologies and the pyomo framework is currently applicable to storage technologies. The technology-level storage controllers may curtail/discard commodity amounts exceeding the needs of the storage technology and the specified demand. However, any unused commodity may be connected to another down-stream component to avoid actual curtailment.

(open-loop-control-framework)=
## Open-loop control framework
The first approach, [open-loop control](#open-loop-control), assumes no feedback of any kind to the controller. The open-loop framework does not require a detailed technology performance model and can essentially act as the performance model. The open-loop framework establishes a control component that runs the control and passes out information about `<commodity>_unmet_demand`, `unused_<commodity>`, `<commodity>_out`, and `total_<commodity>_unmet_demand`.

Supported controllers:
- [`SimpleStorageOpenLoopController`](#pass-through-controller)
- [`DemandOpenLoopStorageController`](#demand-open-loop-storage-controller)
- [`PeakLoadManagementHeuristicOpenLoopStorageController`](#peak-load-management-open-loop-storage-controller)

(pyomo-control-framework)=
## Pyomo control framework
The second systematic control approach, [pyomo control](#pyomo-control), allows for the possibility of feedback control at specified intervals, but can also be used for open-loop control if desired. [Pyomo](https://www.pyomo.org/about) is an open-source optimization software package. It is used in H2Integrate to facilitate modeling and solving control problems, specifically to determine optimal dispatch strategies for dispatchable technologies.

In the pyomo control framework in H2Integrate, each technology can have control rules associated with them that are in turn passed to the pyomo control component, which is owned by the storage technology. The pyomo control component combines the technology rules into a single pyomo model, which is then passed to the storage technology performance model inside a callable dispatch function. The dispatch function also accepts a simulation method from the performance model and iterates between the pyomo model for dispatch commands and the performance simulation function to simulated performance with the specified commands. The dispatch function runs in specified time windows for dispatch and performance until the whole simulation time has been run.

Supported controllers:
- [`HeuristicLoadFollowingStorageController`](#heuristic-load-following-controller)
- [`OptimizedDispatchController`](#optimized-load-following-controller)
