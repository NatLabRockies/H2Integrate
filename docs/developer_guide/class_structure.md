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
- `h2integrate/core/model_baseclass.py`
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

For custom technology-level controllers, inherit from `OpenLoopControlBase`
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
    - Provides `calculate_annual_cf_and_replacement_schedule()` to project annual capacity factors and a replacement schedule across the plant life from a simulated horizon of any length (optionally accounting for degradation).
    - Declares `_time_step_bounds` (min, max in seconds) used to validate the configured simulation time step against the model.
    - Declares `_simulation_duration_bounds` (min, max in years, default annual-only) used to validate the configured simulation duration against the model.

Similarly, inheriting from `CostModelBaseClass` (rather than `om.ExplicitComponent`
directly) means the baseclass:
    - Declares the standard `driver_config` / `plant_config` / `tech_config` options.
    - Reads `n_timesteps`, `dt`, `plant_life`, and `fraction_of_year_simulated` from `plant_config`.
    - Registers the standard cost outputs `CapEx`, `OpEx`, and `VarOpEx` consumed by the finance models, along with the discrete `cost_year` output and a `marginal_cost` output used for dispatch decisions.
    - Provides `calculate_annual_varopex()` to annualize timestep-level variable operating costs across the plant life.
    - Declares `_time_step_bounds` (min, max in seconds) used to validate the configured simulation time step against the model.
    - Declares `_simulation_duration_bounds` (min, max in years, default annual-only) used to validate the configured simulation duration against the model.

Annualization uses fixed 365-day plant years. Until framework-wide calendar alignment is
supported, `H2IntegrateModel` rejects site resources configured with `include_leap_day: true`
during configuration loading. Set this resource option to `false` or omit it. Standalone
resource models retain their leap-day processing support. This restriction does not change
the timestamps generated from the simulation's `start_time` and `dt`.

The CF/replacement helper requires finite, one-dimensional performance and SOH arrays
of identical length, positive rated performance and timestep, and a positive integer
plant life. SOH and its EOL threshold are fractions in [0, 1]. CF projection remains
annual: annual means retain their elapsed durations, including a partial final year.
When cycles repeat, their overlaps with plant years are duration-weighted; timestep
performance is not reconstructed or projected.

An upward SOH jump greater than `1e-9` is assumed to mark a replacement at that sample's
elapsed offset. It closes the outgoing unit's cycle, not the new unit's cycle. SOH alone
cannot reveal a first-sample reset or repeated replacements with identical fresh SOH.
The trailing cycle is completed using the last two post-reset samples' SOH loss per
elapsed year. Projected EOL is checked only at the end of each full annual projection
interval; threshold-crossing times are not interpolated. Fewer than two post-reset samples
or stalled degradation do not imply an EOL replacement. The completed history then repeats
as either all cycles or the final cycle, using identical durations for CF and events.
Replacement counts are discrete events in `[year, year + 1)`, never annualized or rounded.
An event on a year boundary belongs to the following year; initial installation and an
event at retirement are excluded. Observed and projected events can share a plant year.
For example, a completed half-year cycle produces counts `[1, 2, 2]` over three years.

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

This diagram is generated automatically when the documentation is built, so it is always up-to-date with available model classes and their inheritance structure.

```{raw} html
<div style="width:100%; box-sizing:border-box;">
  <iframe src="../_static/class_hierarchy.html" width="100%" height="950px"
          style="border:1px solid #ccc; border-radius:8px;"
          allowfullscreen></iframe>
</div>
```
