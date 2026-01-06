import copy

import numpy as np
import pandas as pd
import openmdao.api as om
from attrs import field, define
from geopy import distance

from h2integrate import ROOT_DIR
from h2integrate.core.utilities import BaseConfig, merge_shared_inputs
from h2integrate.core.validators import contains, range_val
from h2integrate.core.model_baseclasses import CostModelBaseClass
from h2integrate.converters.iron.load_top_down_coeffs import load_top_down_coeffs


@define(kw_only=True)
class IronTransportPerformanceConfig(BaseConfig):
    find_closest_ship_site: bool = field()
    shipment_site: str = field(
        converter=(str.lower, str.capitalize),
        validator=contains(["None", "Duluth", "Chicago", "Cleveland", "Buffalo"]),
    )

    #
    def __attrs_post_init__(self):
        if self.find_closest_ship_site and self.shipment_site != "None":
            msg = "Please set shipment_site to 'None' if find_closest_ship_site is True."
            raise ValueError(msg)


class IronTransportPerformanceComponent(om.ExplicitComponent):
    def initialize(self):
        self.options.declare("driver_config", types=dict)
        self.options.declare("plant_config", types=dict)
        self.options.declare("tech_config", types=dict)

    def setup(self):
        self.config = IronTransportPerformanceConfig.from_dict(
            merge_shared_inputs(self.options["tech_config"]["model_inputs"], "performance"),
            strict=False,
        )
        self.add_output("land_transport_distance", val=0.0, units="km")
        self.add_output("water_transport_distance", val=0.0, units="km")
        self.add_output("total_transport_distance", val=0.0, units="km")

    def calculate_water_distance(self, waypoints, shipping_sites):
        water_transport_distance = 0
        for ii, waypt in enumerate(waypoints):
            if ii == 0:
                starting_lat = shipping_sites.loc[waypoints[0]]["Lat"]
                starting_lon = shipping_sites.loc[waypoints[0]]["Lon"]
                starting_location = (starting_lat, starting_lon)
                continue

            ending_lat = shipping_sites.loc[waypt]["Lat"]
            ending_lon = shipping_sites.loc[waypt]["Lon"]
            ending_location = (ending_lat, ending_lon)

            waypoint_distance = distance.geodesic(
                starting_location, ending_location, ellipsoid="WGS-84"
            ).km
            water_transport_distance += waypoint_distance

            starting_lat = shipping_sites.loc[waypt]["Lat"]
            starting_lon = shipping_sites.loc[waypt]["Lon"]
            starting_location = (starting_lat, starting_lon)

        return water_transport_distance

    def calculate_land_distance(self, ship_site, starting_location, shipping_sites):
        ending_lat = shipping_sites.loc[ship_site]["Lat"]
        ending_lon = shipping_sites.loc[ship_site]["Lon"]
        ending_location = (ending_lat, ending_lon)
        land_transport_distance = distance.geodesic(
            starting_location, ending_location, ellipsoid="WGS-84"
        ).km
        return land_transport_distance

    def compute(self, inputs, outputs):
        lat = self.options["plant_config"].get("site", {}).get("latitude")
        lon = self.options["plant_config"].get("site", {}).get("longitude")
        site_location = (lat, lon)
        shipping_coord_fpath = (
            ROOT_DIR / "converters" / "iron" / "martin_transport" / "shipping_coords.csv"
        )
        shipping_locations = pd.read_csv(shipping_coord_fpath, index_col="Unnamed: 0")

        shipping_waypoints = {
            "Duluth": ["Duluth"],
            "Chicago": [
                "Duluth",
                "Keweenaw",
                "Sault St Marie",
                "De Tour",
                "Mackinaw",
                "Manistique",
                "Chicago",
            ],
            "Cleveland": [
                "Duluth",
                "Keweenaw",
                "Sault St Marie",
                "De Tour",
                "Lake Huron",
                "Port Huron",
                "Erie",
                "Cleveland",
            ],
            "Buffalo": [
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
        if self.config.find_closest_ship_site:
            min_distance = 1e20
            land_distance_for_min = 0
            water_distance_for_min = 0
            for ship_site, waypoints in shipping_waypoints.items():
                land_distance_km = self.calculate_land_distance(
                    ship_site, site_location, shipping_locations
                )
                water_distance_km = self.calculate_water_distance(waypoints, shipping_locations)

                transport_distance = land_distance_km + water_distance_km
                if transport_distance < min_distance:
                    land_distance_for_min = self.calculate_land_distance(
                        ship_site, site_location, shipping_locations
                    )
                    water_distance_for_min = self.calculate_water_distance(
                        waypoints, shipping_locations
                    )
                min_distance = np.min([min_distance, transport_distance])

            outputs["total_transport_distance"] = min_distance
            outputs["land_transport_distance"] = land_distance_for_min
            outputs["water_transport_distance"] = water_distance_for_min

        else:
            land_distance_km = self.calculate_land_distance(
                self.config.shipment_site, site_location, shipping_locations
            )
            water_distance_km = self.calculate_water_distance(
                shipping_waypoints[self.config.shipment_site], shipping_locations
            )
            transport_distance = land_distance_km + water_distance_km
            outputs["total_transport_distance"] = transport_distance
            outputs["land_transport_distance"] = land_distance_km
            outputs["water_transport_distance"] = water_distance_km


@define(kw_only=True)
class IronTransportCostConfig(BaseConfig):
    transport_year: int = field(converter=int, validator=range_val(2022, 2065))
    cost_year: int = field(converter=int, validator=range_val(2010, 2024))


class IronTransportCostComponent(CostModelBaseClass):
    def initialize(self):
        self.options.declare("driver_config", types=dict)
        self.options.declare("plant_config", types=dict)
        self.options.declare("tech_config", types=dict)

    def setup(self):
        n_timesteps = self.options["plant_config"]["plant"]["simulation"]["n_timesteps"]

        target_dollar_year = self.options["plant_config"]["finance_parameters"][
            "cost_adjustment_parameters"
        ]["target_dollar_year"]

        config_dict = merge_shared_inputs(
            copy.deepcopy(self.options["tech_config"]["model_inputs"]), "cost"
        )
        config_dict.update({"cost_year": target_dollar_year})

        self.config = IronTransportCostConfig.from_dict(
            config_dict,
            strict=True,
        )
        super().setup()

        self.add_input("land_transport_distance", val=0.0, units="mi")
        self.add_input("water_transport_distance", val=0.0, units="mi")
        self.add_input("total_transport_distance", val=0.0, units="mi")
        self.add_input("iron_ore_in", val=0.0, shape=n_timesteps, units="t/h")

        self.add_output("iron_ore_out", val=0.0, shape=n_timesteps, units="t/h")
        self.add_output("iron_transport_cost", val=0.0, units="USD/t")
        self.add_output("ore_profit_margin", val=0.0, units="USD/t")

    def compute(self, inputs, outputs, discrete_inputs, discrete_outputs):
        water_coeff_dict = load_top_down_coeffs(
            ["Barge Shipping Cost"], cost_year=self.config.cost_year
        )
        water_year_idx = list(water_coeff_dict["years"]).index(self.config.transport_year)
        water_ship_cost_dol_tonne_mi = water_coeff_dict["Barge Shipping Cost"]["values"][
            water_year_idx
        ]

        water_ship_cost_dol_per_ton = (
            water_ship_cost_dol_tonne_mi * inputs["water_transport_distance"]
        )
        water_ship_cost_USD = np.sum(inputs["iron_ore_in"]) * water_ship_cost_dol_per_ton

        land_coeff_dict = load_top_down_coeffs(
            ["Land Shipping Cost"], cost_year=self.config.cost_year
        )
        land_year_idx = list(land_coeff_dict["years"]).index(self.config.transport_year)
        land_ship_cost_dol_tonne_mi = land_coeff_dict["Land Shipping Cost"]["values"][land_year_idx]

        land_ship_cost_dol_per_ton = land_ship_cost_dol_tonne_mi * inputs["land_transport_distance"]
        land_ship_cost_USD = np.sum(inputs["iron_ore_in"]) * land_ship_cost_dol_per_ton

        total_shipment_cost = water_ship_cost_USD + land_ship_cost_USD

        profit_margin_coeffs = load_top_down_coeffs(["Ore Profit Margin"])
        pm_year_idx = list(profit_margin_coeffs["years"]).index(self.config.transport_year)
        outputs["ore_profit_margin"] = profit_margin_coeffs["Ore Profit Margin"]["values"][
            pm_year_idx
        ]

        outputs["iron_ore_out"] = inputs["iron_ore_in"]  # assume lossless
        outputs["iron_transport_cost"] = total_shipment_cost / np.sum(inputs["iron_ore_in"])
        outputs["VarOpEx"] = total_shipment_cost
