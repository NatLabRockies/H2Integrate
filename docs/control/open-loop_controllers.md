(open-loop-control)=
# Open-Loop Controllers

## Open-Loop Storage Controllers
The open-loop storage controllers can be attached as the control strategy in the `tech_config` for various storage converters (e.g., battery or hydrogen storage). There are two controller types for storage:
1. Pass-through Controller - passes the commodity flow to the output without any modification
2. Demand Open-Loop Storage Controller - uses simple logic to attempt to meet demand using the storage technology.

(pass-through-controller)=
### Simple Open-Loop Storage Controller
The `SimpleStorageOpenLoopController` passes the input commodity flow to the output, possibly with minor adjustments to meet demand. It is useful for testing and as a placeholder for more complex controllers.

For examples of how to use the `SimpleStorageOpenLoopController` open-loop control framework, see the following:
- `examples/01_onshore_steel_mn`
- `examples/02_texas_ammonia`
- `examples/12_ammonia_synloop`

(demand-open-loop-storage-controller)=
### Demand Open-Loop Storage Controller
The `DemandOpenLoopStorageController` uses simple logic to dispatch the storage technology when demand is higher than commodity generation and charges the storage technology when the commodity generation exceeds demand, both cases depending on the storage technology's state of charge. For the `DemandOpenLoopStorageController`, the storage state of charge is an estimate in the control logic and is not informed in any way by the storage technology performance model.

An example of an N2 diagram for a system using the open-loop control framework for hydrogen storage and dispatch is shown below ([click here for an interactive version](./figures/open-loop-n2.html)). Note that the hydrogen out going into the finance model is coming from the control component.

![](./figures/open-loop-n2.png)

For examples of how to use the `DemandOpenLoopStorageController` open-loop control framework, see the following:
- `examples/14_wind_hydrogen_dispatch/`
- `examples/19_simple_dispatch/`
