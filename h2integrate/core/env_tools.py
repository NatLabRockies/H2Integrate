import os
import warnings
from pathlib import Path

from dotenv import load_dotenv

from h2integrate import ROOT_DIR


_DEPRECATION_MSG = (
    "The '{old}' environment variable is deprecated and will be removed in a future release. "
    "Please use '{new}' instead. The nrel.gov API domain has moved to nlr.gov."
)


def _get_env_with_fallback(new_name, old_name):
    """Get an environment variable by its new name, falling back to the deprecated old name.

    If only the old name is set, a deprecation warning is issued.

    Args:
        new_name (str): The new (preferred) environment variable name.
        old_name (str): The deprecated environment variable name.

    Returns:
        str | None: The value of the environment variable, or None if not set.
    """
    # TODO: update so depr_msg is an input
    value = os.getenv(new_name)
    if value is not None:
        return value
    if old_name is None:
        return None
    value = os.getenv(old_name)
    if value is not None:
        warnings.warn(
            _DEPRECATION_MSG.format(old=old_name, new=new_name),
            FutureWarning,
            stacklevel=3,
        )
        return value
    return None


def set_environment_var(global_varname: str, var_value: str):
    """Set `var_value` as the global variable :py:attr:`global_varname`.

    Args:
        var_value (str): value to set for the environment variable
    """
    globals()[global_varname] = var_value
    return globals()[global_varname]


def load_file_with_variables(setter_method, fpath, variables: str | list[str]):
    """Load environment variables from a text file.

    Supports both the new ``NLR_API_*`` and the deprecated ``NREL_API_*`` variable
    names.  If only the old names are found in the file a deprecation warning is
    emitted.

    Args:
        fpath (str | Path): filepath to a text file with the extension '.env' that
            may contain the environment variable(s) in `variables`.
        variables (list | str, optional): environment variable(s) to load from file.
            Defaults to ["NLR_API_KEY", "NLR_API_EMAIL"].

    Raises:
        ValueError: If an environment variable is not found or found multiple times in the file.
    """

    # TODO: make it so it can take in alternative names, but variables should be a string
    # Mapping from new names to old (deprecated) names for file lookups
    _new_to_old = {
        "NLR_API_KEY": "NREL_API_KEY",
        "NLR_API_EMAIL": "NREL_API_EMAIL",
    }

    # open the file and read the lines
    with Path(fpath).open("r") as f:
        lines = f.readlines()
    if isinstance(variables, str):
        variables = [variables]

    old_variables = [_new_to_old(v) for v in variables if v in _new_to_old]

    # iterate through each variable
    for var in variables:
        # find a line containing the environment variable (try new name first, then old)
        line_w_var = [line for line in lines if var in line]
        if len(line_w_var) == 0 and var in _new_to_old:
            old_var = _new_to_old[var]
            line_w_var = [line for line in lines if old_var in line]
            if len(line_w_var) > 0:
                warnings.warn(
                    _DEPRECATION_MSG.format(old=old_var, new=var),
                    FutureWarning,
                    stacklevel=2,
                )
                var = old_var  # use old name for parsing
        if len(line_w_var) != 1:
            raise ValueError(
                f"{var} variable in found in {fpath} file {len(line_w_var)} times. "
                "Please specify this variable once."
            )
        # grab the line containing the variable,
        # assumes the line containing the variable is formatted as "variable=variable_value"
        val = line_w_var[0].split(f"{var}=").strip()
        # if var is an API key, set it as a global variable
        in_old = True if len(old_variables) > 0 and var in old_variables else False
        if var in variables or in_old:
            setter_method(var_value=val)
    return


def set_env_var_dot_env(setter_method, varname_new: str, varname_old: str | None = None, path=None):
    """Sets the environment variable :py:attr:`varname_new` from a .env file.

    Also supports the deprecated :py:attr:`varname_old` variable
    name for backward compatibility (with deprecation warnings).

    The following logic is used if `path` is input and exists:

    1) If the filename of the path is '.env', load the environment variables using `load_dotenv()`.
        Proceed to Step 3.
    2) If the filename of the path has an extension of '.env' (such a filename of 'my_env.env'),
        then load the environment variables using `load_file_with_variables()`. Proceed to step 3.

    The following logic is used if `path` is not input or does not exist:

    1) check for possible locations of the '.env' file. Searches the current working directory,
        the ROOT_DIR, and the parent of the ROOT_DIR. If the '.env' file is found in one of these
        locations, load the environment variables using `load_dotenv()`. Proceed to step 3.

    The following is run after the above step(s):

    3) Get the environment variable :py:attr:`varname_new` (falling back to the
        deprecated :py:attr:`varname_old`). If found, set it as global variables
        using :py:attr:`setter_method`.

    Args:
        path (Path | str, optional): Path to environment file.
            Defaults to None.
    """
    # generalized version of set_nlr_key_dot_env
    # varname_new is like _ENV_KEY_NEW
    # varname_old is like _ENV_KEY_OLD
    if path and Path(path).exists():
        if Path(path).name == ".env":
            load_dotenv(path)
        if Path(path).suffix == ".env":
            load_file_with_variables(setter_method, path, variables=varname_new)
    else:
        possible_locs = [Path.cwd() / ".env", ROOT_DIR / ".env", ROOT_DIR.parent / ".env"]
        for r in possible_locs:
            if Path(r).exists():
                load_dotenv(r)
    val = _get_env_with_fallback(varname_new, varname_old)
    if val is not None:
        setter_method(var_value=val)


def get_environment_var(
    global_varname, setter_method, varname_new: str, varname_old: str | None = None, env_path=None
):
    """Load the environment variable named :py:attr:`varname_new` (or :py:attr:`varname_old`).
    This method does the following:

    1) check for :py:attr:`varname_new` (or deprecated :py:attr:`varname_old`) environment variable,
        return if found. Otherwise, proceed to Step 2.
    2) check if the key has already been set as a global variable from
        running :py:attr:`setter_method`. If not set, proceed to Step 3.
    3) Attempt to set the key by calling :py:attr:`setter_method`.
    4) Check if the key has been set as a global variable. If found, return.
        Otherwise, raises a ValueError.

    Args:
        env_path (Path | str, optional): Filepath to .env file.
            Defaults to None.

    Raises:
        ValueError: If py:attr:`varname_old` was not found as an environment variable
            and the path to the environment file was not input.
        ValueError: If py:attr:`varname_old` was not found as an environment variable and not
            set properly using the environment path.

    Returns:
        str: value of the environment variable
    """

    # check if set as an environment variable (new name first, then old with warning)
    env_val = _get_env_with_fallback(varname_new, varname_old)
    if env_val is not None:
        return env_val

    # check if set as a global variable
    if len(globals()[global_varname]) == 0:
        # if len(developer_nlr_gov_key) == 0:
        # attempt to set the variable from a .env file
        set_env_var_dot_env(setter_method, varname_new, varname_old, path=env_path)

    if len(globals()[global_varname]) == 0:
        # variable was not found
        raise ValueError(
            f"{varname_new} (or {varname_old}) has not been set. "
            f"Please set the {varname_new} environment variable."
        )
    return globals()[global_varname]
