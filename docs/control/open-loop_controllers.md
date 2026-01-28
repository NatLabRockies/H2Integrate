(open-loop-control)=
# Open-Loop Controllers

## Open-Loop Storage Controllers
The open-loop storage controllers can be attached as the control strategy in the `tech_config` for various storage converters (e.g., battery or hydrogen storage). There are two controller types for storage:
1. Pass-through Controller - passes the commodity flow to the output without any modification
2. Demand Open-Loop Storage Controller - uses simple logic to attempt to meet demand using the storage technology.

(pass-through-controller)=
### Pass-Through Controller
The `pass_through_controller` simply directly passes the input commodity flow to the output without any modifications. It is useful for testing, as a placeholder for more complex controllers, and for maintaining consistency between controlled and uncontrolled frameworks as this 'controller' does not alter the system output in any way.

For examples of how to use the `pass_through_controller` open-loop control framework, see the following:
- `examples/01_onshore_steel_mn`
- `examples/02_texas_ammonia`
- `examples/12_ammonia_synloop`

(demand-open-loop-storage-controller)=
### Demand Open-Loop Storage Controller
The `demand_open_loop_storage_controller` uses simple logic to dispatch the storage technology when demand is higher than commodity generation and charges the storage technology when the commodity generation exceeds demand, both cases depending on the storage technology's state of charge. For the `demand_open_loop_storage_controller`, the storage state of charge is an estimate in the control logic and is not informed in any way by the storage technology performance model.

An example of an N2 diagram for a system using the open-loop control framework for hydrogen storage and dispatch is shown below ([click here for an interactive version](./figures/open-loop-n2.html)). Note that the hydrogen out going into the finance model is coming from the control component.

![](./figures/open-loop-n2.png)

For examples of how to use the `demand_open_loop_storage_controller` open-loop control framework, see the following:
- `examples/14_wind_hydrogen_dispatch/`
- `examples/19_simple_dispatch/`

## Open-Loop Converter Controllers

Open-loop converter controllers define rule-based logic for meeting commodity demand profiles without using dynamic system feedback. These controllers operate independently at each timestep.

This page documents two core controller types:
1. Demand Open-Loop Converter Controller — meets a fixed demand profile.
2. Flexible Demand Open-Loop Converter Controller — adjusts demand up or down within flexible bounds.

(demand-open-loop-converter-controller)=
### Demand Open-Loop Converter Controller
The `demand_open_loop_converter_controller` allocates commodity input to meet a defined demand profile. It does not contain energy storage logic, only **instantaneous** matching of supply and demand.

The controller computes each value per timestep:
- Unmet demand (non-zero when supply < demand, otherwise 0.)
- Unused commodity (non-zero when supply > demand, otherwise 0.)
- Delivered output (commodity supplied to demand sink)

This provides a simple baseline for understanding supply–demand balance before adding complex controls.

#### Configuration
The controller is defined within the `tech_config` and requires these inputs.

| Field             | Type           | Description                           |
| ----------------- | -------------- | ------------------------------------- |
| `commodity_name`  | `str`          | Commodity name (e.g., `"hydrogen"`).  |
| `commodity_units` | `str`          | Units (e.g., `"kg/h"`).               |
| `demand_profile`  | scalar or list | Timeseries demand or constant demand. |

```yaml
control_strategy:
    model: demand_open_loop_converter_controller
model_inputs:
  control_parameters:
    commodity_name: hydrogen
    commodity_units: kg/h
    demand_profile: [10, 10, 12, 15, 14]
```
For an example of how to use the `demand_open_loop_converter_controller` open-loop control framework, see the following:
- `examples/23_solar_wind_ng_demand`

(flexible-demand-open-loop-converter-controller)=
### Flexible Demand Open-Loop Converter Controller
The `flexible_demand_open_loop_converter_controller` extends the fixed-demand controller by allowing the actual demand to flex up or down within defined bounds. This is useful for demand-side management scenarios where:
- Processes can defer demand (e.g., flexible industrial loads)
- The system requires demand elasticity without dynamic optimization

The controller computes:
- Flexible demand (clamped within allowable ranges)
- Unmet flexible demand
- Unused commodity
- Delivered output

Everything remains open-loop no storage, no intertemporal coupling.

For an example of how to use the `flexible_demand_open_loop_converter_controller` open-loop control framework, see the following:
- `examples/23_solar_wind_ng_demand`

The flexible demand component takes an input commodity production profile, the maximum demand profile, and various constraints (listed below), and creates a "flexible demand profile" that follows the original input commodity production profile while satisfying varying constraint.
Please see the figure below for an example of how the flexible demand profile can vary from the original demand profile based on the input commodity production profile and the ramp rates.
The axes are unlabeled to allow for generalization to any commodity and unit type.

| ![Flexible Demand Example](figures/flex_demand_fig.png) |
|-|


#### Configuration
The flexible demand controller is defined within the `tech_config` with the following parameters:

| Field               | Type           | Description                                  |
| ------------------- | -------------- | -------------------------------------------- |
| `commodity_name`          | `str`          | Commodity name.                              |
| `commodity_units`         | `str`          | Units for all values.                        |
| `demand_profile`          | scalar or list | Default (nominal) demand profile.            |
| `turndown_ratio`          | float          | Minimum fraction of baseline demand allowed. |
| `ramp_down_rate_fraction` | float          | Maximum ramp-down rate per timestep expressed as a fraction of baseline demand. |
| `ramp_up_rate_fraction` | float          | Maximum ramp-up rate per timestep expressed as a fraction of baseline demand. |
| `min_utilization` | float          | Minimum total fraction of baseline demand that must be met over the entire simulation. |

```yaml
model_inputs:
  control_parameters:
    commodity_name: hydrogen
    commodity_units: kg/h
    demand_profile: [10, 12, 10, 8]
    turndown_ratio: 0.1
    ramp_down_rate_fraction: 0.5
    ramp_up_rate_fraction: 0.5
    min_utilization: 0
```
