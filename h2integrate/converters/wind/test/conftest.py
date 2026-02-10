import os

import pytest
from hopp import TEST_ENV_VAR

from test.conftest import temp_dir, pytest_collection_modifyitems  # noqa: F401


def pytest_sessionstart(session):
    os.environ["ENV"] = TEST_ENV_VAR

    initial_resource_dir = os.getenv("RESOURCE_DIR")
    # if user provided a resource directory, save it to a temp variable
    # this allows tests to run as expected while not causing
    # unexpected behavior afterwards
    if initial_resource_dir is not None:
        os.environ["TEMP_RESOURCE_DIR"] = f"{initial_resource_dir}"

    os.environ.pop("RESOURCE_DIR", None)


def pytest_sessionfinish(session, exitstatus):
    # if user provided a resource directory, load it from the temp variable
    # and reset the original environment variable
    # this prevents unexpected behavior after running tests

    user_dir = os.getenv("TEMP_RESOURCE_DIR")
    if user_dir is not None:
        os.environ["RESOURCE_DIR"] = user_dir
    os.environ.pop("TEMP_RESOURCE_DIR", None)


@pytest.fixture
def plant_config_wtk():
    site_config = {
        "latitude": 35.2018863,
        "longitude": -101.945027,
        "resource": {
            "wind_resource": {
                "resource_model": "WTKNRELDeveloperAPIWindResource",
                "resource_parameters": {
                    "resource_year": 2012,
                },
            }
        },
    }
    plant_dict = {
        "plant_life": 30,
        "simulation": {"n_timesteps": 8760, "dt": 3600, "start_time": "01/01 00:30:00"},
    }

    d = {"site": site_config, "plant": plant_dict}
    return d


@pytest.fixture
def wind_plant_config():
    layout_config = {
        "layout_mode": "basicgrid",
        "layout_options": {
            "row_D_spacing": 5.0,
            "turbine_D_spacing": 5.0,
            "rotation_angle_deg": 0.0,
            "row_phase_offset": 0.0,
            "layout_shape": "square",
        },
    }
    pysam_config = {
        "Farm": {
            "wind_farm_wake_model": 0,
        },
        "Losses": {
            "ops_strategies_loss": 10.0,
        },
    }
    design_config = {
        "num_turbines": 50,
        "hub_height": 115,
        "rotor_diameter": 170,
        "turbine_rating_kw": 6000,
        "create_model_from": "default",
        "config_name": "WindPowerSingleOwner",
        "pysam_options": pysam_config,
        "layout": layout_config,
    }
    return design_config
