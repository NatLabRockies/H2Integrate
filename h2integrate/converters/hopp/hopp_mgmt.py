import copy

import numpy as np
from hopp.simulation.hopp_interface import HoppInterface
from hopp.simulation.technologies.sites import SiteInfo


def recreate_hopp_config_for_optimization(
    hopp_config: dict,
    pv_rating_kw=None,
    wind_turbine_rating_kw=None,
    battery_rating_kw=None,
    battery_rating_kwh=None,
) -> dict:
    """
    Adjusts the HOPP configuration dictionary for optimization based on system ratings.

    This function modifies the HOPP configuration (``hopp_config``) to reflect the desired
    ratings for photovoltaic (PV), wind turbine, and battery systems. It ensures that the
    configuration adheres to specific tolerances and removes technologies if their ratings
    fall below certain thresholds. It also sets a range where a lower rating than given will
    be used so optimization algorithms can adjust ratings, pushing them into feasible ranges
    or below removal thresholds.

    Args:
        hopp_config (dict): The original HOPP configuration dictionary containing site,
            technology, and cost information.
        pv_rating_kw (float, optional): Desired system capacity for photovoltaic (PV) in
            kilowatts. If None, PV configuration remains unchanged in the config dictionary.
        wind_turbine_rating_kw (float, optional): Desired turbine rating for wind in kilowatts.
            If None, wind configuration remains unchanged in the config dictionary.
        battery_rating_kw (float, optional): Desired system capacity for battery in kilowatts.
            If None, battery configuration remains unchanged in the config dictionary.
        battery_rating_kwh (float, optional): Desired energy capacity for battery in kilowatt-
            hours. If None, battery configuration remains unchanged in the config dictionary.

    Returns:
        dict: A modified copy of the HOPP configuration dictionary with updated system ratings
        and technology configurations based on the function input values.

    Notes:
        - Technologies are removed from the configuration if their ratings fall below the
            ``smooth_tol`` threshold.
        - Ratings are interpolated between ``smooth_tol`` and ``rating_tol`` for values within
            this range.
        - Cost information related to removed technologies is also removed from the configuration.
        - Battery operation and maintenance (O&M) costs are recalculated based on the provided
          ratings.

    Example:
        ::

            updated_config = recreate_hopp_config_for_optimization(
                hopp_config=original_config,
                pv_rating_kw=500,
                wind_turbine_rating_kw=1000,
                battery_rating_kw=200,
                battery_rating_kwh=400,
            )

    Raises:
        KeyError: If required keys are missing in the `hopp_config` dictionary.
        TypeError: If the input ratings are not numeric values.
    """

    hopp_config_internal = copy.deepcopy(hopp_config)
    rating_tol = 50.0
    min_tol = 50.0
    smooth_tol = 1.0

    if wind_turbine_rating_kw is not None and "wind" in hopp_config_internal["technologies"]:
        if wind_turbine_rating_kw <= min_tol:
            hopp_config_internal["technologies"]["wind"]["turbine_rating_kw"] = min_tol
        elif wind_turbine_rating_kw <= rating_tol:
            if wind_turbine_rating_kw <= smooth_tol:
                hopp_config_internal["technologies"].pop("wind")
                hopp_config_internal["site"]["wind"] = False
                hopp_config_internal["config"]["cost_info"].pop("wind_installed_cost_mw")
                hopp_config_internal["config"]["cost_info"].pop("wind_om_per_kw")
                hopp_config_internal["config"]["simulation_options"]["wind"]["skip_financial"] = (
                    True
                )
            else:
                wind_turbine_rating_kw = np.interp(
                    wind_turbine_rating_kw, [smooth_tol, rating_tol], [smooth_tol, 0.1 * rating_tol]
                )
        else:
            hopp_config_internal["technologies"]["wind"]["turbine_rating_kw"] = (
                wind_turbine_rating_kw
            )

    if pv_rating_kw is not None:
        if pv_rating_kw <= min_tol:
            hopp_config_internal["technologies"]["pv"]["system_capacity_kw"] = min_tol
        elif pv_rating_kw <= rating_tol:
            if pv_rating_kw <= smooth_tol:
                hopp_config_internal["technologies"].pop("pv")
                hopp_config_internal["site"]["solar"] = False
                hopp_config_internal["site"].pop("solar_resource_file")
                hopp_config_internal["config"]["cost_info"].pop("solar_installed_cost_mw")
                hopp_config_internal["config"]["cost_info"].pop("pv_om_per_kw")
            else:
                pv_rating_kw = np.interp(
                    pv_rating_kw, [smooth_tol, rating_tol], [smooth_tol, 0.1 * rating_tol]
                )
        else:
            hopp_config_internal["technologies"]["pv"]["system_capacity_kw"] = pv_rating_kw

    if battery_rating_kw is not None:
        if battery_rating_kw <= rating_tol:
            if battery_rating_kw <= smooth_tol:
                hopp_config_internal["technologies"].pop("battery")
                hopp_config_internal["config"].pop("dispatch_options")
                hopp_config_internal["config"]["cost_info"].pop("storage_installed_cost_mwh")
                hopp_config_internal["config"]["cost_info"].pop("storage_installed_cost_mw")
                hopp_config_internal["config"]["cost_info"].pop("battery_om_per_kw")
            else:
                battery_rating_kw = np.interp(
                    battery_rating_kw, [smooth_tol, rating_tol], [smooth_tol, 0.1 * rating_tol]
                )
        else:
            if (
                hopp_config_internal["config"]["cost_info"]
                and "battery_om_per_kwh" in hopp_config_internal["config"]["cost_info"]
            ):
                batt_om_per_kwh = hopp_config_internal["config"]["cost_info"]["battery_om_per_kwh"]
                batt_om_per_kw = hopp_config_internal["config"]["cost_info"]["battery_om_per_kw"]
                total_batt_om_per_kw = (
                    battery_rating_kw * batt_om_per_kw + battery_rating_kwh * batt_om_per_kwh
                ) / battery_rating_kw
                hopp_config_internal["config"]["cost_info"]["battery_om_per_kw"] = (
                    total_batt_om_per_kw
                )

            hopp_config_internal["technologies"]["battery"]["system_capacity_kw"] = (
                battery_rating_kw
            )
        if (
            hopp_config_internal["config"]["cost_info"]
            and "battery_om_per_kwh" in hopp_config_internal["config"]["cost_info"]
        ):
            hopp_config_internal["config"]["cost_info"].pop("battery_om_per_kwh")
    if battery_rating_kwh is not None and "battery" in hopp_config_internal["technologies"]:
        if battery_rating_kwh <= rating_tol:
            if battery_rating_kwh <= smooth_tol:
                hopp_config_internal["technologies"].pop("battery")
                hopp_config_internal["config"].pop("dispatch_options")
                hopp_config_internal["config"]["cost_info"].pop("storage_installed_cost_mwh")
                hopp_config_internal["config"]["cost_info"].pop("storage_installed_cost_mw")
                hopp_config_internal["config"]["cost_info"].pop("battery_om_per_kw")
            else:
                battery_rating_kwh = np.interp(
                    battery_rating_kwh, [smooth_tol, rating_tol], [smooth_tol, 0.1 * rating_tol]
                )
        else:
            hopp_config_internal["technologies"]["battery"]["system_capacity_kwh"] = (
                battery_rating_kwh
            )

    return hopp_config_internal


# Function to set up the HOPP model
def setup_hopp(
    hopp_config,
    pv_rating_kw=None,
    wind_turbine_rating_kw=None,
    battery_rating_kw=None,
    battery_rating_kwh=None,
    electrolyzer_rating=None,
    n_timesteps=8760,
):
    # overwrite individual fin_model values with cost_info values
    hopp_config_internal = copy.deepcopy(hopp_config)

    # TODO: improve this if logic to correctly account for if the user
    # defines a desired schedule or uses the electrolyzer rating as the desired schedule
    if "battery" in hopp_config_internal["technologies"].keys() and (
        "desired_schedule" not in hopp_config_internal["site"].keys()
        or hopp_config_internal["site"]["desired_schedule"] == []
    ):
        hopp_config_internal["site"]["desired_schedule"] = [10.0] * n_timesteps

    if electrolyzer_rating is not None:
        hopp_config_internal["site"]["desired_schedule"] = [electrolyzer_rating] * n_timesteps

    hopp_site = SiteInfo(**hopp_config_internal["site"])

    # setup hopp interface
    if np.any([pv_rating_kw, wind_turbine_rating_kw, battery_rating_kw, battery_rating_kwh]):
        hopp_config_internal = recreate_hopp_config_for_optimization(
            hopp_config=hopp_config_internal,
            wind_turbine_rating_kw=wind_turbine_rating_kw,
            pv_rating_kw=pv_rating_kw,
            battery_rating_kw=battery_rating_kw,
            battery_rating_kwh=battery_rating_kwh,
        )
    else:
        hopp_config_internal = copy.deepcopy(hopp_config)

    if "wave" in hopp_config_internal["technologies"].keys():
        wave_cost_dict = hopp_config_internal["technologies"]["wave"].pop("cost_inputs")

    if "battery" in hopp_config_internal["technologies"].keys():
        hopp_config_internal["site"].update({"desired_schedule": hopp_site.desired_schedule})

    hi = HoppInterface(hopp_config_internal)
    hi.system.site = hopp_site

    if "wave" in hi.system.technologies.keys():
        hi.system.wave.create_mhk_cost_calculator(wave_cost_dict)

    return hi


# Function to run hopp from provided inputs from setup_hopp()
def run_hopp(hi, project_lifetime, verbose=True, n_timesteps=8760):
    hi.simulate(project_life=project_lifetime)

    capex = 0.0
    opex = 0.0
    try:
        solar_capex = hi.system.pv.total_installed_cost
        solar_opex = hi.system.pv.om_total_expense[0]
        capex += solar_capex
        opex += solar_opex
    except AttributeError:
        pass

    try:
        wind_capex = hi.system.wind.total_installed_cost
        wind_opex = hi.system.wind.om_total_expense[0]
        capex += wind_capex
        opex += wind_opex
    except AttributeError:
        pass

    try:
        battery_capex = hi.system.battery.total_installed_cost
        battery_opex = hi.system.battery.om_total_expense[0]
        capex += battery_capex
        opex += battery_opex
    except AttributeError:
        pass

    grid_outputs = hi.system.grid._system_model.Outputs
    # store results for later use
    hopp_results = {
        "hopp_interface": hi,
        "hybrid_plant": hi.system,
        "combined_hybrid_power_production_hopp": grid_outputs.system_pre_interconnect_kwac[
            0:n_timesteps
        ],
        "combined_hybrid_curtailment_hopp": hi.system.grid.generation_curtailed,
        "curtailment_percent": hi.system.grid.curtailment_percent,
        "percent_load_missed": hi.system.grid.missed_load_percentage,
        "energy_shortfall_hopp": hi.system.grid.missed_load,
        "annual_energies": hi.system.annual_energies,
        "hybrid_npv": hi.system.net_present_values.hybrid,
        "npvs": hi.system.net_present_values,
        "lcoe": hi.system.lcoe_real,
        "lcoe_nom": hi.system.lcoe_nom,
        "capex": capex,
        "opex": opex,
    }
    if verbose:
        print("\nHOPP Results")
        print("Hybrid Annual Energy: ", hopp_results["annual_energies"])
        print("Capacity factors: ", hi.system.capacity_factors)
        print("Real LCOE from HOPP: ", hi.system.lcoe_real)

    return hopp_results
