(financeparameters:specifiyingfinanceparameters)=
# Finance Parameters
## Overview
The `finance_parameters` section of the `plant_config` defines the financial subsystems of the plant. These parameters configure how costs, revenues, and investment metrics are calculated across all or parts of the modeled system.
```{note}
The `plant_life` parameter from the `plant` section of the `plant_config` is also used in finance calculations as the operating life of the plant.
```

If a user is computing finances, then at a minimum, `finance_parameters` must include:
- `cost_adjustment_parameters`:
  - `target_dollar_year`: dollar-year to convert costs to.
  - `cost_year_adjustment_inflation`: used to adjust costs for each technology from its native cost year to the `target_dollar_year` (see [details on cost years and cost models here](cost:cost_years))

Other variables in finance_parameters vary depending on the financial analysis structure. There are two major modes of operation:
- **Single-model mode (default)**: All technologies are grouped together into a single financial calculation.
- **Subgroup mode**: Technologies are split into one or more subgroups, each with its own commodity and one or more finance models.

### Finance Groups vs. Finance Subgroups
Within this framework, there are two distinct layers, **finance groups** and **finance subgroups**:

#### Finance groups
  A finance group contains the attributes needed to run one finance model:
  - `finance_model`:
    The name of the financial model to use (e.g., `ProFastLCO`). Must correspond to one of the available models in `self.supported_models`.
  - `model_inputs`:
    A dictionary of parameters passed into the chosen finance model. These provide customization of assumptions such as discount rate, debt fraction, or cost escalation.
  - `commodity` (conditionally required):
    The product or service whose financial performance is being analyzed (e.g., hydrogen, electricity). Required if `finance_subgroups` are not used, otherwise defined within `finance_subgroups`.

#### Finance subgroups
  Subgroups are flexible collections of technologies that map to one or more finance groups. They allow you to:
  - Calculate financial metrics for only part of the system.
  - Compare different metrics of the same system (e.g., delivered vs. produced cost of hydrogen).
  - Run multiple models (e.g., LCOH, LCOE, LCOS, or NPV) on overlapping or distinct sets of technologies.
  - Model distributed or multi-location systems finances within a single plant configuration.

  Subgroups contain information on how to construct the specific subgroup:
  - `commodity`:
    The product or service whose financial performance is being analyzed (e.g., hydrogen, electricity). Each finance subgroup is tied to a single commodity.
  - `technologies`:
    Technologies to include in the specific subgroup calculation (e.g., you might only want to include technologies that produce electricity in the levelized cost of energy calculation).
  - `finance_groups`:
    List of `finance_groups` that contain the `finance_model` and `model_inputs`. Required if multiple `finance_groups` are being used. Technology-specific `finance_groups` can be called by using the technology name listed in the `tech_config` (e.g., `steel` to use the steel specific finance model).
  - `commodity_desc` (optional):
    A text label to further distinguish outputs for a commodity. This is particularly useful when multiple finance models or subgroups reference the same commodity but need to produce separate outputs.
  - `commodity_stream` (optional):
    A text label of a technology that outputs the specified ``commodity`` to use as the commodity production stream in finance calculations. This is particularly useful when wanting to choose a specific commodity stream to use in finance calculations (such as the outputs of combiners or splitters)

```{important}
If no subgroups are defined, a **default subgroup** is created that contains *all technologies* and references the default finance model and commodity defined in `finance_groups`.
```

## Example finance configurations

We'll now walk through three common configurations, highlighting the differences in the `plant_config` files and showcasing examples that use each approach.

(finparam:nosubgroups)=
### Single-model (no subgroups)
If no `finance_subgroups` are specified, all technologies are automatically grouped into a single default subgroup. In this case:
  - `commodity` and `finance_model` must be defined directly in `finance_groups`.
  - A default subgroup named `default` is created internally.

General format:
```yaml
finance_parameters:
  finance_groups:
    commodity: "hydrogen"
    finance_model: "ProFastLCO"
    model_inputs:
      discount_rate: 0.08
```

Outputs are named:
```
finance_subgroup_default.<finance_model_output>
```

Examples:
- [Example 7](https://github.com/NREL/H2Integrate/blob/develop/examples/07_run_of_river_plant/plant_config.yaml)


(finparams:singlemodelsubgroups)=
### Single finance model with subgroups
If `finance_groups` contains a single model definition, you may split technologies into multiple subgroups. Each subgroup defines its own `commodity` and list of `technologies` but uses the shared finance model.

In this case you see that the commodity is not defined within the `finance_groups` and is instead defined within the `finance_subgroups`. In this example there are two separate financial calculations one for `subgroup_a`, which is for the hydrogen commodity and one for `subgroup_b`, which is for the ammonia commodity and includes the "electrolyzer" and "asu". If you had additional technologies in your `tech_config` besides those, they would have to be included in the `finance_subgroups` to be included in the financial calculations.

General format:
```yaml
finance_parameters:
  finance_groups:
    finance_model: "ProFastLCO"
    model_inputs: #dictionary of inputs for ProFastLCO
  finance_subgroups:
    subgroup_a:
      commodity: "hydrogen" #required
      technologies: ["electrolyzer"]
    subgroup_b:
      commodity: "ammonia" #required
      technologies: ["electrolyzer", "asu"]
```

Outputs are named:
```
finance_subgroup_<subgroup_name>.<finance_model_output>
```

Examples:
- [Example 02](https://github.com/NREL/H2Integrate/tree/develop/examples/02_texas_ammonia/plant_config.yaml)
- [Example 03 - CO2H](https://github.com/NREL/H2Integrate/tree/develop/examples/03_methanol/co2_hydrogenation/plant_config_co2h.yaml)
- [Example 09 - DOC](https://github.com/NREL/H2Integrate/tree/develop/examples/09_co2/direct_ocean_capture/plant_config.yaml)
  <!-- - [Example 05](/examples/)
  - 11, 12, 13, 14, 15, 17 -->

```{note}
Within `finance_groups`, the `commodity`, `finance_model`, and `model_inputs` may be placed under a named key for the finance group and indented one level deeper. This structure is optional when only a single finance model is used, but it is supported for consistency with the format required when specifying multiple finance models (see [Specifying Multiple Finance Groups](finparams:multimodelsubgroups)).
```

(finparams:multimodelsubgroups)=
### Multiple financial models with subgroups
When multiple finance models are needed (e.g., to calculate both NPV and LCOH, or to compare multiple finance cases), multiple finance groups can be defined and assigned to subgroups.

General format:
```yaml
finance_parameters:
  finance_groups:
    group_a:
      finance_model: "ProFastLCO"
      model_inputs: {discount_rate: 0.08}
    group_b:
      finance_model: "NPVFinancial"
      model_inputs: {discount_rate: 0.05}
  finance_subgroups:
    subgroup_a:
      commodity: "hydrogen"
      finance_groups: ["group_a"]
      technologies: ["electrolyzer"]
    subgroup_b:
      commodity: "hydrogen"
      commodity_desc: "delivered"
      finance_groups: ["group_a", "group_b"]
      technologies: ["pipeline", "storage"]
```
Output naming:
- If multiple finance groups are in the same subgroup, output names include the subgroup, commodity, description (if provided), and finance group name to avoid collisions in the OpenMDAO framework:
```
finance_subgroup_<subgroup_name>.<financial_model_output>_<commodity_desc>_<financial_group>
finance_subgroup_subgroup_a.LCOH_group_a
finance_subgroup_subgroup_b.LCOH_delivered_group_a
finance_subgroup_subgroup_b.NPV_hydrogen_delivered_group_b
```

Examples:
- [Example 10](https://github.com/NREL/H2Integrate/blob/develop/examples/10_electrolyzer_om/plant_config.yaml)

#### Key Behaviors
- If `finance_parameters` is missing --> no finance model is created.
- If no `finance_subgroups` are defined → a default subgroup containing all technologies is created automatically.
- Finance groups must not include a key named "default", as this is reserved for internal use.
- Each subgroup must reference valid technology keys from technology_config['technologies']. Invalid keys raise errors.
- Finance models must be listed in `self.supported_models`. Unknown models raise errors.
