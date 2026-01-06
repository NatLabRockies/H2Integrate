import copy

import numpy as np
from attrs import field, define, validators
from floris import TimeSeries, FlorisModel

from h2integrate.core.utilities import CacheBaseConfig, merge_shared_inputs
from h2integrate.core.validators import gt_zero, contains, range_val
from h2integrate.core.model_baseclasses import CacheBaseClass
from h2integrate.converters.wind.tools.resource_tools import (
    average_wind_data_for_hubheight,
    weighted_average_wind_data_for_hubheight,
)
from h2integrate.converters.wind.wind_plant_baseclass import WindPerformanceBaseClass
from h2integrate.converters.wind.layout.simple_grid_layout import (
    BasicGridLayoutConfig,
    make_basic_grid_turbine_layout,
)


@define
class FlorisWindPlantPerformanceConfig(CacheBaseConfig):
    """Configuration class for FlorisWindPlantPerformanceModel.

    Attributes:
        num_turbines (int): number of turbines in farm
        floris_wake_config (dict): dictionary containing FLORIS inputs for flow_field, wake,
            solver, and logging.
        floris_turbine_config (dict): dictionary containing turbine parameters formatted for FLORIS.
        operational_losses (float | int): non-wake losses represented as a percentage
            (between 0 and 100).
        hub_height (float | int, optional): a value of -1 indicates to use the hub-height
            from the `floris_turbine_config`. Otherwise, is the turbine hub-height
            in meters. Defaults to -1.
        floris_operation_model (str, optional): turbine operation model. Defaults to 'cosine-loss'.
        default_turbulence_intensity (float): default turbulence intensity to use if not found
            in wind resource data.
        layout (dict): layout parameters dictionary.
        resource_data_averaging_method (str): string indicating what method to use to
            adjust or select resource data if no resource data is available at a height
            exactly equal to the turbine hub-height. Defaults to 'weighted_average'.
            The available methods are:
            - 'weighted_average': average the resource data at the heights that most closely bound
                the hub-height, weighted by the difference between the resource heights and the
                hub-height.
            - 'average': average the resource data at the heights that most closely bound
                the hub-height.
            - 'nearest': use the resource data at the height closest to the hub-height.
        enable_caching (bool, optional): if True, checks if the outputs have be saved to a
            cached file or saves outputs to a file. Defaults to True.
        cache_dir (str | Path, optional): folder to use for reading or writing cached results files.
            Only used if enable_caching is True. Defaults to "cache".
        hybrid_turbine_design (bool, optional): whether multiple turbine types are included in
            the farm. Defaults to False. The functionality to use multiple turbine types
            is not yet implemented. Will result in NotImplementedError if True.
    """

    num_turbines: int = field(converter=int, validator=gt_zero)
    floris_wake_config: dict = field()
    floris_turbine_config: dict = field()
    default_turbulence_intensity: float = field()
    operational_losses: float = field(validator=range_val(0.0, 100.0))
    hub_height: float = field(default=-1, validator=validators.ge(-1))
    floris_operation_model: str = field(default="cosine-loss")
    layout: dict = field(default={})
    resource_data_averaging_method: str = field(
        default="weighted_average", validator=contains(["weighted_average", "average", "nearest"])
    )
    hybrid_turbine_design: bool = field(default=False)

    # if using multiple turbines, then need to specify resource reference height
    def __attrs_post_init__(self):
        super().__attrs_post_init__()
        n_turbine_types = len(self.floris_wake_config.get("farm", {}).get("turbine_type", []))
        n_pos = len(self.floris_wake_config.get("farm", {}).get("layout_x", []))
        if n_turbine_types > 1 and n_turbine_types != n_pos:
            self.hybrid_turbine_design = True

        # use floris_turbines
        if self.hub_height < 0 and not self.hybrid_turbine_design:
            self.hub_height = self.floris_turbine_config.get("hub_height")

        # check that user did not provide a layout in the floris_wake_config
        gave_x_coords = len(self.floris_wake_config.get("farm", {}).get("layout_x", [])) > 0
        gave_y_coords = len(self.floris_wake_config.get("farm", {}).get("layout_y", [])) > 0
        if gave_x_coords or gave_y_coords:
            msg = (
                "Layout provided in `floris_wake_config['farm']` but layout will be created "
                "based on the `layout_mode` and `layout_options` provided in the "
                "`layout` dictionary. Please set the layout in "
                "floris_wake_config['farm']['layout_x'] and floris_wake_config['farm']['layout_y']"
                " to empty lists"
            )
            raise ValueError(msg)


class FlorisWindPlantPerformanceModel(WindPerformanceBaseClass, CacheBaseClass):
    """
    An OpenMDAO component that wraps a Floris model.
    It takes wind turbine model parameters and wind resource data as input and
    outputs power generation data.
    """

    def setup(self):
        self.n_timesteps = int(self.options["plant_config"]["plant"]["simulation"]["n_timesteps"])

        performance_inputs = self.options["tech_config"]["model_inputs"]["performance_parameters"]

        # initialize layout config
        layout_options = {}
        if "layout" in performance_inputs:
            layout_params = self.options["tech_config"]["model_inputs"]["performance_parameters"][
                "layout"
            ]
        layout_mode = layout_params.get("layout_mode", "basicgrid")
        layout_options = layout_params.get("layout_options", {})
        if layout_mode == "basicgrid":
            self.layout_config = BasicGridLayoutConfig.from_dict(layout_options)
        self.layout_mode = layout_mode

        # initialize wind turbine config
        self.config = FlorisWindPlantPerformanceConfig.from_dict(
            merge_shared_inputs(self.options["tech_config"]["model_inputs"], "performance")
        )

        if self.config.hybrid_turbine_design:
            raise NotImplementedError(
                "H2I does not currently support running multiple different wind turbine "
                "designs with Floris."
            )

        self.add_input(
            "num_turbines",
            val=self.config.num_turbines,
            units="unitless",
            desc="number of turbines in farm",
        )

        self.add_input(
            "hub_height",
            val=self.config.hub_height,
            units="m",
            desc="turbine hub-height",
        )

        self.add_output(
            "total_electricity_produced",
            val=0.0,
            units="kW*h/year",
            desc="Annual energy production from WindPlant",
        )
        self.add_output("total_capacity", val=0.0, units="kW", desc="Wind farm rated capacity")

        self.add_output(
            "capacity_factor", val=0.0, units="percent", desc="Wind farm capacity factor"
        )

        super().setup()

        power_curve = self.config.floris_turbine_config.get("power_thrust_table").get("power")
        self.wind_turbine_rating_kW = np.max(power_curve)

    def format_resource_data(self, hub_height, wind_resource_data):
        # NOTE: could weight resource data of bounding heights like
        # `weighted_parse_resource_data` method in HOPP

        bounding_heights = self.calculate_bounding_heights_from_resource_data(
            hub_height, wind_resource_data, resource_vars=["wind_speed", "wind_direction"]
        )
        if len(bounding_heights) == 1:
            resource_height = bounding_heights[0]
            windspeed = wind_resource_data[f"wind_speed_{resource_height}m"]
            winddir = wind_resource_data[f"wind_direction_{resource_height}m"]
        else:
            if self.config.resource_data_averaging_method == "nearest":
                height_difference = [np.abs(hub_height - b) for b in bounding_heights]
                resource_height = bounding_heights[np.argmin(height_difference).flatten()[0]]
                windspeed = wind_resource_data[f"wind_speed_{resource_height}m"]
                winddir = wind_resource_data[f"wind_direction_{resource_height}m"]
            if self.config.resource_data_averaging_method == "weighted_average":
                windspeed = weighted_average_wind_data_for_hubheight(
                    wind_resource_data, bounding_heights, hub_height, "wind_speed"
                )
                winddir = weighted_average_wind_data_for_hubheight(
                    wind_resource_data, bounding_heights, hub_height, "wind_direction"
                )
            if self.config.resource_data_averaging_method == "average":
                windspeed = average_wind_data_for_hubheight(
                    wind_resource_data, bounding_heights, "wind_speed"
                )
                winddir = average_wind_data_for_hubheight(
                    wind_resource_data, bounding_heights, "wind_direction"
                )

        # get turbulence intensity

        # check if turbulence intensity is available in wind resource data
        if any("turbulence_intensity_" in k for k in wind_resource_data.keys()):
            for height in bounding_heights:
                if f"turbulence_intensity_{height}m" in wind_resource_data:
                    ti = wind_resource_data.get(
                        f"turbulence_intensity_{height}m", self.config.default_turbulence_intensity
                    )
                    break
        else:
            ti = wind_resource_data.get(
                "turbulence_intensity", self.config.default_turbulence_intensity
            )

        time_series = TimeSeries(
            wind_directions=winddir,
            wind_speeds=windspeed,
            turbulence_intensities=ti,
        )

        return time_series

    def compute(self, inputs, outputs, discrete_inputs, discrete_outputs):
        # NOTE: could update air density based on elevation if elevation is included
        # in the resource data.
        # would need to duplicate the ``calculate_air_density`` function from HOPP

        # 1. Check if the results for the current configuration are already cached
        config_dict = self.config.as_dict()
        config_dict.update({"wind_turbine_size_kw": self.wind_turbine_rating_kW})
        loaded_results = self.load_outputs(
            inputs, outputs, discrete_inputs, discrete_outputs={}, config_dict=config_dict
        )
        if loaded_results:
            # Case has been run before and outputs have been set, can exit this function
            return

        # 2. If caching is not enabled or a cache file does not exist, run FLORIS
        n_turbs = int(np.round(inputs["num_turbines"][0]))

        # Copy main config files
        floris_config = copy.deepcopy(self.config.floris_wake_config)
        turbine_design = copy.deepcopy(self.config.floris_turbine_config)

        # update the turbine hub-height in the floris turbine config
        turbine_design.update({"hub_height": inputs["hub_height"][0]})

        # update the operation model in the floris turbine config
        turbine_design.update({"operation_model": self.config.floris_operation_model})

        # format resource data and input into model
        time_series = self.format_resource_data(
            inputs["hub_height"][0], discrete_inputs["wind_resource_data"]
        )

        # make layout for number of turbines
        if self.layout_mode == "basicgrid":
            x_pos, y_pos = make_basic_grid_turbine_layout(
                turbine_design.get("rotor_diameter"), n_turbs, self.layout_config
            )

        floris_farm = {"layout_x": x_pos, "layout_y": y_pos, "turbine_type": [turbine_design]}

        floris_config["farm"].update(floris_farm)

        # initialize FLORIS
        floris_config["flow_field"].update({"turbulence_intensities": []})
        self.fi = FlorisModel(floris_config)

        # set the layout and wind data in Floris
        self.fi.set(layout_x=x_pos, layout_y=y_pos, wind_data=time_series)

        # run the model
        self.fi.run()

        power_farm = self.fi.get_farm_power().reshape(self.n_timesteps)  # W

        # Adding losses (excluding turbine and wake losses)
        operational_efficiency = (100 - self.config.operational_losses) / 100
        gen = power_farm * operational_efficiency / 1000  # kW

        # set outputs
        outputs["electricity_out"] = gen
        outputs["total_capacity"] = n_turbs * self.wind_turbine_rating_kW

        max_production = n_turbs * self.wind_turbine_rating_kW * len(gen)
        outputs["total_electricity_produced"] = np.sum(gen)
        outputs["capacity_factor"] = np.sum(gen) / max_production

        # 3. Cache the results for future use if enabled
        self.cache_outputs(
            inputs, outputs, discrete_inputs, discrete_outputs={}, config_dict=config_dict
        )
