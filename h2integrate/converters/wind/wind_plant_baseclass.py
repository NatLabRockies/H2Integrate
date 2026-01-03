import openmdao.api as om


class WindPerformanceBaseClass(om.ExplicitComponent):
    def initialize(self):
        self.options.declare("driver_config", types=dict)
        self.options.declare("plant_config", types=dict)
        self.options.declare("tech_config", types=dict)

    def setup(self):
        n_timesteps = self.options["plant_config"]["plant"]["simulation"]["n_timesteps"]
        dt = self.options["plant_config"]["plant"]["simulation"]["dt"]

        self.add_output(
            "electricity_out",
            val=0.0,
            shape=n_timesteps,
            units=f"kW*({dt}*s)",
            desc="Power output from WindPlant",
        )
        self.add_discrete_input(
            "wind_resource_data",
            val={},
            desc="Wind resource data dictionary",
        )

    def calculate_bounding_heights_from_resource_data(
        self, hub_height_meters, resource_data, resource_vars=["wind_speed"]
    ):
        """This method finds the wind resource heights that bound the turbine hub-height.
        This method returns resource heights (`height_1` and/or `height_2`) that are closest
        to the turbine hub-height and where ``height_1 < hub_height_meters < height_2`` OR
        ``height_1 == hub_height_meters``.

        Note:
            This function assumes resource heights are integers. This function also assumes
            that all variables in ``resource_vars`` have the same resource heights.

        Args:
            hub_height_meters (int | float): turbine hub-height in meters
            resource_data (dict): wind resource data dictionary.
            resource_vars (list[str], optional): Wind resource data types
                used to find the bounding resource heights. Defaults to
                ["wind_speed"].

        Returns:
            list[int]: list of resource heights in meters that most closely bound
                the turbine hub-height.
        """
        heights_per_parameter = {}
        allowed_hub_height_meters = set()
        # get a list of resource heights from the wind resource dictionary
        # for the resource parameters `resource_vars`
        for param in resource_vars:
            params_heights = [
                int(k.split("_")[-1].replace("m", "").strip())
                for k, v in resource_data.items()
                if param in k and "m" in k.split("_")[-1]
            ]
            if len(params_heights) > 0:
                heights_per_parameter.update({param: params_heights})
                allowed_hub_height_meters.update(params_heights)

        # Check if any resource height is equal to the hub-height
        if any(float(hh) == float(hub_height_meters) for hh in allowed_hub_height_meters):
            return [int(hub_height_meters)]
        # Find the bounding hub-heights
        # Find the resource heights below the turbine height
        heights_lower = [hh for hh in allowed_hub_height_meters if hh / hub_height_meters < 1]
        # Find the resource heights above the turbine height
        heights_upper = [hh for hh in allowed_hub_height_meters if hh / hub_height_meters > 1]
        # Select the lower-bound resource height as the one closest to `hub_height_meters`
        height_low = (
            max(heights_lower) if len(heights_lower) > 0 else min(allowed_hub_height_meters)
        )
        # Select the upper-bound resource height as the one closest to `hub_height_meters`
        height_high = (
            min(heights_upper) if len(heights_upper) > 0 else max(allowed_hub_height_meters)
        )
        return [int(height_low), int(height_high)]

    def compute(self, inputs, outputs, discrete_inputs, discrete_outputs):
        """
        Computation for the OM component.

        For a template class this is not implement and raises an error.
        """

        raise NotImplementedError("This method should be implemented in a subclass.")


class WindFinanceBaseClass(om.ExplicitComponent):
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
