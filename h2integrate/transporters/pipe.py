import openmdao.api as om


class PipePerformanceModel(om.ExplicitComponent):
    """
    Pass-through pipe with no losses.
    """

    _time_step_bounds = (
        1,
        1e9,
    )  # (min, max) time step lengths (in seconds) compatible with this model

    def initialize(self):
        self.options.declare(
            "transport_item",
            values=[
                "hydrogen",
                "co2",
                "methanol",
                "ammonia",
                "nitrogen",
                "natural_gas",
                "wellhead_gas",
                "water",
            ],
        )
        self.options.declare("plant_config", types=dict)

    def setup(self):
        transport_item = self.options["transport_item"]
        self.input_name = transport_item + "_in"
        self.output_name = transport_item + "_out"

        n_timesteps = int(self.options["plant_config"]["plant"]["simulation"]["n_timesteps"])

        if transport_item == "natural_gas":
            units = "MMBtu/h"
        elif transport_item == "water":
            units = "galUS"
        elif transport_item == "co2":
            units = "kg/h"
        else:
            units = "kg/s"

        self.add_input(
            self.input_name,
            val=-1.0,
            shape=n_timesteps,
            units=units,
        )
        self.add_output(
            self.output_name,
            val=-1.0,
            shape=n_timesteps,
            units=units,
        )

    def compute(self, inputs, outputs):
        outputs[self.output_name] = inputs[self.input_name]
