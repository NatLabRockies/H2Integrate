import os
from pathlib import Path

import pytest

from h2integrate.core.env_tools import (
    set_env_var,
    load_env_vars_from_file,
    get_environment_variables,
)


@pytest.fixture(scope="function")
def temp_env_var(credential_value: str):
    """Temporarily set the `RESOURCE_DIR` environment variable to example 11's weather folder."""
    # NOTE: changes to this fixture can result in hard-to-debug test failures
    # in tests for resource components. Please do not modify this fixture if possible!

    original = os.environ.get("TEST_CREDENTIAL")
    os.environ["TEST_CREDENTIAL"] = credential_value
    yield credential_value
    os.environ.pop("TEST_CREDENTIAL", None)
    assert os.getenv("TEST_CREDENTIAL") is None
    if original is not None:
        os.environ["TEST_CREDENTIAL"] = original


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
        file.write("TEST_CREDENTIAL=my_credential_value\n")

    env_vars = load_env_vars_from_file(file_path=env_path)
    with subtests.test("Read using = seperator"):
        assert env_vars["TEST_CREDENTIAL"] == "my_credential_value"

    # add another variable to the file
    with env_path.open("a+") as file:
        file.write("TEST_CREDENTIAL_B=testing@yahoo.fake\n")

    env_vars = load_env_vars_from_file(env_path)
    with subtests.test("Two credential with = seperator (TEST_CREDENTIAL)"):
        assert env_vars["TEST_CREDENTIAL"] == "my_credential_value"
    with subtests.test("Two credential with = seperator (TEST_CREDENTIAL_B)"):
        assert env_vars["TEST_CREDENTIAL_B"] == "testing@yahoo.fake"

    # add a line without a separator to the file and a line using a different separator
    with env_path.open("a+") as file:
        file.write("TEST_CREDENTIAL_C_IS_A_SENTENCE\nTEST_CREDENTIAL_D : testingValue\n")

    env_vars = load_env_vars_from_file(env_path)
    with subtests.test("Empty line and mixed separators (TEST_CREDENTIAL)"):
        assert env_vars["TEST_CREDENTIAL"] == "my_credential_value"
    with subtests.test("Empty line and mixed separators (TEST_CREDENTIAL_B)"):
        assert env_vars["TEST_CREDENTIAL_B"] == "testing@yahoo.fake"
    with subtests.test("Empty line and mixed separators (TEST_CREDENTIAL_D)"):
        assert env_vars["TEST_CREDENTIAL_D"] == "testingValue"
    with subtests.test("Empty line and mixed separators (skipped sentence line)"):
        extra_vars = set(env_vars) - {"TEST_CREDENTIAL", "TEST_CREDENTIAL_B", "TEST_CREDENTIAL_D"}
        assert len(extra_vars) == 0


@pytest.mark.unit
@pytest.mark.parametrize("credential_value", ["new_value"])
def test_get_environment_variables_already_set(subtests, temp_env_var):
    with subtests.test("TEST_CREDENTIAL environment variable (starting)"):
        assert os.environ.get("TEST_CREDENTIAL") == "new_value"

    with subtests.test("NLR_API_KEY environment variable (starting)"):
        assert os.environ.get("NLR_API_KEY") == "a" * 40

    env_vars = get_environment_variables("TEST_CREDENTIAL", "NLR_API_KEY", set_variables=False)

    with subtests.test("TEST_CREDENTIAL returned"):
        assert env_vars["TEST_CREDENTIAL"] == "new_value"

    with subtests.test("NLR_API_KEY returned"):
        assert env_vars["NLR_API_KEY"] == "a" * 40

    with subtests.test("TEST_CREDENTIAL environment variable (ending)"):
        assert os.environ.get("TEST_CREDENTIAL") == "new_value"

    with subtests.test("NLR_API_KEY environment variable (ending)"):
        assert os.environ.get("NLR_API_KEY") == "a" * 40


@pytest.mark.unit
def test_get_environment_variables_from_filepath(subtests, temp_dir):
    env_path = temp_dir / "myapi.env"

    os.environ.pop("TEST_CREDENTIAL_A", None)
    os.environ.pop("TEST_CREDENTIAL_B", None)

    env_file_txt = f"TEST_CREDENTIAL_A={temp_dir}\nTEST_CREDENTIAL_B=bees\n"

    with env_path.open("w+") as file:
        file.write(env_file_txt)

    # started off not as environment variable
    with subtests.test("TEST_CREDENTIAL_A not an environment variable"):
        assert os.environ.get("TEST_CREDENTIAL_A") is None

    with subtests.test("TEST_CREDENTIAL_B not an environment variable"):
        assert os.environ.get("TEST_CREDENTIAL_B") is None

    # values pulled from file
    env_vars = get_environment_variables(
        "TEST_CREDENTIAL_A", "TEST_CREDENTIAL_B", file_path=env_path, set_variables=False
    )

    with subtests.test("TEST_CREDENTIAL_A value"):
        assert env_vars["TEST_CREDENTIAL_A"] == str(temp_dir)

    with subtests.test("TEST_CREDENTIAL_B value"):
        assert env_vars["TEST_CREDENTIAL_B"] == "bees"

    # were not set as environment variables
    with subtests.test("TEST_CREDENTIAL_A not set"):
        assert os.environ.get("TEST_CREDENTIAL_A") is None

    with subtests.test("TEST_CREDENTIAL_B not set"):
        assert os.environ.get("TEST_CREDENTIAL_B") is None


@pytest.mark.unit
def test_get_environment_variables_from_default_folder(subtests, temp_dir):
    """Specify the file_name arg but not the filepath"""

    os.environ.pop("TEST_CREDENTIAL_A", None)
    os.environ.pop("TEST_CREDENTIAL_B", None)

    # started off not as environment variable
    with subtests.test("TEST_CREDENTIAL_A not an environment variable"):
        assert os.environ.get("TEST_CREDENTIAL_A") is None

    with subtests.test("TEST_CREDENTIAL_B not an environment variable"):
        assert os.environ.get("TEST_CREDENTIAL_B") is None

    current_dir = Path.cwd()

    os.chdir(temp_dir)

    env_path = temp_dir / "myfile.env"

    env_file_txt = f"TEST_CREDENTIAL_A={temp_dir}\nTEST_CREDENTIAL_B=howdyFolks\n"
    env_file_txt += "TEST_CREDENTIAL_C=i<3H2I\n"

    with env_path.open("w+") as file:
        file.write(env_file_txt)

    env_vars = get_environment_variables(
        "TEST_CREDENTIAL_A", "TEST_CREDENTIAL_B", file_name="myfile.env", set_variables=False
    )

    with subtests.test("TEST_CREDENTIAL_A value"):
        assert env_vars["TEST_CREDENTIAL_A"] == str(temp_dir)

    with subtests.test("TEST_CREDENTIAL_B value"):
        assert env_vars["TEST_CREDENTIAL_B"] == "howdyFolks"

    # were not set as environment variables
    with subtests.test("TEST_CREDENTIAL_A not set"):
        assert os.environ.get("TEST_CREDENTIAL_A") is None

    with subtests.test("TEST_CREDENTIAL_B not set"):
        assert os.environ.get("TEST_CREDENTIAL_B") is None

    os.chdir(current_dir)


@pytest.mark.unit
def test_get_environment_variables_from_default_cwd(subtests, temp_dir):
    os.environ.pop("TEST_CREDENTIAL_B", None)
    os.environ.pop("TEST_CREDENTIAL_C", None)

    # started off not as environment variable
    with subtests.test("TEST_CREDENTIAL_B not an environment variable"):
        assert os.environ.get("TEST_CREDENTIAL_B") is None

    with subtests.test("TEST_CREDENTIAL_B not an environment variable"):
        assert os.environ.get("TEST_CREDENTIAL_C") is None

    current_dir = Path.cwd()

    os.chdir(temp_dir)

    env_path = temp_dir / ".env"

    env_file_txt = f"TEST_CREDENTIAL_A={temp_dir}\nTEST_CREDENTIAL_B=byeFolks\n"
    env_file_txt += "TEST_CREDENTIAL_C=i<3H2I\n"

    with env_path.open("w+") as file:
        file.write(env_file_txt)

    env_vars = get_environment_variables(
        "TEST_CREDENTIAL_B", "TEST_CREDENTIAL_C", set_variables=True
    )

    with subtests.test("TEST_CREDENTIAL_B value"):
        assert env_vars["TEST_CREDENTIAL_B"] == "byeFolks"

    with subtests.test("TEST_CREDENTIAL_C value"):
        assert env_vars["TEST_CREDENTIAL_C"] == "i<3H2I"

    # were not set as environment variables
    with subtests.test("TEST_CREDENTIAL_B set as environment variable"):
        assert os.environ.get("TEST_CREDENTIAL_B") == "byeFolks"

    with subtests.test("TEST_CREDENTIAL_C set as environment variable"):
        assert os.environ.get("TEST_CREDENTIAL_C") == "i<3H2I"

    os.chdir(current_dir)
