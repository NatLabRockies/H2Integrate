import openmdao.api as om


class NaturalGasPerformanceBaseClass(om.ExplicitComponent):
    """
    Base class for natural gas plant performance models.

    This base class defines the common interface for natural gas combustion
    turbine (NGCT) and natural gas combined cycle (NGCC) performance models.
    """

    def initialize(self):
        self.options.declare("driver_config", types=dict)
        self.options.declare("plant_config", types=dict)
        self.options.declare("tech_config", types=dict)

    def setup(self):
        n_timesteps = self.options["plant_config"]["plant"]["simulation"]["n_timesteps"]
        dt = self.options["plant_config"]["plant"]["simulation"]["dt"]
        sim_length_dt = n_timesteps * dt
        self.add_input(
            "natural_gas_in",
            val=0.0,
            shape=n_timesteps,
            units="MMBtu",
            desc="Natural gas input energy",
        )
        self.add_output(
            "electricity_out",
            val=0.0,
            shape=n_timesteps,
            units=f"MW*({dt}*s)",
            desc="Electricity output from natural gas plant",
        )
        self.add_output(
            "total_electricity_produced",
            val=0.0,
            units=f"MW*({dt}*s)/({sim_length_dt}*s)",
            desc="Total electrical energy production",
        )

    def compute(self, inputs, outputs):
        """
        Computation for the OM component.

        For a template class this is not implemented and raises an error.
        """

        raise NotImplementedError("This method should be implemented in a subclass.")
