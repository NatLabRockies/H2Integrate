from h2integrate.core.model_baseclasses import PerformanceModelBaseClass


class BatteryPerformanceBaseClass(PerformanceModelBaseClass):
    def setup(self):
        self.commodity = "electricity"
        self.commodity_rate_units = "kW"
        self.commodity_amount_units = "kW*h"
        super().setup()

        self.add_input(
            "electricity_in",
            val=0.0,
            shape_by_conn=True,
            units="kW",
            desc="Power input to Battery",
        )

        # self.add_output(
        #     "electricity_out",
        #     val=0.0,
        #     copy_shape="electricity_in",
        #     units="kW",
        #     desc="Total electricity out of Battery",
        # )

        self.add_output(
            "SOC",
            val=0.0,
            copy_shape="electricity_in",
            units="percent",
            desc="State of charge of Battery",
        )

        self.add_output(
            "battery_electricity_discharge",
            val=0.0,
            copy_shape="electricity_in",
            units="kW",
            desc="Electricity output from Battery only",
        )

    def compute(self, inputs, outputs):
        """
        Computation for the OM component.

        For a template class this is not implemented and raises an error.
        """

        raise NotImplementedError("This method should be implemented in a subclass.")
