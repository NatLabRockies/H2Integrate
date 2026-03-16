from pytest import fixture

from h2integrate import EXAMPLE_DIR
from h2integrate.core.inputs.validation import load_driver_yaml

from test.conftest import temp_dir, pytest_collection_modifyitems  # noqa: F401


@fixture
def driver_config():
    driver_config = load_driver_yaml(
        EXAMPLE_DIR / "21_iron_examples" / "iron_dri" / "driver_config.yaml"
    )
    return driver_config


@fixture
def plant_config():
    plant_config = {
        "plant": {
            "plant_life": 30,
            "simulation": {
                "n_timesteps": 8760,
                "dt": 3600,
            },
        },
        "finance_parameters": {
            "cost_adjustment_parameters": {
                "cost_year_adjustment_inflation": 0.025,
                "target_dollar_year": 2022,
            }
        },
    }
    return plant_config
