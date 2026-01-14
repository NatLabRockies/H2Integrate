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
        "site": {
            "latitude": 41.717,
            "longitude": -88.398,
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


def test_iron_transport_performance_chicago(plant_config, subtests):
    # Chicago land distance: 68.19490223326876 km
    # Chicago has water distance of 1414.8120870922066 km
    tech_config_chicago = {
        "model_inputs": {
            "performance_parameters": {
                "find_closest_ship_site": False,
                "shipment_site": "Chicago",
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
    prob.run_model()

    with subtests.test("Total transport distance equals land + water"):
        tot_distance = prob.get_val(
            "transport.water_transport_distance", units="km"
        ) + prob.get_val("transport.land_transport_distance", units="km")
        assert (
            pytest.approx(prob.get_val("transport.total_transport_distance", units="km"), rel=1e-6)
            == tot_distance
        )
    with subtests.test("Chicago land transport distance"):
        assert (
            pytest.approx(
                prob.get_val("transport.land_transport_distance", units="km")[0], rel=1e-6
            )
            == 68.19490223326876
        )
    with subtests.test("Chicago water transport distance"):
        assert (
            pytest.approx(
                prob.get_val("transport.water_transport_distance", units="km")[0], rel=1e-6
            )
            == 1359.70926331  # 1414.8120870922066
        )


def test_iron_transport_performance_buffalo(plant_config, subtests):
    # Buffalo land distance: 794.1713773276688 km
    # Buffalo has water distance of 1621.9112211308186 km
    tech_config_buffalo = {
        "model_inputs": {
            "performance_parameters": {
                "find_closest_ship_site": False,
                "shipment_site": "Buffalo",
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
    prob.run_model()

    with subtests.test("Total transport distance equals land + water"):
        tot_distance = prob.get_val(
            "transport.water_transport_distance", units="km"
        ) + prob.get_val("transport.land_transport_distance", units="km")
        assert (
            pytest.approx(prob.get_val("transport.total_transport_distance", units="km"), rel=1e-6)
            == tot_distance
        )
    with subtests.test("Buffalo land transport distance"):
        assert (
            pytest.approx(
                prob.get_val("transport.land_transport_distance", units="km")[0], rel=1e-6
            )
            == 794.1713773276688
        )
    with subtests.test("Buffalo water transport distance"):
        assert (
            pytest.approx(
                prob.get_val("transport.water_transport_distance", units="km")[0], rel=1e-6
            )
            == 1621.9112211308186
        )


def test_iron_transport_performance_cleveland(plant_config, subtests):
    # Cleveland land distance: 555.2088919541055 km
    # Cleveland has water distance of 1341.7141480490504 km
    tech_config_cleveland = {
        "model_inputs": {
            "performance_parameters": {
                "find_closest_ship_site": False,
                "shipment_site": "Cleveland",
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
    prob.run_model()

    with subtests.test("Total transport distance equals land + water"):
        tot_distance = prob.get_val(
            "transport.water_transport_distance", units="km"
        ) + prob.get_val("transport.land_transport_distance", units="km")
        assert (
            pytest.approx(prob.get_val("transport.total_transport_distance", units="km"), rel=1e-6)
            == tot_distance
        )
    with subtests.test("Cleveland land transport distance"):
        assert (
            pytest.approx(
                prob.get_val("transport.land_transport_distance", units="km")[0], rel=1e-6
            )
            == 555.2088919541055
        )
    with subtests.test("Cleveland water transport distance"):
        assert (
            pytest.approx(
                prob.get_val("transport.water_transport_distance", units="km")[0], rel=1e-6
            )
            == 1341.7141480490504
        )


def test_iron_transport_performance_closest_loc(plant_config, subtests):
    tech_config_find_closest = {
        "model_inputs": {
            "performance_parameters": {
                "find_closest_ship_site": True,
                "shipment_site": "None",
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
    prob.run_model()

    with subtests.test("Total transport distance equals land + water"):
        tot_distance = prob.get_val(
            "transport.water_transport_distance", units="km"
        ) + prob.get_val("transport.land_transport_distance", units="km")
        assert (
            pytest.approx(prob.get_val("transport.total_transport_distance", units="km"), rel=1e-6)
            == tot_distance
        )
    with subtests.test("Duluth land transport distance"):
        assert (
            pytest.approx(
                prob.get_val("transport.land_transport_distance", units="km")[0], rel=1e-6
            )
            == 632.4711909045266
        )
    with subtests.test("Duluth water transport distance"):
        assert (
            pytest.approx(
                prob.get_val("transport.water_transport_distance", units="km")[0], rel=1e-6
            )
            == 0
        )


def test_iron_transport_cost_cleveland(plant_config, subtests):
    # total cost: 62.94298688675447 USD/tonne
    # land cost: 38.4320718826894 USD/tonne
    # water cost: 24.51091500406507 USD/tonne
    annual_ore_production = 12385.195376438356 * 365
    hourly_ore_production = np.ones(8760) * annual_ore_production / 8760
    tech_config_chicago = {
        "model_inputs": {
            "performance_parameters": {
                "find_closest_ship_site": False,
                "shipment_site": "Cleveland",
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

    prob.set_val("transport_cost.iron_ore_in", hourly_ore_production, units="t/h")

    prob.run_model()

    with subtests.test("Ore profit margin"):
        assert (
            pytest.approx(prob.get_val("transport_cost.ore_profit_margin", units="USD/t"), rel=1e-6)
            == 6.0
        )

    with subtests.test("Shipment cost usd/ton"):
        varom = prob.get_val("transport_cost.VarOpEx", units="USD/year")
        cost_per_unit = varom / annual_ore_production
        assert pytest.approx(cost_per_unit[0], abs=1e-3) == 62.94298688675447
