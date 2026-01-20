---
jupytext:
  text_representation:
    extension: .md
    format_name: myst
    format_version: 0.13
    jupytext_version: 1.18.1
kernelspec:
  display_name: hopp
  language: python
  name: python3
---

# Sizing Modes with Resizeable Converters

When the size of one converter is changed, it may be desirable to have other converters in the plant resized to match.
This can be done manually by setting the sizes of each converter in the  `tech_config`, but it can also be done automatically with resizeable converters.
Resizeable converters can execute their own built-in sizing methods based on how much of a feedstock can be produced upstream, or how much of a commodity can be offtaken downstream by other converters.
By connecting the capacities of converters to other converters, one can build a logical re-sizing scheme for a multi-technology plant that will resize all converters by changing just one config parameter.

## Setting up a resizeable converter

To set up a resizeable converter, use `ResizeablePerformanceModelBaseConfig` and `ResizeablePerformanceModelBaseClass`.
The `ResizeablePerformanceModelBaseConfig` will declare sizing performance parameters (size_mode, flow_used_for_sizing, max_feedstock_ratio, max_commodity_ratio) within the tech_config.
The `ResizeablePerformanceModelBaseClass` will automatically parse these parameters into the `inputs` and `discrete_inputs` that the performance model will need for resizing.
Here is the start of an example `tech_config` for such a converter:

```{code-cell} ipython3
tech_config = {
    "model_inputs": {
        "shared_parameters": {
            "production_capacity": 1000.0,
        },
        "performance_parameters": {
            "size_mode": "normal",  # Always required
            "flow_used_for_sizing": "electricity",  # Not required in "normal" mode
            "max_feedstock_ratio": 1.6,  # Only used in "resize_by_max_feedstock"
            "max_commodity_ratio": 0.7,  # Only used in "resize_by_max_commodity"
        },
    }
}
```

Currently, there are three different modes defined for `size_mode`:

- `normal`: In this mode, converters function as they always have previously:
    - The size of the asset is fixed within `compute()`.
- `resize_by_max_feedstock`: In this mode, the size of the converter is adjusted to be able to utilize all of the available feedstock:
    - The size of the asset should be calculated within `compute()` as a function of the maximum value of `<feedstock>_in` - with the `<feedstock>` specified by the `flow_used_for_sizing` parameter.
    - This function will utilizes the `max_feedstock_ratio` parameter - e.g., if `max_feedstock_ratio` is 1.6, the converter will be resized so that its input capacity is 1.6 times the max of `<feedstock>_in`.
    - The `set_val` method will over-write any previous sizing variables to reflect the adjusted size of the converter.
- `resize_by_max_commodity`: In this mode, the size of the asset is adjusted to be able to supply its product to the full capacity of another downstream converter:
    - The size of the asset should be calculated within `compute()` as a function of the `max_<commodity>_capacity` input - with the `<feedstock>` specified by the `resize by flow` parameter.
    - This function will utilizes the `max_commodity_ratio` parameter - e.g., if `max_commodity_ratio` is 0.7, the converter will be resized so that its output capacity is 0.7 times a connected `max_<commodity>_capacity` input.
    - The `set_val` method will over-write any previous sizing variables to reflect the adjusted size of the converter.

To construct a resizeable converter from an existing converter, very few changes must be made, and only to the performance model.
`ResizeablePerformanceModelBaseConfig` can replace `BaseConfig` and `ResizeablePerformanceModelBaseClass` can replace `om.ExplicitComponent`.
The setup function must be modified to include any `max_<feedstock>_capacity` outputs or `max_<commodity>_capacity` inputs that can be connected to do the resizing.
Then, any `feedstock_sizing_function` or `feedstock_sizing_function` that the converter needs to resize itself should be defined, if not already.

```{code-cell} ipython3
from pathlib import Path

import numpy as np
from h2integrate.core.utilities import merge_shared_inputs
from h2integrate.core.model_baseclasses import ResizeablePerformanceModelBaseClass, ResizeablePerformanceModelBaseConfig
from h2integrate.core.h2integrate_model import H2IntegrateModel
from h2integrate.core.inputs.validation import load_tech_yaml, load_driver_yaml, load_plant_yaml


# Set a root directory for file loading
EXAMPLE_DIR = Path("../../examples/25_sizing_modes").resolve()
```

```{code-cell} ipython3
class TechPerformanceModelConfig(ResizeablePerformanceModelBaseConfig):
    # Declare tech-specific config parameters
    size: float = 1.0


class TechPerformanceModel(ResizeablePerformanceModelBaseClass):
    def setup(self):
        self.config = TechPerformanceModelConfig.from_dict(
            merge_shared_inputs(self.options["tech_config"]["model_inputs"], "performance"),
            strict=False,
        )
        super().setup()

        # Declare tech-specific inputs and outputs
        self.add_input("size", val=self.config.size, units="unitless")
        # Declare any commodities produced that need to be connected to downstream converters
        # if this converter is in `resize_by_max_commodity` mode
        self.add_input("max_<commodity>_capacity", val=1000.0, units="kg/h")
        # Any feedstocks consumed that need to be connected to upstream converters
        # if those converters are in `resize_by_max_commodity` mode
        self.add_output("max_<feedstock>_capacity", val=1000.0, units="kg/h")

    def feedstock_sizing_function(max_feedstock):
        max_feedstock * 0.1231289  # random number for example

    def commodity_sizing_function(max_commodity):
        max_commodity * 0.4651  # random number for example

    def compute(self, inputs, outputs, discrete_inputs, discrete_outputs):
        size_mode = discrete_inputs["size_mode"]

        # Make changes to computation based on sizing_mode:
        if size_mode != "normal":
            size = inputs["size"]
            if size_mode == "resize_by_max_feedstock":
                if inputs["flow_used_for_sizing"] == "<feedstock>":
                    feed_ratio = inputs["max_feedstock_ratio"]
                    size_for_max_feed = self.feedstock_sizing_function(
                        np.max(inputs["<feedstock>_in"])
                    )
                    size = size_for_max_feed * feed_ratio
            elif size_mode == "resize_by_max_commodity":
                if inputs["flow_used_for_sizing"] == "<commodity>":
                    comm_ratio = inputs["max_commodity_ratio"]
                    size_for_max_comm = self.commodity_sizing_function(
                        np.max(inputs["max_<commodity>_capacity"])
                    )
                    size = size_for_max_comm * comm_ratio
            self.set_val("size", size)
```

## Example plant setup

Here, there are three technologies in the the `tech_config.yaml`:

1. A `hopp` plant producing electricity,
2. An `electrolyzer` producing hydrogen from that electricity, and
3. An `ammonia` plant producing ammonia from that hydrogen.

The electrolyzer and ammonia technologies are resizeable. For starters, we will set them up in `"normal"` mode

```{code-cell} ipython3
# Create a H2Integrate model
driver_config = load_driver_yaml(EXAMPLE_DIR / "driver_config.yaml")
plant_config = load_plant_yaml(EXAMPLE_DIR / "plant_config.yaml")
tech_config = load_tech_yaml(EXAMPLE_DIR / "tech_config.yaml")

# Replace a relative file in the example with a hard-coded reference for the docs version
fn = tech_config["technologies"]["hopp"]["model_inputs"]["performance_parameters"]["hopp_config"]["site"]["solar_resource_file"][3:]
tech_config["technologies"]["hopp"]["model_inputs"]["performance_parameters"]["hopp_config"]["site"]["solar_resource_file"] = EXAMPLE_DIR.parent / fn

fn = tech_config["technologies"]["hopp"]["model_inputs"]["performance_parameters"]["hopp_config"]["site"]["wind_resource_file"][3:]
tech_config["technologies"]["hopp"]["model_inputs"]["performance_parameters"]["hopp_config"]["site"]["wind_resource_file"] = EXAMPLE_DIR.parent / fn

input_config = {
    "name": "H2Integrate_config",
    "system_summary": "hybrid plant containing ammonia plant and electrolyzer",
    "driver_config": driver_config,
    "plant_config": plant_config,
    "technology_config": tech_config,
}
model = H2IntegrateModel(input_config)

# Print the value of the size_mode tech_config parameters
for tech in ["electrolyzer", "ammonia"]:
    print(
        tech
        + ": "
        + str(
            model.technology_config["technologies"][tech]["model_inputs"]["performance_parameters"][
                "size_mode"
            ]
        )
    )
```

The `technology_interconnections` in the `plant_config` is set up to send electricity from the wind plant to the electrolyzer, then hydrogen from the electrolyzer to the ammonia plant. When set up to run in `resize_by_max_commodity` mode, there will also be an entry to send the `max_hydrogen_capacity` from the ammonia plant to the electrolyzer. Note: this will create a feedback loop within the OpenMDAO problem, which requires an iterative solver.

```{code-cell} ipython3
for connection in model.plant_config["technology_interconnections"]:
    print(connection)
```

When we run this example the electrolyzer is sized to 640 MW (as set by the config), although the electricity profile going in has a max of over 1000 MW.
The LCOH is $4.49/kg H2 and the LCOA is $1.35/kg NH3.

```{code-cell} ipython3
# Run the model
model.run()

# Print selected output
for value in [
    "electrolyzer.electricity_in",
    "electrolyzer.electrolyzer_size_mw",
    "electrolyzer.hydrogen_capacity_factor",
    "ammonia.hydrogen_in",
    "ammonia.max_hydrogen_capacity",
    "ammonia.ammonia_capacity_factor",
    "finance_subgroup_h2.LCOH",
    "finance_subgroup_nh3.LCOA",
]:
    print(value + ": " + str(np.max(model.prob.get_val(value))))
```

### `resize_by_max_feedstock` mode

In this case, the electrolyzer will be sized to match the maximum `electricity_in` coming from HOPP.
This increases the electrolyzer size to 1080 MW, the smallest multiple of 40 MW (the cluster size) matching the max HOPP power output of 1048 MW.
This increases the LCOH to $4.80/kg H2, and increases the LCOA to $1.54/kg NH3, since electrolyzer is now oversized to utilize all of the HOPP electricity at peak output but thus has a lower hydrogen production capacity factor.

```{code-cell} ipython3
# Create a H2Integrate model, modifying tech_config as necessary
tech_config["technologies"]["electrolyzer"]["model_inputs"]["performance_parameters"][
    "size_mode"
] = "resize_by_max_feedstock"
tech_config["technologies"]["electrolyzer"]["model_inputs"]["performance_parameters"][
    "flow_used_for_sizing"
] = "electricity"
tech_config["technologies"]["electrolyzer"]["model_inputs"]["performance_parameters"][
    "max_feedstock_ratio"
] = 1.0
input_config["technology_config"] = tech_config
model = H2IntegrateModel(input_config)

# Run the model
model.run()

# Print selected output
for value in [
    "electrolyzer.electricity_in",
    "electrolyzer.electrolyzer_size_mw",
    "electrolyzer.hydrogen_capacity_factor",
    "ammonia.hydrogen_in",
    "ammonia.max_hydrogen_capacity",
    "ammonia.ammonia_capacity_factor",
    "finance_subgroup_h2.LCOH",
    "finance_subgroup_nh3.LCOA",
]:
    print(value + ": " + str(np.max(model.prob.get_val(value))))
```

### `resize_by_max_product` mode

In this case, the electrolyzer will be sized to match the maximum hydrogen capacity of the ammonia plant.
This requires the `technology_interconnections` entry to send the `max_hydrogen_capacity` from the ammonia plant to the electrolyzer.
This decreases the electrolyzer size to 560 MW, the closest multiple of 40 MW (the cluster size) that will ensure an h2 production capacity that matches the ammonia plant's h2 intake at its max ammonia production capacity.
This increases the LCOH to $4.64/kg H2, but reduces the LCOA to $1.30/kg NH3, since electrolyzer size was matched to ammonia production but not HOPP.

```{code-cell} ipython3
# Create a H2Integrate model, modifying tech_config and plant_config as necessary
tech_config["technologies"]["electrolyzer"]["model_inputs"]["performance_parameters"][
    "size_mode"
] = "resize_by_max_commodity"
tech_config["technologies"]["electrolyzer"]["model_inputs"]["performance_parameters"][
    "flow_used_for_sizing"
] = "hydrogen"
tech_config["technologies"]["electrolyzer"]["model_inputs"]["performance_parameters"][
    "max_commodity_ratio"
] = 1.0
input_config["technology_config"] = tech_config
plant_config["technology_interconnections"] = [
    ["hopp", "electrolyzer", "electricity", "cable"],
    ["electrolyzer", "ammonia", "hydrogen", "pipe"],
    ["ammonia", "electrolyzer", "max_hydrogen_capacity"],
]
input_config["plant_config"] = plant_config

model = H2IntegrateModel(input_config)

# Run the model
model.run()

# Print selected output
for value in [
    "electrolyzer.electricity_in",
    "electrolyzer.electrolyzer_size_mw",
    "electrolyzer.hydrogen_capacity_factor",
    "ammonia.hydrogen_in",
    "ammonia.max_hydrogen_capacity",
    "ammonia.ammonia_capacity_factor",
    "finance_subgroup_h2.LCOH",
    "finance_subgroup_nh3.LCOA",
]:
    print(value + ": " + str(np.max(model.prob.get_val(value))))
```

## Using optimizer with multiple connections

With both `electrolyzer` and `ammonia` in `size_by_max_feedstock` mode, the COBYLA optimizer can co-optimize the `max_feedstock_ratio` variables to minimize LCOA to $1.20/kg. This is achieved at a capacity factor of approximately 55% in both the electrolyzer and the ammonia plant.

```{code-cell} ipython3
# Create a H2Integrate model, modifying tech_config and driver_config as necessary
tech_config["technologies"]["electrolyzer"]["model_inputs"]["performance_parameters"][
    "size_mode"
] = "resize_by_max_feedstock"
tech_config["technologies"]["electrolyzer"]["model_inputs"]["performance_parameters"][
    "flow_used_for_sizing"
] = "electricity"
tech_config["technologies"]["electrolyzer"]["model_inputs"]["performance_parameters"][
    "max_feedstock_ratio"
] = 1.0
tech_config["technologies"]["ammonia"]["model_inputs"]["performance_parameters"]["size_mode"] = (
    "resize_by_max_feedstock"
)
tech_config["technologies"]["ammonia"]["model_inputs"]["performance_parameters"][
    "flow_used_for_sizing"
] = "hydrogen"
tech_config["technologies"]["ammonia"]["model_inputs"]["performance_parameters"][
    "max_feedstock_ratio"
] = 1.0
input_config["technology_config"] = tech_config
plant_config["technology_interconnections"] = [
    ["hopp", "electrolyzer", "electricity", "cable"],
    ["electrolyzer", "ammonia", "hydrogen", "pipe"],
]
input_config["plant_config"] = plant_config
driver_config["driver"]["optimization"]["flag"] = True
driver_config["design_variables"]["electrolyzer"]["max_feedstock_ratio"]["flag"] = True
driver_config["design_variables"]["ammonia"]["max_feedstock_ratio"]["flag"] = True
input_config["driver_config"] = driver_config
model = H2IntegrateModel(input_config)

# Run the model
model.run()

# Print selected outputs
for value in [
    "electrolyzer.electricity_in",
    "electrolyzer.electrolyzer_size_mw",
    "electrolyzer.hydrogen_capacity_factor",
    "ammonia.hydrogen_in",
    "ammonia.max_hydrogen_capacity",
    "ammonia.ammonia_capacity_factor",
    "finance_subgroup_h2.LCOH",
    "finance_subgroup_nh3.LCOA",
]:
    print(value + ": " + str(np.max(model.prob.get_val(value))))
```
