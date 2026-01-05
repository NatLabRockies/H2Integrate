from pathlib import Path

from attrs import field, define
from turbine_models.tools.library_tools import check_turbine_library_for_turbine
from turbine_models.tools.interface_tools import get_pysam_turbine_specs, get_floris_turbine_specs

from h2integrate import H2I_LIBRARY_DIR
from h2integrate.core.utilities import BaseConfig, get_path, write_readable_yaml


def export_turbine_to_pysam_format(
    turbine_name: str, output_folder: Path | str | None = None, output_filename: str | None = None
):
    """Make a turbine model file for PySAM.Windpower Turbine using data from the turbine-models
    library.

    Args:
        turbine_name (str): name of turbine in turbine-models library.
        output_folder (Path | str | None, optional): Output folder to save turbine model
            file to. If None, uses the H2I_LIBRARY_DIR. Defaults to None.
        output_filename (str | None, optional): Output filename for the turbine model file
            as. If None, filename is f"pysam_options_{turbine_name}.yaml". Defaults to None.

    Raises:
        ValueError: if turbine_name does match a turbine in the turbine-models library.

    Returns:
        Path: filepath to .yaml file formatted for PySAM.WindPower Turbine.
    """
    is_valid = check_turbine_library_for_turbine(turbine_name)
    if not is_valid:
        msg = (
            f"Turbine {turbine_name} was not found in the turbine-models library. "
            "For a list of available turbine names, run `print_turbine_name_list()` method "
            "available in `turbine_models.tools.library_tools`."
        )
        raise ValueError(msg)
    if output_folder is None:
        output_folder = H2I_LIBRARY_DIR
    else:
        output_folder = get_path(output_folder)

    if output_filename is None:
        output_filename = f"pysam_options_{turbine_name}.yaml"

    output_filepath = output_folder / output_filename

    turbine_specs = get_pysam_turbine_specs(turbine_name)

    pysam_options = {"Turbine": turbine_specs}

    write_readable_yaml(pysam_options, output_filepath)

    return output_filepath


@define
class FlorisTurbineDefaults(BaseConfig):
    """Config class to specify default turbine parameters that are required by FLORIS.

    Attributes:
        TSR (float | int): default turbine tip-speed-ratio. Defaults to 8.0
        ref_air_density (float | int): default air density for power-curve in kg/m**3.
            Defaults to 1.225.
        ref_tilt (float | int): default reference turbine shaft tilt angle in degrees.
            Defaults to 5.0
        cosine_loss_exponent_yaw (float | int): default cosine loss exponent for yaw.
            Defaults to 1.88
        cosine_loss_exponent_tilt (float | int): default cosine loss exponent for tilt.
            Defaults to 1.88
    """

    TSR: float | int = field(default=8.0)
    ref_air_density: float | int = field(default=1.225)
    ref_tilt: float | int = field(default=5.0)
    cosine_loss_exponent_yaw: float | int = field(default=1.88)
    cosine_loss_exponent_tilt: float | int = field(default=1.88)

    def power_thrust_defaults(self):
        d = self.as_dict()
        power_thrust_variables = {k: v for k, v in d.items() if k != "TSR"}
        return power_thrust_variables


def export_turbine_to_floris_format(
    turbine_name: str,
    output_folder: Path | str | None = None,
    output_filename: str | None = None,
    floris_defaults: dict | FlorisTurbineDefaults = FlorisTurbineDefaults(),
):
    """Make a turbine model file for FLORIS using data from the turbine-models library.

    Args:
        turbine_name (str): name of turbine in turbine-models library.
        output_folder (Path | str | None, optional): Output folder to save turbine model
            file to. If None, uses the H2I_LIBRARY_DIR. Defaults to None.
        output_filename (str | None, optional): Output filename for the turbine model file
            as. If None, filename is f"floris_turbine_{turbine_name}.yaml". Defaults to None.
        floris_defaults (dict | FlorisTurbineDefaults, optional): Default values to use to populate
            missing parameters from the turbine-models library that are required for the
            FLORIS turbine model. Defaults to FlorisTurbineDefaults().

    Raises:
        ValueError: if turbine_name does match a turbine in the turbine-models library.

    Returns:
        Path: filepath to .yaml file formatted for FLORIS.
    """
    if isinstance(floris_defaults, dict):
        floris_defaults = FlorisTurbineDefaults.from_dict(floris_defaults)

    is_valid = check_turbine_library_for_turbine(turbine_name)
    if not is_valid:
        msg = (
            f"Turbine {turbine_name} was not found in the turbine-models library. "
            "For a list of available turbine names, run `print_turbine_name_list()` method "
            "available in `turbine_models.tools.library_tools`."
        )
        raise ValueError(msg)
    if output_folder is None:
        output_folder = H2I_LIBRARY_DIR
    else:
        output_folder = get_path(output_folder)

    if output_filename is None:
        output_filename = f"floris_turbine_{turbine_name}.yaml"

    output_filepath = output_folder / output_filename

    turbine_specs = get_floris_turbine_specs(turbine_name)

    # add in default values
    if turbine_specs.get("TSR", None) is None:
        turbine_specs.update({"TSR": floris_defaults.TSR})

    power_thrust_defaults = floris_defaults.power_thrust_defaults()
    for var, default_val in power_thrust_defaults.items():
        if turbine_specs["power_thrust_table"].get(var, None) is None:
            turbine_specs["power_thrust_table"].update({var: default_val})

    write_readable_yaml(turbine_specs, output_filepath)

    return output_filepath
