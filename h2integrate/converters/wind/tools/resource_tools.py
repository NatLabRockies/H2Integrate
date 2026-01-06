import numpy as np
from scipy.constants import R, g, convert_temperature


RHO_0 = 1.225  # Air density at sea level (kg/m3)
T_REF = 20  # Standard air temperature (Celsius)
MOLAR_MASS_AIR = 28.96  # Molar mass of air (g/mol)
LAPSE_RATE = 0.0065  # Temperature lapse rate (K/m) for 0-11000m above sea level


def calculate_air_density(elevation_m: float) -> float:
    """
    Calculate air density based on site elevation using the Barometric formula.

    This function is based on Equation 1 from: https://en.wikipedia.org/wiki/Barometric_formula#Density_equations
    Imported constants are:

        - g: acceleration due to gravity (m/s2)
        - R: universal gas constant (J/mol-K)

    Args:
        elevation_m (float): Elevation of site in meters

    Returns:
        float: Air density in kg/m^3 at elevation of site
    """

    # Reference elevation at sea level (m)
    elevation_sea_level = 0.0

    # Convert temperature to Kelvin
    T_ref_K = convert_temperature([T_REF], "C", "K")[0]

    # Exponent value used in equation below
    e = g * (MOLAR_MASS_AIR / 1e3) / (R * LAPSE_RATE)

    # Calculate air density at site elevation
    rho = RHO_0 * ((T_ref_K - ((elevation_m - elevation_sea_level) * LAPSE_RATE)) / T_ref_K) ** (
        e - 1
    )
    return rho


def weighted_average_wind_data_for_hubheight(
    wind_resource_data: dict,
    bounding_resource_heights: tuple[int] | list[int],
    hub_height: float | int,
    wind_resource_spec: str,
):
    """Compute the weighted average of wind resource data at two resource heights.

    Args:
        wind_resource_data (dict): dictionary of wind resource data
        bounding_resource_heights (tuple[int] | list[int]): resource heights that bound the
            hub-height, formatted as [lower_resource_height, upper_resource_height]
        hub_height (float | int): wind turbine hub-height in meters.
        wind_resource_spec (str): wind resource data key that is unique for
            each hub-height. Such as `'wind_speed'` or `'wind_direction'`

    Raises:
        ValueError: if f'{wind_resource_spec}_{lower_resource_height}m' or
            f'{wind_resource_spec}_{upper_resource_height}m' are not found in `wind_resource_data`

    Returns:
        np.ndarray: wind resource data averaged between the two bounding heights.
    """
    height_lower, height_upper = bounding_resource_heights

    has_lowerbound = f"{wind_resource_spec}_{height_lower}m" in wind_resource_data
    has_upperbound = f"{wind_resource_spec}_{height_upper}m" in wind_resource_data
    if not has_lowerbound or not has_upperbound:
        msg = (
            f"Wind resource data for {wind_resource_spec} is missing either "
            f"{height_lower}m or {height_upper}m"
        )
        raise ValueError(msg)

    weight1 = np.abs(height_lower - hub_height)
    weight2 = np.abs(height_upper - hub_height)

    weighted_wind_resource = (
        (weight1 * wind_resource_data[f"{wind_resource_spec}_{height_lower}m"])
        + (weight2 * wind_resource_data[f"{wind_resource_spec}_{height_upper}m"])
    ) / (weight1 + weight2)

    return weighted_wind_resource


def average_wind_data_for_hubheight(
    wind_resource_data: dict,
    bounding_resource_heights: tuple[int] | list[int],
    wind_resource_spec: str,
):
    """Compute the average of wind resource data at two resource heights.

    Args:
        wind_resource_data (dict): dictionary of wind resource data
        bounding_resource_heights (tuple[int] | list[int]): resource heights that bound the
            hub-height, formatted as [lower_resource_height, upper_resource_height]
        wind_resource_spec (str): wind resource data key that is unique for
            each hub-height. Such as `'wind_speed'` or `'wind_direction'`

    Raises:
        ValueError: if f'{wind_resource_spec}_{lower_resource_height}m' or
            f'{wind_resource_spec}_{upper_resource_height}m' are not found in `wind_resource_data`

    Returns:
        np.ndarray: wind resource data averaged between the two bounding heights.
    """
    height_lower, height_upper = bounding_resource_heights

    has_lowerbound = f"{wind_resource_spec}_{height_lower}m" in wind_resource_data
    has_upperbound = f"{wind_resource_spec}_{height_upper}m" in wind_resource_data
    if not has_lowerbound or not has_upperbound:
        msg = (
            f"Wind resource data for {wind_resource_spec} is missing either "
            f"{height_lower}m or {height_upper}m"
        )
        raise ValueError(msg)

    combined_data = np.stack(
        [
            wind_resource_data[f"{wind_resource_spec}_{height_lower}m"],
            wind_resource_data[f"{wind_resource_spec}_{height_upper}m"],
        ]
    )
    averaged_data = combined_data.mean(axis=0)

    return averaged_data
