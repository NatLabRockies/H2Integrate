import PySAM.Pvwattsv8 as Pvwatts
from attrs import field, define

from h2integrate.core.utilities import BaseConfig, merge_shared_inputs, check_pysam_input_params
from h2integrate.core.validators import contains, range_val_or_none
from h2integrate.converters.solar.solar_baseclass import SolarPerformanceBaseClass


@define(kw_only=True)
class PYSAMSolarPlantPerformanceModelDesignConfig(BaseConfig):
    """Configuration class for design parameters of the solar pv plant.
        PYSAMSolarPlantPerformanceModel which uses the Pvwattsv8 module
        available in PySAM. PySAM documentation can be found
        `here <https://nrel-pysam.readthedocs.io/en/main/modules/Pvwattsv8.html#pvwattsv8>`__


    Attributes:
        pv_capacity_kWdc (float): Required, DC system capacity in kW-dc.
        dc_ac_ratio (float | None): Also known as inverter loading ratio, ratio of max DC
            output of PV to max AC output of inverter. If None, then uses the default
            value associated with config_name.
        create_model_from (str):
            - 'default': instantiate Pvwattsv8 model from the default config 'config_name'
            - 'new': instantiate new Pvwattsv8 model (default). Requires pysam_options.
        config_name (str,optional): PySAM.Pvwattsv8 configuration name for non-hybrid PV systems.
            Defaults to 'PVWattsSingleOwner'. Only used if create_model_from='default'.
        tilt (float | None): Panel tilt angle in the range (0.0, 90.0).
            If None, then uses the default value associated with config_name if create_model_from
            is 'default' unless tilt_angle_func is either set to 'lat' or 'lat-func'.
        tilt_angle_func (str):
            - 'none': use value specific in 'tilt' (default).
            - 'lat-func': optimal tilt angle based on the latitude.
            - 'lat': tilt angle equal to the latitude of the solar resource.
        pysam_options (dict, optional): dictionary of Pvwatts input parameters with
            top-level keys corresponding to the different Pvwattsv8 variable groups.
            (please refer to Pvwattsv8 documentation
            `here <https://nrel-pysam.readthedocs.io/en/main/modules/Pvwattsv8.html>`__
            )

    """

    pv_capacity_kWdc: float = field()

    dc_ac_ratio: float = field(
        default=None, validator=range_val_or_none(0.0, 2.0)
    )  # default value depends on config

    create_model_from: str = field(
        default="new", validator=contains(["default", "new"]), converter=(str.strip, str.lower)
    )

    tilt: float = field(default=None, validator=range_val_or_none(0.0, 90.0))

    tilt_angle_func: str = field(
        default="none",
        validator=contains(["none", "lat-func", "lat"]),
        converter=(str.strip, str.lower),
    )

    config_name: str = field(
        default="PVWattsSingleOwner",
        validator=contains(
            [
                "PVWattsCommercial",
                "PVWattsCommunitySolar",
                "PVWattsHostDeveloper",
                "PVWattsMerchantPlant",
                "PVWattsNone",
                "PVWattsResidential",
                "PVWattsSaleLeaseback",
                "PVWattsSingleOwner",
                "PVWattsThirdParty",
                "PVWattsAllEquityPartnershipFlip",
            ]
        ),
    )

    pysam_options: dict = field(default={})

    def __attrs_post_init__(self):
        if self.create_model_from == "new" and not bool(self.pysam_options):
            msg = (
                "To create a new Pvwattsv8 object, please provide a dictionary "
                "of Pvwattsv8 design variables for the 'pysam_options' key."
            )
            raise ValueError(msg)

        self.check_pysam_options()

    def check_pysam_options(self):
        """Checks that top-level keys of pysam_options dictionary are valid and that
        system capacity is not given in pysam_options.

        Raises:
           ValueError: if top-level keys of pysam_options are not valid.
           ValueError: if system_capacity is provided in pysam_options["SystemDesign"]
        """

        valid_groups = [
            "SolarResource",
            "Lifetime",
            "SystemDesign",
            "Shading",
            "AdjustmentFactors",
            "HybridCosts",
        ]
        if bool(self.pysam_options):
            invalid_groups = [k for k in self.pysam_options if k not in valid_groups]
            if len(invalid_groups) > 0:
                msg = (
                    f"Invalid group(s) found in pysam_options: {invalid_groups}. "
                    f"Valid groups are: {valid_groups}."
                )
                raise ValueError(msg)
            if self.pysam_options.get("SystemDesign", {}).get("system_capacity", None) is not None:
                msg = (
                    "Please do not specify system_capacity in the pysam_options dictionary. "
                    "The solar-PV capacity (in kW-dc) should be set with the 'pv_capacity_kWdc' "
                    "performance parameter."
                )
                raise ValueError(msg)
        return

    def create_input_dict(self):
        """Create dictionary of inputs to over-write the default values
            associated with the specified PVWatts configuration.

        Returns:
           dict: dictionary of SystemDesign and SolarResource parameters from user-input.
        """

        full_dict = self.as_dict()
        design_cols = ["dc_ac_ratio", "tilt"]
        design_dict = {k: v for k, v in full_dict.items() if k in design_cols and v is not None}
        return {"SystemDesign": design_dict}


class PYSAMSolarPlantPerformanceModel(SolarPerformanceBaseClass):
    """
    An OpenMDAO component that wraps a SolarPlant model.
    It takes solar parameters as input and outputs power generation data.
    """

    def setup(self):
        super().setup()

        self.design_config = PYSAMSolarPlantPerformanceModelDesignConfig.from_dict(
            merge_shared_inputs(self.options["tech_config"]["model_inputs"], "performance"),
            strict=False,
        )
        self.add_input(
            "system_capacity_DC",
            val=self.design_config.pv_capacity_kWdc,
            units="kW",
            desc="PV rated capacity in DC",
        )
        self.add_output("system_capacity_AC", val=0.0, units="kW", desc="PV rated capacity in AC")
        self.add_output(
            "annual_energy",
            val=0.0,
            units="kW*h/year",
            desc="Annual energy production in kWac",
        )

        if self.design_config.create_model_from == "default":
            self.system_model = Pvwatts.default(self.design_config.config_name)
        elif self.design_config.create_model_from == "new":
            self.system_model = Pvwatts.new(self.design_config.config_name)

        design_dict = self.design_config.create_input_dict()

        # update design_dict if user provides non-empty design information
        if bool(self.design_config.pysam_options):
            check_pysam_input_params(design_dict, self.design_config.pysam_options)

            for group, group_parameters in self.design_config.pysam_options.items():
                if group in design_dict:
                    design_dict[group].update(group_parameters)
                else:
                    design_dict.update({group: group_parameters})

        self.design_dict = design_dict
        self.system_model.assign(design_dict)

    def calc_tilt_angle(self, latitude):
        """
        Calculates the tilt angle of the PV panel based on the tilt option described by
        design_config.tilt_angle_func.

        Returns:
            float: tilt angle of the PV panel in degrees.
        """
        # If tilt angle function is 'none', use the provided tilt value or default
        if self.design_config.tilt_angle_func == "none":
            # If using a default PySAM model, get tilt from model if not specified
            if self.design_config.create_model_from == "default":
                if self.design_config.tilt is None:
                    # Return the default tilt from the system model
                    return self.system_model.value("tilt")
                else:
                    # Return user-specified tilt
                    return self.design_config.tilt

            # If creating a new PySAM model, get tilt from pysam_options or default to 0
            if self.design_config.create_model_from == "new":
                if self.design_config.tilt is None:
                    # Return tilt from pysam_options if provided, else 0
                    return self.design_config.pysam_options.get("SystemDesign", {}).get("tilt", 0)
                else:
                    # Return user-specified tilt
                    return self.design_config.tilt

        # If tilt angle function is 'lat', use the latitude as the tilt
        if self.design_config.tilt_angle_func == "lat":
            return latitude

        # If tilt angle function is 'lat-func', use empirical formulas based on latitude
        if self.design_config.tilt_angle_func == "lat-func":
            if latitude <= 25:
                # For latitudes <= 25, use 0.87 * latitude
                return latitude * 0.87
            if 25 < latitude <= 50:
                # For latitudes between 25 and 50, use 0.76 * latitude + 3.1
                return (latitude * 0.76) + 3.1
            # For latitudes > 50, use latitude directly
            return latitude

    def format_resource_data(self, solar_resource_data):
        """Format solar resource data into the format required for the
        PySAM PvWattsv8 module. This method includes:

        1. Renaming solar resource data keys to the keynames
        expected by the PvWattsv8 modules
        2. Remove any solar resource data that PvWattsv8 does not use.

        Args:
            solar_resource_data (dict): solar resource data dictionary

        Returns:
            dict: PySAM formatted solar resource data
        """

        resource_name_mapper = {
            "elevation": "elev",
            "site_lat": "lat",
            "site_lon": "lon",
            "data_tz": "tz",
            "year": "year",
            "month": "month",
            "day": "day",
            "hour": "hour",
            "minute": "minute",
            "dni": "dn",
            "dhi": "df",
            "ghi": "gh",
            "wind_speed": "wspd",
            "temperature": "tdry",
            "wind_direction": "wdir",
            "pressure": "pres",
            "dew_point": "tdew",
            "relative_humidity": "rhum",
            "surface_albedo": "alb",
            "snow_depth": "snow",
        }

        reformatted_data = {}
        for old_key, values in solar_resource_data.items():
            if old_key in resource_name_mapper:
                new_key = resource_name_mapper[old_key]
                if not isinstance(values, (float, int, str, bool)):
                    reformatted_data.update({new_key: values.astype(float).tolist()})
                else:
                    reformatted_data.update({new_key: values})
        return reformatted_data

    def compute(self, inputs, outputs, discrete_inputs, discrete_outputs):
        # calculate the tilt angle based on site latitude (use 0 if site latitude is not input)
        tilt = self.calc_tilt_angle(discrete_inputs["solar_resource_data"].get("site_lat", 0))
        # over-write the tilt angle if it was specified in the design dict
        tilt_angle = self.design_dict.get("SystemDesign", {}).get("tilt", tilt)
        # assign the tilt angle
        self.system_model.value("tilt", tilt_angle)

        # set the system capacity
        self.system_model.value("system_capacity", inputs["system_capacity_DC"][0])

        solar_resource_data = discrete_inputs["solar_resource_data"]
        # format solar resource data into the necessary format for PySAM
        solar_resource = self.format_resource_data(solar_resource_data)
        self.system_model.value("solar_resource_data", solar_resource)

        # run the model
        self.system_model.execute(0)

        # assign outputs
        outputs["electricity_out"] = self.system_model.Outputs.gen  # kW-dc
        pv_capacity_kWdc = self.system_model.value("system_capacity")
        dc_ac_ratio = self.system_model.value("dc_ac_ratio")
        outputs["system_capacity_AC"] = pv_capacity_kWdc / dc_ac_ratio
        outputs["annual_energy"] = self.system_model.value("ac_annual")
