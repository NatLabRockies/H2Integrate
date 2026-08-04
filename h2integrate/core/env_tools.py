import os
import warnings
from pathlib import Path

from h2integrate import ROOT_DIR


def _check_duplicate_environment_vars(
    *args: str, original_env_vars: dict, new_env_vars: dict
) -> set:
    """Check if any environment variables are defined twice and if so,
    check for any mismatched values.

    Args:
        args (str): Name(s) of the environment variable(s) that should be retrieved from
            environment variable dictionaries
        original_env_vars (dict): dictionary of previously loaded environment variables
        new_env_vars (dict): dictionary of additionally loaded environment variables

    Returns:
        set: environment variables that exist in both environment variable
            dictionaries and have different values
    """

    # common variables between both sets of variables
    shared_vars = set(original_env_vars) & set(new_env_vars)
    if not shared_vars:
        # return empty set
        return shared_vars
    # args that are shared variables
    shared_args = set(args) & shared_vars
    if not shared_args:
        # return empty set, no duplicate args
        return shared_args
    # Check if theres a value mismatch between shared args
    mismatched_args = set()
    for arg in list(shared_args):
        if original_env_vars[arg] != new_env_vars[arg]:
            mismatched_args.add(arg)
    return mismatched_args


def set_env_var(*, overwrite: bool = False, **kwargs: str):
    """Set or overwrite environment variables.

    Args:
        overwrite (bool, optional): Indicator to overwrite existing environment variables provided
            in :py:attr:`kwargs`. Defaults to False.
        kwargs (str): name and value of environment variables to set. If :py:attr:`overwrite` is
            False, the value will be skipped.
    """
    for name, value in kwargs.items():
        if os.environ.get(name) is not None and not overwrite:
            continue
        os.environ[name] = value


def load_env_vars_from_file(file_path: Path) -> dict:
    """Load any dictionary-like key, value pairs from a configuration file (e.g. .env or .cdsapirc)
    that uses either a ``key=value`` or ``key:value`` format for storing data.

    Args:
        file_path (Path): The full file path and name containing configuration details to be
            extracted.

    Returns:
        dict: Dictionary of key, value pairs found in :py:attr:`file_path`.
    """

    if isinstance(file_path, str):
        file_path = Path(file_path).resolve()
    env_vars = {}
    if not file_path.is_file():
        return env_vars
    with file_path.open("r") as f:
        for line in f.readlines():
            if "=" in line:
                sep = "="
            elif ":" in line:
                sep = ":"
            else:
                # skip line if invalid or missing separator
                continue
            k, v = line.strip().split(sep, 1)
            env_vars[k.strip()] = v.strip()
    return env_vars


def get_environment_variables(
    *args: str,
    file_name: str | None = ".env",
    file_path: str | None = None,
    set_variables: bool = True,
):
    """Retrieve a series of environment variables and values from existing environment variables,
    from a fully resolved :py:attr:`file_path`, or from a :py:attr:`file_name` located in either
    the home directory, H2Integrate root directory, or the current working directory.

    This function does the following:

    1) Check the existing environment variables for :py:attr:`args`. If any :py:attr:`args`
    have not yet been set as environment variables, continue to 2.

    2) If :py:attr:`file_path` is provided, then load environment variables from
    :py:attr:`file_path`. If :py:attr:`set_variables` is True, then set the environment
    variables that were found. Return the environment variables found up to this point.
    If :py:attr:`file_path` is None, continue to 3.

    3) Check default directories (home directory, H2Integrate root directory, or the current
    working directory) for :py:attr:`file_name` and load environment variables if the filepath
    is valid. This prioritizes environment variable values found in step 1 over environment
    variables loaded from the files. If :py:attr:`set_variables` is True, then
    set the environment variables that were found. Return the environment variables found
    up to this point.

    Args:
        args (str): Name(s) of the environment variable(s) that should be retrieved from
            environment variables, :py:attr:`file_path` or a default location of
            :py:attr:`file_name`.
        file_name (str, optional): The name of a configuration file found in either the H2Integrate
            root directory, the user's home directory, or the user's current working directory
            that should contain the environment variable(s) in :py:attr:`args`. Defaults to '.env'.
        file_path (str | Path, optional): The full file path for where the configuration file can be
            found if not using one of the default directories.
        set_variables (bool, optional): If True, set the environment variables if they
            haven't already been set.

    Returns:
        dict: Dictionary of the :py:attr:`args` that values were found for.
    """
    # Step 1: Get existing environment variables
    # Check if the environment variables have already been set
    env_vars = {name: var for name in args if (var := os.environ.get(name)) is not None}
    remaining_vars = set(args) - set(env_vars)
    if not remaining_vars:
        # All environment variables have already been set
        return env_vars

    # Step 2: Load environment variables from `file_path`
    if file_path is not None:
        file_path = Path(file_path).resolve()
        if file_path.is_file():
            # Prioritize environment variables from specified `file_path`
            env_vars |= load_env_vars_from_file(file_path)
            # Remove extraneous environment variables that were loaded from the file
            env_vars_subset = {name: env_vars.get(name) for name in args if name in env_vars}
            if set_variables:
                # Set the environment variables
                set_env_var(overwrite=True, **env_vars_subset)
            # NOTE: should we check here if all the environment variables were found?
            # Should the next part of the code execute if theres remaining
            # environment variables?
            return env_vars_subset

        raise FileNotFoundError(f"Provided `file_path` is invalid: {file_path}")

    # Step 3: Look in the cwd, home directory, and H2Integrate ROOT folders for `file_name`
    default_folders = [ROOT_DIR, ROOT_DIR.parent, Path.cwd(), Path.home()]
    if file_name is None:
        # If a file_name isn't provided, look for a .env file
        file_name = ".env"

    for folder in default_folders:
        if (file_path := (folder / file_name)).is_file():
            # Prioritize environment variables that have already been set
            env_vars_from_file = load_env_vars_from_file(file_path)
            mismatched_vars = _check_duplicate_environment_vars(
                *args, original_env_vars=env_vars, new_env_vars=env_vars_from_file
            )
            if mismatched_vars:
                mismatched_txt = "\n".join(
                    f"Environment variable '{mis_var}' set to '{env_vars_from_file[mis_var]}' in "
                    f"file {file_path!s} but set as value '{env_vars[mis_var]}' earlier."
                    for mis_var in mismatched_vars
                )
                msg = (
                    f"Mismatched values found for environment variable(s) {list(mismatched_vars)}. "
                    f"{mismatched_txt}. Values loaded from file {file_path} will not be used."
                )
                warnings.warn(msg, UserWarning, stacklevel=3)

            env_vars = env_vars_from_file | env_vars

    # Remove extraneous environment variables that were loaded from file(s)
    env_vars_subset = {name: env_vars.get(name) for name in args if name in env_vars}
    if set_variables:
        # Set the environment variables
        set_env_var(overwrite=True, **env_vars_subset)
    return env_vars_subset
