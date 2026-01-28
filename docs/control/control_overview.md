# Control Overview

There are two different systematic approaches, or frameworks, in H2Integrate for control: [open-loop](#open-loop-control) and [pyomo](#pyomo-control). These two frameworks are useful in different situations and have different impacts on the system and control strategies that can be implemented. Both control frameworks are focused on technology-level dispatching. The open-loop framework has logic that is applicable to both storage technologies and converter technologies and the pyomo framework is currently applicable to storage technologies. However, we plan to extend them to work more generally as system controllers. Although the controllers are not operating at the system-level for now, they behave somewhat like system controllers in that they may curtail/discard commodity amounts exceeding the needs of the storage technology and the specified demand. However, any unused commodity may be connected to another down-stream component to avoid actual curtailment.

(open-loop-control-framework)=
## Open-loop control framework
The first approach, [open-loop control](#open-loop-control), assumes no feedback of any kind to the controller. The open-loop framework does not require a detailed technology performance model and can essentially act as the performance model. The open-loop framework establishes a control component that runs the control and passes out information about `<commodity>_unmet_demand`, `unused_<commodity>`, `<commodity>_out`, and `total_<commodity>_unmet_demand`.

Supported controllers:
- [`pass_through_controller`](#pass-through-controller)
- [`demand_open_loop_storage_controller`](#demand-open-loop-storage-controller)
- [`demand_open_loop_converter_controller`](#demand-open-loop-converter-controller)
- [`flexible_demand_open_loop_converter_controller`](#flexible-demand-open-loop-converter-controller)


(pyomo-control-framework)=
## Pyomo control framework
The second systematic control approach, [pyomo control](#pyomo-control), allows for the possibility of feedback control at specified intervals, but can also be used for open-loop control if desired. [Pyomo](https://www.pyomo.org/about) is an open-source optimization software package. It is used in H2Integrate to facilitate modeling and solving control problems, specifically to determine optimal dispatch strategies for dispatchable technologies.

In the pyomo control framework in H2Integrate, each technology can have control rules associated with them that are in turn passed to the pyomo control component, which is owned by the storage technology. The pyomo control component combines the technology rules into a single pyomo model, which is then passed to the storage technology performance model inside a callable dispatch function. The dispatch function also accepts a simulation method from the performance model and iterates between the pyomo model for dispatch commands and the performance simulation function to simulated performance with the specified commands. The dispatch function runs in specified time windows for dispatch and performance until the whole simulation time has been run.

Supported controllers:
- [`heuristic_load_following_controller`](#heuristic-load-following-controller)
