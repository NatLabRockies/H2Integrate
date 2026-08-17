"""
Pytest configuration file.
"""

import os

from test.conftest import (  # noqa: F401
    temp_dir,
    temp_copy_of_example,
    pytest_collection_modifyitems,
)


def pytest_sessionstart(session):
    initial_om_report_setting = os.getenv("OPENMDAO_REPORTS")
    if initial_om_report_setting is not None:
        os.environ["TMP_OPENMDAO_REPORTS"] = initial_om_report_setting

    os.environ["OPENMDAO_REPORTS"] = "none"

    initial_feedstock_dir = os.getenv("FEEDSTOCK_DIR")
    # if user provided a feedstock directory, save it to a temp variable
    # this allows tests to run as expected while not causing
    # unexpected behavior afterwards
    if initial_feedstock_dir is not None:
        os.environ["TEMP_FEEDSTOCK_DIR"] = f"{initial_feedstock_dir}"

    os.environ.pop("FEEDSTOCK_DIR", None)


def pytest_sessionfinish(session, exitstatus):
    # if user provided a feedstock directory, load it from the temp variable
    # and reset the original environment variable
    # this prevents unexpected behavior after running tests
    user_dir = os.getenv("TEMP_FEEDSTOCK_DIR")
    if user_dir is not None:
        os.environ["FEEDSTOCK_DIR"] = user_dir
    os.environ.pop("TEMP_FEEDSTOCK_DIR", None)

    initial_om_report_setting = os.getenv("TMP_OPENMDAO_REPORTS")
    if initial_om_report_setting is not None:
        os.environ["OPENMDAO_REPORTS"] = initial_om_report_setting
    os.environ.pop("TMP_OPENMDAO_REPORTS", None)
