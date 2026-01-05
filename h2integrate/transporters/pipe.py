import openmdao.api as om


class PipePerformanceModel(om.ExplicitComponent):
    """
    Pass-through pipe with no losses.
    """

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
                "crude_ore",
                "wellhead_gas",
                "iron_ore",
                "reformer_catalyst",
                "water",
                "carbon",
                "lime",
                "pig_iron",
            ],
        )

    def setup(self):
        transport_item = self.options["transport_item"]
        self.input_name = transport_item + "_in"
        self.output_name = transport_item + "_out"

        if transport_item == "natural_gas":
            units = "MMBtu"
        elif transport_item == "reformer_catalyst":
            units = "(m**3)"
        elif transport_item == "water":
            units = "galUS"
        elif transport_item == "co2":
            units = "kg/h"
        else:
            units = "kg/s"

        self.add_input(
            self.input_name,
            val=-1.0,
            shape_by_conn=True,
            copy_shape=self.output_name,
            units=units,
        )
        self.add_output(
            self.output_name,
            val=-1.0,
            shape_by_conn=True,
            copy_shape=self.input_name,
            units=units,
        )

    def compute(self, inputs, outputs):
        outputs[self.output_name] = inputs[self.input_name]
