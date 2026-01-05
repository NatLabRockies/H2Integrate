import openmdao.api as om


class BatteryPerformanceBaseClass(om.ExplicitComponent):
    def initialize(self):
        self.options.declare("driver_config", types=dict)
        self.options.declare("plant_config", types=dict)
        self.options.declare("tech_config", types=dict)

    def setup(self):
        dt = self.options["plant_config"]["plant"]["simulation"]["dt"]

        self.add_input(
            "electricity_in",
            val=0.0,
            shape_by_conn=True,
            units=f"kW*({dt}*s)",
            desc="Power input to Battery",
        )

        self.add_output(
            "electricity_out",
            val=0.0,
            copy_shape="electricity_in",
            units=f"kW*({dt}*s)",
            desc="Total electricity out of Battery",
        )

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
            units=f"kW*({dt}*s)",
            desc="Electricity output from Battery only",
        )

    def compute(self, inputs, outputs):
        """
        Computation for the OM component.

        For a template class this is not implemented and raises an error.
        """

        raise NotImplementedError("This method should be implemented in a subclass.")
