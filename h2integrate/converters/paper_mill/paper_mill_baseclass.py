from h2integrate.core.model_baseclasses import CostModelBaseClass, PerformanceModelBaseClass


class PaperMillPerformanceBaseClass(PerformanceModelBaseClass):
    def initialize(self):
        super().initialize()
        self.commodity = "paper"
        self.commodity_amount_units = "t"
        self.commodity_rate_units = "t/h"

    def setup(self):
        super().setup()
        n_timesteps = self.options["plant_config"]["plant"]["simulation"]["n_timesteps"]
        # NOTE: the SteelPerformanceModel does not use electricity or hydrogen in its calc
        self.add_input("electricity_in", val=0, shape=n_timesteps, units="kW")
        self.add_input("wood_in", val=0, shape=n_timesteps, units="kg/h")
        self.add_input("water_in", val=0, shape=n_timesteps, units="kg/h")        
        self.add_input("chemicals_in", val=0, shape=n_timesteps, units="t/h")

    def compute(self, inputs, outputs):
        """
        Computation for the OM component.

        For a template class this is not implement and raises an error.
        """

        raise NotImplementedError("This method should be implemented in a subclass.")


class PaperMillCostBaseClass(CostModelBaseClass):
    def setup(self):
        # Inputs for cost model configuration
        super().setup()
        self.add_input("plant_capacity_mtpy", val=0, units="t/year", desc="Annual plant capacity")
        self.add_input("plant_capacity_factor", val=0, units=None, desc="Capacity factor")
        self.add_input("wood_cost", val=0, units="USD/t", desc="Levelized cost of wood")
        self.add_input("electricity_cost", val=0, units="USD/(MW*h)", desc="Levelized cost of electricity")
        self.add_input("water_cost", val=0, units="USD/kg", desc="Levelized cost of water")
        self.add_input("chemicals_cost", val=0, units="USD/t", desc="Levelized cost of water")
