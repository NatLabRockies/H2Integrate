import pytest

from h2integrate import EXAMPLE_DIR

from test.conftest import temp_dir, pytest_collection_modifyitems  # noqa: F401


@pytest.fixture
def plant_config():
    plant = {
        "plant": {
            "plant_life": 30,
            "simulation": {
                "dt": 3600,
                "n_timesteps": 8760,
                "start_time": "01/01/1900 00:30:00",
                "timezone": 0,
            },
        },
        "site": {"latitude": 30.6617, "longitude": -101.7096, "resources": {}},
    }

    return plant


@pytest.fixture
def solar_resource_dict():
    pv_resource_dir = EXAMPLE_DIR / "11_hybrid_energy_plant" / "tech_inputs" / "weather" / "solar"
    pv_filename = "30.6617_-101.7096_psmv3_60_2013.csv"
    pv_resource_dict = {
        "resource_year": 2013,
        "resource_dir": pv_resource_dir,
        "resource_filename": pv_filename,
    }
    return pv_resource_dict
