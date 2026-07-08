import os
from pathlib import Path

import pytest

from h2integrate.core.env_tools import get_environment_var


# @pytest.fixture(scope="function")
# def temp_environment_var():
#     """Temporarily set the `RESOURCE_DIR` environment variable to example 11's weather folder."""
#     # NOTE: changes to this fixture can result in hard-to-debug test failures
#     # in tests for resource components. Please do not modify this fixture if possible!
#     resource_dir = str(EXAMPLE_DIR / "11_hybrid_energy_plant" / "tech_inputs" / "weather")
#     original = os.environ.get("RESOURCE_DIR")
#     os.environ["RESOURCE_DIR"] = resource_dir
#     yield resource_dir
#     os.environ.pop("RESOURCE_DIR", None)
#     assert os.getenv("RESOURCE_DIR") is None
#     if original is not None:
#         os.environ["RESOURCE_DIR"] = original

xx_test_env_var_xx = ""


def setter_getter_method(var_value):
    global xx_test_env_var_xx
    if var_value is not None:
        xx_test_env_var_xx = var_value
    return xx_test_env_var_xx


@pytest.mark.unit
def test_set_environment_var(subtests):
    with subtests.test("Initialized Properly"):
        assert xx_test_env_var_xx == ""

    setter_getter_method(var_value="testing_set_environment_var")
    with subtests.test("Set to long string"):
        assert xx_test_env_var_xx == "testing_set_environment_var"

    setter_getter_method(var_value=None)
    with subtests.test("Unchanged when var_value is None"):
        assert xx_test_env_var_xx == "testing_set_environment_var"

    setter_getter_method(var_value="")
    with subtests.test("Set to empty string"):
        assert xx_test_env_var_xx == ""


@pytest.mark.unit
def test_get_environment_var_dot_env_provided_path(temp_dir, subtests):
    """
    Test when an environment variable is set using a .env file and
    the path to the .env file is specified. This tests `set_env_var_dot_env`
    when using the `dotenv.load_dotenv()` method to load the environment variables
    from a .env file with a specified path.
    """

    with subtests.test("Initialized Properly"):
        assert xx_test_env_var_xx == ""

    env_path = temp_dir / ".env"
    with env_path.open("w+") as file:
        file.write("TESTING_ENV=provided_a_path\n")

    get_environment_var(
        setter_getter_method, "TESTING_ENV", varname_old="TEST_ENV_OLD", env_path=env_path
    )

    with subtests.test("Global variable was set"):
        assert xx_test_env_var_xx == "provided_a_path"

    setter_getter_method(var_value="")


@pytest.mark.unit
def test_get_environment_var_with_fallback(subtests):
    """
    Test when an environment variable value is accessed using `_get_env_with_fallback()`.
    The global environment variable itself is unmodified (its not set).
    """
    # below tests the get env var where it should run _get_env_with_fallback
    # which doesnt set the environment variable
    with subtests.test("Initialized Properly"):
        assert xx_test_env_var_xx == ""

    os.environ["TEST_ENV"] = "none"
    env_var_val = get_environment_var(setter_getter_method, "TEST_ENV", "TEST_ENV_OLD")

    with subtests.test("Returned TEST_ENV"):
        assert env_var_val == "none"

    os.environ.pop("TEST_ENV", None)
    with subtests.test("global didnt change (unsure if this is OK)"):
        assert xx_test_env_var_xx == ""


@pytest.mark.unit
def test_get_environment_var_dot_env(temp_dir, subtests):
    """
    Test when an environment variable is set using a .env file and
    the path to the .env file is NOT specified. This tests `set_env_var_dot_env`
    when using the `dotenv.load_dotenv()` method to load the environment variables
    from a .env file in one of the default possible locations (current working directory).
    """
    current_dir = Path.cwd()

    os.chdir(temp_dir)

    env_path = temp_dir / ".env"
    set_str = "did_not_provide_a_path"
    with env_path.open("w+") as file:
        file.write(f"TEST_ENV_OLD={set_str}\n")

    tmp_dir_path = Path.cwd() / ".env"
    with subtests.test("env file exists"):
        assert tmp_dir_path.is_file()

    get_environment_var(
        setter_getter_method, "NOT_REAL_ENV", varname_old="TEST_ENV_OLD", env_path=None
    )

    with subtests.test("Global variable was set"):
        assert xx_test_env_var_xx == set_str

    with subtests.test("Global variable was set #2"):
        retrieved_val = setter_getter_method(var_value=None)
        assert retrieved_val == set_str

    os.chdir(current_dir)
    setter_getter_method(var_value="")


@pytest.mark.unit
def test_get_environment_var_env_suffix_file(temp_dir, subtests):
    """
    Test when an environment variable is set using a file with a .env suffix and
    the path to the file is specified. This tests `set_env_var_dot_env`
    when using the `load_file_with_variables()` method to load the environment variables
    from a file with a specified path.
    """
    current_dir = Path.cwd()

    os.chdir(temp_dir)

    env_key = "TESTING_ENVIRONMENT_KEY"
    set_str = str(temp_dir)  # set the value to the temp dir name

    env_path = temp_dir / "vars.env"

    with env_path.open("w+") as file:
        file.write(f"{env_key}={set_str}\n")

    tmp_dir_path = Path.cwd() / "vars.env"

    with subtests.test("env file exists"):
        assert tmp_dir_path.is_file()

    with subtests.test("Global variable starts as empty"):
        assert xx_test_env_var_xx == ""

    get_environment_var(setter_getter_method, env_key, varname_old=None, env_path=env_path)

    with subtests.test("Global variable was set"):
        assert xx_test_env_var_xx == set_str

    with subtests.test("Global variable was set #2"):
        retrieved_val = setter_getter_method(var_value=None)
        assert retrieved_val == set_str

    os.chdir(current_dir)
