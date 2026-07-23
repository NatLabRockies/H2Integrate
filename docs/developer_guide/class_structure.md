(class_structure)=
# Class structure in H2Integrate

A major focus of H2Integrate is modularizing the components and system architecture so it's easier to construct and analyze complex hybrid energy systems producing commodities for a variety of uses.
As such, we've taken great care to develop a series of baseclasses and inherited classes to help users develop their own models.

## Choosing baseclasses for your model

Every model in H2Integrate inherits from a small set of baseclasses that wire it
into the rest of the framework. Before writing a new model, pick the appropriate base
class and configuration class for each piece of your technology:

| Piece               | Baseclass                                                | Config baseclass                |
| ------------------- | -------------------------------------------------------- | ------------------------------- |
| Performance model   | `PerformanceModelBaseClass`                              | `BaseConfig`                    |
| Cost model          | `CostModelBaseClass`                                     | `CostModelBaseConfig`           |
| Controller (optional)   | A `PassthroughController` is inserted automatically; see [Technology-Level Control](../control/technology_level_control/technology_control_overview.md) for custom controller baseclasses | n/a |

General model baseclasses and configs baseclasses are defined in:
- `h2integrate/core/model_baseclasses.py`
- `h2integrate/core/utilities.py`

- **Adding a brand-new technology?** Inherit directly from existing core baseclasses and configuration baseclasses
       - Performance models use: `PerformanceModelBaseClass` and `BaseConfig`
       - Cost models use: `CostModelBaseClass` and `CostModelBaseConfig`
- **Adding a technology that already has a category-specific baseclass?** Inherit
  from a category-specific baseclass instead to easily set up shared I/O and commodity attributes for that technology. Existing examples include:
      - `SolarPerformanceBaseClass`,
      - `WindPerformanceBaseClass`
      - `ElectrolyzerPerformanceBaseClass`

```{note}
Category-specific baseclasses are only worth creating when **multiple models
share inputs, outputs, or methods**. The wind module is a canonical example:
both `FlorisWindPlantPerformanceModel` and `PYSAMWindPlantPerformanceModel`
inherit from `WindPerformanceBaseClass` so they share the same wind-resource
discrete input and turbine-rating output. If you are writing a technology model
that doesn't fit into an existing category, skip the intermediate baseclass and
inherit directly from `PerformanceModelBaseClass`.
```

Configuration classes use the [`attrs`](https://www.attrs.org) library and the
`BaseConfig.from_dict` constructor, which validates user-supplied entries from
`tech_config['model_inputs']` against the declared fields. This pattern is now
standard for both performance and cost models in H2Integrate.

For custom technology-level controllers, inherit from `StorageOpenLoopControlBase`
(open-loop) or `PyomoStorageControllerBaseClass` (pyomo-based). See
[Technology-Level Control](../control/technology_level_control/technology_control_overview.md)
for details.

## Inherited classes

Inheriting from `PerformanceModelBaseClass` (rather than `om.ExplicitComponent`
directly) means the baseclass:
    - Declares the standard `driver_config` / `plant_config` / `tech_config` options.
    - Reads `n_timesteps`, `dt`, `plant_life`, and `fraction_of_year_simulated` from `plant_config`.
    - Validates that `commodity`, `commodity_rate_units`, and `commodity_amount_units` are set on the subclass and registers all of the standard production outputs from those attributes.
    - Adds the command-value input and uncurtailed output for `flexible` models, and provides the `apply_curtailment()` helper.

### Multiple layers of inheritance

Individual technology classes could inherit directly from the core baseclasses. If there are multiple technologies that have a lot of the same inputs, outputs, and/or methods we can use an additional layer of class inheritance that helps reduce duplicated code and potential errors.

Let us take a PEM electrolyzer model as an example.
Each electrolyzer model has shared methods and attributes that would be present in any valid model.
These methods are defined at the `ElectrolyzerBaseClass` level, which inherits from `ConverterBaseClass`.
Any implemented electrolyzer model should inherit from `ElectrolyzerBaseClass` to make use of its already built out structure and methods.

## Interactive class hierarchy

The diagram below shows **every model class** in H2Integrate and how they inherit from one another.
The visual encoding uses three dimensions:

- **Color** represents the application group (electricity, chemical, metal, etc.)
- **Shape** represents the model category (converter, storage, transporter, etc.)
- **Border thickness** indicates inheritance depth (thicker borders = higher-level parent classes)

Arrows point from parent to child.
You can **zoom**, **pan**, **hover** for details, and **drag** nodes to rearrange the layout.

To regenerate this visualization after code changes, run:

```bash
python docs/generate_class_hierarchy.py
```

```{raw} html
<div style="width:100%; box-sizing:border-box;">
  <iframe src="../_static/class_hierarchy.html" width="100%" height="950px"
          style="border:1px solid #ccc; border-radius:8px;"
          allowfullscreen></iframe>
</div>
```
