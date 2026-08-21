# System-Level Control

System-level control (SLC) within H2I is meant to operate to control the entire plant with performance and cost feedback driving the operation of the plant or system in a closed-loop. It acts as a supervisory controller meaning that it can work to coordinate the entire system and can work with other technology level controllers.

```{note}
The SLC framework is *technology-agnostic* and works with any H2I technology (converters, storage, feedstocks, demand components, etc.). It only cares about a technology's [`_control_classifier`](control_classifier.md) and the commodity it produces. To opt a technology in, set `_control_classifier` on its performance model; for `flexible` models, also call `self.apply_curtailment(outputs)` at the end of `compute()`. See the [developer guide on adding a new technology](../../developer_guide/adding_a_new_technology.md) for the full checklist.
```

The most basic SLC is shown in the figure below, where the SLC receives a `{commodity}_demand` signal. Based on that demand it emits a per-technology `{tech_name}_{commodity}_set_point` signal to each controlled technology. Each technology group contains a controller that converts the incoming `{commodity}_set_point` into the `{commodity}_command_value` actually consumed by the technology's performance model. From each technology block there is `{commodity}_out` (potentially changed by the command-value signal) that is connected via feedback to the SLC. The SLC will then attempt to converge the system where it will loop through changing the per-tech set points in attempts to meet the system demand until the overall system stops changing how much `{commodity}_out` each technology is outputting.

```{note}
Every technology group has an *implicit passthrough controller* that converts `{commodity}_set_point` into `{commodity}_command_value`. If a technology defines its own `control_strategy`, that controller is used instead. This convention keeps the framework consistent and makes the set-point to command-value hand-off uniform for every technology, regardless of whether an SLC is present.
```

```{important}
SLC demand is set by connecting a demand component (for example, `GenericDemandComponent`) to the system. Currently, the only supported models for the demand component are the `GenericDemandComponent` and the `FlexibleDemandComponent`. The technology defined as the demand component must be included in the `technology_interconnections` in the plant configuration file.
```

```{figure} figures/slc_basic.png
:width: 70%
:align: center
```

The SLC control strategy, demand technology, and solver options are set within `plant_config.yaml` under the `"system_level_control"` section.

```yaml
system_level_control:
  control_strategy: DemandFollowingControl
  demand_component: electrical_load_demand
  solver_options:
    solver_name: gauss_seidel
    max_iter: 20
    convergence_tolerance: 1.0e-6
```

To set the demand for SLC, define exactly the demand block/component in `tech_config.yaml`. For example:

```yaml
electrical_load_demand:
    performance_model:
        model: GenericDemandComponent
    model_inputs:
        performance_parameters:
        commodity: electricity
        commodity_rate_units: kW
        demand_profile: 30000
```

## Control Strategies
There are several simple control strategies already implemented in the SLC paradigm. While fairly simplistic, they are meant to illustrate how information can be passed from different blocks/components (converters, storage, feedstocks, demand, etc.) and models (performance, cost, finance) to use within the SLC.

The current control strategies are:
1. [Demand Following](#slc-demand-following)
2. [Profit Maximization](#slc-profit-max)
3. [Cost Minimization](#slc-cost-min)

```{note}
The strategies currently implemented are experimental and will likely require further development for specific analyses.
```

All control strategies inherit [`SystemLevelControlBase`](#slc-base), which is a base class that has common setup logic shared by all system-level control strategies.

See additional information, which is more developer focused, about the [`SystemLevelControlBase`](#slc-base).

## Solver Options
The system attempts to converge the system using a solver. The solver is defined in `solver_options`.
