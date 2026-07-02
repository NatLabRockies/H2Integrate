import numpy as np
import openmdao.api as om


class CurtailableComponentModel(om.ExplicitComponent):
    _time_step_bounds = (
        1,
        1e9,
    )  # (min, max) time step lengths (in seconds) compatible with this model

    def initialize(self):
        self.options.declare("commodity", types=str)
        self.options.declare("plant_config", types=dict)

    def setup(self):
        self.commodity = self.options["commodity"]
        n_timesteps = int(self.options["plant_config"]["plant"]["simulation"]["n_timesteps"])
        self.add_input(f"{self.commodity}_out", shape=n_timesteps, units=None, units_by_conn=True)
        self.add_input(
            f"{self.commodity}_command_value",
            shape=n_timesteps,
            units=None,
            copy_units=f"{self.commodity}_out",
        )

        self.add_output(
            f"modulated_{self.commodity}_out",
            shape=n_timesteps,
            units=None,
            copy_units=f"{self.commodity}_out",
        )
        self.add_output(
            f"curtailed_{self.commodity}_out",
            shape=n_timesteps,
            units=None,
            copy_units=f"{self.commodity}_out",
        )

    def compute(self, inputs, outputs):
        set_point_difference = (
            inputs[f"{self.commodity}_out"] - inputs[f"{self.commodity}_command_value"]
        )
        # commodity_out exceeds setpoint
        excess_commodity = np.where(set_point_difference > 0, set_point_difference, 0)
        commodity_to_setpoint = inputs[f"{self.commodity}_out"] - excess_commodity

        outputs[f"modulated_{self.commodity}_out"] = commodity_to_setpoint
        outputs[f"curtailed_{self.commodity}_out"] = excess_commodity
