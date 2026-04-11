from h2integrate.core.model_baseclasses import PerformanceModelBaseClass


class SolarPerformanceBaseClass(PerformanceModelBaseClass):
    _time_step_bounds = (3600, 3600)  # (min, max) time step lengths compatible with this model

    def initialize(self):
        super().initialize()
        self.commodity = "electricity"
        self.commodity_rate_units = "kW"
        self.commodity_amount_units = "kW*h"

    def setup(self):
        super().setup()

        self.add_discrete_input(
            "solar_resource_data",
            val={},
            desc="Solar resource data dictionary",
        )

    def compute(self, inputs, outputs, discrete_inputs, discrete_outputs):
        """
        Computation for the OM component.

        For a template class this is not implement and raises an error.
        """

        raise NotImplementedError("This method should be implemented in a subclass.")
