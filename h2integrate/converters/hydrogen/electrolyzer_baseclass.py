from h2integrate.core.model_baseclasses import (
    CostModelBaseClass,
    PerformanceModelBaseClass,
    ResizeablePerformanceModelBaseClass,
)


class ElectrolyzerPerformanceBaseClass(
    ResizeablePerformanceModelBaseClass, PerformanceModelBaseClass
):
    def setup(self):
        self.commodity = "hydrogen"
        self.commodity_rate_units = "kg/h"
        self.commodity_amount_units = "kg"

        super().setup()

        # Define inputs for electricity and outputs for hydrogen and oxygen generation
        self.add_input("electricity_in", val=0.0, shape=self.n_timesteps, units="kW")
        # self.add_output("hydrogen_out", val=0.0, shape=n_timesteps, units="kg/h")
        # self.add_output(
        #     "time_until_replacement", val=80000.0, units="h", desc="Time until replacement"
        # )
        # self.add_output("total_hydrogen_produced", val=0.0, units="kg/year")

    def compute(self, inputs, outputs):
        """
        Computation for the OM component.

        For a template class this is not implement and raises an error.
        """

        raise NotImplementedError("This method should be implemented in a subclass.")


class ElectrolyzerCostBaseClass(CostModelBaseClass):
    def setup(self):
        n_timesteps = self.options["plant_config"]["plant"]["simulation"]["n_timesteps"]
        super().setup()
        self.add_input(
            "total_hydrogen_produced", val=0.0, units="kg"
        )  # NOTE: unsure if this is used
        self.add_input("electricity_in", val=0.0, shape=n_timesteps, units="kW")
