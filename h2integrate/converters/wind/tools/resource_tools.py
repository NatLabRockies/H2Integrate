import numpy as np
import scipy
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

    # weight1 is the weight applied to the lower-bound height
    weight1 = np.abs(height_upper - hub_height)
    # weight2 is the weight applied to the upper-bound height
    weight2 = np.abs(height_lower - hub_height)

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


# def height_to_winspeed_func(height, a, b, c):
#     ws = a*np.log(b*height - c)
#     return ws


def height_to_winspeed_func(ur_zr_z, psi):
    ur, zr, z = ur_zr_z
    u = ur * (z / zr) ** psi
    return u


def estimate_wind_speed_with_curve_fit(
    wind_resource_data: dict,
    bounding_resource_heights: tuple[int] | list[int],
    hub_height: float | int,
    run_per_timestep: bool = False,
):
    """Estimate the wind resource data at the hub-height using a curve-fit.

    Args:
        wind_resource_data (dict): dictionary of wind resource data
        hub_height (float | int): wind turbine hub-height in meters.

    Returns:
        np.ndarray: wind resource data estimated at the hub-height
    """
    ws_dict = {k: v for k, v in wind_resource_data.items() if "wind_speed" in k}
    # ws_heights = np.array([int(ws_h.split("wind_speed_")[-1].strip("m")) for ws_h
    # in list(ws_dict.keys())])
    # ws_speeds = np.array([ws_dict[f"wind_speed_{int(height)}m"] for
    #  height in ws_heights])
    # n_timesteps = len(ws_dict[f"wind_speed_{int(ws_heights[0])}m"])

    ws_heights = np.array(bounding_resource_heights)
    np.array([ws_dict[f"wind_speed_{int(height)}m"] for height in ws_heights])
    n_timesteps = len(ws_dict[f"wind_speed_{int(ws_heights[0])}m"])

    # calc closest height
    ub_diff = np.abs(np.max(ws_heights) - hub_height)
    lb_diff = np.abs(np.min(ws_heights) - hub_height)

    if ub_diff >= lb_diff:
        # lower-bound is closer, use lower bound as reference and upper bound as input
        z_ref = np.min(ws_heights) * np.ones(n_timesteps)
        ws_ref = ws_dict[f"wind_speed_{int(np.min(ws_heights))}m"]
        z = np.max(ws_heights) * np.ones(n_timesteps)
        ws = ws_dict[f"wind_speed_{int(np.max(ws_heights))}m"]

    else:
        # upper bound is closer, use upper bound as reference and lower bound as input
        z_ref = np.max(ws_heights) * np.ones(n_timesteps)
        ws_ref = ws_dict[f"wind_speed_{int(np.max(ws_heights))}m"]
        z = np.min(ws_heights) * np.ones(n_timesteps)
        ws = ws_dict[f"wind_speed_{int(np.min(ws_heights))}m"]

    if not run_per_timestep:
        curve_coeff, curve_cov = scipy.optimize.curve_fit(
            height_to_winspeed_func,
            (ws_ref, z_ref, z),
            ws,
            p0=(1.0),
            # bounds = [np.floor(np.
            # min(ws_speeds[:,i])),np.ceil(np.max(ws_speeds[:,i]))]
        )
        ws_at_hubheight = height_to_winspeed_func(
            (ws_ref, z_ref, hub_height * np.ones(n_timesteps)), *curve_coeff
        )
        return ws_at_hubheight

    ws_at_hubheight = np.zeros(n_timesteps)
    for i in range(n_timesteps):
        curve_coeff, curve_cov = scipy.optimize.curve_fit(
            height_to_winspeed_func,
            (np.array(ws_ref[i]), np.array(z_ref[i]), np.array(z[i])),
            np.array(ws[i]),
            p0=(1.0),
        )
        ws_at_hubheight[i] = height_to_winspeed_func(
            (ws_ref[i], z_ref[i], hub_height), *curve_coeff
        )

    # ws_at_hubheight = np.zeros(n_timesteps)
    # for i in range(n_timesteps):
    #     curve_coeff, curve_cov = scipy.optimize.curve_fit(
    #             height_to_winspeed_func,
    #             (ws_heights,
    #             ws_speeds[:,i],
    #             p0=(1.0, 1.0, 1.0),
    #             # bounds = [np.floor(np.min(ws_speeds[:,i])),np.ceil(np.max(ws_speeds[:,i]))]
    #         )

    # ws_at_hubheight = height_to_winspeed_func((ws_ref,z_ref,hub_height*np.ones(n_timesteps)),
    # *curve_coeff)

    return ws_at_hubheight


# if __name__ == "__main__":
#     from h2integrate import ROOT_DIR
#     import openmdao.api as om
#     import matplotlib.pyplot as plt
#     from h2integrate.resource.wind.nrel_developer_wtk_api import WTKNRELDeveloperAPIWindResource

#     plant_config = {
#         "site": {
#             "latitude": 34.22,
#             "longitude": -102.75,
#             "resources": {
#                 "wind_resource": {
#                     "resource_model": "wind_toolkit_v2_api",
#                     "resource_parameters": {
#                         "latitude": 35.2018863,
#                         "longitude": -101.945027,
#                         "resource_year": 2012,  # 2013,
#                     },
#                 }
#             },
#         },
#         "plant": {
#             "plant_life": 30,
#             "simulation": {
#                 "dt": 3600,
#                 "n_timesteps": 8760,
#                 "start_time": "01/01/1900 00:30:00",
#                 "timezone": 0,
#             },
#         },
#     }

#     prob = om.Problem()
#     comp = WTKNRELDeveloperAPIWindResource(
#         plant_config=plant_config,
#         resource_config=plant_config["site"]["resources"]["wind_resource"]["resource_parameters"],
#         driver_config={},
#     )
#     prob.model.add_subsystem("resource", comp)
#     prob.setup()
#     prob.run_model()
#     wtk_data = prob.get_val("resource.wind_resource_data")

#     ws_est = wind_speed_adjustment_for_hubheight(wtk_data,120)

#     # fig, ax = plt.subplots(1,1)

#     # ws_vals0 = ws_df.iloc[0].values
#     # ws_vals_est0 = ws_est_df.iloc[0].values

#     # ax.scatter(ws_heights, ws_vals0, c='tab:blue', label='measured')
#     # ax.plot(ws_heights, ws_vals_est0, c='tab:red', label='estimated')


#     # ax.set_ylabel("wind_speed")
#     # ax.set_xlabel("height")


#     fig.savefig(ROOT_DIR.parent/"ws_vs_height.png",bbox_inches="tight")
