from pathlib import Path

import pytest
import openmdao.api as om
from pytest import fixture

from h2integrate.resource.solar.openmeteo_solar import OpenMeteoHistoricalSolarResource


@fixture
def plant_simulation_utc_start():
    plant_utc = {
        "plant_life": 30,
        "simulation": {
            "dt": 3600,
            "n_timesteps": 8760,
            "start_time": "01/01/1900 00:30:00",
            "timezone": 0,
        },
    }
    return plant_utc


@fixture
def plant_simulation_nonutc_start():
    plant_localtz = {
        "plant_life": 30,
        "simulation": {
            "dt": 3600,
            "n_timesteps": 8760,
            "start_time": "01/01/1900 00:30:00",
            "timezone": -6,
        },
    }
    return plant_localtz


@fixture
def site_config_download_from_h2i():
    site = {
        "latitude": 44.04218,
        "longitude": -95.19757,
        "resources": {
            "solar_resource": {
                "resource_model": "openmeteo_solar_api",
                "resource_parameters": {
                    "resource_year": 2023,
                },
            }
        },
    }
    return site


def test_solar_resource_h2i_download(
    plant_simulation_utc_start, site_config_download_from_h2i, subtests
):
    plant_config = {
        "site": site_config_download_from_h2i,
        "plant": plant_simulation_utc_start,
    }

    prob = om.Problem()
    comp = OpenMeteoHistoricalSolarResource(
        plant_config=plant_config,
        resource_config=plant_config["site"]["resources"]["solar_resource"]["resource_parameters"],
        driver_config={},
    )
    prob.model.add_subsystem("resource", comp)
    prob.setup()
    prob.run_model()
    solar_data = prob.get_val("resource.solar_resource_data")
    with subtests.test("filepath for data was found where expected"):
        assert Path(solar_data["filepath"]).exists()
        assert (
            Path(solar_data["filepath"]).name
            == "44.04218_-95.19757_2023_openmeteo_archive_solar_60min_utc_tz.csv"
        )

    data_keys = [k for k, v in solar_data.items() if not isinstance(v, float | int | str)]
    with subtests.test("Data timezone"):
        assert pytest.approx(solar_data["data_tz"], rel=1e-6) == 0
    with subtests.test("Site Elevation"):
        assert pytest.approx(solar_data["elevation"], rel=1e-6) == 449
    with subtests.test("resource data is 8760 in length"):
        assert all(len(solar_data[k]) == 8760 for k in data_keys)
    with subtests.test("theres 16 timeseries data keys"):
        assert len(data_keys) == 16
    with subtests.test("Start time"):
        assert solar_data["start_time"] == "2023/01/01 00:00:00 (+0000)"
    with subtests.test("Time step"):
        assert solar_data["dt"] == 3600
