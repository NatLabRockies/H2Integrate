import os

from hopp import TEST_ENV_VAR

from test.conftest import temp_dir, pytest_collection_modifyitems  # noqa: F401


def pytest_sessionstart(session):
    os.environ["ENV"] = TEST_ENV_VAR

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
