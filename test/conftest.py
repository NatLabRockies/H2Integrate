"""
Pytest configuration file.
"""

import os

from h2integrate.resource.utilities.nrel_developer_api_keys import set_nrel_key_dot_env


def pytest_sessionstart(session):
    initial_om_report_setting = os.getenv("OPENMDAO_REPORTS")
    if initial_om_report_setting is not None:
        os.environ["TMP_OPENMDAO_REPORTS"] = initial_om_report_setting

    os.environ["OPENMDAO_REPORTS"] = "none"

    # Set a dummy API key
    os.environ["NREL_API_KEY"] = "a" * 40
    set_nrel_key_dot_env()

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
