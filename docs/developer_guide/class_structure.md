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

(annualization-methods)=
### Annualization

For models supporting nonannual simulations, use the inherited annualization methods
to project annual outputs across plant life. Their pure calculation functions live in
`h2integrate/core/annualization.py`; model implementations should normally call the base-class
methods rather than assemble the private helpers themselves.

A "plant year" here is always 365 days (31,536,000 s); a simulation shorter or longer than that is
split at plant-year boundaries and each segment is averaged over its actual duration. No built-in
model calls these methods yet because all models default to annual-only support (see
`_simulation_duration_bounds`); a model opts in by widening its bounds and calling them, for example:

```python
# In a performance model's compute(); state of health (SOH) is optional
annual_capacity_factors, replacement_schedule = self.calculate_annual_cf_and_replacement_schedule(
    performance_timeseries=outputs["electricity_out"],
    rated_performance=self.config.rated_capacity,
    state_of_health_timeseries=None,  # or a timeseries of SOH fractions in [0, 1]
    eol_soh=None,  # end-of-life SOH threshold, required only when SOH is given
)

# In a cost model's compute(); timestep-level variable costs in USD per timestep
annual_varopex = self.calculate_annual_varopex(varopex_timeseries)
```

Both results have one entry per plant year (`plant_life` entries).

CF (capacity factor) and variable costs use duration-weighted annual means. Optional SOH supports
timestep-level completion of the trailing cycle and integer replacement counts per year. For arguments,
extrapolation options, and boundary behavior, see
{py:meth}`~h2integrate.core.model_baseclass.PerformanceModelBaseClass.calculate_annual_cf_and_replacement_schedule`
and {py:meth}`~h2integrate.core.model_baseclass.CostModelBaseClass.calculate_annual_varopex`.

When SOH is given, the final (incomplete) cycle is extended beyond the simulation by projecting
SOH forward at its average loss per timestep over the last year of that cycle (or the whole cycle
if shorter) until it reaches the end-of-life threshold. Projected CF is the average CF over the
same samples, reduced in proportion to the projected SOH. This projection has two limitations:

- Reducing CF with SOH assumes output is capacity-limited. For dispatch-limited technologies, such
  as a controlled battery with spare energy capacity, CF stays nearly constant as SOH falls, so
  projected CF is understated.
- A constant average loss rate overestimates fade that slows over time (e.g. calendar aging), so
  projected replacements occur too early.

Simulated years are not affected. When either limitation matters, simulate the full plant life.

The plant-level `plant.simulation.annual_extrapolation_method` allows the user to select `tile`, `final_sim_value`,
or `time_averaged_sim_value` when multiple simulated year segments must be extended across the
remaining plant life. Technology implementations can override it per call using
`no_degradation_extrapolation` for capacity-factor projection or `annual_extrapolation_method`
for variable OpEx projection. A finance subgroup using a custom timeseries may also override the
plant setting; otherwise, it inherits the plant-level value. See
{ref}`Plant lifetime and simulation <plant-simulation-settings>`.

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
