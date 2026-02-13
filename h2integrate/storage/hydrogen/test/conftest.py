"""
Pytest configuration file.
"""

import os

from h2integrate.storage.test.conftest import plant_config  # noqa: F401

from test.conftest import temp_dir, pytest_collection_modifyitems  # noqa: F401


def pytest_sessionstart(session):
    initial_om_report_setting = os.getenv("OPENMDAO_REPORTS")
    if initial_om_report_setting is not None:
        os.environ["TMP_OPENMDAO_REPORTS"] = initial_om_report_setting

    os.environ["OPENMDAO_REPORTS"] = "none"


def pytest_sessionfinish(session, exitstatus):
    initial_om_report_setting = os.getenv("TMP_OPENMDAO_REPORTS")
    if initial_om_report_setting is not None:
        os.environ["OPENMDAO_REPORTS"] = initial_om_report_setting
    os.environ.pop("TMP_OPENMDAO_REPORTS", None)
