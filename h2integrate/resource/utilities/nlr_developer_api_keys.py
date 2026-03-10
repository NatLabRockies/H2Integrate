import os
import warnings
from pathlib import Path

from dotenv import load_dotenv

from h2integrate import ROOT_DIR


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
    value = os.getenv(old_name)
    if value is not None:
        warnings.warn(
            _DEPRECATION_MSG.format(old=old_name, new=new_name),
            FutureWarning,
            stacklevel=3,
        )
        return value
    return None


def set_developer_nlr_gov_key(key: str):
    """Set `key` as the global variable `developer_nlr_gov_key`.

    Args:
        key (str): API key for NLR Developer Network. Should be length 40.
    """
    global developer_nlr_gov_key
    developer_nlr_gov_key = key
    return developer_nlr_gov_key


def set_developer_nlr_gov_email(email: str):
    """Set `email` as the global variable `developer_nlr_gov_email`.

    Args:
        email (str): email corresponding to the API key for NLR Developer Network.
    """
    global developer_nlr_gov_email
    developer_nlr_gov_email = email
    return developer_nlr_gov_email


def load_file_with_variables(fpath, variables=["NLR_API_KEY", "NLR_API_EMAIL"]):
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
        if var in (_ENV_KEY_NEW, _ENV_KEY_OLD):
            set_developer_nlr_gov_key(val)
        # if var is an API email, set it as a global variable
        if var in (_ENV_EMAIL_NEW, _ENV_EMAIL_OLD):
            set_developer_nlr_gov_email(val)
    return


def set_nlr_key_dot_env(path=None):
    """Sets the environment variables NLR_API_EMAIL and NLR_API_KEY from a .env file.

    Also supports the deprecated ``NREL_API_EMAIL`` and ``NREL_API_KEY`` variable
    names for backward compatibility (with deprecation warnings).

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

    3) Get the environment variables NLR_API_KEY and NLR_API_EMAIL (falling back to the
        deprecated NREL_API_KEY / NREL_API_EMAIL). If found, set them as global variables
        using `set_developer_nlr_gov_key()` / `set_developer_nlr_gov_email()`.

    Args:
        path (Path | str, optional): Path to environment file.
            Defaults to None.
    """
    if path and Path(path).exists():
        if Path(path).name == ".env":
            load_dotenv(path)
        if Path(path).suffix == ".env":
            load_file_with_variables(path, variables=_ENV_KEY_NEW)
            load_file_with_variables(path, variables=_ENV_EMAIL_NEW)
    else:
        possible_locs = [Path.cwd() / ".env", ROOT_DIR / ".env", ROOT_DIR.parent / ".env"]
        for r in possible_locs:
            if Path(r).exists():
                load_dotenv(r)
    api_key = _get_env_with_fallback(_ENV_KEY_NEW, _ENV_KEY_OLD)
    api_email = _get_env_with_fallback(_ENV_EMAIL_NEW, _ENV_EMAIL_OLD)
    if api_key is not None:
        set_developer_nlr_gov_key(api_key)
    if api_email is not None:
        set_developer_nlr_gov_email(api_email)


def get_nlr_developer_api_key(env_path=None):
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
    env_val = _get_env_with_fallback(_ENV_KEY_NEW, _ENV_KEY_OLD)
    if env_val is not None:
        return env_val

    # check if set as a global variable
    global developer_nlr_gov_key
    if len(developer_nlr_gov_key) == 0:
        # attempt to set the variable from a .env file
        set_nlr_key_dot_env(path=env_path)

    if len(developer_nlr_gov_key) == 0:
        # variable was not found
        raise ValueError(
            "NLR_API_KEY (or NREL_API_KEY) has not been set. "
            "Please set the NLR_API_KEY environment variable."
        )
    return developer_nlr_gov_key


def get_nlr_developer_api_email(env_path=None):
    """Load the API email (NLR_API_EMAIL). This method does the following:

    1) check for NLR_API_EMAIL (or deprecated NREL_API_EMAIL) environment variable,
        return if found. Otherwise, proceed to Step 2.
    2) check if the email has already been set as a global variable from running
        `set_nlr_key_dot_env()`. If not set, proceed to Step 3.
    3) Attempt to set the email by calling `set_nlr_key_dot_env()`.
    4) Check if the email has been set as a global variable. If found, return.
        Otherwise, raises a ValueError.

    Args:
        env_path (Path | str, optional): Filepath to .env file.
            Defaults to None.

    Raises:
        ValueError: If NLR_API_EMAIL was not found as an environment variable
            and the path to the environment file was not input.
        ValueError: If NLR_API_EMAIL was not found as an environment variable and not
            set properly using the environment path.

    Returns:
        str: email for NLR Developer Network API.
    """

    # check if set as an environment variable (new name first, then old with warning)
    env_val = _get_env_with_fallback(_ENV_EMAIL_NEW, _ENV_EMAIL_OLD)
    if env_val is not None:
        return env_val

    # check if set as a global variable
    global developer_nlr_gov_email
    if len(developer_nlr_gov_email) == 0:
        # attempt to set the variable from a .env file
        set_nlr_key_dot_env(path=env_path)

    if len(developer_nlr_gov_email) == 0:
        # variable was not found
        raise ValueError(
            "NLR_API_EMAIL (or NREL_API_EMAIL) has not been set. "
            "Please set the NLR_API_EMAIL environment variable."
        )
    return developer_nlr_gov_email
