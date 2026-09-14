"""
Calculates transportation of iron ore pellets from MN/MI iron range to iron plants.
Considers both barge transport through the Great Lakes corridor and road/rail transport.
"""

import copy

import numpy as np
import pandas as pd
import openmdao.api as om
from attrs import field, define, validators
from geopy import distance

from h2integrate.core.utilities import BaseConfig, merge_shared_inputs
from h2integrate.core.model_baseclasses import CostModelBaseClass


@define(kw_only=True)
class IronTransportPerformanceConfig(BaseConfig):
    """Configuration class for IronTransportPerformanceComponent.

    Args:
        find_closest_ship_site (bool): Whether to find the closest shipping site automatically.
        shipment_site (str): The specific shipping site to use if not finding the closest one.
            Allowed sites are "None", "Duluth", "Chicago", "Cleveland", and "Buffalo". Defaults
            to "None".
        land_circuity_ratio (float): Ratio of land distance to geodesic distance. Defaults to
            1.68, which is an estimate for rail. See :doc:`/technology_models/iron_transport`
            for more info.

    Raises:
        ValueError: Raised if shipment_site is not set to "None" while find_closest_ship_site
            is True.
    """

    find_closest_ship_site: bool = field()
    shipment_site: str = field(
        converter=(str.lower, str.capitalize),
        validator=validators.in_(["None", "Duluth", "Chicago", "Cleveland", "Buffalo"]),
    )
    land_circuity_ratio: float = field(default=1.68)  # ratio of land distance to geodesic distance

    #
    def __attrs_post_init__(self):
        if self.find_closest_ship_site and self.shipment_site != "None":
            msg = "Please set shipment_site to 'None' if find_closest_ship_site is True."
            raise ValueError(msg)


class IronTransportPerformanceComponent(om.ExplicitComponent):
    """Component to calculate iron ore pellet transportation distances considering both
    land and water routes.
    """

    _time_step_bounds = (
        3600,
        3600,
    )  # (min, max) time step lengths (in seconds) compatible with this model

    def initialize(self):
        self.options.declare("driver_config", types=dict)
        self.options.declare("plant_config", types=dict)
        self.options.declare("tech_config", types=dict)

    def setup(self):
        self.config = IronTransportPerformanceConfig.from_dict(
            merge_shared_inputs(self.options["tech_config"]["model_inputs"], "performance"),
            strict=True,
            additional_cls_name=self.__class__.__name__,
        )

        # Look up origin and destination from plant_config
        self.add_input("origin_latitude", shape=1, require_connection=True, units="deg")
        self.add_input("origin_longitude", shape=1, require_connection=True, units="deg")
        self.add_input("destination_latitude", shape=1, require_connection=True, units="deg")
        self.add_input("destination_longitude", shape=1, require_connection=True, units="deg")

        self.add_output("land_transport_distance_overland", val=0.0, units="km")
        self.add_output("land_transport_distance_great_lakes", val=0.0, units="km")
        self.add_output("water_transport_distance_great_lakes", val=0.0, units="km")

    def calculate_water_distance(self, waypoints, shipping_sites):
        """Calculates the distance via the great lakes to transport iron ore pellets.

        Args:
            waypoints (list): List of waypoint identifiers representing the water route.
            shipping_sites (pandas.DataFrame): DataFrame containing the latitude and longitude
                of shipping sites.

        Returns:
            float: Total water transport distance in kilometers.

        Note:
            The function uses geopy.distance.geodesic() and assumes WGS-84 / EPSG:4326 coordinates.
        """
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

    def calculate_land_distance(self, starting_location, ending_location):
        """calculates the distance via land to transport iron ore pellets.

        Args:
            starting_location (tuple): Tuple containing the latitude and longitude of the
                starting location.
            ending_location (tuple): Tuple containing the latitude and longitude of the
                ending location.

        Returns:
            float: Total land transport distance in kilometers, adjusted for circuity.

        Note:
            The function uses geopy.distance.geodesic() and assumes WGS-84 / EPSG:4326 coordinates.
        """
        land_transport_distance = distance.geodesic(
            starting_location, ending_location, ellipsoid="WGS-84"
        ).km

        # Apply circuity ratio to account for non-straight-line travel on land
        land_transport_distance *= self.config.land_circuity_ratio

        return land_transport_distance

    def compute(self, inputs, outputs):
        """Computes the land and water transport distances for iron ore pellets based on
        the provided inputs. The distances are calculated for both overland and
        Great Lakes shipping routes.
        """
        # Parse in the origin and destination coordinates
        orig_lat = inputs["origin_latitude"][0]
        orig_lon = inputs["origin_longitude"][0]
        origin_coords = (orig_lat, orig_lon)

        dest_lat = inputs["destination_latitude"][0]
        dest_lon = inputs["destination_longitude"][0]
        final_dest_coords = (dest_lat, dest_lon)

        # We will first calculate the straight-line overland distance from origin to destination.
        # In the cost model, we will determine if Great Lakes shipping is cheaper than overland.
        overland_dist_km = self.calculate_land_distance(origin_coords, final_dest_coords)
        outputs["land_transport_distance_overland"] = overland_dist_km

        # Set the waypoints for the barge shipping from Duluth/Superior to six different ports:
        # Chicago, Gary, Detroit, Toledo, Cleveland, and Buffalo
        barge_waypoint_coords = pd.DataFrame(
            [
                [46.7565839, -92.0831726],
                [47.779184, -87.904044],
                [46.4858356, -84.4162313],
                [45.9900047, -83.903314],
                [44.4911758, -82.6883793],
                [43.0007752, -82.4409521],
                [42.3159495, -83.0741043],
                [41.8705601, -83.2852269],
                [41.6312673, -83.5333356],
                [41.5154262, -81.7403171],
                [42.8847962, -78.8907495],
                [45.770559, -84.7139415],
                [45.958765, -86.2567032],
                [41.8832576, -87.6081092],
                [41.6235154, -87.3667538],
            ],
            index=[
                "Duluth",
                "Keweenaw",
                "Sault St Marie",
                "De Tour",
                "Lake Huron",
                "Port Huron",
                "Detroit",
                "Erie",
                "Toledo",
                "Cleveland",
                "Buffalo",
                "Mackinaw",
                "Manistique",
                "Chicago",
                "Gary",
            ],
            columns=["Lat", "Lon"],
        )

        barge_waypoints = {
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
            "Gary": [
                "Duluth",
                "Keweenaw",
                "Sault St Marie",
                "De Tour",
                "Mackinaw",
                "Manistique",
                "Gary",
            ],
            "Detroit": [
                "Duluth",
                "Keweenaw",
                "Sault St Marie",
                "De Tour",
                "Lake Huron",
                "Port Huron",
                "Detroit",
            ],
            "Toledo": [
                "Duluth",
                "Keweenaw",
                "Sault St Marie",
                "De Tour",
                "Lake Huron",
                "Port Huron",
                "Erie",
                "Toledo",
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

        # First, find distance between origin and origin port (Duluth) in km
        land_distance_origin_km = self.calculate_land_distance(
            origin_coords,
            barge_waypoint_coords.loc["Duluth"].values,
        )

        # Find the distance on land from each of the three barge destinations to the final
        # destination and take route with the minimum land distance
        if self.config.find_closest_ship_site:
            min_distance = 1e20
            land_distance_for_min = 0
            water_distance_for_min = 0
            for barge_dest, waypoints in barge_waypoints.items():
                barge_lat = barge_waypoint_coords.loc[barge_dest]["Lat"]
                barge_lon = barge_waypoint_coords.loc[barge_dest]["Lon"]
                barge_dest_coords = (barge_lat, barge_lon)
                land_distance_dest_km = self.calculate_land_distance(
                    barge_dest_coords, final_dest_coords
                )
                water_distance_km = self.calculate_water_distance(waypoints, barge_waypoint_coords)

                if land_distance_dest_km < min_distance:
                    min_distance = land_distance_dest_km

                    land_distance_for_min = self.calculate_land_distance(
                        barge_dest_coords, final_dest_coords
                    )
                    water_distance_for_min = self.calculate_water_distance(
                        waypoints, barge_waypoint_coords
                    )
                    # Add in distance from mine to Duluth
                    land_distance_for_min += land_distance_origin_km

                    # final_dest = barge_dest

            outputs["land_transport_distance_great_lakes"] = land_distance_for_min
            outputs["water_transport_distance_great_lakes"] = water_distance_for_min
        else:
            barge_dest = self.config.shipment_site
            barge_lat = barge_waypoint_coords.loc[barge_dest]["Lat"]
            barge_lon = barge_waypoint_coords.loc[barge_dest]["Lon"]
            barge_dest_coords = (barge_lat, barge_lon)
            land_distance_km = self.calculate_land_distance(barge_dest_coords, final_dest_coords)
            water_distance_km = self.calculate_water_distance(
                barge_waypoints[self.config.shipment_site], barge_waypoint_coords
            )
            outputs["land_transport_distance_great_lakes"] = land_distance_km
            outputs["water_transport_distance_great_lakes"] = water_distance_km


@define(kw_only=True)
class IronTransportCostConfig(BaseConfig):
    """Configuration for calculating iron ore pellet transportation costs.

    Args:
        transport_year (int): The year for which transportation costs are calculated.
        cost_year (int): The year for which cost data is relevant.
        land_shipping_cost (float): Cost of land shipping in $/ton-mi. Default is 0.0522 $/ton-mi.
            See :doc:`/technology_models/iron_transport` for more info on the default cost.
        water_shipping_cost (float): Cost of water shipping in $/ton-mi. Default is 0.0235 $/ton-mi.
            See :doc:`/technology_models/iron_transport` for more info on the default cost.
        marginal_cost (float): Marginal cost of transportation. Default is 0.0.
    """

    transport_year: int = field(converter=int, validator=(validators.ge(2022), validators.le(2065)))
    cost_year: int = field(converter=int, validator=(validators.ge(2010), validators.le(2024)))
    land_shipping_cost: float = field(default=0.0522)  # $/ton-mi
    water_shipping_cost: float = field(default=0.0235)  # $/ton-mi
    marginal_cost: float = field(default=0.0)


class IronTransportCostComponent(CostModelBaseClass):
    """Component for calculating iron ore pellet transportation costs."""

    _time_step_bounds = (
        3600,
        3600,
    )  # (min, max) time step lengths (in seconds) compatible with this model

    def initialize(self):
        self.options.declare("driver_config", types=dict)
        self.options.declare("plant_config", types=dict)
        self.options.declare("tech_config", types=dict)

    def setup(self):
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
            additional_cls_name=self.__class__.__name__,
        )
        super().setup()

        self.add_input("land_transport_distance_great_lakes", val=0.0, units="mi")
        self.add_input("water_transport_distance_great_lakes", val=0.0, units="mi")
        self.add_input("land_transport_distance_overland", val=0.0, units="mi")
        self.add_input("iron_ore_in", val=0.0, shape=self.n_timesteps, units="t/h")

        self.add_output("iron_ore_out", val=0.0, shape=self.n_timesteps, units="t/h")
        self.add_output("iron_transport_cost", val=0.0, units="USD/t")

    def compute(self, inputs, outputs, discrete_inputs, discrete_outputs):
        # Calculate cost with barge shipping through Great Lakes
        water_ship_cost_dol_tonne_mi = self.config.water_shipping_cost
        water_ship_cost_dol_per_ton = (
            water_ship_cost_dol_tonne_mi * inputs["water_transport_distance_great_lakes"]
        )
        water_ship_cost_USD = np.sum(inputs["iron_ore_in"]) * water_ship_cost_dol_per_ton

        land_ship_cost_dol_tonne_mi = self.config.land_shipping_cost
        land_ship_cost_dol_per_ton = (
            land_ship_cost_dol_tonne_mi * inputs["land_transport_distance_great_lakes"]
        )
        land_ship_cost_USD = np.sum(inputs["iron_ore_in"]) * land_ship_cost_dol_per_ton

        total_shipment_cost_GL = water_ship_cost_USD + land_ship_cost_USD

        # Calculate cost with just overland shipping
        overland_ship_cost_dol_per_ton = (
            land_ship_cost_dol_tonne_mi * inputs["land_transport_distance_overland"]
        )
        overland_ship_cost_USD = np.sum(inputs["iron_ore_in"]) * overland_ship_cost_dol_per_ton

        # Find minimum shipping cost
        total_shipment_cost = min(total_shipment_cost_GL, overland_ship_cost_USD)

        # Output final costs
        outputs["iron_ore_out"] = inputs["iron_ore_in"]  # assume lossless
        outputs["iron_transport_cost"] = total_shipment_cost / np.sum(inputs["iron_ore_in"])
        outputs["VarOpEx"] = total_shipment_cost
