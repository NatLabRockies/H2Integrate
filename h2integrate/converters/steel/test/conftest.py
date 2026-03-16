import pytest

from h2integrate import EXAMPLE_DIR
from h2integrate.core.inputs.validation import load_driver_yaml

from test.conftest import temp_dir, pytest_collection_modifyitems  # noqa: F401


@pytest.fixture
def driver_config(temp_dir):  # noqa: F811  # NOTE: no idea why this error is raised
    driver_config = load_driver_yaml(
        EXAMPLE_DIR / "21_iron_examples" / "iron_dri" / "driver_config.yaml"
    )
    driver_config["general"]["folder_output"] = temp_dir
    return driver_config
