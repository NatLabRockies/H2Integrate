import openmdao.api as om


class CablePerformanceModel(om.ExplicitComponent):
    """
    Pass-through cable with no losses.
    """

    def initialize(self):
        self.options.declare("transport_item", values=["electricity"])

    def setup(self):
        self.input_name = self.options["transport_item"] + "_in"
        self.output_name = self.options["transport_item"] + "_out"
        self.add_input(
            self.input_name,
            val=-1.0,
            shape_by_conn=True,
            copy_shape=self.output_name,
            units="kW",
        )
        self.add_output(
            self.output_name,
            val=-1.0,
            shape_by_conn=True,
            copy_shape=self.input_name,
            units="kW",
        )

    def compute(self, inputs, outputs):
        outputs[self.output_name] = inputs[self.input_name]
