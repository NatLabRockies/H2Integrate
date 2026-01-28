"""
Quick-and-dirty model for iron transport
"""

from pathlib import Path

import pandas as pd
import geopy.distance

from h2integrate.converters.iron.load_top_down_coeffs import load_top_down_coeffs


CD = Path(__file__).parent

ship_coords = pd.read_csv(CD / "shipping_coords.csv", index_col=0)


def calc_water_ship_cost(year):
    """Calculates waterborne shipping costs for iron transport.

    This function retrieves barge shipping cost coefficients for a given year
    and computes the shipping cost per tonne for various destinations. It also
    constructs route coordinates for each shipping path.

    Args:
        year (int): The year for which shipping costs are calculated.

    Returns:
        dict: A dictionary where keys are destination names and values contain:
            - dist_km (float): Distance in kilometers.
            - waypts (list): List of waypoints along the route.
            - coords (list of tuples): Latitude and longitude coordinates for each waypoint.
            - ship_cost_tonne (float): Shipping cost per tonne for the given year.
    """
    coeff_dict = load_top_down_coeffs(["Barge Shipping Cost"])
    year_idx = list(coeff_dict["years"]).index(year)
    ship_cost_dol_tonne_mi = coeff_dict["Barge Shipping Cost"]["values"][year_idx]
    ship_cost_dol_tonne_km = ship_cost_dol_tonne_mi / 1.60934

    ship_dict = {}

    ship_dict["Cleveland"] = {
        "dist_km": 1341.7141480490504,
        "waypts": [
            "Duluth",
            "Keweenaw",
            "Sault St Marie",
            "De Tour",
            "Lake Huron",
            "Port Huron",
            "Erie",
            "Cleveland",
        ],
    }

    ship_dict["Buffalo"] = {
        "dist_km": 1621.9112211308186,
        "waypts": [
            "Duluth",
            "Keweenaw",
            "Sault St Marie",
            "De Tour",
            "Lake Huron",
            "Port Huron",
            "Erie",
            "Cleveland",
            "Buffalo",
        ],
    }

    ship_dict["Chicago"] = {
        "dist_km": 1414.8120870922066,
        "waypts": [
            "Duluth",
            "Keweenaw",
            "Sault St Marie",
            "De Tour",
            "Mackinaw",
            "Manistique",
            "Chicago",
        ],
    }

    for key, rte_dict in ship_dict.items():
        rte = rte_dict["waypts"]
        rte_list = []
        for name in rte:
            coord = ship_coords.loc[name]
            lat = coord["Lat"]
            lon = coord["Lon"]
            rte_list.append((lat, lon))
        rte_dict["coords"] = rte_list
        ship_cost_tonne = ship_cost_dol_tonne_km * rte_dict["dist_km"]
        rte_dict["ship_cost_tonne"] = ship_cost_tonne
        ship_dict[key] = rte_dict

    return ship_dict


def calc_iron_ship_cost(iron_config):
    """Computes total iron transport cost, including land and water shipping.

    This function calculates the minimum cost of shipping iron from available
    shipping sites to the final destination, considering both water and land
    transportation costs.

    Args:
        iron_config (dict): Configuration dictionary containing:
            - project_parameters (dict): Includes `cost_year` (int), the year for cost estimation.
            - iron (dict): Contains `site` (dict) with `lat`
                and `lon` keys for destination coordinates.

    Returns:
        tuple:
            - iron_transport_cost_tonne (float): Minimum transport cost per tonne.
            - ore_profit_pct (float): Estimated ore profit margin for the given year.
    """
    year = iron_config["project_parameters"]["cost_year"]

    ship_dict = calc_water_ship_cost(year)

    coeff_dict = load_top_down_coeffs(["Land Shipping Cost", "Ore Profit Margin"])
    year_idx = list(coeff_dict["years"]).index(year)
    ship_cost_dol_tonne_mi = coeff_dict["Land Shipping Cost"]["values"][year_idx]
    ship_cost_dol_tonne_km = ship_cost_dol_tonne_mi / 1.60934

    iron_site = iron_config["iron"]["site"]

    # Find the cheapest site to ship from
    ship_sites = ["Duluth", "Chicago", "Cleveland", "Buffalo"]
    ship_costs_dol_tonne = []
    for ship_site in ship_sites:
        start_coords = ship_coords.loc[ship_site].values
        iron_win_coords = [iron_site["lat"], iron_site["lon"]]
        dist_km = geopy.distance.distance(start_coords, iron_win_coords).km
        ship_cost_dol_tonne = 0
        if ship_site != "Duluth":
            ship_cost_dol_tonne += ship_dict[ship_site]["ship_cost_tonne"]
        ship_cost_dol_tonne += dist_km * ship_cost_dol_tonne_km
        ship_costs_dol_tonne.append(ship_cost_dol_tonne)

    iron_transport_cost_tonne = min(ship_costs_dol_tonne)

    ore_profit_pct = coeff_dict["Ore Profit Margin"]["values"][year_idx]

    return iron_transport_cost_tonne, ore_profit_pct
