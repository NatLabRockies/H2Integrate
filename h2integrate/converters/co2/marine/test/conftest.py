import importlib

import pytest

from test.conftest import (  # noqa: F401
    temp_dir,
    temp_copy_of_example,
    pytest_collection_modifyitems,
)


has_mcm = importlib.util.find_spec("mcm") is not None


@pytest.fixture
def plant_config():
    plant_config = {
        "plant": {
            "plant_life": 30,
            "simulation": {
                "n_timesteps": 8760,
                "dt": 3600,
            },
        },
    }
    return plant_config


# docs fencepost start: DO NOT REMOVE
@pytest.fixture(scope="function")
def driver_config(temp_dir):  # noqa: F811
    driver_config = {
        "general": {
            "folder_output": str(temp_dir),
        },
    }
    return driver_config


# docs fencepost end: DO NOT REMOVE
