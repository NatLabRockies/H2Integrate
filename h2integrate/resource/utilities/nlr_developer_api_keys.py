from functools import partial, update_wrapper

from h2integrate.core.env_tools import get_environment_var, set_env_var_dot_env, set_environment_var


# global variables
developer_nlr_gov_key = ""
developer_nlr_gov_email = ""

# Setter methods for each NLR API variable
set_developer_nlr_gov_key = partial(set_environment_var, global_varname="developer_nlr_gov_key")
update_wrapper(set_developer_nlr_gov_key, set_environment_var)
set_developer_nlr_gov_email = partial(set_environment_var, global_varname="developer_nlr_gov_email")
update_wrapper(set_developer_nlr_gov_email, set_environment_var)

# Getter methods called by NLR API resource models
get_nlr_developer_api_key = partial(
    get_environment_var,
    global_varname="developer_nlr_gov_key",
    setter_method=set_developer_nlr_gov_key,
    varname_new="NLR_API_KEY",
    varname_old="NREL_API_KEY",
)
update_wrapper(get_nlr_developer_api_key, get_environment_var)

get_nlr_developer_api_email = partial(
    get_environment_var,
    global_varname="developer_nlr_gov_email",
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
