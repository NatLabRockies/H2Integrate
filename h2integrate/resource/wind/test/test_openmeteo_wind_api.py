from pathlib import Path

import pytest
import openmdao.api as om
from pytest import fixture

from h2integrate.resource.wind.openmeteo_wind import OpenMeteoHistoricalWindResource


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
def plant_simulation_nonutc_start():
    plant = {
        "plant_life": 30,
        "simulation": {
            "dt": 3600,
            "n_timesteps": 8760,
            "start_time": "01/01/1900 00:30:00",
            "timezone": -6,
        },
    }
    return plant


@fixture
def site_config_download_from_web():
    site = {
        "latitude": 44.04218,
        "longitude": -95.19757,
        "resources": {
            "wind_resource": {
                "resource_model": "OpenMeteoHistoricalWindResource",
                "resource_parameters": {
                    "resource_year": 2023,
                    "resource_filename": "open-meteo-44.04N95.20W438m.csv",
                },
            }
        },
    }
    return site


@fixture
def site_config_download_from_h2i():
    site = {
        "latitude": 44.04218,
        "longitude": -95.19757,
        "resources": {
            "wind_resource": {
                "resource_model": "OpenMeteoHistoricalWindResource",
                "resource_parameters": {
                    "resource_year": 2023,
                },
            }
        },
    }
    return site


def test_wind_resource_web_download(
    plant_simulation_utc_start, site_config_download_from_web, subtests
):
    plant_config = {
        "site": site_config_download_from_web,
        "plant": plant_simulation_utc_start,
    }

    prob = om.Problem()
    comp = OpenMeteoHistoricalWindResource(
        plant_config=plant_config,
        resource_config=plant_config["site"]["resources"]["wind_resource"]["resource_parameters"],
        driver_config={},
    )
    prob.model.add_subsystem("resource", comp)
    prob.setup()
    prob.run_model()
    wind_data = prob.get_val("resource.wind_resource_data")

    with subtests.test("filepath for data was found where expected"):
        assert Path(wind_data["filepath"]).exists()
        assert Path(wind_data["filepath"]).name == "open-meteo-44.04N95.20W438m.csv"

    data_keys = [k for k, v in wind_data.items() if not isinstance(v, float | int | str)]
    with subtests.test("Data timezone"):
        assert pytest.approx(wind_data["data_tz"], rel=1e-6) == 0
    with subtests.test("Site Elevation"):
        assert pytest.approx(wind_data["elevation"], rel=1e-6) == 438
    with subtests.test("resource data is 8760 in length"):
        assert all(len(wind_data[k]) == 8760 for k in data_keys)
    with subtests.test("theres 12 timeseries data keys"):
        assert len(data_keys) == 12
    with subtests.test("Start time"):
        assert wind_data["start_time"] == "2023/01/01 00:00:00 (+0000)"
    with subtests.test("Time step"):
        assert wind_data["dt"] == 3600


def test_wind_resource_h2i_download(
    plant_simulation_nonutc_start, site_config_download_from_h2i, subtests
):
    plant_config = {
        "site": site_config_download_from_h2i,
        "plant": plant_simulation_nonutc_start,
    }

    prob = om.Problem()
    comp = OpenMeteoHistoricalWindResource(
        plant_config=plant_config,
        resource_config=plant_config["site"]["resources"]["wind_resource"]["resource_parameters"],
        driver_config={},
    )
    prob.model.add_subsystem("resource", comp)
    prob.setup()
    prob.run_model()
    wind_data = prob.get_val("resource.wind_resource_data")

    with subtests.test("filepath for data was found where expected"):
        assert Path(wind_data["filepath"]).exists()
        assert (
            Path(wind_data["filepath"]).name
            == "44.04218_-95.19757_2023_openmeteo_archive_60min_local_tz.csv"
        )

    data_keys = [k for k, v in wind_data.items() if not isinstance(v, float | int | str)]
    with subtests.test("Data timezone"):
        assert pytest.approx(wind_data["data_tz"], rel=1e-6) == -6
    with subtests.test("Site Elevation"):
        assert pytest.approx(wind_data["elevation"], rel=1e-6) == 449
    with subtests.test("resource data is 8760 in length"):
        assert all(len(wind_data[k]) == 8760 for k in data_keys)
    with subtests.test("theres 13 timeseries data keys"):
        assert len(data_keys) == 13
    with subtests.test("Start time"):
        assert wind_data["start_time"] == "2023/01/01 00:00:00 (-0600)"
    with subtests.test("Time step"):
        assert wind_data["dt"] == 3600
