import openmdao.api as om

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
        n_timesteps = self.options["plant_config"]["plant"]["simulation"]["n_timesteps"]
        super().setup()

        # n_timesteps is number of timesteps in a simulation
        self.n_timesteps = self.options["plant_config"]["plant"]["simulation"]["n_timesteps"]
        # dt is seconds per timestep
        self.dt = self.options["plant_config"]["plant"]["simulation"]["dt"]
        # plant_life is number of years the plant is expected to operate for
        self.plant_life = int(self.options["plant_config"]["plant"]["plant_life"])
        hours_per_year = 8760
        # hours simulated is the number of hours in a simulation
        hours_simulated = (self.dt / 3600) * self.n_timesteps
        # fraction_of_year_simulated is the ratio of simulation length to length of year
        # and may be used to estimate annual performance from simulation performance
        self.fraction_of_year_simulated = hours_simulated / hours_per_year

        self.set_outputs()
        # Define inputs for electricity and outputs for hydrogen and oxygen generation
        self.add_input("electricity_in", val=0.0, shape=n_timesteps, units="kW")
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


class ElectrolyzerFinanceBaseClass(om.ExplicitComponent):
    def initialize(self):
        self.options.declare("driver_config", types=dict)
        self.options.declare("plant_config", types=dict)
        self.options.declare("tech_config", types=dict)

    def setup(self):
        self.add_input("CapEx", val=0.0, units="USD")
        self.add_input("OpEx", val=0.0, units="USD/year")
        self.add_output("NPV", val=0.0, units="USD", desc="Net present value")

    def compute(self, inputs, outputs):
        """
        Computation for the OM component.

        For a template class this is not implement and raises an error.
        """

        raise NotImplementedError("This method should be implemented in a subclass.")
