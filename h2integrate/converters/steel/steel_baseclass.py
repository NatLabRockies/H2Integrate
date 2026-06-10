from h2integrate.core.model_baseclasses import CostModelBaseClass, PerformanceModelBaseClass


class SteelPerformanceBaseClass(PerformanceModelBaseClass):
    _time_step_bounds = (
        3600,
        3600,
    )  # (min, max) time step lengths (in seconds) compatible with this model
    _control_classifier = "dispatchable"

    def initialize(self):
        super().initialize()
        self.commodity = "steel"
        self.commodity_amount_units = "t"
        self.commodity_rate_units = "t/h"

    def setup(self):
        super().setup()
        n_timesteps = self.options["plant_config"]["plant"]["simulation"]["n_timesteps"]
        # NOTE: the SteelPerformanceModel does not use electricity or hydrogen in its calc
        self.add_input("electricity_in", val=0.0, shape=n_timesteps, units="kW")
        self.add_input("hydrogen_in", val=0.0, shape=n_timesteps, units="kg/h")

        # Dispatchable models receive a command value from a tech-level controller.
        # Auto-injected ``PassthroughController`` or a user-defined control strategy
        # supplies this input. The default is a large value so an unconnected run
        # leaves raw production uncurtailed.
        self.add_input(
            f"{self.commodity}_command_value",
            val=1.0e9,
            shape=n_timesteps,
            units=self.commodity_rate_units,
            desc=f"Command value for {self.commodity} production from tech controller",
        )

    def compute(self, inputs, outputs):
        """
        Computation for the OM component.

        For a template class this is not implement and raises an error.
        """

        raise NotImplementedError("This method should be implemented in a subclass.")


class SteelCostBaseClass(CostModelBaseClass):
    _time_step_bounds = (
        3600,
        3600,
    )  # (min, max) time step lengths (in seconds) compatible with this model

    def setup(self):
        # Inputs for cost model configuration
        super().setup()
        self.add_input("plant_capacity_mtpy", val=0.0, units="t/year", desc="Annual plant capacity")
        self.add_input("plant_capacity_factor", val=0.0, units=None, desc="Capacity factor")
        self.add_input("LCOH", val=0.0, units="USD/kg", desc="Levelized cost of hydrogen")
        self.add_input(
            "electricity_cost", val=0.0, units="USD/(MW*h)", desc="Levelized cost of electricity"
        )
