import operator
import functools
from typing import Any

import numpy as np
import PySAM.Windpower as Windpower
import matplotlib.pyplot as plt
from attrs import field, define

from h2integrate.core.utilities import BaseConfig, merge_shared_inputs
from h2integrate.core.validators import gt_zero, contains
from h2integrate.converters.wind.wind_plant_baseclass import WindPerformanceBaseClass
from h2integrate.converters.wind.layout.simple_grid_layout import (
    BasicGridLayoutConfig,
    make_basic_grid_turbine_layout,
)


@define(kw_only=True)
class PySAMPowerCurveCalculationInputs(BaseConfig):
    """Inputs for the ``calculate_powercurve()`` function in the PySAM Windpower module.
    The PySAM documentation of the inputs for this function can be found
    `here <https://nrel-pysam.readthedocs.io/en/main/modules/Windpower.html#PySAM.Windpower.Windpower.Turbine>`_


    Attributes:
        elevation (float): elevation in meters. Required if using Weibull resource model,
            otherwise should be zero. Defaults to 0.
        wind_default_max_cp (float): max power coefficient. Defaults to 0.45.
        wind_default_max_tip_speed (float): max tip speed in m/s. Defaults to 60.
        wind_default_max_tip_speed_ratio (float): max tip-speed ratio. Defaults to 8.
        wind_default_cut_in_speed (float): cut-in wind speed in m/s. Defaults to 4.
        wind_default_cut_out_speed (float): cut-out wind speed in m/s. Defaults to 25.
        wind_default_drive_train (int): integer representing wind turbine drive train type.
            Defaults to 0. The mapping of drive train number to drive train type is:
            - 0: 3 Stage Planetary
            - 1: Single Stage - Low Speed Generator
            - 2: Multi-Generator
            - 3: Direct Drive
    """

    elevation: int | float = field(default=0)
    wind_default_max_cp: int | float = field(default=0.45)
    wind_default_max_tip_speed: int | float = field(default=60)
    wind_default_max_tip_speed_ratio: int | float = field(default=8)
    wind_default_cut_in_speed: int | float = field(default=4)
    wind_default_cut_out_speed: int | float = field(default=25)
    wind_default_drive_train: int = field(
        default=0, converter=int, validator=contains([0, 1, 2, 3])
    )


@define(kw_only=True)
class PYSAMWindPlantPerformanceModelConfig(BaseConfig):
    """Configuration class for PYSAMWindPlantPerformanceModel.

    Attributes:
        num_turbines (int): number of turbines in farm
        hub_height (float): wind turbine hub-height in meters
        rotor_diameter (float): wind turbine rotor diameter in meters.
        turbine_rating_kw (float): wind turbines rated power in kW
        create_model_from (str):
            - 'default': instantiate Windpower model from the default config 'config_name'
            - 'new': instantiate new Windpower model (default). Requires pysam_options.
        config_name (str,optional): PySAM.Windpower configuration name for non-hybrid wind systems.
            Defaults to 'WindPowerSingleOwner'. Only used if create_model_from='default'.
        pysam_options (dict, optional): dictionary of Windpower input parameters with
            top-level keys corresponding to the different Windpower variable groups.
            (please refer to Windpower documentation
            `here <https://nrel-pysam.readthedocs.io/en/main/modules/Windpower.html>`__
            )
        run_recalculate_power_curve (bool, optional): whether to recalculate the wind turbine
            power curve. defaults to True.
    """

    num_turbines: int = field(converter=int, validator=gt_zero)
    hub_height: float = field(validator=gt_zero)
    rotor_diameter: float = field(validator=gt_zero)
    turbine_rating_kw: float = field(validator=gt_zero)

    create_model_from: str = field(
        default="new", validator=contains(["default", "new"]), converter=(str.strip, str.lower)
    )

    config_name: str = field(
        default="WindPowerSingleOwner",
        validator=contains(
            [
                "WindPowerAllEquityPartnershipFlip",
                "WindPowerCommercial",
                "WindPowerLeveragedPartnershipFlip",
                "WindPowerMerchantPlant",
                "WindPowerNone",
                "WindPowerResidential",
                "WindPowerSaleLeaseback",
                "WindPowerSingleOwner",
            ]
        ),
    )
    pysam_options: dict = field(default={})
    run_recalculate_power_curve: bool = field(default=True)
    layout: dict = field(default={})
    powercurve_calc_config: dict = field(default={})

    def __attrs_post_init__(self):
        if self.create_model_from == "new" and not bool(self.pysam_options):
            msg = (
                "To create a new Windpower object, please provide a dictionary "
                "of Windpower design variables for the 'pysam_options' key."
            )
            raise ValueError(msg)

        self.check_pysam_options()

    def check_pysam_options(self):
        """Checks that top-level keys of pysam_options dictionary are valid and that
        system capacity is not given in pysam_options.

        Raises:
           ValueError: if top-level keys of pysam_options are not valid.
           ValueError: if wind_turbine_hub_ht is provided in pysam_options["Turbine"]
        """
        valid_groups = [
            "Turbine",
            "Farm",
            "Resource",
            "Losses",
            "AdjustmentFactors",
            "HybridCosts",
            "Uncertainty",
        ]
        if bool(self.pysam_options):
            invalid_groups = [k for k in self.pysam_options if k not in valid_groups]
            if len(invalid_groups) > 0:
                msg = (
                    f"Invalid group(s) found in pysam_options: {invalid_groups}. "
                    f"Valid groups are: {valid_groups}."
                )
                raise ValueError(msg)

            if self.pysam_options.get("Turbine", {}).get("hub_height", None) is not None:
                msg = (
                    "Please do not specify wind_turbine_hub_ht in the pysam_options dictionary. "
                    "The wind turbine hub height should be set with the 'hub_height' "
                    "performance parameter."
                )
                raise ValueError(msg)

            if (
                self.pysam_options.get("Turbine", {}).get("wind_turbine_rotor_diameter", None)
                is not None
            ):
                msg = (
                    "Please do not specify wind_turbine_rotor_diameter in the pysam_options "
                    "dictionary. The wind turbine rotor diameter should be set with the "
                    "'rotor_diameter' performance parameter."
                )
                raise ValueError(msg)

        return

    def create_input_dict(self):
        """Create dictionary of inputs to over-write the default values
            associated with the specified Windpower configuration.

        Returns:
           dict: dictionary of Turbine group parameters from user-input.
        """
        design_dict = {
            "Turbine": {
                "wind_turbine_hub_ht": self.hub_height,
                "wind_turbine_rotor_diameter": self.rotor_diameter,
            },
        }

        return design_dict


class PYSAMWindPlantPerformanceModel(WindPerformanceBaseClass):
    """
    An OpenMDAO component that wraps a WindPlant model.
    It takes wind parameters as input and outputs power generation data.
    """

    def setup(self):
        super().setup()

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

        # initialize power-curve recalc config
        powercurveconfig = {}
        if "powercurve_calc_config" in performance_inputs:
            powercurveconfig = self.options["tech_config"]["model_inputs"][
                "performance_parameters"
            ]["powercurve_calc_config"]
        self.power_curve_config = PySAMPowerCurveCalculationInputs.from_dict(powercurveconfig)

        # initialize wind turbine config
        self.config = PYSAMWindPlantPerformanceModelConfig.from_dict(
            merge_shared_inputs(self.options["tech_config"]["model_inputs"], "performance")
        )

        self.add_input(
            "num_turbines",
            val=self.config.num_turbines,
            units="unitless",
            desc="number of turbines in farm",
        )

        self.add_input(
            "wind_turbine_rating",
            val=self.config.turbine_rating_kw,
            units="kW",
            desc="rating of an individual turbine in kW",
        )

        self.add_input(
            "rotor_diameter",
            val=self.config.rotor_diameter,
            units="m",
            desc="turbine rotor diameter",
        )

        self.add_input(
            "hub_height",
            val=self.config.hub_height,
            units="m",
            desc="turbine hub-height in meters",
        )

        self.add_output(
            "annual_energy",
            val=0.0,
            units="kW*h/year",
            desc="Annual energy production from WindPlant in kW",
        )
        self.add_output(
            "total_capacity", val=0.0, units="kW", desc="Wind farm rated capacity in kW"
        )

        if self.config.create_model_from == "default":
            self.system_model = Windpower.default(self.config.config_name)
        elif self.config.create_model_from == "new":
            self.system_model = Windpower.new(self.config.config_name)

        design_dict = self.config.create_input_dict()
        if bool(self.config.pysam_options):
            for group, group_parameters in self.config.pysam_options.items():
                if group in design_dict:
                    design_dict[group].update(group_parameters)
                else:
                    design_dict.update({group: group_parameters})
        self.system_model.assign(design_dict)

        self.data_to_field_number = {
            "temperature": 1,
            "pressure": 2,
            "wind_speed": 3,
            "wind_direction": 4,
        }

    def format_resource_data(self, hub_height, wind_resource_data):
        """Format wind resource data into the format required for the
        PySAM Windpower module. The data is formatted as:

        - **fields** (*list[int]*): integers corresponding to data type,
            ex: [1, 2, 3, 4, 1, 2, 3, 4]. Ror each field (int) the corresponding data is:
            - 1: Ambient temperature in degrees Celsius
            - 2: Atmospheric pressure in in atmospheres.
            - 3: Wind speed in meters per second (m/s)
            - 4: Wind direction in degrees east of north (degrees).
        - **heights** (*list[int | float]*): floats corresponding to the resource height.
            ex: [100, 100, 100, 100, 120, 120, 120, 120]
        - **data** (*list[list]*): list of length equal to `n_timesteps` with data of
            corresponding field and resource height.
            ex. if `data[t]` is [-23.5, 0.65, 7.6, 261.2, -23.7, 0.65, 7.58, 261.1] then:
            - 23.5 is temperature at 100m at timestep
            - 7.6 is wind speed at 100m at timestep
            - 7.58 is wind speed at 120m at timestep

        Args:
            hub_height (int | float): turbine hub-height in meters.
            wind_resource_data (dict): wind resource data dictionary.

        Returns:
            dict: PySAM formatted wind resource data.
        """

        data_to_precision = {
            "temperature": 1,
            "pressure": 2,
            "wind_speed": 2,
            "wind_direction": 1,
        }

        # find the resource heights that are closest to the hub-height for
        # PySAM Windpower resource data except pressure
        bounding_heights = self.calculate_bounding_heights_from_resource_data(
            hub_height,
            wind_resource_data,
            resource_vars=["wind_speed", "wind_direction", "temperature"],
        )

        # create list of resource heights and fields (as numbers)
        # heights and fields should be the same length
        # heights is a list of resource heights for each data type
        heights = np.repeat(bounding_heights, len(self.data_to_field_number))
        field_number_to_data = {v: k for k, v in self.data_to_field_number.items()}
        # fields is a list of numbers representing the data type
        fields = np.tile(list(field_number_to_data.keys()), len(bounding_heights))
        n_timesteps = int(self.options["plant_config"]["plant"]["simulation"]["n_timesteps"])

        # initialize resource data array
        resource_data = np.zeros((n_timesteps, len(fields)))
        cnt = 0
        for height, field_num in zip(heights, fields):
            # get the rounding precision for the field
            rounding_precision = data_to_precision[field_number_to_data[field_num]]
            # make the keyname for the field number and resource height to
            # pull from the wind_resource_dict
            resource_key = f"{field_number_to_data[field_num]}_{int(height)}m"
            if resource_key in wind_resource_data:
                # the resource data exists!
                resource_data[:, cnt] = wind_resource_data[resource_key].round(rounding_precision)
            else:
                # see if the wind resource data includes any data for the field variable
                if any(
                    field_number_to_data[field_num] in c for c in list(wind_resource_data.keys())
                ):
                    # get the resource heights for the field variable from wind_resource_data
                    data_heights = [
                        float(c.split("_")[-1].replace("m", "").strip())
                        for c in list(wind_resource_data.keys())
                        if field_number_to_data[field_num] in c
                    ]
                    if len(data_heights) > 1:
                        # get the nearest resource heights nearest to the wind turbine hub-height
                        # for all the available resource heights corresponding to the field variable
                        nearby_heights = [
                            self.calculate_bounding_heights_from_resource_data(
                                hub_ht,
                                wind_resource_data,
                                resource_vars=[field_number_to_data[field_num]],
                            )
                            for hub_ht in data_heights
                        ]
                        # make nearby_heights a list of unique values
                        nearby_heights = functools.reduce(operator.iadd, nearby_heights, [])
                        nearby_heights = list(set(nearby_heights))
                        # if theres multiple nearby heights, find the one that is closest
                        # to the target resource height
                        if len(nearby_heights) > 1:
                            height_diff = [
                                np.abs(valid_height - height) for valid_height in nearby_heights
                            ]
                            closest_height = nearby_heights[np.argmin(height_diff).flatten()[0]]
                            # make the resource key for the field and closest height to use
                            resource_key = (
                                f"{field_number_to_data[field_num]}_{int(closest_height)}m"
                            )

                        else:
                            # make the resource key for the field and closest height to use
                            resource_key = (
                                f"{field_number_to_data[field_num]}_{int(nearby_heights[0])}m"
                            )

                    else:
                        # theres only one resource height for the data variable
                        # make the resource key for the field and closest height to use
                        resource_key = f"{field_number_to_data[field_num]}_{int(data_heights[0])}m"
                    if resource_key in wind_resource_data:
                        # check if new key is in wind_resource_data and add the data if it is
                        resource_data[:, cnt] = wind_resource_data[resource_key].round(
                            rounding_precision
                        )
            cnt += 1
        # format data for compatibility with PySAM WindPower
        data = {
            "heights": heights.astype(float).tolist(),
            "fields": fields.tolist(),
            "data": resource_data.tolist(),
        }
        return data

    def recalculate_power_curve(self, rotor_diameter, turbine_rating_kw):
        """Update the turbine power curve for a given rotor diameter and rated turbine capacity.

        Args:
            rotor_diameter (int): turbine rotor diameter in meters.
            turbine_rating_kw (float | int): desired turbine rated capacity in kW

        Returns:
            bool: True if the new power curve has a maximum value equal to `turbine_rating_kw`
        """

        self.system_model.Turbine.calculate_powercurve(
            turbine_rating_kw,
            int(rotor_diameter),
            self.power_curve_config.elevation,
            self.power_curve_config.wind_default_max_cp,
            self.power_curve_config.wind_default_max_tip_speed,
            self.power_curve_config.wind_default_max_tip_speed_ratio,
            self.power_curve_config.wind_default_cut_in_speed,
            self.power_curve_config.wind_default_cut_out_speed,
            self.power_curve_config.wind_default_drive_train,
        )
        success = False
        if max(self.system_model.value("wind_turbine_powercurve_powerout")) == float(
            turbine_rating_kw
        ):
            success = True
        return success

    def compute(self, inputs, outputs, discrete_inputs, discrete_outputs):
        rotor_diameter = inputs["rotor_diameter"][0]
        turbine_rating_kw = inputs["wind_turbine_rating"][0]
        n_turbs = int(np.round(inputs["num_turbines"][0]))

        # format resource data and input into model
        data = self.format_resource_data(
            inputs["hub_height"][0], discrete_inputs["wind_resource_data"]
        )
        self.system_model.value("wind_resource_data", data)

        # recalculate power curve based on rotor diameter and turbine rating
        success = True
        if self.config.run_recalculate_power_curve:
            success = self.recalculate_power_curve(rotor_diameter, turbine_rating_kw)

        # if power-curve could not be adjusted to match input values
        if not success:
            msg = (
                "Could not adjust turbine powercurve to match turbine rating of ",
                f"{turbine_rating_kw} kW with a rotor diameter of {rotor_diameter} meters",
            )
            raise ValueError(msg)

        # assign new turbine specs to the model
        turbine_rated_power_kW = max(self.system_model.value("wind_turbine_powercurve_powerout"))
        farm_capacity = turbine_rated_power_kW * n_turbs
        self.system_model.value("wind_turbine_rotor_diameter", rotor_diameter)
        self.system_model.value("wind_turbine_hub_ht", inputs["hub_height"][0])
        self.system_model.value("system_capacity", farm_capacity)

        # make layout for number of turbines
        if self.layout_mode == "basicgrid":
            x_pos, y_pos = make_basic_grid_turbine_layout(
                self.system_model.value("wind_turbine_rotor_diameter"), n_turbs, self.layout_config
            )

        self.system_model.value("wind_farm_xCoordinates", tuple(x_pos))
        self.system_model.value("wind_farm_yCoordinates", tuple(y_pos))

        # run the model
        self.system_model.execute(0)

        outputs["electricity_out"] = self.system_model.Outputs.gen
        outputs["total_capacity"] = self.system_model.Farm.system_capacity
        outputs["annual_energy"] = self.system_model.Outputs.annual_energy

    def post_process(self, show_plots=False):
        def plot_turbine_points(
            ax: plt.Axes = None,
            plotting_dict: dict[str, Any] = {},
        ) -> plt.Axes:
            """
            Plots turbine layout.

            Args:
                ax (plt.Axes, optional): An existing axes object to plot on. If None,
                    a new figure and axes will be created. Defaults to None.
                plotting_dict (Dict[str, Any], optional):  A dictionary to customize plot
                    appearance.  Valid keys include:
                        * 'color' (str): Turbine marker color. Defaults to 'black'.
                        * 'marker' (str):  Turbine marker style. Defaults to '.'.
                        * 'markersize' (int): Turbine marker size. Defaults to 10.
                        * 'label' (str): Label for the legend. Defaults to None.

            Returns:
                plt.Axes: The axes object used for the plot.

            Raises:
                IndexError: If any value in `turbine_indices` is an invalid turbine index.
            """

            # Generate axis, if needed
            if ax is None:
                _, ax = plt.subplots()

            xpos = self.system_model.value("wind_farm_xCoordinates")
            ypos = self.system_model.value("wind_farm_yCoordinates")

            # Generate plotting dictionary
            default_plotting_dict = {
                "color": "black",
                "marker": ".",
                "markersize": 10,
                "label": None,
            }
            plotting_dict = {**default_plotting_dict, **plotting_dict}

            # Plot
            ax.plot(
                xpos,
                ypos,
                linestyle="None",
                **plotting_dict,
            )

            # Make sure axis set to equal
            ax.axis("equal")

            return ax

        if show_plots is True:
            _, ax = plt.subplots(1, 1, figsize=(16, 10))
            plot_turbine_points(ax=ax)
            plt.xlabel("x-coordinate")
            plt.ylabel("y-coordinate")
