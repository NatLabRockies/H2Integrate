import pytest

from test.conftest import temp_dir, pytest_collection_modifyitems  # noqa: F401


@pytest.fixture
def plant_config(n_timesteps):
    plant = {
        "plant": {
            "plant_life": 30,
            "simulation": {
                "dt": 3600,
                "n_timesteps": n_timesteps,
            },
        },
    }
    return plant
