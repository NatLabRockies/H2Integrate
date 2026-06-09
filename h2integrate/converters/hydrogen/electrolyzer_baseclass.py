from h2integrate.core.model_baseclasses import (
    CostModelBaseClass,
    ResizeablePerformanceModelBaseClass,
)


class ElectrolyzerPerformanceBaseClass(ResizeablePerformanceModelBaseClass):
    _time_step_bounds = (
        3600,
        3600,
    )  # (min, max) time step lengths (in seconds) compatible with this model
    _control_classifier = "dispatchable"

    def initialize(self):
        super().initialize()
        self.commodity = "hydrogen"
        self.commodity_rate_units = "kg/h"
        self.commodity_amount_units = "kg"

    def setup(self):
        super().setup()

        # Define inputs for electricity
        self.add_input("electricity_in", val=0.0, shape=self.n_timesteps, units="kW")

        # Dispatchable models receive a command value from a tech-level controller.
        # Auto-injected ``PassthroughController`` or a user-defined control strategy
        # supplies this input. The default is a large value so an unconnected run
        # leaves raw production uncurtailed.
        self.add_input(
            f"{self.commodity}_command_value",
            val=1.0e9,
            shape=self.n_timesteps,
            units=self.commodity_rate_units,
            desc=f"Command value for {self.commodity} production from tech controller",
        )

    def compute(self, inputs, outputs):
        """
        Computation for the OM component.

        For a template class this is not implement and raises an error.
        """

        raise NotImplementedError("This method should be implemented in a subclass.")


class ElectrolyzerCostBaseClass(CostModelBaseClass):
    _time_step_bounds = (
        3600,
        3600,
    )  # (min, max) time step lengths (in seconds) compatible with this model

    def setup(self):
        n_timesteps = self.options["plant_config"]["plant"]["simulation"]["n_timesteps"]
        super().setup()
        self.add_input("total_hydrogen_produced", val=0.0, units="kg")
        self.add_input("electricity_in", val=0.0, shape=n_timesteps, units="kW")
