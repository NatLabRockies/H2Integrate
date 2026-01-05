import openmdao.api as om

from h2integrate.core.model_baseclasses import CostModelBaseClass


class SteelPerformanceBaseClass(om.ExplicitComponent):
    def initialize(self):
        self.options.declare("driver_config", types=dict)
        self.options.declare("plant_config", types=dict)
        self.options.declare("tech_config", types=dict)

    def setup(self):
        n_timesteps = self.options["plant_config"]["plant"]["simulation"]["n_timesteps"]
        dt = self.options["plant_config"]["plant"]["simulation"]["dt"]
        self.add_input("electricity_in", val=0.0, shape=n_timesteps, units=f"kW*({dt}*s)")
        self.add_input("hydrogen_in", val=0.0, shape=n_timesteps, units="kg/h")
        self.add_output("steel", val=0.0, shape=n_timesteps, units="t/year")

    def compute(self, inputs, outputs):
        """
        Computation for the OM component.

        For a template class this is not implement and raises an error.
        """

        raise NotImplementedError("This method should be implemented in a subclass.")


class SteelCostBaseClass(CostModelBaseClass):
    def setup(self):
        # Inputs for cost model configuration
        super().setup()
        self.add_input("plant_capacity_mtpy", val=0.0, units="t/year", desc="Annual plant capacity")
        self.add_input("plant_capacity_factor", val=0.0, units=None, desc="Capacity factor")
        self.add_input("LCOH", val=0.0, units="USD/kg", desc="Levelized cost of hydrogen")
        self.add_input(
            "electricity_cost", val=0.0, units="USD/(MW*h)", desc="Levelized cost of electricity"
        )


class SteelFinanceBaseClass(om.ExplicitComponent):
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
