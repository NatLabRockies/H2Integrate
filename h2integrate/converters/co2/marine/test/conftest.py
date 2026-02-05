import shutil

import pytest


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


@pytest.fixture
def tech_config():
    return {
        "model_inputs": {
            "performance_parameters": {
                "power_single_ed_w": 24000000.0,  # W
                "flow_rate_single_ed_m3s": 0.6,  # m^3/s
                "number_ed_min": 1,
                "number_ed_max": 10,
                "E_HCl": 0.05,  # kWh/mol
                "E_NaOH": 0.05,  # kWh/mol
                "y_ext": 0.9,
                "y_pur": 0.2,
                "y_vac": 0.6,
                "frac_ed_flow": 0.01,
                "use_storage_tanks": True,
                "initial_tank_volume_m3": 0.0,  # m^3
                "store_hours": 12.0,  # hours
                "sal": 33.0,  # ppt
                "temp_C": 12.0,  # degrees Celsius
                "dic_i": 0.0022,  # mol/L
                "pH_i": 8.1,  # initial pH
            },
        },
    }


@pytest.fixture(scope="module")
def driver_config(tmp_path_factory):
    temp_dir = tmp_path_factory.mktemp("output")
    driver_config = {
        "general": {
            "folder_output": str(temp_dir),
        },
    }
    yield driver_config
    shutil.rmtree(str(temp_dir))
