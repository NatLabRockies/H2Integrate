import pandas as pd
import PySAM.MhkWave as MhkWave
from attrs import field, define, validators

from h2integrate.core.utilities import BaseConfig, merge_shared_inputs
from h2integrate.core.model_baseclasses import PerformanceModelBaseClass


@define(kw_only=True)
class PySAMWavePerformanceConfig(BaseConfig):
    """Configuration class for PySAMWavePerformanceModel.

    Args:
        device_rating_kw (float): Rated power of the MHK wave device [kW].
        num_devices (int): Number of MHK wave devices in the system.
        wave_power_matrix (List[List[float]]): Power matrix of the wave energy device
            as a function of significant wave height (Hs) [m] and energy period (Te) [s].
            The first row contains the energy period bin centers, and the first column
            of each subsequent row contains the Hs bin center followed by the device
            power output [kW] at each (Hs, Te) combination.
            Required if ``create_model_from == 'new'``.
        resource_year (int, optional): Calendar year of the resource data, used to
            generate timestamps for the time-series resource input. Defaults to 2010.
        create_model_from (str):
            - ``'default'``: instantiate MhkWave model from the default config
              ``config_name``.
            - ``'new'``: instantiate a new MhkWave model (default). Requires
              ``wave_power_matrix``.
        config_name (str, optional): PySAM.MhkWave configuration name for non-hybrid
            wave systems. Defaults to ``'MEwaveNone'``. Only used if
            ``create_model_from='default'``.
        pysam_options (dict, optional): Dictionary of MhkWave input parameters with
            top-level keys corresponding to the different MhkWave variable groups.
            Refer to the MhkWave documentation
            `here <https://nrel-pysam.readthedocs.io/en/main/modules/MhkWave.html>`__.
    """

    device_rating_kw: float = field(validator=validators.gt(0))
    num_devices: int = field(validator=validators.gt(0))
    wave_power_matrix: list[list[float]] | None = field(default=None)
    resource_year: int = field(default=2010, converter=int)

    create_model_from: str = field(
        default="new",
        validator=validators.in_(["default", "new"]),
        converter=(str.strip, str.lower),
    )

    config_name: str = field(
        default="MEwaveNone",
        validator=validators.in_(
            [
                "MEwaveBatterySingleOwner",
                "MEwaveLCOECalculator",
                "MEwaveNone",
                "MEwaveSingleOwner",
            ]
        ),
    )
    pysam_options: dict = field(default={})

    def __attrs_post_init__(self):
        if self.create_model_from == "new" and self.wave_power_matrix is None:
            msg = (
                "To create a new MhkWave object, please provide a "
                "wave_power_matrix in the config."
            )
            raise ValueError(msg)

        self.check_pysam_options()

    def check_pysam_options(self):
        """Check that top-level keys of pysam_options are valid and that
        system capacity is not given in pysam_options.

        Raises:
            ValueError: If top-level keys of pysam_options are not valid.
            ValueError: If ``number_devices`` is provided in
                ``pysam_options["MHKWave"]``.
        """
        valid_groups = [
            "MHKWave",
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

            if self.pysam_options.get("MHKWave", {}).get("number_devices", None) is not None:
                msg = (
                    "Please do not specify number_devices in the pysam_options dictionary. "
                    "The number of wave devices should be set with the 'num_devices' "
                    "performance parameter."
                )
                raise ValueError(msg)

        return

    def create_input_dict(self):
        """Create a dictionary of inputs to override the default values
        associated with the specified MhkWave configuration.

        Loss parameters default to zero; override them via ``pysam_options``
        if non-zero losses are required.

        Returns:
            dict: Dictionary of MHKWave group parameters from user input.
        """
        design_dict = {
            "MHKWave": {
                "number_devices": self.num_devices,
                "loss_array_spacing": 0.0,
                "loss_resource_overprediction": 0.0,
                "loss_transmission": 0.0,
                "loss_downtime": 0.0,
                "loss_additional": 0.0,
            },
        }

        return design_dict


class PySAMWavePerformanceModel(PerformanceModelBaseClass):
    """An OpenMDAO component that wraps the PySAM MhkWave model.

    It takes wave resource parameters as input and outputs power generation data.
    This model operates in time-series mode (wave_resource_model_choice = 1),
    accepting arrays of significant wave height and energy period at each timestep.
    """

    _time_step_bounds = (
        3600,
        3600,
    )  # (min, max) time step lengths (in seconds) compatible with this model
    _control_classifier = "flexible"

    def initialize(self):
        super().initialize()
        self.commodity = "electricity"
        self.commodity_rate_units = "kW"
        self.commodity_amount_units = "kW*h"

    def setup(self):
        super().setup()
        self.config = PySAMWavePerformanceConfig.from_dict(
            merge_shared_inputs(self.options["tech_config"]["model_inputs"], "performance"),
            additional_cls_name=self.__class__.__name__,
        )

        #### Wave Resource ####
        self.add_input(
            "significant_wave_height",
            val=0.0,
            shape=self.n_timesteps,
            units="m",
        )

        self.add_input(
            "energy_period",
            val=0.0,
            shape=self.n_timesteps,
            units="s",
        )

        #### Wave Device Parameters ####
        self.add_input(
            "num_devices",
            val=self.config.num_devices,
            units="unitless",
            desc="Number of wave devices in the system",
        )

        self.add_input(
            "device_rating",
            val=self.config.device_rating_kw,
            units="kW",
            desc="Rated power of the wave energy device",
        )

        if self.config.create_model_from == "default":
            self.system_model = MhkWave.default(self.config.config_name)
        elif self.config.create_model_from == "new":
            self.system_model = MhkWave.new()
            self.system_model.value("wave_power_matrix", self.config.wave_power_matrix)

        design_dict = self.config.create_input_dict()
        if bool(self.config.pysam_options):
            for group, group_parameters in self.config.pysam_options.items():
                if group in design_dict:
                    design_dict[group].update(group_parameters)
                else:
                    design_dict.update({group: group_parameters})
        self.system_model.assign(design_dict)

    def compute(self, inputs, outputs):
        # Set time-series resource mode
        self.system_model.MHKWave.wave_resource_model_choice = 1

        # Assign wave resource time series
        significant_wave_height = inputs["significant_wave_height"]
        energy_period = inputs["energy_period"]
        n = len(significant_wave_height)

        self.system_model.value("significant_wave_height", significant_wave_height)
        self.system_model.value("energy_period", energy_period)
        self.system_model.value("number_records", n)
        self.system_model.value("number_hours", n * (self.dt / 3600))

        # Generate timestamps for the time-series resource input
        timestamps = pd.date_range(
            start=f"{self.config.resource_year}-01-01", periods=n, freq=f"{int(self.dt)}s"
        )
        self.system_model.value("year", list(timestamps.year.astype(float)))
        self.system_model.value("month", list(timestamps.month.astype(float)))
        self.system_model.value("day", list(timestamps.day.astype(float)))
        self.system_model.value("hour", list(timestamps.hour.astype(float)))
        self.system_model.value("minute", list(timestamps.minute.astype(float)))

        # Set system capacity
        num_devices = inputs["num_devices"][0]
        device_rating = inputs["device_rating"][0]
        system_capacity_kw = num_devices * device_rating
        self.system_model.value("device_rated_power", device_rating)
        self.system_model.value("system_capacity", system_capacity_kw)
        self.system_model.value("number_devices", num_devices)

        # Run the model
        self.system_model.execute(0)

        outputs["electricity_out"] = self.system_model.Outputs.gen
        outputs["rated_electricity_production"] = system_capacity_kw

        outputs["total_electricity_produced"] = outputs["electricity_out"].sum() * (self.dt / 3600)

        outputs["annual_electricity_produced"] = self.system_model.Outputs.annual_energy
        outputs["capacity_factor"] = (
            self.system_model.Outputs.capacity_factor / 100
        )  # divide by 100 to make it unitless

        # Honor a system-level controller's set-point by curtailing
        # `electricity_out`. No-op when there is no system-level controller.
        self.apply_curtailment(outputs)
