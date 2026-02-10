from h2integrate.core.model_baseclasses import CostModelBaseClass, PerformanceModelBaseClass


class DesalinationPerformanceBaseClass(PerformanceModelBaseClass):
    def initialize(self):
        super().initialize()
        self.commodity = "water"
        self.commodity_amount_units = "m**3"
        self.commodity_rate_units = "m**3/h"

    def setup(self):
        super().setup()

        self.add_output("mass", val=0.0, units="kg", desc="Mass of desalination system")
        self.add_output("footprint", val=0.0, units="m**2", desc="Footprint of desalination system")

    def compute(self, inputs, outputs):
        """
        Computation for the OM component.

        For a template class this is not implement and raises an error.
        """

        raise NotImplementedError("This method should be implemented in a subclass.")


class DesalinationCostBaseClass(CostModelBaseClass):
    def setup(self):
        super().setup()
        # Inputs for cost model configuration
        self.add_input(
            "plant_capacity_kgph", val=0.0, units="kg/h", desc="Desired freshwater flow rate"
        )
