import numpy as np
import pytest
import openmdao.api as om
from pytest import fixture

from h2integrate.converters.iron.iron_transport import (
    IronTransportCostComponent,
    IronTransportPerformanceComponent,
)


@fixture
def plant_config():
    plant_config = {
        "sites": {
            "site": {
                "latitude": 41.717,
                "longitude": -88.398,
            },
        },
        "plant": {
            "plant_life": 30,
            "simulation": {
                "n_timesteps": 8760,
                "dt": 3600,
            },
        },
        "finance_parameters": {
            "cost_adjustment_parameters": {
                "cost_year_adjustment_inflation": 0.025,
                "target_dollar_year": 2022,
            }
        },
    }
    return plant_config


@pytest.mark.regression
def test_iron_transport_performance_chicago(plant_config, subtests):
    # Chicago land distance: 68.19490223326876 km
    # Chicago has water distance of 1414.8120870922066 km
    tech_config_chicago = {
        "model_inputs": {
            "performance_parameters": {
                "find_closest_ship_site": False,
                "shipment_site": "Chicago",
                "land_circuity_ratio": 1,
            }
        }
    }
    prob = om.Problem()
    transport = IronTransportPerformanceComponent(
        plant_config=plant_config,
        tech_config=tech_config_chicago,
        driver_config={},
    )

    prob.model.add_subsystem("transport", transport, promotes=["*"])
    prob.setup()
    # Duluth coordinates
    prob.set_val("transport.origin_latitude", 46.7565839, units="deg")
    prob.set_val("transport.origin_longitude", -92.0831726, units="deg")
    # Just outside Chicago
    prob.set_val("transport.destination_latitude", 41.717, units="deg")
    prob.set_val("transport.destination_longitude", -88.398, units="deg")
    prob.run_model()

    with subtests.test("Chicago Land vs water+land distance"):
        tot_distance = prob.get_val(
            "transport.water_transport_distance_great_lakes", units="km"
        ) + prob.get_val("transport.land_transport_distance_great_lakes", units="km")
        assert np.all(
            prob.get_val("transport.land_transport_distance_overland", units="km") < tot_distance
        )
    with subtests.test("Chicago land transport distance"):
        assert (
            pytest.approx(
                prob.get_val("transport.land_transport_distance_great_lakes", units="km")[0],
                rel=1e-6,
            )
            == 68.19490223326876
        )
    with subtests.test("Chicago water transport distance"):
        assert (
            pytest.approx(
                prob.get_val("transport.water_transport_distance_great_lakes", units="km")[0],
                rel=1e-6,
            )
            == 1359.70926331  # 1414.8120870922066
        )


@pytest.mark.regression
def test_iron_transport_performance_buffalo(plant_config, subtests):
    # Buffalo land distance: 794.1713773276688 km
    # Buffalo has water distance of 1621.9112211308186 km
    tech_config_buffalo = {
        "model_inputs": {
            "performance_parameters": {
                "find_closest_ship_site": False,
                "shipment_site": "Buffalo",
                "land_circuity_ratio": 1,
            }
        }
    }
    prob = om.Problem()
    transport = IronTransportPerformanceComponent(
        plant_config=plant_config,
        tech_config=tech_config_buffalo,
        driver_config={},
    )

    prob.model.add_subsystem("transport", transport, promotes=["*"])
    prob.setup()
    # Duluth coordinates
    prob.set_val("transport.origin_latitude", 46.7565839, units="deg")
    prob.set_val("transport.origin_longitude", -92.0831726, units="deg")
    # Just outside Chicago
    prob.set_val("transport.destination_latitude", 41.717, units="deg")
    prob.set_val("transport.destination_longitude", -88.398, units="deg")
    prob.run_model()

    with subtests.test("Buffalo Land vs water+land distance"):
        tot_distance = prob.get_val(
            "transport.water_transport_distance_great_lakes", units="km"
        ) + prob.get_val("transport.land_transport_distance_great_lakes", units="km")
        assert np.all(
            prob.get_val("transport.land_transport_distance_overland", units="km") < tot_distance
        )
    with subtests.test("Buffalo land transport distance"):
        assert (
            pytest.approx(
                prob.get_val("transport.land_transport_distance_great_lakes", units="km")[0],
                rel=1e-6,
            )
            == 794.1713773276688
        )
    with subtests.test("Buffalo water transport distance"):
        assert (
            pytest.approx(
                prob.get_val("transport.water_transport_distance_great_lakes", units="km")[0],
                rel=1e-6,
            )
            == 1621.9112211308186
        )


@pytest.mark.regression
def test_iron_transport_performance_cleveland(plant_config, subtests):
    # Cleveland land distance: 555.2088919541055 km
    # Cleveland has water distance of 1341.7141480490504 km
    tech_config_cleveland = {
        "model_inputs": {
            "performance_parameters": {
                "find_closest_ship_site": False,
                "shipment_site": "Cleveland",
                "land_circuity_ratio": 1,
            }
        }
    }
    prob = om.Problem()
    transport = IronTransportPerformanceComponent(
        plant_config=plant_config,
        tech_config=tech_config_cleveland,
        driver_config={},
    )

    prob.model.add_subsystem("transport", transport, promotes=["*"])
    prob.setup()
    # Duluth coordinates
    prob.set_val("transport.origin_latitude", 46.7565839, units="deg")
    prob.set_val("transport.origin_longitude", -92.0831726, units="deg")
    # Just outside Chicago
    prob.set_val("transport.destination_latitude", 41.717, units="deg")
    prob.set_val("transport.destination_longitude", -88.398, units="deg")
    prob.run_model()

    with subtests.test("Cleveland Land vs water+land distance"):
        tot_distance = prob.get_val(
            "transport.water_transport_distance_great_lakes", units="km"
        ) + prob.get_val("transport.land_transport_distance_great_lakes", units="km")
        assert np.all(
            prob.get_val("transport.land_transport_distance_overland", units="km") < tot_distance
        )
    with subtests.test("Cleveland land transport distance"):
        assert (
            pytest.approx(
                prob.get_val("transport.land_transport_distance_great_lakes", units="km")[0],
                rel=1e-6,
            )
            == 555.2088919541055
        )
    with subtests.test("Cleveland water transport distance"):
        assert (
            pytest.approx(
                prob.get_val("transport.water_transport_distance_great_lakes", units="km")[0],
                rel=1e-6,
            )
            == 1341.7141480490504
        )


@pytest.mark.regression
def test_iron_transport_performance_closest_loc(plant_config, subtests):
    tech_config_find_closest = {
        "model_inputs": {
            "performance_parameters": {
                "find_closest_ship_site": True,
                "shipment_site": "None",
                "land_circuity_ratio": 1,
            }
        }
    }

    prob = om.Problem()
    transport = IronTransportPerformanceComponent(
        plant_config=plant_config,
        tech_config=tech_config_find_closest,
        driver_config={},
    )

    prob.model.add_subsystem("transport", transport, promotes=["*"])
    prob.setup()
    # Duluth coordinates
    prob.set_val("transport.origin_latitude", 46.7565839, units="deg")
    prob.set_val("transport.origin_longitude", -92.0831726, units="deg")
    # Just outside Chicago
    prob.set_val("transport.destination_latitude", 41.717, units="deg")
    prob.set_val("transport.destination_longitude", -88.398, units="deg")
    prob.run_model()

    with subtests.test("Buffalo Land vs water+land distance"):
        tot_distance = prob.get_val(
            "transport.water_transport_distance_great_lakes", units="km"
        ) + prob.get_val("transport.land_transport_distance_great_lakes", units="km")
        assert np.all(
            prob.get_val("transport.land_transport_distance_overland", units="km") < tot_distance
        )
    with subtests.test("Duluth land transport distance"):
        assert (
            pytest.approx(
                prob.get_val("transport.land_transport_distance_overland", units="km")[0], rel=1e-6
            )
            == 632.4711909045266
        )
    with subtests.test("Duluth water transport distance"):
        assert (
            pytest.approx(
                prob.get_val("transport.water_transport_distance_great_lakes", units="km")[0],
                rel=1e-6,
            )
            == 1359.70926331
        )


@pytest.mark.regression
def test_iron_transport_cost_cleveland(plant_config, subtests):
    # land cost: 20.51456753 USD/tonne
    # water cost: 37.60052956 USD/tonne
    annual_ore_production = 12385.195376438356 * 365
    hourly_ore_production = np.ones(8760) * annual_ore_production / 8760
    tech_config_chicago = {
        "model_inputs": {
            "performance_parameters": {
                "find_closest_ship_site": False,
                "shipment_site": "Cleveland",
                "land_circuity_ratio": 1,
            },
            "cost_parameters": {
                "transport_year": 2022,
                "cost_year": 2022,
            },
        }
    }
    prob = om.Problem()
    perf = IronTransportPerformanceComponent(
        plant_config=plant_config,
        tech_config=tech_config_chicago,
        driver_config={},
    )

    cost = IronTransportCostComponent(
        plant_config=plant_config,
        tech_config=tech_config_chicago,
        driver_config={},
    )

    prob.model.add_subsystem("transport_perf", perf, promotes=["*"])
    prob.model.add_subsystem("transport_cost", cost, promotes=["*"])

    prob.setup()
    # Duluth coordinates
    prob.set_val("transport_perf.origin_latitude", 46.7565839, units="deg")
    prob.set_val("transport_perf.origin_longitude", -92.0831726, units="deg")

    # Just outside Chicago
    prob.set_val("transport_perf.destination_latitude", 41.717, units="deg")
    prob.set_val("transport_perf.destination_longitude", -88.398, units="deg")

    prob.set_val("transport_cost.iron_ore_in", hourly_ore_production, units="t/h")

    prob.run_model()

    with subtests.test("Shipment cost usd/ton"):
        varom = prob.get_val("transport_cost.VarOpEx", units="USD/year")
        cost_per_unit = varom / annual_ore_production
        assert pytest.approx(cost_per_unit[0], abs=1e-3) == 20.51456753
