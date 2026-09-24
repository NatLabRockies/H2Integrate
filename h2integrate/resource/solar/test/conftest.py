import pytest

from h2integrate.resource.test.conftest import (  # noqa: F401
    site_config,
    plant_simulation,
    pytest_sessionstart,
    pytest_sessionfinish,
)

from test.conftest import (  # noqa: F401
    temp_dir,
    temp_copy_of_example,
    pytest_collection_modifyitems,
)


# docs fencepost start: DO NOT REMOVE
@pytest.fixture
def plant_simulation_multiyear(tz, n_timesteps, dt):
    plant = {
        "plant_life": 30,
        "simulation": {
            "dt": dt,
            "n_timesteps": n_timesteps,
            "start_time": "01/01/1900 00:30:00",
            "timezone": tz,
        },
    }
    return plant


@pytest.fixture
def site_config_multiyear(lat, lon):
    site_config_my = {
        "latitude": lat,
        "longitude": lon,
    }
    return site_config_my


@pytest.fixture
def resource_config_multiyear(
    lat, lon, resource_year, include_leap, yr_setting, resource_fname, yr_order
):
    resource_config = {
        "latitude": lat,
        "longitude": lon,
        "resource_year": resource_year,
        "include_leap_day": include_leap,
        "resource_year_setting": yr_setting,
        "resource_year_order": yr_order,
        "resource_filename": resource_fname,
    }
    return resource_config


# docs fencepost end: DO NOT REMOVE
