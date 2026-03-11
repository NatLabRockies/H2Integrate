"""
Pytest configuration file.
"""

import os
import shutil

import pytest

from h2integrate.resource.utilities.nlr_developer_api_keys import set_nlr_key_dot_env


def pytest_sessionstart(session):
    initial_om_report_setting = os.getenv("OPENMDAO_REPORTS")
    if initial_om_report_setting is not None:
        os.environ["TMP_OPENMDAO_REPORTS"] = initial_om_report_setting

    os.environ["OPENMDAO_REPORTS"] = "none"

    # Set a dummy API key
    os.environ["NLR_API_KEY"] = "a" * 40
    set_nlr_key_dot_env()

    # Set RESOURCE_DIR to None so pulls example files from default DIR
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

    initial_om_report_setting = os.getenv("TMP_OPENMDAO_REPORTS")
    if initial_om_report_setting is not None:
        os.environ["OPENMDAO_REPORTS"] = initial_om_report_setting
    os.environ.pop("TMP_OPENMDAO_REPORTS", None)


def pytest_collection_modifyitems(config, items):
    """Enforce the usage marking tests as either unit, regression, or integration tests.
    This method will need to be imported into all subsequent ``contest.py`` files.
    """
    test_types = {"unit", "regression", "integration"}
    missing_type_mark = [
        f"{item.path}::{item.name}"
        for item in items
        if not test_types.intersection([el.name for el in item.iter_markers()])
    ]
    if missing_type_mark:
        errors = "\n".join(missing_type_mark)
        msg = (
            "The following tests must be marked as either 'unit', 'regression', or 'integration'"
            f" tests using `@pytest.mark.<test-type>`:\n{errors}"
        )
        raise pytest.UsageError(msg)


@pytest.fixture(scope="module")
def temp_dir(tmp_path_factory):
    """Temp directory for YAML outputs."""
    temp_dir = tmp_path_factory.mktemp("temp_dir")
    yield temp_dir
    shutil.rmtree(str(temp_dir))
