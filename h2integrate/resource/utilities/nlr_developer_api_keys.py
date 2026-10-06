import warnings
from pathlib import Path

from h2integrate.core.env_tools import get_environment_variables


_DEPRECATION_MSG = (
    "The '{old}' environment variable is deprecated and will be removed in a future release. "
    "Please use '{new}' instead. The nrel.gov API domain has moved to nlr.gov."
)

_ENV_MISSING_MSG = (
    "{new} (or {old}) has not been set. " "Please set the {new} environment variable."
)


def get_nlr_developer_api_credential(
    which: str, env_path: str | Path | None = None, set_vars: bool = True
) -> str:
    """Get either the NLR API email or key with a fallback for the NREL credentials.

    Args:
        which (str): One of "email" or "key" to indicate which NLR API credential should be
            retrieved.
        env_path (None | Path | str, optional): Filepath to file containing NLR API credentials.
            Defaults to None.
        set_vars (bool, optional): If True, set the environment variables if they
            haven't already been set. Defaults to True.

    Raises:
        ValueError: Raised if an invalid value was passed to :py:attr:`which`.
        KeyError: Raised if neither of the NLR or NREL credentials could be found.

    Returns:
        str: API key or email for NLR Developer Network.
    """
    if which.lower() not in ("email", "key"):
        raise ValueError("`which` must be one of 'email' or 'key'.")
    old_name = f"NREL_API_{which.upper()}"
    new_name = f"NLR_API_{which.upper()}"
    nlr_api_vars = get_environment_variables(
        new_name, old_name, file_path=env_path, set_variables=set_vars
    )
    if not bool(nlr_api_vars):
        # returned an empty dictionary
        raise ValueError(_ENV_MISSING_MSG.format(old=old_name, new=new_name))
    if (old_name in nlr_api_vars) and (new_name not in nlr_api_vars):
        warnings.warn(
            _DEPRECATION_MSG.format(old=old_name, new=new_name),
            FutureWarning,
            stacklevel=3,
        )
    return list(nlr_api_vars.values())[0]


def get_nlr_developer_api_key() -> str:
    """Load the API key (NLR_API_KEY) for the NLR Developer Network.

    Raises:
        ValueError: If NLR_API_KEY or NREL_API_KEY was not found as an environment variable

    Returns:
        str: API key for NLR Developer Network. Should be length 40.
    """
    nlr_api_key = get_nlr_developer_api_credential(which="key")
    return nlr_api_key


def get_nlr_developer_api_email() -> str:
    """Load the API email (NLR_API_EMAIL) for the NLR Developer Network.

    Raises:
        ValueError: If NLR_API_EMAIL or NREL_API_EMAIL was not found as an environment variable

    Returns:
        str: email corresponding to the API key for NLR Developer Network.

    """
    nlr_api_email = get_nlr_developer_api_credential(which="email")
    return nlr_api_email
