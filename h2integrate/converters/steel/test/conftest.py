import shutil

import pytest

from h2integrate import EXAMPLE_DIR
from h2integrate.core.inputs.validation import load_driver_yaml

from test.conftest import pytest_collection_modifyitems  # noqa: F401


@pytest.fixture(scope="module")
def temp_dir(tmp_path_factory):
    """Temp directory for YAML outputs."""
    temp_dir = tmp_path_factory.mktemp("temp_dir")
    yield temp_dir
    shutil.rmtree(str(temp_dir))


@pytest.fixture
def driver_config(temp_dir):
    driver_config = load_driver_yaml(EXAMPLE_DIR / "21_iron_mn_to_il" / "driver_config.yaml")
    driver_config["general"]["folder_output"] = temp_dir
    return driver_config
