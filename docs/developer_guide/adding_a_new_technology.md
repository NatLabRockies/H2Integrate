# Adding a new technology to new H2Integrate

This doc page describes the steps to add a new technology to the new H2Integrate.
In broad strokes, this involves writing performance and cost wrappers for your technology in the expected format, then adding those to the list of available technologies in the codebase. Once you've gone through this process you can use your model by specifying it in your `tech_config.yaml`.

We'll first walk through a relatively straightforward example of adding a new technology, then discuss some of the more complex cases you might encounter.
When you contribute your model to H2Integrate, make sure to follow the pull request checklist for new technologies at the bottom of this doc page.


## Baseclasses in H2Integrate
Every model in H2Integrate inherits from a small set of baseclasses that wire it
into the rest of the framework. Before writing code, pick the appropriate base
class and configuration class for each piece of your technology.

See the class structure in H2I to learn more: [Class Structure](#class_structure)

## Adding a new technology

Common model types (performance, cost, control, etc.) with slightly more explanation and examples are include here: [Technology Model Types](#technology_model_types)

Every model has:
- [Required class attributes](#required-class-attributes): These are usually defined within the class but not in a specific function definition.
- [Basic functions](#basic-functions-of-every-model):
    - `initialize(self)`
    - `setup(self)`
    - `compute(self)`
- [Inputs and outputs](#adding_io): There are OpenMDAO inputs and outputs that are defined within the baseclasses and required for the H2I model to execute a full simulation. Additional inputs and outputs for a specific model can also be added.


(basic-functions-of-every-model)=
### Basic functions of every model

Every model within H2Integrate follows a similar structure to help make it easier to work within H2Integrate and across models. We typically have separate performance and cost models for a given technology so you can more easily use a combination of these models in your analysis.

Within the class for a technology you have three basic functions that are always included and these are special methods expected and used by OpenMDAO under the hood:

1. `initialize(self)`
    - This has the extreme basics for the component, such as defining the commodity.

2. `setup(self)`
    - Builds a `BaseConfig`-derived configuration class from `tech_config['model_inputs']`
    - Sets the inputs and outputs the wrapped model needs to run. See [Adding additional inputs or outputs](#adding_io) if more IO is needed beyond what is inherited from the baseclass.

3. `compute(self)`
    - Where the magic happens (and all of the calculations occur), it runs the wrapped or native model.
    - Calculations use inputs defined in the `setup()`.
    - Sets the standard outputs that were declared in the setup method.

```{note}
`setup` is where the configuration object is built and where any additional I/O is registered. Always call `super().setup()` first so that the baseclass can register the standard production outputs (and, for flexible models, the command-value input). The `compute` signature is
`compute(self, inputs, outputs, discrete_inputs, discrete_outputs)` because performance models may use discrete I/O (e.g. resource data dictionaries).
```

```{tip}
`merge_shared_inputs(model_inputs, kind)` combines
`model_inputs['{kind}_parameters']` and `model_inputs['shared_parameters']`
into a single dictionary, and raises if a key is defined in both. Pair it with
`BaseConfig.from_dict(..., strict=True)` so that unknown keys in `tech_config`
are flagged immediately.
```

Here is an example of setting up a solar performance model in H2Integrate.

```python
from h2integrate.core.model_baseclasses import PerformanceModelBaseClass


class SolarPerformanceClass(PerformanceModelBaseClass):
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

        # add discrete input
        self.add_discrete_input(
            "solar_resource_data",
            val={},
            desc="Solar resource data dictionary",
        )

        # add input
        self.add_input(
            "system_capacity",
            val=self.config.system_capacity_kw,
            desc="system capacity of solar farm",
        )

        # add output
        self.add_output(
            "panel_efficiency",
            units="unitless",
            desc="solar panel annual efficiency",
        )

    def compute(self, inputs, outputs, discrete_inputs, discrete_outputs):
        # example calculation using inputs set in `setup()
        # this input can be an openmdao design variable
        rated_pv_output = inputs["system_capacity"]*0.33 `

        # example of calculation using a value from the attrs configuration class.
        # this method of input cannot be an openmdao design variable
        cloud_cover = self.config.cloud_cover * 0.2

        # more calculations
        ...

        ...

        # set outputs defined in `setup()` or baseclass `setup()`
        output["panel_efficiency"] = panel_efficiency

        # this output is defined in the `PerformanceModelBaseClass` but is required to be set in the performance model since that class is inherited
        output["capacity_factor"] = capacity_factor

```

(required-class-attributes)=
### Required class attributes

Every model must define the following class attributes. These are typically set on the category baseclass so that all subclasses inherit them, but they can also be set or overridden on individual model classes.

- `_time_step_bounds` (tuple[int, int]): `(min, max)` simulation time-step lengths (in seconds) the model can run at. Use `(3600, 3600)` for hourly-only models and a wider range (e.g. `(300, 3600)`) for models that support sub-hourly time steps. The plant simulation `dt` must lie within every model's bounds.

Performance models must also define the following class attributes:
- `commodity` (str), `commodity_rate_units` (str), `commodity_amount_units` (str): set in `initialize()` (or before calling `super().setup()`). These define the commodity produced by the model and the units used for its rate (e.g. `"kW"`, `"kg/h"`) and cumulative amount (e.g. `"kW*h"`, `"kg"`). `PerformanceModelBaseClass.setup()` uses them to register all of the standard outputs and will raise `NotImplementedError` if any are missing.
- `_control_classifier` (str): How the system-level controller (SLC) should treat this model. One of `"fixed"`, `"flexible"`, `"dispatchable"`, `"storage"`, or `"feedstock"`. The classifier determines whether the SLC sends a set-point to the model and how its output is folded into the dispatch logic. See the [control classifier docs](../control/system_level_control/control_classifier.md) for details.

For `flexible` models specifically, the baseclass automatically registers the `{commodity}_command_value` input and `uncurtailed_{commodity}_out` output, and the `compute()` method must call `self.apply_curtailment(outputs)` after writing the raw production to `outputs[f"{commodity}_out"]`. For `dispatchable` models the command value is consumed by the model's own internal logic; no curtailment helper is needed. `fixed` and `feedstock` models do not receive a command value at all.

(adding_io)=
### Adding additional inputs or outputs

If you need to add additional inputs or outputs to the model class, you can do so by adding them to the `setup` method. You might want to add additional inputs or outputs so that you can run design sweeps or optimization.

```{note}
OpenMDAO inputs can be set as design variables in an optimization and OpenMDAO outputs as can be set as constraints or objectives. To do this they must be defined using the `add_input()` and `add_output()` functions within the `setup()` method.
```
This would look like the following:

```python
class ECOElectrolyzerPerformanceModel(ElectrolyzerPerformanceBaseClass):
    """
    An OpenMDAO component that wraps the PEM electrolyzer model.
    Takes electricity input and outputs hydrogen and oxygen generation rates.
    """
    def setup(self):
        super().setup()
        ### add an unique input for model
        ### this specific input pulls the value from the configuration class
        self.add_input('membrane_efficiency', val=self.config.membrane_efficiency, units="percent", desc='membrane specific efficiency')

        ### add a unique output for model
        ### this output sets a default value of 0.0, which is helpful if the output is only calculated in certain instances
        self.add_output('efficiency', val=0.0, desc='Average efficiency of the electrolyzer')
```

## Add the new technology to the `supported_models.py` file
This file contains the registry of every technology available in H2Integrate.
Add your new technology with the appropriate key depending on whether it is a performance, cost, control, or financial model.

```{important}
Use a string version of the class name as the dictionary key. This greatly simplifies debugging configuration issues and improves model findability in the documentation and code.
```

The registry uses lazy imports to decrease computational overhead: each value is a
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

## More complex cases

Adding a new technology to H2Integrate can be more complex than the simple example we walked through.
For example, your technology might not fit into an existing bucket, or you might need to add additional inputs or outputs than what's defined in the baseclass.
Let's briefly discuss these cases and how to handle them.

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

### Other cases

If you encounter a case that isn't covered here, please discuss it with the H2Integrate dev team for guidance.
H2Integrate is constantly evolving and we plan to encounter new challenges as we add more technologies to the model.
Your feedback and suggestions help you and others use H2Integrate successfully.

(pull-request-template)=
## Pull request checklist for new technologies

When you're ready to submit a pull request for your new model please ensure you complete all
items in the "New Model Checklist" section of the pull request template. Remember that adding
a new technology typically requires review from both a core maintainer and ideally a second team
member, as these additions significantly expand H2Integrate's capabilities and set patterns for
future development.
