# System-Level Control

System-level control (SLC) within H2I is meant to operate to control the entire plant with performance and cost feedback driving the operation of the plant or system in a closed-loop. It acts as a supervisory controller meaning that it can work to coordinate the entire system and can work with other technology level controllers.

The most basic SLC is shown in the figured below, where the SLC receives a demand. Based on that demand it will output set points for `{commodity}_out` to the individual technology blocks included within the system. Each technology based on it's controller classification will respond to the set point. From each technology block there is `{commodity}_out` (potentially changed by the set point signal) that is connected via feedback to the SLC. The SLC will then attempt to converge the system where it will loop through changing the set points in attempts to meet the demand until the overall system stops changing how much `{commodity}_out` each technology is outputting.

```{figure} figures/slc_basic.png
:width: 70%
:align: center
```

The SLC control strategy and solver options are set within `plant_config.yaml` under the `"system_level_control"` section.

```{yaml}
system_level_control:
  control_strategy: DemandFollowingControl
  solver_options:
    solver_name: gauss_seidel
    max_iter: 20
    convergence_tolerance: 1.0e-6
```

To set the demand for the SLC that is configured in the `tech_config.yaml` using a demand block/component. For example:

```{yaml}
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
2. [Cost Minimization](#slc-cost-min)
3. [Profit Maximization](#slc-profit-max)

```{note}
The strategies currently implemented are experimental and will likely require further development for specific analyses.
```

All control strategies inherit `SystemLevelControlBase`, which is a base class that has common setup logic shared by all system-level control strategies.

See additional information, which is more developer focused, about the [`SystemLevelControlBase`](#slc-base).

## Solver Options
The system attempts to converge the system using a solver. The solver is defined in `solver_options`.
