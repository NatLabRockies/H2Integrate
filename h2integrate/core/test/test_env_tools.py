import os
from contextlib import chdir

import pytest

from h2integrate.core.env_tools import (
    set_env_var,
    load_env_vars_from_file,
    get_environment_variables,
    _check_duplicate_environment_vars,
)


@pytest.fixture(scope="function")
def temp_env_var(credential_value: str):
    """Temporarily set the `TEST_CREDENTIAL` environment variable"""
    # NOTE: changes to this fixture can result in hard-to-debug test failures
    # in tests for environment variables components. Please do not modify this fixture if possible!

    original = os.environ.get("TEST_CREDENTIAL")
    os.environ["TEST_CREDENTIAL"] = credential_value
    yield credential_value
    os.environ.pop("TEST_CREDENTIAL", None)
    assert os.getenv("TEST_CREDENTIAL") is None
    if original is not None:
        os.environ["TEST_CREDENTIAL"] = original


@pytest.mark.unit
def test_duplicate_defined_environment_vars(subtests):
    env_vars0 = {
        "A": "alphabet",
        "B": "numbers",
    }

    # Check that an empty set is returned when values match
    duplicate_vars = _check_duplicate_environment_vars(
        "A", "B", original_env_vars=env_vars0, new_env_vars=env_vars0
    )
    with subtests.test("No mismatched shared variable values"):
        assert not bool(duplicate_vars)

    env_vars1 = {
        "A": "alpha-bet",
        "B": "numbers",
    }

    # Check that mismatched variables are returned without a match
    duplicate_vars = _check_duplicate_environment_vars(
        "A", "B", original_env_vars=env_vars0, new_env_vars=env_vars1
    )
    with subtests.test("A has mismatched values"):
        assert len(duplicate_vars) == 1
        assert list(duplicate_vars)[0] == "A"

    # Check that an empty set is returned when specified variable matches
    duplicate_vars = _check_duplicate_environment_vars(
        "B", original_env_vars=env_vars0, new_env_vars=env_vars1
    )
    with subtests.test("No mismatched shared args"):
        assert not bool(duplicate_vars)


@pytest.mark.unit
@pytest.mark.parametrize("credential_value", ["none"])
def test_set_environment_var(subtests, temp_env_var):
    with subtests.test("Environment variable set"):
        assert os.environ["TEST_CREDENTIAL"] == "none"

    kwargs = {"TEST_CREDENTIAL": "updated"}
    set_env_var(overwrite=True, **kwargs)

    with subtests.test("Environment variable updated"):
        assert os.environ["TEST_CREDENTIAL"] == "updated"

    kwargs = {"TEST_CREDENTIAL": "overwritten"}
    set_env_var(overwrite=False, **kwargs)
    with subtests.test("Environment variable not overwritten"):
        assert os.environ["TEST_CREDENTIAL"] == "updated"


@pytest.mark.unit
def test_load_env_vars_from_file(subtests, temp_dir):
    env_path = temp_dir / ".env"
    with env_path.open("w+") as file:
        file.write("TEST_CREDENTIAL=my_credential_value\n")  # = with no spaces
        file.write("TEST_CREDENTIAL_B=testing@yahoo.fake\n")  # = with spaces
        file.write("TEST_CREDENTIAL_C_IS_A_SENTENCE\n")  # should be skipped
        file.write("TEST_CREDENTIAL_D : testingValue\n")  # : with spaces
        file.write("TEST_CREDENTIAL_E :: another_credential\n")  # consecutive delimiter

    env_vars = load_env_vars_from_file(file_path=env_path)

    with subtests.test("Environment variable values"):
        # Four valid entries are loaded
        assert len(env_vars) == 4

        # Credential using an equals separator
        assert env_vars["TEST_CREDENTIAL"] == "my_credential_value"

        # Credential containing an at sign
        assert env_vars["TEST_CREDENTIAL_B"] == "testing@yahoo.fake"

        # Line without a separator is skipped
        assert "TEST_CREDENTIAL_C" not in env_vars

        # Credential using a colon separator with spaces
        assert env_vars["TEST_CREDENTIAL_D"] == "testingValue"

        # Credential using consecutive delimiters
        assert env_vars["TEST_CREDENTIAL_E"] == ": another_credential"


@pytest.mark.unit
@pytest.mark.parametrize("credential_value", ["new_value"])
def test_get_environment_variables_already_set(subtests, temp_env_var):
    with subtests.test("Environment variables are set before lookup"):
        assert os.environ.get("TEST_CREDENTIAL") == "new_value"
        assert os.environ.get("NLR_API_KEY") == "a" * 40

    env_vars = get_environment_variables("TEST_CREDENTIAL", "NLR_API_KEY", set_variables=False)

    with subtests.test("Environment variables are returned"):
        assert env_vars["TEST_CREDENTIAL"] == "new_value"
        assert env_vars["NLR_API_KEY"] == "a" * 40

    with subtests.test("Environment variables remain set after lookup"):
        assert os.environ.get("TEST_CREDENTIAL") == "new_value"
        assert os.environ.get("NLR_API_KEY") == "a" * 40


@pytest.mark.unit
def test_get_environment_variables_from_filepath(subtests, temp_dir):
    os.environ.pop("TEST_CREDENTIAL_A", None)
    os.environ.pop("TEST_CREDENTIAL_B", None)

    # environment variables were properly removed prior to rest of test
    with subtests.test("Environment variables are unset before lookup"):
        assert os.environ.get("TEST_CREDENTIAL_A") is None
        assert os.environ.get("TEST_CREDENTIAL_B") is None

    # Make a file containing credentials
    env_path = temp_dir / "myapi.env"
    env_file_txt = f"TEST_CREDENTIAL_A={temp_dir}\nTEST_CREDENTIAL_B=bees\n"

    with env_path.open("w+") as file:
        file.write(env_file_txt)

    # Get the environment variables but don't set them
    env_vars = get_environment_variables(
        "TEST_CREDENTIAL_A", "TEST_CREDENTIAL_B", file_path=env_path, set_variables=False
    )

    with subtests.test("Environment variables are returned from the file"):
        assert env_vars["TEST_CREDENTIAL_A"] == str(temp_dir)
        assert env_vars["TEST_CREDENTIAL_B"] == "bees"

    # Check that variables were not set as environment variables
    with subtests.test("Environment variables remain unset after lookup"):
        assert os.environ.get("TEST_CREDENTIAL_A") is None
        assert os.environ.get("TEST_CREDENTIAL_B") is None


@pytest.mark.unit
def test_get_environment_variables_from_default_folder(subtests, temp_dir):
    """Specify the file_name arg but not the filepath"""

    os.environ.pop("TEST_CREDENTIAL_A", None)
    os.environ.pop("TEST_CREDENTIAL_B", None)

    # environment variables were properly removed prior to rest of test
    with subtests.test("Environment variables are unset before lookup"):
        assert os.environ.get("TEST_CREDENTIAL_A") is None
        assert os.environ.get("TEST_CREDENTIAL_B") is None

    # Make a file containing credentials
    env_path = temp_dir / "myfile.env"

    env_file_txt = f"TEST_CREDENTIAL_A={temp_dir}\nTEST_CREDENTIAL_B=howdyFolks\n"
    env_file_txt += "TEST_CREDENTIAL_C=i<3H2I\n"

    with env_path.open("w+") as file:
        file.write(env_file_txt)

    # Change CWD to the temporary folder when loading environment variables
    # Get the environment variables but don't set them
    with chdir(temp_dir):
        env_vars = get_environment_variables(
            "TEST_CREDENTIAL_A", "TEST_CREDENTIAL_B", file_name="myfile.env", set_variables=False
        )

    with subtests.test("Environment variables are returned from the default folder"):
        assert env_vars["TEST_CREDENTIAL_A"] == str(temp_dir)
        assert env_vars["TEST_CREDENTIAL_B"] == "howdyFolks"

    # were not set as environment variables
    with subtests.test("Environment variables remain unset after lookup"):
        assert os.environ.get("TEST_CREDENTIAL_A") is None
        assert os.environ.get("TEST_CREDENTIAL_B") is None


@pytest.mark.unit
def test_get_environment_variables_from_default_cwd(subtests, temp_dir):
    os.environ.pop("TEST_CREDENTIAL_B", None)
    os.environ.pop("TEST_CREDENTIAL_C", None)

    # environment variables were properly removed prior to rest of test
    with subtests.test("Environment variables are unset before lookup"):
        assert os.environ.get("TEST_CREDENTIAL_B") is None
        assert os.environ.get("TEST_CREDENTIAL_C") is None

    # Create path to .env file and make the file
    env_path = temp_dir / ".env"

    env_file_txt = f"TEST_CREDENTIAL_A={temp_dir}\nTEST_CREDENTIAL_B=byeFolks\n"
    env_file_txt += "TEST_CREDENTIAL_C=i<3H2I\n"

    with env_path.open("w+") as file:
        file.write(env_file_txt)

    # Change CWD to the temporary folder when loading environment variables
    # Don't specify a filepath or filename
    # Get the environment variables and set them
    with chdir(temp_dir):
        env_vars = get_environment_variables(
            "TEST_CREDENTIAL_B", "TEST_CREDENTIAL_C", set_variables=True
        )

    # credentials were found and returned
    with subtests.test("Environment variables are returned from the default file"):
        assert env_vars["TEST_CREDENTIAL_B"] == "byeFolks"
        assert env_vars["TEST_CREDENTIAL_C"] == "i<3H2I"

    # credentials were set as environment variables
    with subtests.test("Environment variables are set after lookup"):
        assert os.environ.get("TEST_CREDENTIAL_B") == "byeFolks"
        assert os.environ.get("TEST_CREDENTIAL_C") == "i<3H2I"

    # Change environment variable B to a new value
    os.environ["TEST_CREDENTIAL_B"] = "byeFriends"
    os.environ.pop("TEST_CREDENTIAL_C", None)
    expected_str = (
        f"Environment variable 'TEST_CREDENTIAL_B' set to 'byeFolks' in file "
        f"{env_path!s} but set as value 'byeFriends' earlier."
    )
    with subtests.test("Mismatched environment variables"):
        with chdir(temp_dir):
            with pytest.warns(UserWarning) as excinfo:
                env_vars = get_environment_variables(
                    "TEST_CREDENTIAL_B", "TEST_CREDENTIAL_C", set_variables=True
                )
            assert expected_str in str(excinfo.list[0].message)
