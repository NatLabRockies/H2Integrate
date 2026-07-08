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


def load_file_with_variables(
    setter_method, fpath, varname_new: str, varname_old: str | None = None
):
    """Load an environment variable from a text file.

    Supports both the new ``varname_new`` and deprecated ``varname_old`` variable
    names.  If only the old name is found in the file, a deprecation warning is
    emitted.

    Args:
        fpath (str | Path): filepath to a text file with the extension '.env' that
            may contain the environment variable in `variables`.
        varname_new (str): environment variable to load from file.

    Raises:
        ValueError: If an environment variable is not found or found multiple times in the file.
    """

    # open the file and read the lines
    with Path(fpath).open("r") as f:
        lines = f.readlines()

    # find a line containing the environment variable (try new name first, then old)
    line_w_var = [line for line in lines if varname_new in line]
    var = varname_new
    if len(line_w_var) == 0 and varname_old is not None:
        line_w_var = [line for line in lines if varname_old in line]
        if len(line_w_var) > 0:
            warnings.warn(
                _DEPRECATION_MSG.format(old=varname_old, new=varname_new),
                FutureWarning,
                stacklevel=2,
            )
            var = varname_old  # use old name for parsing
    if len(line_w_var) != 1:
        # TODO: add an input to toggle whether to thow an error
        # If not throw an error, set the val to None
        raise ValueError(
            f"{var} variable in found in {fpath} file {len(line_w_var)} times. "
            "Please specify this variable once."
        )
    # grab the line containing the variable,
    # assumes the line containing the variable is formatted as "variable=variable_value"
    val = line_w_var[0].split(f"{var}=")[-1].strip()
    # set variable as a global variable
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
    if path and Path(path).exists():
        if Path(path).name == ".env":
            load_dotenv(path)
        if Path(path).suffix == ".env":
            load_file_with_variables(
                setter_method, path, varname_new=varname_new, varname_old=varname_old
            )
    else:
        possible_locs = [Path.cwd() / ".env", ROOT_DIR / ".env", ROOT_DIR.parent / ".env"]
        for r in possible_locs:
            if Path(r).exists():
                load_dotenv(r)
        # TODO: add in checks to run load_file_with_variables from possible locs
        # list(Path.cwd().glob("*.env"))
    val = _get_env_with_fallback(varname_new, varname_old)
    if val is not None:
        setter_method(var_value=val)


def get_environment_var(
    setter_method, varname_new: str, varname_old: str | None = None, env_path=None
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
        # TODO: call setter method here
        return env_val

    global_var_value = setter_method(var_value=None)
    # check if set as a global variable
    if len(global_var_value) == 0:
        # attempt to set the variable from a .env file
        set_env_var_dot_env(setter_method, varname_new, varname_old, path=env_path)

    global_var_value = setter_method(var_value=None)
    if len(global_var_value) == 0:
        # variable was not found
        raise ValueError(
            f"{varname_new} (or {varname_old}) has not been set. "
            f"Please set the {varname_new} environment variable."
        )

    # global_var_value = setter_method(var_value=None)
    return global_var_value
