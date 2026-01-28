"""
Pytest configuration file.
"""

import os


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
