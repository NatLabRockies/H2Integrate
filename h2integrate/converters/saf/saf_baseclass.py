from h2integrate.core.model_baseclasses import CostModelBaseClass, PerformanceModelBaseClass


class SAFPerformanceBaseClass(PerformanceModelBaseClass):
    _time_step_bounds = (
        3600,
        3600,
    )  # (min, max) time step lengths (in seconds) compatible with this model

    def initialize(self):
        super().initialize()
        self.commodity = "saf"
        self.commodity_amount_units = "t"
        self.commodity_rate_units = "t/h"

    def setup(self):
        super().setup()
        n_timesteps = self.options["plant_config"]["plant"]["simulation"]["n_timesteps"]
        self.add_input("electricity_in", val=0, shape=n_timesteps, units="kW")
        self.add_input("lignin_in", val=0, shape=n_timesteps, units="kg/h")
        self.add_input("water_in", val=0, shape=n_timesteps, units="kg/h")
        self.add_input("hydrogen_in", val=0, shape=n_timesteps, units="kg/h")
        self.add_input("salt_mix_in", val=0, shape=n_timesteps, units="kg/h")
        self.add_input("hydrogen_chloride_in", val=0, shape=n_timesteps, units="kg/h")

    def compute(self, inputs, outputs):
        """
        Computation for the OM component.

        For a template class this is not implement and raises an error.
        """

        raise NotImplementedError("This method should be implemented in a subclass.")


class SAFCostBaseClass(CostModelBaseClass):
    def setup(self):
        # Inputs for cost model configuration
        super().setup()
        self.add_input("plant_capacity_mtpy", val=0, units="t/year", desc="Annual plant capacity")
        self.add_input("plant_capacity_factor", val=0, units=None, desc="Capacity factor")
        self.add_input("lignin_cost", val=0, units="USD/kg", desc="Levelized cost of lignin")
        self.add_input(
            "electricity_cost", val=0, units="USD/(kW*h)", desc="Levelized cost of electricity"
        )
        self.add_input("water_cost", val=0, units="USD/kg", desc="Levelized cost of water")
        self.add_input("hydrogen_cost", val=0, units="USD/kg", desc="Levelized cost of hydrogen")
        self.add_input("salt_mix_cost", val=0, units="USD/kg", desc="Levelized cost of chemicals")
        self.add_input(
            "hydrogen_chloride_cost", val=0, units="USD/kg", desc="Levelized cost of chemicals"
        )
