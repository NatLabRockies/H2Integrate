import numpy as np
import openmdao.api as om

from h2integrate.core.supported_models import is_electricity_producer


class ElectricitySumComp(om.ExplicitComponent):
    """
    Component to sum up electricity produced through different technologies.
    """

    def initialize(self):
        self.options.declare("tech_configs", types=dict, desc="Configuration for each technology")
        self.options.declare("plant_config", types=dict, desc="Configuration for each technology")

    def setup(self):
        n_timesteps = self.options["plant_config"]["plant"]["simulation"]["n_timesteps"]
        dt = self.options["plant_config"]["plant"]["simulation"]["dt"]
        n_timesteps * dt
        # Add inputs for each electricity producing technology
        for tech in self.options["tech_configs"]:
            if is_electricity_producer(tech):
                self.add_input(
                    f"electricity_{tech}",
                    shape=8760,
                    val=0.0,
                    units=f"kW*({dt}*s)",
                    desc=f"Electricity produced by {tech}",
                )

        # Add output for total electricity produced
        self.add_output(
            "total_electricity_produced",
            val=0.0,
            units="kW*h/year",  # f"kW*({dt}*s)/({sim_length_dt}*s)",
            desc="Total electricity produced",
        )

    def compute(self, inputs, outputs):
        # Sum up all electricity streams for electricity-producing technologies
        outputs["total_electricity_produced"] = np.sum(
            [
                inputs[f"electricity_{tech}"]
                for tech in self.options["tech_configs"]
                if is_electricity_producer(tech)
            ]
        )
