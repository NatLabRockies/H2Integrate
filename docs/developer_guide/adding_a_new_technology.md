# Adding a new technology to new H2Integrate

This doc page describes the steps to add a new technology to the new H2Integrate.
In broad strokes, this involves writing performance and cost wrappers for your technology in the format that H2Integrate expects, then adding those to the list of available technologies in the H2Integrate codebase.
We'll first walk through a relatively straightforward example of adding a new technology, then discuss some of the more complex cases you might encounter.

## Adding a new technology

We'll start by walking through the process to add a simple solar performance model to H2Integrate.

1. **Determine what type of technology you're adding** and if it fits into an existing H2Integrate bucket.
In this case, we're adding a solar technology, which has an existing set of baseclasses that we will use.
These baseclasses are defined in `h2integrate/converters/solar/solar_baseclass.py`.
They provide the basic structure for a solar technology, including the required inputs and outputs for the models.
Here's what that baseclass looks like:

```python
class SolarPerformanceBaseClass(om.ExplicitComponent):

    def initialize(self):
        self.options.declare('plant_config', types=dict)
        self.options.declare('tech_config', types=dict)
        self.options.declare('driver_config', types=dict)

    def setup(self):
        self.add_output('electricity_out', val=0.0, shape=n_timesteps, units='kW', desc='Power output from SolarPlant')

    def compute(self, inputs, outputs):
        """
        Computation for the OM component.

        For a template class this is not implement and raises an error.
        """

        raise NotImplementedError("This method should be implemented in a subclass.")
```

2. **Write the performance model for your technology.**
We'll be wrapping a PySAM model for this example.
We inherit from the baseclass and implement the `setup` and `compute` methods.
The baseclass describes the required inputs and outputs that the model should have, and the `compute` method is where the actual computation happens.
In this case, we only need to compute the electricity output from the solar plant.
Here's what the performance model looks like:

```python
class PYSAMSolarPlantPerformanceComponent(SolarPerformanceBaseClass):
    """
    An OpenMDAO component that wraps a SolarPlant model.
    It takes wind parameters as input and outputs power generation data.
    """
    def setup(self):
        super().setup()
        self.config_name = "PVWattsSingleOwner"
        self.system_model = Pvwatts.default(self.config_name)

        lat = self.options['plant_config']['site']['latitude']
        lon = self.options['plant_config']['site']['longitude']
        year = self.options['plant_config']['site']['year']
        solar_resource = SolarResource(lat, lon, year)
        self.system_model.value("solar_resource_data", solar_resource.data)

    def compute(self, inputs, outputs):
        self.system_model.execute(0)
        outputs['electricity_out'] = self.system_model.Outputs.gen
```

```{note}
The `setup` method is where we initialize the PySAM model and set the solar resource data.
We call the baseclass's `setup` method using the `super()` function, then added additional setup steps for the PySAM model.
```

3. **Write the cost model for your technology.**
The process for writing a cost model is similar to the performance model, with the required inputs and outputs defined in the technology cost model baseclass. The technology cost model baseclass should inherit the main cost model baseclass (`CostModelBaseClass`) with additional inputs, outputs, and setup added as necessary. The `CostModelBaseClass` has no predefined inputs, but all cost models must output `CapEx`, `OpEx`, and `cost_year`.

If the dollar-year for the costs (capex and opex) are **inherent to the cost model**, e.g. costs are always output with a certain associated dollar-year, a cost model may look like this:

```python
from attrs import field, define
from h2integrate.core.utilities import merge_shared_inputs
from h2integrate.core.validators import gt_zero, contains, must_equal
from h2integrate.core.model_base import CostModelBaseConfig, CostModelBaseClass

# make a cost config input to get user-provided inputs that won't be passed from other models
@define(kw_only=True)
class ReverseOsmosisCostModelConfig(BaseConfig):
    # the config variables for the cost model would be provided in the tech_config[tech]['model_inputs']['cost_parameters'] or tech_config[tech]['model_inputs']['shared_parameters']
    freshwater_kg_per_hour: float = field(validator=gt_zero)
    freshwater_density: float = field(validator=gt_zero)
    # if the dollar-year for the costs are inherent to the model, set the cost year in the cost config as a set value
    cost_year: int = field(default = 2013, converter=int, validator=must_equal(2013))

# make the cost model
class ReverseOsmosisCostModel(CostModelBaseClass):
    def setup(self):

        self.config = ReverseOsmosisCostModelConfig.from_dict(
            merge_shared_inputs(self.options["tech_config"]["model_inputs"], "cost")
        )

        super().setup()

        # add extra inputs or outputs for the cost model
        self.add_input(
            "plant_capacity_kgph", val=0.0, units="kg/h", desc="Desired freshwater flow rate"
        )

    def compute(self, inputs, outputs, discrete_inputs, discrete_outputs):
        # calculate CapEx and OpEx in USD
        desal_capex = 32894 * (self.config.freshwater_kg_per_hour / 3600)  # [USD]

        desal_opex = 4841 * (self.config.freshwater_kg_per_hour / 3600)  # [USD/yr]

        outputs["CapEx"] = capex
        outputs["OpEx"] = opex

```

If the dollar-year for the costs (capex and opex) **depend on the user cost inputs within the `tech_config` file**, a cost model may look like below:

```python
from attrs import field, define
from h2integrate.core.utilities import BaseConfig, CostModelBaseConfig, merge_shared_inputs
from h2integrate.core.validators import gt_zero, contains
from h2integrate.core.model_base import CostModelBaseConfig, CostModelBaseClass

@define(kw_only=True)
class ATBUtilityPVCostModelConfig(CostModelBaseConfig):
    capex_per_kWac: float | int = field(validator=gt_zero)
    opex_per_kWac_per_year: float | int = field(validator=gt_zero)
    # if the dollar-year for the costs is based on the user input costs, the cost year must be user-input and is a required input to the CostModelBaseConfig


class ATBUtilityPVCostModel(CostModelBaseClass):
    def setup(self):

        self.config = ATBUtilityPVCostModelConfig.from_dict(
            merge_shared_inputs(self.options["tech_config"]["model_inputs"], "cost")
        )

        super().setup()

        # add extra inputs or outputs for the cost model
        self.add_input("system_capacity_AC", val=0.0, units="kW", desc="PV rated capacity in AC")

    def compute(self, inputs, outputs, discrete_inputs, discrete_outputs):
        # calculate CapEx and OpEx in USD
        capacity = inputs["system_capacity_AC"][0]
        capex = self.config.capex_per_kWac * capacity
        opex = self.config.opex_per_kWac_per_year * capacity
        outputs["CapEx"] = capex
        outputs["OpEx"] = opex
```

4. **Write the control model for your technology.**
For this simplistic case, we will skip the control model because controls models can currently only be added to
storage technologies. The process for writing a control model is similar to the performance model, with the
required inputs and outputs defined in the baseclass.

5. **Next, add the new technology to the `supported_models.py` file.**
This file contains a dictionary of all the available technologies in H2Integrate.
Add your new technology to the dictionary with the appropriate keys depending on if it a performance, cost, or financial model.

```{important}
When adding a new technology use a string version of the class name as the dictionary key mapping
to the class. This greatly simplifies debugging configuration issues and model findability within the
documentation and code.
```

Here's what the updated `supported_models.py` file looks like with our new solar technology added as the first entry:

```python
from h2integrate.converters.solar.solar_pysam import PYSAMSolarPlantPerformanceComponent

supported_models = {
    "PYSAMSolarPlantPerformanceModel" : PYSAMSolarPlantPerformanceComponent,

    "RunOfRiverHydroPerformanceModel": RunOfRiverHydroPerformanceModel,
    "RunOfRiverHydroCostModel": RunOfRiverHydroCostModel,
    "ECOElectrolyzerPerformanceModel": ECOElectrolyzerPerformanceModel,
    "SingliticoCostModel": SingliticoCostModel,
    "BasicElectrolyzerCostModel": BasicElectrolyzerCostModel,
    "CustomElectrolyzerCostModel": CustomElectrolyzerCostModel,

    ...
}
```

6. **Finally, you can now use your new technology in H2Integrate.**
You can create a new case that uses this technology in the `tech_config.yaml` level or add it to an existing scenario and run the model to see the results.


## More complex cases

Adding a new technology to H2Integrate can be more complex than the simple example we walked through.
For example, your technology might not fit into an existing bucket, or you might need to add additional inputs or outputs than what's defined in the baseclass.
Let's briefly discuss these cases and how to handle them.

### Adding a new technology type

Take the case where you're adding a new technology that doesn't fit into an existing bucket, e.g. a nuclear power plant.
If you're adding multiple models that will exist in that new space, it would make sense to create a new baseclass that defines the required inputs and outputs for your technology.
You can then inherit from that baseclass in your performance and cost models.
If you're only making a single model, a baseclass isn't necessary, and you can define the required inputs and outputs directly in your models.
This shouldn't be a prohibitively challenging step, but it's generally easier to add technologies that fit into existing buckets as you can draw from those examples.

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

        # Special HOPP handling for short-term
        if tech_name in combined_performance_and_cost_model_technologies:
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

## Pull Request Checklist for New Technologies

When you're ready to submit a pull request for your new technology, please ensure you complete all items in the "New Technology Checklist" section of the pull request template.
Remember that adding a new technology typically requires review from both a core maintainer and ideally a second team member, as these additions significantly expand H2Integrate's capabilities and set patterns for future development.
