from h2integrate.core.model_baseclasses import (
    CostModelBaseClass,
    ResizeablePerformanceModelBaseClass,
)


class ElectrolyzerPerformanceBaseClass(ResizeablePerformanceModelBaseClass):
    _time_step_bounds = (3600, 3600)  # (min, max) time step lengths compatible with this model

    def initialize(self):
        super().initialize()
        self.commodity = "hydrogen"
        self.commodity_rate_units = "kg/h"
        self.commodity_amount_units = "kg"

    def setup(self):
        super().setup()

        # Define inputs for electricity
        self.add_input("electricity_in", val=0.0, shape=self.n_timesteps, units="kW")

    def compute(self, inputs, outputs):
        """
        Computation for the OM component.

        For a template class this is not implement and raises an error.
        """

        raise NotImplementedError("This method should be implemented in a subclass.")


class ElectrolyzerCostBaseClass(CostModelBaseClass):
    _time_step_bounds = (3600, 3600)  # (min, max) time step lengths compatible with this model

    def setup(self):
        n_timesteps = self.options["plant_config"]["plant"]["simulation"]["n_timesteps"]
        super().setup()
        self.add_input("total_hydrogen_produced", val=0.0, units="kg")
        self.add_input("electricity_in", val=0.0, shape=n_timesteps, units="kW")
