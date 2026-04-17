import PySAM.MhkTidal as MhkTidal
from attrs import field, define

from h2integrate.core.utilities import BaseConfig, merge_shared_inputs
from h2integrate.core.validators import gt_zero, contains
from h2integrate.core.model_baseclasses import PerformanceModelBaseClass


@define(kw_only=True)
class PySAMTidalPerformanceConfig(BaseConfig):
    """
    Configuration class for MHKTidalPlant.

    Args:
        device_rating_kw (float): Rated power of the MHK device [kW]
        num_devices (int): Number of MHK tidal devices in the system
        tidal_power_curve (List[List[float]]): Power curve of tidal energy device as
            function of stream speeds [kW]. Required if create_model_from == 'new'.
        create_model_from (str):
            - 'default': instantiate MhkTidal model from the default config 'config_name'
            - 'new': instantiate new MhkTidal model (default). Requires pysam_options.
        config_name (str,optional): PySAM.MhkTidal configuration name for non-hybrid wind systems.
            Defaults to 'MEtidalNone'. Only used if create_model_from='default'.
        pysam_options (dict, optional): dictionary of MhkTidal input parameters with
            top-level keys corresponding to the different MhkTidal variable groups.
            (please refer to MhkTidal documentation
            `here <https://nrel-pysam.readthedocs.io/en/main/modules/MhkTidal.html>`__
            )
        run_recalculate_power_curve (bool, optional): If True, the tidal device power curve will be
            recalculated based on the device_rating_kw and original power_curve. Defaults to False.

    """

    device_rating_kw: float = field(validator=gt_zero)
    num_devices: int = field(validator=gt_zero)
    tidal_power_curve: list[list[float]] | None = field(default=None)

    create_model_from: str = field(
        default="new", validator=contains(["default", "new"]), converter=(str.strip, str.lower)
    )

    config_name: str = field(
        default="MEtidalNone",
        validator=contains(
            [
                "MEtidalLCOECalculator",
                "MEtidalNone",
            ]
        ),
    )
    pysam_options: dict = field(default={})
    run_recalculate_power_curve: bool = field(default=False)

    def __attrs_post_init__(self):
        if self.create_model_from == "new" and not bool(self.pysam_options):
            msg = (
                "To create a new MhkTidal object, please provide a dictionary "
                "of MhkTidal design variables for the 'pysam_options' key."
            )
            raise ValueError(msg)

        if self.create_model_from == "new" and self.tidal_power_curve is None:
            msg = (
                "To create a new MhkTidal object, please provide a "
                "tidal_power_curve in the config."
            )
            raise ValueError(msg)

        self.check_pysam_options()

    def check_pysam_options(self):
        """Checks that top-level keys of pysam_options dictionary are valid and that
        system capacity is not given in pysam_options.

        Raises:
           ValueError: if top-level keys of pysam_options are not valid.
           ValueError: if number_devices is provided in pysam_options["MHKTidal"]
        """
        valid_groups = [
            "MHKTidal",
            "AdjustmentFactors",
        ]
        if bool(self.pysam_options):
            invalid_groups = [k for k in self.pysam_options if k not in valid_groups]
            if len(invalid_groups) > 0:
                msg = (
                    f"Invalid group(s) found in pysam_options: {invalid_groups}. "
                    f"Valid groups are: {valid_groups}."
                )
                raise ValueError(msg)

            if self.pysam_options.get("MHKTidal", {}).get("number_devices", None) is not None:
                msg = (
                    "Please do not specify number_devices in the pysam_options dictionary. "
                    "The number of tidal devices should be set with the 'num_devices' "
                    "performance parameter."
                )
                raise ValueError(msg)

        return

    def create_input_dict(self):
        """Create dictionary of inputs to over-write the default values
            associated with the specified MhkTidal configuration.

        Returns:
           dict: dictionary of MHKTidal group parameters from user-input.
        """
        design_dict = {
            "MHKTidal": {
                "number_devices": self.num_devices,
            },
        }

        return design_dict


class PySAMTidalPerformanceModel(PerformanceModelBaseClass):
    """An OpenMDAO component that wraps the PySAM MhkTidal model.
    It takes tidal parameters as input and outputs power generation data.
    """

    _time_step_bounds = (
        3600,
        3600,
    )  # (min, max) time step lengths (in seconds) compatible with this model

    def initialize(self):
        super().initialize()
        self.commodity = "electricity"
        self.commodity_rate_units = "kW"
        self.commodity_amount_units = "kW*h"

    def setup(self):
        super().setup()
        self.config = PySAMTidalPerformanceConfig.from_dict(
            merge_shared_inputs(self.options["tech_config"]["model_inputs"], "performance"),
            additional_cls_name=self.__class__.__name__,
        )

        #### Tidal Resource ####
        self.add_input(
            "tidal_velocity",
            val=0.0,
            shape=self.n_timesteps,
            units="m/s",
        )

        #### Tidal Device Parameters ####
        self.add_input(
            "num_devices",
            val=self.config.num_devices,
            units="unitless",
            desc="Number of tidal devices in the system",
        )

        self.add_input(
            "device_rating",
            val=self.config.device_rating_kw,
            units="kW",
            desc="Rated power of the tidal energy device",
        )

        if self.config.create_model_from == "default":
            self.system_model = MhkTidal.default(self.config.config_name)
        elif self.config.create_model_from == "new":
            self.system_model = MhkTidal.new()
            self.system_model.value("tidal_power_curve", self.config.tidal_power_curve)

        design_dict = self.config.create_input_dict()
        if bool(self.config.pysam_options):
            for group, group_parameters in self.config.pysam_options.items():
                if group in design_dict:
                    design_dict[group].update(group_parameters)
                else:
                    design_dict.update({group: group_parameters})
        self.system_model.assign(design_dict)

    def recalculate_power_curve(self, device_rating_kw, power_curve):
        """Recalculate tidal device power curve based on the device rating.

        Args:
            device_rating_kw (float): Rated power of the tidal energy device in kW.
            power_curve (List[List[float]]): Original power curve of tidal energy
                device as function of stream speeds [kW].

        Returns:
            List[List[float]]: Recalculated power curve based on the device rating.
        """
        original_rated_power = max([point[1] for point in power_curve])
        scaling_factor = device_rating_kw[0] / original_rated_power
        recalculated_power_curve = [(point[0], point[1] * scaling_factor) for point in power_curve]

        return recalculated_power_curve

    def compute(self, inputs, outputs):
        # set tidal resource model choice
        self.system_model.MHKTidal.tidal_resource_model_choice = (
            1  # Time-series data=1 JPD=0 (Joint-probability distribution)
        )

        # assign resource to tidal model
        tidal_velocity = inputs["tidal_velocity"]
        self.system_model.value("tidal_velocity", tidal_velocity)

        # recalculate power curve if specified in config
        if self.config.run_recalculate_power_curve:
            recalculated_power_curve = self.recalculate_power_curve(
                device_rating_kw=inputs["device_rating"],
                power_curve=self.config.tidal_power_curve,
            )
            self.system_model.value("tidal_power_curve", recalculated_power_curve)

        # calculate system capacity
        system_capacity_kw = inputs["num_devices"][0] * inputs["device_rating"][0]
        self.system_model.value("system_capacity", system_capacity_kw)
        self.system_model.value("number_devices", inputs["num_devices"][0])

        # run the model
        self.system_model.execute(0)

        outputs["electricity_out"] = self.system_model.Outputs.gen
        outputs["rated_electricity_production"] = system_capacity_kw

        outputs["total_electricity_produced"] = outputs["electricity_out"].sum() * (self.dt / 3600)
        outputs["annual_electricity_produced"] = self.system_model.Outputs.annual_energy

        outputs["capacity_factor"] = (
            self.system_model.Outputs.capacity_factor / 100
        )  # divide by 100 to make it unitless
