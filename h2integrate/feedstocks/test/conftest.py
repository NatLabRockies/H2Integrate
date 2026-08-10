"""
Pytest configuration file.
"""

import os

from h2integrate import EXAMPLE_DIR

from test.conftest import (  # noqa: F401
    temp_dir,
    temp_dir_module,
    temp_copy_of_example,
    pytest_collection_modifyitems,
    temp_copy_of_example_module_scope,
)


def pytest_sessionstart(session):
    initial_om_report_setting = os.getenv("OPENMDAO_REPORTS")
    if initial_om_report_setting is not None:
        os.environ["TMP_OPENMDAO_REPORTS"] = initial_om_report_setting

    os.environ["OPENMDAO_REPORTS"] = "none"

    # set environment variables used for
    # tests in h2integrate/core/test/test_recorder.py
    os.environ["TEST_RECORDER_OUTPUT_EXAMPLE"] = "05_wind_h2_opt"
    os.environ["TEST_RECORDER_OUTPUT_DIR"] = "testingtesting_output_dir"
    os.environ["TEST_RECORDER_OUTPUT_FILE0"] = "testingtesting_filename.sql"
    os.environ["TEST_RECORDER_OUTPUT_FILE1"] = "testingtesting_filename0.sql"
    os.environ["TEST_RECORDER_OUTPUT_FILE2"] = "testingtesting_filename1.sql"


def pytest_sessionfinish(session, exitstatus):
    initial_om_report_setting = os.getenv("TMP_OPENMDAO_REPORTS")
    if initial_om_report_setting is not None:
        os.environ["OPENMDAO_REPORTS"] = initial_om_report_setting
    os.environ.pop("TMP_OPENMDAO_REPORTS", None)

    # remove files that were created in h2integrate/core/test/test_recorder.py
    if os.getenv("TEST_RECORDER_OUTPUT_EXAMPLE") is not None:
        test_dir = (
            EXAMPLE_DIR
            / os.getenv("TEST_RECORDER_OUTPUT_EXAMPLE")
            / os.getenv("TEST_RECORDER_OUTPUT_DIR")
        )
        file0path = test_dir / os.getenv("TEST_RECORDER_OUTPUT_FILE0")
        file1path = test_dir / os.getenv("TEST_RECORDER_OUTPUT_FILE1")
        file2path = test_dir / os.getenv("TEST_RECORDER_OUTPUT_FILE2")
        if file0path.exists():
            file0path.unlink()
        if file1path.exists():
            file1path.unlink()
        if file2path.exists():
            file2path.unlink()
        # remove folder created in h2integrate/core/test/test_recorder.py
        if test_dir.exists():
            files_in_test_folder = list(test_dir.iterdir())
            if len(files_in_test_folder) == 0:
                test_dir.rmdir()

        # remove environment variables used for tests in
        # h2integrate/core/test/test_recorder.py
        os.environ.pop("TEST_RECORDER_OUTPUT_EXAMPLE", None)
        os.environ.pop("TEST_RECORDER_OUTPUT_DIR", None)
        os.environ.pop("TEST_RECORDER_OUTPUT_FILE0", None)
        os.environ.pop("TEST_RECORDER_OUTPUT_FILE1", None)
        os.environ.pop("TEST_RECORDER_OUTPUT_FILE2", None)
