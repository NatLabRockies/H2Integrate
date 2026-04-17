import openmdao.api as om


class CablePerformanceModel(om.ExplicitComponent):
    """
    Pass-through cable with no losses.
    """

    _time_step_bounds = (
        1,
        1e9,
    )  # (min, max) time step lengths (in seconds) compatible with this model

    def initialize(self):
        self.options.declare("transport_item", values=["electricity"])
        self.options.declare("plant_config", types=dict)

    def setup(self):
        n_timesteps = int(self.options["plant_config"]["plant"]["simulation"]["n_timesteps"])
        self.input_name = self.options["transport_item"] + "_in"
        self.output_name = self.options["transport_item"] + "_out"
        self.add_input(
            self.input_name,
            val=-1.0,
            shape=n_timesteps,
            units="kW",
        )
        self.add_output(
            self.output_name,
            val=-1.0,
            shape=n_timesteps,
            units="kW",
        )

    def compute(self, inputs, outputs):
        outputs[self.output_name] = inputs[self.input_name]
