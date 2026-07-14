import os
from pathlib import Path

from h2integrate import ROOT_DIR


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
    that uses either a ``key=value` or `key:value` format for storing data.

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
                # skip this line
                continue
            k, v = line.strip().split(sep, 1)
            env_vars[k.strip()] = v.strip()
    return env_vars


def get_environment_variables(
    *args: str,
    file_name: str | None = None,
    file_path: str | None = None,
    set_variables: bool = True,
):
    """Retrieve a series of credentials from a :py:attr:`file_name` in either the home directory
    or H2Integrate root directory. If `:py:attr:`file_path` is provided, then :py:attr:`file_name`
    and already set environment variables will be ignored. If :py:attr:`file_name` is provided, then
    already set environment variables will be ignored. If neither file options are used, then an
    existing environment variable will be retrieved.

    Args:
        args (str): Name(s) of the credential(s) that should be retrieved from either
            :py:attr:`file_name` or environment variables.
        file_name (str, optional): The name of a configuration file found in either the H2Integrate
            root directory or the user's home directory that should contain the credential(s) in
            :py:attr:`args`.
        file_path (str | Path, optional): The full file path for where the configuration file can be
        found if not using the H2Integrate root directory or user home directory
        set_variables (bool, optional): If True, set the environment variables if they
            haven't already been set.

    Returns:
        dict: Dictionary of all :py:attr:`args` with values of either the value if found.
    """
    # Check if the environment variables have already been set
    env_vars = {name: os.environ.get(name) for name in args if os.environ.get(name) is not None}
    remaining_vars = set(env_vars) - set(args)
    if len(remaining_vars) == 0:
        # All environment variables have already been set
        return env_vars

    if file_path is not None:
        file_path = Path(file_path).resolve()
        if file_path.is_file():
            env_vars = load_env_vars_from_file(file_path)
            env_vars_subset = {name: env_vars.get(name) for name in args if name in env_vars}
            if set_variables:
                # Set the environment variables
                set_env_var(overwrite=True, **env_vars_subset)
            return env_vars_subset

        raise FileNotFoundError(f"Provided `file_path` is invalid: {file_path}")

    default_folders = [Path.cwd(), Path.home(), ROOT_DIR, ROOT_DIR.parent]
    if file_name is None:
        # If a file_name isn't provided, look for a .env file
        file_name = ".env"

    for folder in default_folders:
        if (file_path := (folder / file_name)).is_file():
            env_vars |= load_env_vars_from_file(file_path)

    env_vars_subset = {name: env_vars.get(name) for name in args if name in env_vars}
    if set_variables:
        # Set the environment variables
        set_env_var(overwrite=True, **env_vars_subset)
    return env_vars_subset
