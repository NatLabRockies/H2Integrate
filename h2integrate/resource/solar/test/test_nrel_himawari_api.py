from pathlib import Path

import openmdao.api as om
from pytest import fixture

from h2integrate.resource.solar.nrel_developer_himawari_api_models import (
    Himawari7SolarAPI,
    Himawari8SolarAPI,
    HimawariTMYSolarAPI,
)


@fixture
def plant_simulation_config():
    plant = {
        "plant_life": 30,
        "simulation": {
            "dt": 3600,
            "n_timesteps": 8760,
            "start_time": "01/01/1900 00:30:00",
            "timezone": 0,
        },
    }
    return plant


@fixture
def himawari7_site_config_tmy():
    # Brisbane, Australia
    himawari7_site_tmy = {
        "latitude": -27.3649,
        "longitude": 152.67935,
        "resources": {
            "solar_resource": {
                "resource_model": "himawari_tmy_solar_v3_api",
                "resource_parameters": {
                    "resource_year": "tmy-2020",
                },
            }
        },
    }
    return himawari7_site_tmy


@fixture
def himawari7_site_config():
    # Brisbane, Australia
    himawari7_site_tmy = {
        "latitude": -27.3649,
        "longitude": 152.67935,
        "resources": {
            "solar_resource": {
                "resource_model": "himawari7_solar_v3_api",
                "resource_parameters": {
                    "resource_year": 2013,
                },
            }
        },
    }
    return himawari7_site_tmy


@fixture
def himawari8_site_config():
    # KL, Malaysia
    himawari8_site = {
        "latitude": 3.25735,
        "longitude": 101.656312,
        "resources": {
            "solar_resource": {
                "resource_model": "himawari8_solar_v3_api",
                "resource_parameters": {
                    "resource_year": 2020,
                },
            }
        },
    }
    return himawari8_site


def test_himawari_tmy(plant_simulation_config, himawari7_site_config_tmy, subtests):
    plant_config = {
        "site": himawari7_site_config_tmy,
        "plant": plant_simulation_config,
    }

    prob = om.Problem()
    comp = HimawariTMYSolarAPI(
        plant_config=plant_config,
        resource_config=plant_config["site"]["resources"]["solar_resource"]["resource_parameters"],
        driver_config={},
    )
    prob.model.add_subsystem("resource", comp)
    prob.setup()
    prob.run_model()
    data = prob.get_val("resource.solar_resource_data")

    name_expected = "-27.3649_152.67935_tmy-2020_himawari_tmy_v3_60min_utc_tz.csv"
    with subtests.test("Filename expected"):
        assert name_expected == (Path(data["filepath"])).name


def test_himawari7(plant_simulation_config, himawari7_site_config, subtests):
    plant_config = {
        "site": himawari7_site_config,
        "plant": plant_simulation_config,
    }

    prob = om.Problem()
    comp = Himawari7SolarAPI(
        plant_config=plant_config,
        resource_config=plant_config["site"]["resources"]["solar_resource"]["resource_parameters"],
        driver_config={},
    )
    prob.model.add_subsystem("resource", comp)
    prob.setup()
    prob.run_model()
    data = prob.get_val("resource.solar_resource_data")

    name_expected = "-27.3649_152.67935_2013_himawari7_v3_60min_utc_tz.csv"
    with subtests.test("Filename expected"):
        assert name_expected == (Path(data["filepath"])).name


def test_himawari8(plant_simulation_config, himawari8_site_config, subtests):
    plant_config = {
        "site": himawari8_site_config,
        "plant": plant_simulation_config,
    }

    prob = om.Problem()
    comp = Himawari8SolarAPI(
        plant_config=plant_config,
        resource_config=plant_config["site"]["resources"]["solar_resource"]["resource_parameters"],
        driver_config={},
    )
    prob.model.add_subsystem("resource", comp)
    prob.setup()
    prob.run_model()
    data = prob.get_val("resource.solar_resource_data")

    name_expected = "3.25735_101.656312_2020_himawari8_v3_60min_utc_tz.csv"
    with subtests.test("Filename expected"):
        assert name_expected == (Path(data["filepath"])).name
