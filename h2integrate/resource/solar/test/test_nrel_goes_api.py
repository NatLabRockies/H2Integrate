from pathlib import Path

import openmdao.api as om
from pytest import fixture

from h2integrate import RESOURCE_DEFAULT_DIR
from h2integrate.resource.solar.nrel_developer_goes_api_models import (
    GOESTMYSolarAPI,
    GOESConusSolarAPI,
    GOESFullDiscSolarAPI,
    GOESAggregatedSolarAPI,
)


@fixture
def plant_simulation_utc_start():
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
def site_config():
    site = {
        "latitude": 34.22,
        "longitude": -102.75,
        "resources": {
            "solar_resource": {
                "resource_model": "GOESAggregatedSolarAPI",
                "resource_parameters": {
                    "latitude": 34.22,
                    "longitude": -102.75,
                    "resource_year": 2012,
                },
            }
        },
    }
    return site


def test_goes_aggregated_loaded_from_default_dir(plant_simulation_utc_start, site_config, subtests):
    plant_config = {
        "site": site_config,
        "plant": plant_simulation_utc_start,
    }

    prob = om.Problem()
    comp = GOESAggregatedSolarAPI(
        plant_config=plant_config,
        resource_config=plant_config["site"]["resources"]["solar_resource"]["resource_parameters"],
        driver_config={},
    )
    prob.model.add_subsystem("resource", comp)
    prob.setup()
    prob.run_model()
    goes_data = prob.get_val("resource.solar_resource_data")

    solar_dir = RESOURCE_DEFAULT_DIR / "solar"
    with subtests.test("filepath for data was found where expected"):
        assert Path(goes_data["filepath"]).exists()
        assert Path(goes_data["filepath"]).parent == solar_dir

    data_keys = [
        "ghi",
        "dhi",
        "dni",
        "temperature",
        "pressure",
        "dew_point",
        "wind_speed",
        "wind_direction",
    ]
    with subtests.test("resource data is 8760 in length"):
        assert all(len(goes_data[k]) == 8760 for k in data_keys)


def test_goes_conus_loaded_from_default_dir(plant_simulation_utc_start, site_config, subtests):
    plant_config = {
        "site": site_config,
        "plant": plant_simulation_utc_start,
    }

    filename = "34.22_-102.75_2012_goes_aggregated_v4_60min_utc_tz.csv"
    plant_config["site"]["resources"]["solar_resource"]["resource_parameters"].update(
        {"resource_filename": filename}
    )
    plant_config["site"]["resources"]["solar_resource"]["resource_parameters"]["resource_year"] = (
        2020
    )

    prob = om.Problem()
    comp = GOESConusSolarAPI(
        plant_config=plant_config,
        resource_config=plant_config["site"]["resources"]["solar_resource"]["resource_parameters"],
        driver_config={},
    )
    prob.model.add_subsystem("resource", comp)
    prob.setup()
    prob.run_model()
    goes_data = prob.get_val("resource.solar_resource_data")

    solar_dir = RESOURCE_DEFAULT_DIR / "solar"
    with subtests.test("filepath for data was found where expected"):
        assert Path(goes_data["filepath"]).exists()
        assert Path(goes_data["filepath"]).parent == solar_dir

    data_keys = [
        "ghi",
        "dhi",
        "dni",
        "temperature",
        "pressure",
        "dew_point",
        "wind_speed",
        "wind_direction",
    ]
    with subtests.test("resource data is 8760 in length"):
        assert all(len(goes_data[k]) == 8760 for k in data_keys)


def test_goes_fulldisc_loaded_from_default_dir(plant_simulation_utc_start, site_config, subtests):
    plant_config = {
        "site": site_config,
        "plant": plant_simulation_utc_start,
    }

    filename = "34.22_-102.75_2012_goes_aggregated_v4_60min_utc_tz.csv"
    plant_config["site"]["resources"]["solar_resource"]["resource_parameters"].update(
        {"resource_filename": filename}
    )
    plant_config["site"]["resources"]["solar_resource"]["resource_parameters"]["resource_year"] = (
        2020
    )

    prob = om.Problem()
    comp = GOESFullDiscSolarAPI(
        plant_config=plant_config,
        resource_config=plant_config["site"]["resources"]["solar_resource"]["resource_parameters"],
        driver_config={},
    )
    prob.model.add_subsystem("resource", comp)
    prob.setup()
    prob.run_model()
    goes_data = prob.get_val("resource.solar_resource_data")

    solar_dir = RESOURCE_DEFAULT_DIR / "solar"
    with subtests.test("filepath for data was found where expected"):
        assert Path(goes_data["filepath"]).exists()
        assert Path(goes_data["filepath"]).parent == solar_dir

    data_keys = [
        "ghi",
        "dhi",
        "dni",
        "temperature",
        "pressure",
        "dew_point",
        "wind_speed",
        "wind_direction",
    ]
    with subtests.test("resource data is 8760 in length"):
        assert all(len(goes_data[k]) == 8760 for k in data_keys)


def test_goes_tmy_loaded_from_default_dir(plant_simulation_utc_start, site_config, subtests):
    plant_config = {
        "site": site_config,
        "plant": plant_simulation_utc_start,
    }

    filename = "34.22_-102.75_2012_goes_aggregated_v4_60min_utc_tz.csv"
    plant_config["site"]["resources"]["solar_resource"]["resource_parameters"].update(
        {"resource_filename": filename}
    )

    plant_config["site"]["resources"]["solar_resource"]["resource_parameters"]["resource_year"] = (
        "tmy-2022"
    )

    prob = om.Problem()
    comp = GOESTMYSolarAPI(
        plant_config=plant_config,
        resource_config=plant_config["site"]["resources"]["solar_resource"]["resource_parameters"],
        driver_config={},
    )
    prob.model.add_subsystem("resource", comp)
    prob.setup()
    prob.run_model()
    goes_data = prob.get_val("resource.solar_resource_data")

    solar_dir = RESOURCE_DEFAULT_DIR / "solar"
    with subtests.test("filepath for data was found where expected"):
        assert Path(goes_data["filepath"]).exists()
        assert Path(goes_data["filepath"]).parent == solar_dir

    data_keys = [
        "ghi",
        "dhi",
        "dni",
        "temperature",
        "pressure",
        "dew_point",
        "wind_speed",
        "wind_direction",
    ]
    with subtests.test("resource data is 8760 in length"):
        assert all(len(goes_data[k]) == 8760 for k in data_keys)
