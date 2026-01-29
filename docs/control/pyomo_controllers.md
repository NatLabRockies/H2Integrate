(pyomo-control)=
# Pyomo control framework
[Pyomo](https://www.pyomo.org/about) is an open-source optimization software package. It is used in H2Integrate to facilitate modeling and solving control problems, specifically to determine optimal dispatch strategies for dispatchable technologies.

Pyomo control allows for the possibility of feedback control at specified intervals, but can also be used for open-loop control if desired. In the pyomo control framework in H2Integrate, each technology can have control rules associated with them that are in turn passed to the pyomo control component, which is owned by the storage technology. The pyomo control component combines the technology rules into a single pyomo model, which is then passed to the storage technology performance model inside a callable dispatch function. The dispatch function also accepts a simulation method from the performance model and iterates between the pyomo model for dispatch commands and the performance simulation function to simulate performance with the specified commands. The dispatch function runs in specified time windows for dispatch and performance until the whole simulation time has been run.

An example of an N2 diagram for a system using the pyomo control framework for hydrogen storage and dispatch is shown below ([click here for an interactive version](./figures/pyomo-n2.html)). Note the control rules being passed to the dispatch component and the dispatch function, containing the full pyomo model, being passed to the performance model for the battery/storage technology. Another important thing to recognize, in contrast to the open-loop control framework, is that the storage technology outputs (commodity out, SOC, unused commodity, etc) are passed out of the performance model when using the Pyomo control framework rather than from the control component.

![](./figures/pyomo-n2.png)

The pyomo control framework currently supports both a simple heuristic method and an optimized dispatch method for load following control.

(heuristic-load-following-controller)=
## Heuristic Load Following Controller
The simple heuristic method is specified by setting the storage control to  `heuristic_load_following_controller`. When using the pyomo framework, a `dispatch_rule_set` for each technology connected to the storage technology must also be specified. These will typically be `pyomo_dispatch_generic_converter` for generating technologies, and `pyomo_dispatch_generic_storage` for storage technologies. More complex rule sets may be developed as needed.

For an example of how to use the heuristic pyomo control framework with the `heuristic_load_following_controller`, see
- `examples/18_pyomo_heuristic_wind_battery_dispatch`

(optimized-load-following-controller)=
## Optimized Load Following Controller
The optimized dispatch method is specified by setting the storage control to  `optimized_dispatch_controller`. The same `dispatch_rule_set` for each technology connected to the storage technology is followed as in the heuristic case. This method maximizes the load met while minimizing the cost of the system (operating cost) over each specified time window.

For an example of how to use the optimized pyomo control framework with the `optimized_dispatch_controller`, see
- `examples/27_pyomo_optimized_dispatch`
