from functools import partial, update_wrapper

from h2integrate.core.env_tools import get_environment_var, set_env_var_dot_env


# global variables
developer_nlr_gov_key = ""
developer_nlr_gov_email = ""


# Setter methods for each NLR API variable
def set_developer_nlr_gov_key(var_value):
    global developer_nlr_gov_key
    if var_value is not None:
        developer_nlr_gov_key = var_value
    return developer_nlr_gov_key


def set_developer_nlr_gov_email(var_value):
    global developer_nlr_gov_email
    if var_value is not None:
        developer_nlr_gov_email = var_value
    return developer_nlr_gov_email


# Getter methods called by NLR API resource models
get_nlr_developer_api_key = partial(
    get_environment_var,
    setter_method=set_developer_nlr_gov_key,
    varname_new="NLR_API_KEY",
    varname_old="NREL_API_KEY",
)
update_wrapper(get_nlr_developer_api_key, get_environment_var)

get_nlr_developer_api_email = partial(
    get_environment_var,
    setter_method=set_developer_nlr_gov_email,
    varname_new="NLR_API_EMAIL",
    varname_old="NREL_API_EMAIL",
)
update_wrapper(get_nlr_developer_api_email, get_environment_var)

# Generic setter methods
set_nlr_api_key_dot_env = partial(
    set_env_var_dot_env,
    setter_method=set_developer_nlr_gov_key,
    varname_new="NLR_API_KEY",
    varname_old="NREL_API_KEY",
)
set_nlr_email_key_dot_env = partial(
    set_env_var_dot_env,
    setter_method=set_developer_nlr_gov_email,
    varname_new="NLR_API_EMAIL",
    varname_old="NREL_API_EMAIL",
)


# Setter methods for both variables needed for NLR API calls
def set_nlr_key_dot_env(path=None):
    set_nlr_api_key_dot_env(path=path)
    set_nlr_email_key_dot_env(path=path)
