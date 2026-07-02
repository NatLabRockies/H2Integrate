import os
import warnings
from pathlib import Path
from functools import partial, update_wrapper

from dotenv import load_dotenv

from h2integrate import ROOT_DIR


# instantiate global variables
developer_nlr_gov_key = ""
developer_nlr_gov_email = ""

# Mapping from new env var names to deprecated old names
_ENV_KEY_NEW = "NLR_API_KEY"
_ENV_KEY_OLD = "NREL_API_KEY"
_ENV_EMAIL_NEW = "NLR_API_EMAIL"
_ENV_EMAIL_OLD = "NREL_API_EMAIL"

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
    """Set `var_value` as the global variable `developer_nlr_gov_key`.

    Args:
        key (str): API key for NLR Developer Network. Should be length 40.
    """
    # generalized form of set_developer_nlr_gov_key
    globals()[global_varname] = var_value
    # eval(f"global {global_varname}")
    # eval(f"{global_varname} = {var_value}")
    # return eval(global_varname)
    return globals()[global_varname]


set_developer_nlr_gov_key = partial(set_environment_var, global_varname="developer_nlr_gov_key")
set_developer_nlr_gov_email = partial(set_environment_var, global_varname="developer_nlr_gov_email")


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

    # Mapping from new names to old (deprecated) names for file lookups
    _new_to_old = {
        _ENV_KEY_NEW: _ENV_KEY_OLD,
        _ENV_EMAIL_NEW: _ENV_EMAIL_OLD,
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
        # if var is an API email, set it as a global variable
        # if var in (_ENV_EMAIL_NEW, _ENV_EMAIL_OLD):
        #     set_developer_nlr_gov_email(val)
    return


def set_env_var_dot_env(setter_method, varname_new: str, varname_old: str | None = None, path=None):
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
    """Load the API key (NLR_API_KEY). This method does the following:

    1) check for NLR_API_KEY (or deprecated NREL_API_KEY) environment variable,
        return if found. Otherwise, proceed to Step 2.
    2) check if the key has already been set as a global variable from
        running `set_nlr_key_dot_env()`. If not set, proceed to Step 3.
    3) Attempt to set the key by calling `set_nlr_key_dot_env()`.
    4) Check if the key has been set as a global variable. If found, return.
        Otherwise, raises a ValueError.

    Args:
        env_path (Path | str, optional): Filepath to .env file.
            Defaults to None.

    Raises:
        ValueError: If NLR_API_KEY was not found as an environment variable
            and the path to the environment file was not input.
        ValueError: If NLR_API_KEY was not found as an environment variable and not
            set properly using the environment path.

    Returns:
        str: API key for NLR Developer Network.
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


get_nlr_developer_api_key = partial(
    get_environment_var,
    global_varname="developer_nlr_gov_key",
    setter_method=set_developer_nlr_gov_key,
    varname_new=_ENV_KEY_NEW,
    varname_old=_ENV_KEY_OLD,
)
update_wrapper(get_nlr_developer_api_key, get_environment_var)

get_nlr_developer_api_email = partial(
    get_environment_var,
    global_varname="developer_nlr_gov_email",
    setter_method=set_developer_nlr_gov_email,
    varname_new=_ENV_EMAIL_NEW,
    varname_old=_ENV_EMAIL_OLD,
)
update_wrapper(get_nlr_developer_api_email, get_environment_var)

set_nlr_api_key_dot_env = partial(
    set_env_var_dot_env,
    setter_method=set_developer_nlr_gov_key,
    varname_new=_ENV_KEY_NEW,
    varname_old=_ENV_KEY_OLD,
)
set_nlr_email_key_dot_env = partial(
    set_env_var_dot_env,
    setter_method=set_developer_nlr_gov_email,
    varname_new=_ENV_EMAIL_NEW,
    varname_old=_ENV_EMAIL_OLD,
)


def set_nlr_key_dot_env(path=None):
    set_nlr_api_key_dot_env(path=path)
    set_nlr_email_key_dot_env(path=path)
