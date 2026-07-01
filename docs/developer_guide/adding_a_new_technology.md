# Adding a new technology to new H2Integrate

This doc page describes the steps to add a new technology to the new H2Integrate.
In broad strokes, this involves writing performance and cost wrappers for your technology in the format that H2Integrate expects, then adding those to the list of available technologies in the H2Integrate codebase.
We'll first walk through a relatively straightforward example of adding a new technology, then discuss some of the more complex cases you might encounter.

## Choosing baseclasses for your model

Every model in H2Integrate inherits from a small set of baseclasses that wire it
into the rest of the framework. Before writing code, pick the appropriate base
class and configuration class for each piece of your technology:

| Piece               | Baseclass                                                | Config baseclass                |
| ------------------- | -------------------------------------------------------- | ------------------------------- |
| Performance model   | `PerformanceModelBaseClass`                              | `BaseConfig`                    |
| Cost model          | `CostModelBaseClass`                                     | `CostModelBaseConfig`           |
| Controller (opt.)   | A `PassthroughController` is inserted automatically      | n/a                             |

General model baseclasses and configs baseclasses are defined in:
- `h2integrate/core/model_baseclasses.py` 
- `h2integrate/core/utilities.py`

- **Adding a brand-new technology?** Inherit directly from existing baseclasses and configuration baseclasses
       - Performance models use: `PerformanceModelBaseClass` and `BaseConfig`
       - Cost models use: `CostModelBaseClass` and `CostModelBaseConfig`
- **Adding a technology that already has a category-specific baseclass?** Inherit
  from that instead. Existing examples include `SolarPerformanceBaseClass`,
  `WindPerformanceBaseClass`, and `ElectrolyzerPerformanceBaseClass`. These set

```{note}
Category-specific baseclasses are only worth creating when **multiple models
share inputs, outputs, or methods**. The wind module is the canonical example:
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

## Adding a new technology

We'll walk through the process of adding a solar PV performance model to
H2Integrate. Solar already has a category-specific baseclass, so we'll inherit
from that.

1. **Identify (or write) the relevant baseclass.**
For a solar technology, the category baseclass is
`SolarPerformanceBaseClass`, defined in
`h2integrate/converters/solar/solar_baseclass.py`:

```python
from h2integrate.core.model_baseclasses import PerformanceModelBaseClass


class SolarPerformanceBaseClass(PerformanceModelBaseClass):
    # (min, max) time step lengths (in seconds) compatible with this model
    _time_step_bounds = (3600, 3600)
    # System-level control classifier; see the control classifier docs.
    _control_classifier = "flexible"

    def initialize(self):
        super().initialize()
        # Commodity attributes are required by PerformanceModelBaseClass.setup()
        self.commodity = "electricity"
        self.commodity_rate_units = "kW"
        self.commodity_amount_units = "kW*h"

    def setup(self):
        super().setup()

        self.add_discrete_input(
            "solar_resource_data",
            val={},
            desc="Solar resource data dictionary",
        )

    def compute(self, inputs, outputs, discrete_inputs, discrete_outputs):
        raise NotImplementedError("This method should be implemented in a subclass.")
```

Inheriting from `PerformanceModelBaseClass` (rather than `om.ExplicitComponent`
directly) means the baseclass:

- Declares the standard `driver_config` / `plant_config` / `tech_config` options.
- Reads `n_timesteps`, `dt`, `plant_life`, and `fraction_of_year_simulated` from `plant_config`.
- Validates that `commodity`, `commodity_rate_units`, and `commodity_amount_units` are set on the subclass and registers all of the standard production outputs from those attributes.
- Adds the command-value input and uncurtailed output for `flexible` models, and provides the `apply_curtailment()` helper.

Every performance model must therefore define three class attributes and three commodity attributes; see [Required class attributes](#required-class-attributes) below.

2. **Write the performance model for your technology.**
We'll wrap a PySAM PV model. Two things happen in `setup`: we build a
`BaseConfig`-derived configuration class from `tech_config['model_inputs']`,
and we register any additional I/O the wrapped model needs. The `compute`
method then runs the model and writes the standard outputs declared by the
baseclass.

```python
import PySAM.Pvwattsv8 as Pvwatts
from attrs import field, define

from h2integrate.core.utilities import BaseConfig, merge_shared_inputs
from h2integrate.core.validators import contains, range_val_or_none
from h2integrate.converters.solar.solar_baseclass import SolarPerformanceBaseClass


@define(kw_only=True)
class PYSAMSolarPlantPerformanceModelDesignConfig(BaseConfig):
    """Performance-model configuration for ``PYSAMSolarPlantPerformanceModel``.

    Fields declared here are validated against the user inputs supplied in
    ``tech_config['model_inputs']['performance_parameters']`` (or the shared
    block) when ``from_dict`` is called in ``setup``.
    """

    pv_capacity_kWdc: float = field()
    dc_ac_ratio: float = field(default=None, validator=range_val_or_none(0.0, 2.0))
    tilt: float = field(default=None, validator=range_val_or_none(0.0, 90.0))
    config_name: str = field(
        default="PVWattsSingleOwner",
        validator=contains(["PVWattsSingleOwner", "PVWattsCommercial"]),  # truncated
    )


class PYSAMSolarPlantPerformanceModel(SolarPerformanceBaseClass):
    """OpenMDAO component wrapping PySAM's PVWatts v8 model."""

    def setup(self):
        super().setup()

        # Build a validated configuration object from user inputs.
        self.design_config = PYSAMSolarPlantPerformanceModelDesignConfig.from_dict(
            merge_shared_inputs(self.options["tech_config"]["model_inputs"], "performance"),
            strict=True,
            additional_cls_name=self.__class__.__name__,
        )

        # Register any extra I/O beyond what the baseclass already provides.
        self.add_input(
            "system_capacity_DC",
            val=self.design_config.pv_capacity_kWdc,
            units="kW",
            desc="PV rated capacity in DC",
        )
        self.add_output("system_capacity_AC", val=0.0, units="kW")

        self.system_model = Pvwatts.new(self.design_config.config_name)
        # ...assign design parameters to ``self.system_model``...

    def compute(self, inputs, outputs, discrete_inputs, discrete_outputs):
        # ...push inputs and solar resource into the PySAM model...
        self.system_model.value("system_capacity", inputs["system_capacity_DC"][0])
        self.system_model.value("solar_resource_data", discrete_inputs["solar_resource_data"])
        self.system_model.execute(0)

        # Write the standard production outputs declared by SolarPerformanceBaseClass.
        outputs["electricity_out"] = self.system_model.Outputs.gen
        outputs["system_capacity_AC"] = (
            self.system_model.value("system_capacity")
            / self.system_model.value("dc_ac_ratio")
        )
        outputs["rated_electricity_production"] = outputs["system_capacity_AC"]
        outputs["total_electricity_produced"] = (
            outputs["electricity_out"].sum() * (self.dt / 3600)
        )
        outputs["annual_electricity_produced"] = self.system_model.value("ac_annual")

        # Flexible models must apply curtailment at the end of compute(). This
        # clips ``{commodity}_out`` to ``min(uncurtailed, command_value)`` and
        # copies the raw output into ``uncurtailed_{commodity}_out``. It is a
        # no-op when no upstream controller is configured.
        self.apply_curtailment(outputs)
```

See `h2integrate/converters/solar/solar_pysam.py` for the full implementation,
including tilt-angle and resource-data handling.

```{note}
`setup` is where the configuration object is built and where any additional I/O
is registered. Always call `super().setup()` first so that the baseclass can
register the standard production outputs (and, for flexible models, the
command-value input). The `compute` signature is
`compute(self, inputs, outputs, discrete_inputs, discrete_outputs)` because
performance models may use discrete I/O (e.g. resource data dictionaries).
```

```{tip}
`merge_shared_inputs(model_inputs, kind)` combines
`model_inputs['{kind}_parameters']` and `model_inputs['shared_parameters']`
into a single dictionary, and raises if a key is defined in both. Pair it with
`BaseConfig.from_dict(..., strict=True)` so that unknown keys in `tech_config`
are flagged immediately.
```

(required-class-attributes)=
#### Required class attributes

Every performance model (whether it inherits from a category-specific baseclass like `SolarPerformanceBaseClass` or directly from `PerformanceModelBaseClass`) must define the following class attributes. These are typically set on the category baseclass so that all subclasses inherit them, but they can also be set or overridden on individual model classes.

- `_control_classifier` (str): How the system-level controller (SLC) should treat this model. One of `"fixed"`, `"flexible"`, `"dispatchable"`, `"storage"`, or `"feedstock"`. The classifier determines whether the SLC sends a set-point to the model and how its output is folded into the dispatch logic. See the {ref}`control classifier docs <system-level-control>` (`docs/control/system_level_control/control_classifier.md`) for details.
- `_time_step_bounds` (tuple[int, int]): `(min, max)` simulation time-step lengths (in seconds) the model can run at. Use `(3600, 3600)` for hourly-only models and a wider range (e.g. `(300, 3600)`) for models that support sub-hourly time steps. The plant simulation `dt` must lie within every model's bounds.
- `commodity` (str), `commodity_rate_units` (str), `commodity_amount_units` (str): set in `initialize()` (or before calling `super().setup()`). These define the commodity produced by the model and the units used for its rate (e.g. `"kW"`, `"kg/h"`) and cumulative amount (e.g. `"kW*h"`, `"kg"`). `PerformanceModelBaseClass.setup()` uses them to register all of the standard outputs and will raise `NotImplementedError` if any are missing.

For `flexible` models specifically, the baseclass automatically registers the `{commodity}_command_value` input and `uncurtailed_{commodity}_out` output, and the `compute()` method must call `self.apply_curtailment(outputs)` after writing the raw production to `outputs[f"{commodity}_out"]`. For `dispatchable` models the command value is consumed by the model's own internal logic; no curtailment helper is needed. `fixed` and `feedstock` models do not receive a command value at all.

3. **Write the cost model for your technology.**
Cost models follow the same pattern as performance models, but inherit from
`CostModelBaseClass` and use a `CostModelBaseConfig` (or `BaseConfig`)
configuration class. `CostModelBaseClass` registers the required `CapEx`,
`OpEx`, `VarOpEx`, and `cost_year` outputs; no inputs are predefined.

If the dollar-year for the costs is **inherent to the cost model** (i.e. the
model always reports costs in a fixed dollar-year), inherit the config from
`BaseConfig` and pin `cost_year` to a constant:

```python
from attrs import field, define

from h2integrate.core.utilities import BaseConfig, merge_shared_inputs
from h2integrate.core.validators import gt_zero, must_equal
from h2integrate.core.model_baseclasses import CostModelBaseClass


@define(kw_only=True)
class ReverseOsmosisCostModelConfig(BaseConfig):
    # Config values come from tech_config['model_inputs']['cost_parameters']
    # or tech_config['model_inputs']['shared_parameters'].
    freshwater_kg_per_hour: float = field(validator=gt_zero)
    freshwater_density: float = field(validator=gt_zero)
    # cost_year is fixed because this model always reports 2013 USD.
    cost_year: int = field(default=2013, converter=int, validator=must_equal(2013))


class ReverseOsmosisCostModel(CostModelBaseClass):
    def setup(self):
        self.config = ReverseOsmosisCostModelConfig.from_dict(
            merge_shared_inputs(self.options["tech_config"]["model_inputs"], "cost"),
            additional_cls_name=self.__class__.__name__,
        )
        super().setup()

        self.add_input(
            "plant_capacity_kgph", val=0.0, units="kg/h", desc="Desired freshwater flow rate"
        )

    def compute(self, inputs, outputs, discrete_inputs, discrete_outputs):
        capex = 32894 * (self.config.freshwater_kg_per_hour / 3600)  # USD
        opex = 4841 * (self.config.freshwater_kg_per_hour / 3600)    # USD/yr
        outputs["CapEx"] = capex
        outputs["OpEx"] = opex
```

If the dollar-year for the costs **depends on user inputs in `tech_config`**,
inherit the config from `CostModelBaseConfig` instead. `CostModelBaseConfig`
adds a required `cost_year` field, forcing the user to supply it:

```python
from attrs import field, define

from h2integrate.core.utilities import merge_shared_inputs
from h2integrate.core.validators import gt_zero
from h2integrate.core.model_baseclasses import CostModelBaseClass, CostModelBaseConfig


@define(kw_only=True)
class ATBUtilityPVCostModelConfig(CostModelBaseConfig):
    capex_per_kWac: float | int = field(validator=gt_zero)
    opex_per_kWac_per_year: float | int = field(validator=gt_zero)
    # ``cost_year`` is inherited from CostModelBaseConfig and is user-provided.


class ATBUtilityPVCostModel(CostModelBaseClass):
    def setup(self):
        self.config = ATBUtilityPVCostModelConfig.from_dict(
            merge_shared_inputs(self.options["tech_config"]["model_inputs"], "cost"),
            additional_cls_name=self.__class__.__name__,
        )
        super().setup()

        self.add_input("system_capacity_AC", val=0.0, units="kW", desc="PV rated capacity in AC")

    def compute(self, inputs, outputs, discrete_inputs, discrete_outputs):
        capacity = inputs["system_capacity_AC"][0]
        outputs["CapEx"] = self.config.capex_per_kWac * capacity
        outputs["OpEx"] = self.config.opex_per_kWac_per_year * capacity
```

4. **Write the control model for your technology (optional).**
Every technology group in H2Integrate contains a controller subsystem that converts a `{commodity}_set_point` signal into the `{commodity}_command_value` consumed by the performance model. If you do not specify a `control_strategy` for your technology, H2Integrate automatically inserts a `PassthroughController` that simply copies set-point to command value, so most new performance models do not need a custom controller.

You only need to write a control model if you want to override that default — for example, to implement a heuristic or optimized dispatch strategy for a storage technology. The process is similar to the performance model: the controller's required inputs and outputs (`{commodity}_set_point` in, `{commodity}_command_value` out) are defined in the relevant control baseclass. See the [technology-level control overview](../control/technology_level_control/technology_control_overview.md) for available frameworks and supported controllers.

5. **Next, add the new technology to the `supported_models.py` file.**
This file contains the registry of every technology available in H2Integrate.
Add your new technology with the appropriate key depending on whether it is a
performance, cost, or financial model.

```{important}
Use a string version of the class name as the dictionary key. This greatly
simplifies debugging configuration issues and improves model findability in the
documentation and code.
```

The registry uses lazy imports: each value is a
`"relative.module.path:ClassName"` string relative to the `h2integrate`
package, and the class is imported the first time it is accessed. Here's what
the updated `supported_models.py` looks like with the new solar entries:

```python
supported_models = _ModelRegistry(
    {
        # ...
        "PYSAMSolarPlantPerformanceModel": "converters.solar:PYSAMSolarPlantPerformanceModel",
        "ATBUtilityPVCostModel": "converters.solar:ATBUtilityPVCostModel",
        "ECOElectrolyzerPerformanceModel": "converters.hydrogen:ECOElectrolyzerPerformanceModel",
        "SingliticoCostModel": "converters.hydrogen:SingliticoCostModel",
        # ...
    }
)
```

For the import to resolve, also export your class from the relevant subpackage
`__init__.py` (for example, `h2integrate/converters/solar/__init__.py`).

6. **Finally, you can now use your new technology in H2Integrate.**
You can create a new case that uses this technology in the `tech_config.yaml` level or add it to an existing scenario and run the model to see the results.


## More complex cases

Adding a new technology to H2Integrate can be more complex than the simple example we walked through.
For example, your technology might not fit into an existing bucket, or you might need to add additional inputs or outputs than what's defined in the baseclass.
Let's briefly discuss these cases and how to handle them.

### Adding a new technology type

If you're adding a technology that doesn't fit into an existing category — e.g.
a nuclear power plant — you have two options:

- **Single model in the new category.** Inherit directly from
  `PerformanceModelBaseClass` (and `CostModelBaseClass`). Set the
  `commodity`, `commodity_rate_units`, `commodity_amount_units`,
  `_control_classifier`, and `_time_step_bounds` attributes on your model class
  itself. No category baseclass is needed.
- **Multiple models that share I/O or methods in the new category.** Create a
  category-specific baseclass that subclasses `PerformanceModelBaseClass`,
  sets the commodity attributes, and registers any shared inputs/outputs (the
  way `WindPerformanceBaseClass` does for FLORIS and PySAM wind models). Your
  individual models then inherit from this category baseclass.

It's generally easier to add technologies that fit into existing buckets, since
you can draw from those examples.

### Adding additional inputs or outputs

If you need to add additional inputs or outputs to the baseclass, you can do so by adding them to the `setup` method.
This would look like the following:

```python
class ECOElectrolyzerPerformanceModel(ElectrolyzerPerformanceBaseClass):
    """
    An OpenMDAO component that wraps the PEM electrolyzer model.
    Takes electricity input and outputs hydrogen and oxygen generation rates.
    """
    def setup(self):
        super().setup()
        self.add_output('efficiency', val=0.0, desc='Average efficiency of the electrolyzer')
```

### Caching results for expensive computations

If your technology involves computationally expensive calculations, you can leverage the caching functionality built into the H2Integrate model baseclasses.
This allows you to save the results of expensive computations to disk and load them in future runs, avoiding the need to recompute them.
To use this functionality, you need to ensure that your model inherits from the appropriate baseclass (`CacheBaseClass`) and that caching is enabled in your model's configuration.
You can then enable caching by setting the `enable_caching` flag to `True` in your model's `tech_config` file.
Please see the `hopp_wrapper.py` file for an example of how to implement caching in your model.

### Models where the performance and cost are tightly coupled

In some cases, the performance and cost models are tightly coupled, and it might make sense to combine them into a single model.
This is currently the case for the `HOPP` and `h2_storage` wrappers, where the performance and cost models are combined into a single component.
If you're adding a technology where this makes sense, you can follow the same steps as above but you also need to modify the `h2integrate_model.py` file for this special logic.
For now, modify a single  the `create_technology_models.py` file to include your new technology as such:

```python
combined_performance_and_cost_model_technologies = ['HOPPComponent', 'h2_storage', '<your_tech_here>']

# Create a technology group for each technology
for tech_name, individual_tech_config in self.technology_config['technologies'].items():
    if 'feedstocks' in tech_name:
        feedstock_component = FeedstockComponent(feedstocks_config=individual_tech_config)
        self.plant.add_subsystem(tech_name, feedstock_component)
    else:
        tech_group = self.plant.add_subsystem(tech_name, om.Group())
        self.tech_names.append(tech_name)
```

There are also situations where the models are still related but can be treated separately.
In these cases, you can create separate performance and cost models, but you might benefit from sharing some of the logic between them.
For example, you might have a performance model that instantiates a data class that is also used in the cost model.
If the computational burden is low, you can simply instantiate the data class in both models using a single function that returns the data class as done in the `direct_ocean_capture.py` file.
In the middle-ground case where the models might use a shared object that is computationally expensive to create, you can create and cache the object in a pickle file and load it in both models.
This would require additional logic to first check if the cached object exists and is valid before attempting to load it, otherwise it would create the object from scratch.
There is an example of this in the `hopp_wrapper.py` file.

### Specifying allowable time step for your model

`_time_step_bounds` is a required class attribute (see [Required class attributes](#required-class-attributes)). The default category baseclasses use `(3600, 3600)` (hourly timestep only). If your underlying model supports sub-hourly or multi-hour simulation, set `_time_step_bounds` on your subclass:

```python
class ECOElectrolyzerPerformanceModel(ElectrolyzerPerformanceBaseClass):
    """
    An OpenMDAO component that wraps the PEM electrolyzer model.
    Takes electricity input and outputs hydrogen and oxygen generation rates.
    """

    # (min, max) time step lengths (in seconds) compatible with this model
    _time_step_bounds = (300, 3600) # (5-min, 1-hour)
```

To run a simulation with a given time step, every model in the plant must be compatible with the desired `dt` set in `plant_config`.

### Other cases

If you encounter a case that isn't covered here, please discuss it with the H2Integrate dev team for guidance.
H2Integrate is constantly evolving and we plan to encounter new challenges as we add more technologies to the model.
Your feedback and suggestions help you and others use H2Integrate successfully.

## Pull Request Checklist for New Technologies

When you're ready to submit a pull request for your new model please ensure you complete all
items in the "New Model Checklist" section of the pull request template. Remember that adding
a new technology typically requires review from both a core maintainer and ideally a second team
member, as these additions significantly expand H2Integrate's capabilities and set patterns for
future development.
