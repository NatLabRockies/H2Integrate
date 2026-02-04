"""Pared down version of the "Sizing Modes with Resizeable Converters" User Guide example."""

import numpy as np

from h2integrate.core.utilities import merge_shared_inputs
from h2integrate.core.h2integrate_model import H2IntegrateModel
from h2integrate.core.inputs.validation import load_tech_yaml, load_plant_yaml, load_driver_yaml
from h2integrate.core.model_baseclasses import (
    ResizeablePerformanceModelBaseClass,
    ResizeablePerformanceModelBaseConfig,
)


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


driver_config = load_driver_yaml("driver_config.yaml")
plant_config = load_plant_yaml("plant_config.yaml")
tech_config = load_tech_yaml("tech_config.yaml")

# When we run this example in resize_by_max_commodity mode, the electrolyzer is sized to
# 640 MW (as set by the config), although the electricity profile going in has a max of
# over 1000 MW. The LCOH is $4.49/kg H2 and the LCOA is $1.35/kg NH3.
input_config = {
    "name": "H2Integrate_config",
    "system_summary": "hybrid plant containing ammonia plant and electrolyzer",
    "driver_config": driver_config,
    "plant_config": plant_config,
    "technology_config": tech_config,
}
model = H2IntegrateModel(input_config)
model.run()

for value in [
    "electrolyzer.electricity_in",
    "electrolyzer.electrolyzer_size_mw",
    "electrolyzer.capacity_factor",
    "ammonia.hydrogen_in",
    "ammonia.max_hydrogen_capacity",
    "ammonia.capacity_factor",
    "finance_subgroup_h2.LCOH",
    "finance_subgroup_nh3.LCOA",
]:
    print(value + ": " + str(np.max(model.prob.get_val(value))))

# In this case, the electrolyzer will be sized to match the maximum `electricity_in`
# coming from HOPP. This increases the electrolyzer size to 1080 MW, the smallest
# multiple of 40 MW (the cluster size) matching the max HOPP power output of 1048 MW.
# This increases the LCOH to $4.80/kg H2, and increases the LCOA to $1.54/kg NH3
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
model.run()

for value in [
    "electrolyzer.electricity_in",
    "electrolyzer.electrolyzer_size_mw",
    "electrolyzer.capacity_factor",
    "ammonia.hydrogen_in",
    "ammonia.max_hydrogen_capacity",
    "ammonia.capacity_factor",
    "finance_subgroup_h2.LCOH",
    "finance_subgroup_nh3.LCOA",
]:
    print(value + ": " + str(np.max(model.prob.get_val(value))))

# In this case, the electrolyzer will be sized to match the maximum hydrogen capacity of
# the ammonia plant. This requires the `technology_interconnections` entry to send the
# `max_hydrogen_capacity` from the ammonia plant to the electrolyzer. This decreases the
# electrolyzer size to 560 MW, the closest multiple of 40 MW (the cluster size) that
# will ensure an h2 production capacity that matches the ammonia plant's h2 intake at
# its max ammonia production capacity. This increases the LCOH to $4.64/kg H2, but
# reduces the LCOA to $1.30/kg NH3, since electrolyzer size was matched to ammonia
# production but not HOPP.

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
model.run()

for value in [
    "electrolyzer.electricity_in",
    "electrolyzer.electrolyzer_size_mw",
    "electrolyzer.capacity_factor",
    "ammonia.hydrogen_in",
    "ammonia.max_hydrogen_capacity",
    "ammonia.capacity_factor",
    "finance_subgroup_h2.LCOH",
    "finance_subgroup_nh3.LCOA",
]:
    print(value + ": " + str(np.max(model.prob.get_val(value))))


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
model.run()

for value in [
    "electrolyzer.electricity_in",
    "electrolyzer.electrolyzer_size_mw",
    "electrolyzer.capacity_factor",
    "ammonia.hydrogen_in",
    "ammonia.max_hydrogen_capacity",
    "ammonia.capacity_factor",
    "finance_subgroup_h2.LCOH",
    "finance_subgroup_nh3.LCOA",
]:
    print(value + ": " + str(np.max(model.prob.get_val(value))))
