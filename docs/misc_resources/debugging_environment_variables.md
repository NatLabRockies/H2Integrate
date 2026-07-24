---
jupytext:
  text_representation:
    extension: .md
    format_name: myst
    format_version: 0.13
    jupytext_version: 1.18.1
kernelspec:
  display_name: native-ard-h2i
  language: python
  name: python3
---

(env_var_debug:intro)=
# Environment Variables: Non-standard Configuration and Debugging Issues

If you encounter errors with models that use environment variables, such as a missing API key or other credential, this may be because the environment variables were set using a non-recommended method. The different approaches to setting environment variables is documented [in the getting started guides](#environment_variables:environment-variables). If you're setting environment variables with a .env file, then errors may occur because the file is not found.

The following sections will demonstrate how to debug environment variable issues and alternative ways to set environment variables.

- [Environment File: Getting Default Supported Filepaths](env_var_debug:get_default_fpaths)
- [Environment File: Check Default Supported Filepaths](env_var_debug:is_default_fpath)
- [Environment File: Setting Environment Variables prior to H2I Simulation](env_var_debug:nonstandard_fpath)
- [Debug Missing Environment Variables](env_var_debug:debug_missing)
- [Manually Setting Environment Variables](env_var_debug:manual_setting)


## Non-standard environment file location or name

If you're getting an error for a missing environment variable and your environment variables are stored in a `.env` file, then the `.env` file may not be found in the expected location.

(env_var_debug:get_default_fpaths)=
### Get the supported default filepaths

The code below shows how to print a list of the default filepaths that H2I will look for the environment file.


```{code-cell} ipython3
from pathlib import Path

from h2integrate import ROOT_DIR

default_directories = [ROOT_DIR, ROOT_DIR.parent, Path.cwd(), Path.home()]

print("Supported default environment file locations: \n")
for folder in default_directories:
    print(folder/".env")
```

(env_var_debug:is_default_fpath)=
### Determine if environment file is in supported default filepath

If you want to determine whether your environment file is placed in one of the valid locations, the code below will tell you if your environment file is found in any of the default directories:

```python
from pathlib import Path

from h2integrate import ROOT_DIR

default_directories = [ROOT_DIR, ROOT_DIR.parent, Path.cwd(), Path.home()]

env_fpaths = [fpath for folder in default_directories if (fpath:=folder/".env").is_file()]
if not env_fpaths:
    print("Environment file not found in any supported default directories")
else:
    print("Environment file(s) found in the following supported default filepath(s):\n")
    txt = "\n".join(str(f) for f in env_fpaths)
    print(txt)
```

(env_var_debug:nonstandard_fpath)=
### Setting environment variables with non-default environment filepath
If your environment file is not in any of the supported default locations or has a different name than ".env", then you can set the environment variables in your H2I run-script prior to running H2I.

If you know the filepath of your environment file, you can replace `"/path/to/environment_file/.env"` with the filepath of your environment file in the code below. Below shows an example of setting the environment variables `NLR_API_KEY` and `NLR_API_EMAIL` prior to running Example 1.

```python
from h2integrate import H2IntegrateModel
from h2integrate.core.env_tools import get_environment_variables

environment_fpath = "/path/to/environment_file/.env"

# Set the environment variables prior to running H2I
env_vars = get_environment_variables("NLR_API_KEY","NLR_API_EMAIL", file_path=environment_fpath, set_variables=True)

model = H2IntegrateModel("01_onshore_steel_mn.yaml")
model.setup()
model.run()
```

If your environment file **is** in of the default supported directories but is named something different than `".env"`, you could instead set the environment variables prior to running H2I with the following code (replace `"myenv.env"` with the filename of your environment file in the code below):

```python
from h2integrate import H2IntegrateModel
from h2integrate.core.env_tools import get_environment_variables

environment_fname = "myenv.env"

# Set the environment variables prior to running H2I
env_vars = get_environment_variables("NLR_API_KEY","NLR_API_EMAIL", file_name=environment_fname, set_variables=True)

model = H2IntegrateModel("01_onshore_steel_mn.yaml")
model.setup()
model.run()
```

(env_var_debug:debug_missing)=
## Debugging a missing environment variable
For any method of setting environment variables, you can use the code below to determine if your environment variables are being loaded properly or being set.
```{note}
If you're setting environment variables with an environment file in a non-standard location or filename, refer to the section above on how to specify the inputs to the `get_environment_variables` function.
```

Below shows an example of checking if the `NLR_API_KEY` and `NLR_API_EMAIL` environment variables are being **found** and what the values are of the variables that are found:

```python
from pathlib import Path

from h2integrate.core.env_tools import get_environment_variables

# Check if environment variables are being found
env_vars = get_environment_variables("NLR_API_KEY","NLR_API_EMAIL",set_variables=False)
if not env_vars:
    print("No environment variables found")
else:
    print("Found environment variables with the values below:")
    for key, val in env_vars.items():
        print(f"Environment variable `{key}` is set to `{val}`")

```


Below shows an example of checking if the `NLR_API_KEY` and `NLR_API_EMAIL` environment variables are being **set** and what the values are of the variables that are set:

```python
import os
from pathlib import Path

from h2integrate.core.env_tools import get_environment_variables

# Check if environment variables are being set
get_environment_variables("NLR_API_KEY","NLR_API_EMAIL",set_variables=True)

nlr_api_key = os.environ.get("NLR_API_KEY", None)
nlr_api_email = os.environ.get("NLR_API_EMAIL", None)

set_env_vars = dict(zip(["NLR_API_KEY", "NLR_API_EMAIL"], [nlr_api_key, nlr_api_email]))

for key,val in set_env_vars.items():
    if val is None:
        print(f"Environment variable `{key}` was not set")
    else:
        print(f"Environment variable `{key}` is set to `{val}`")
```

(env_var_debug:manual_setting)=
## Quick-fixes to avoid missing environment variable issues

If you're having issues with setting environment variables and need a quick-workaround, you can manually set environment variables in your runscript prior to running H2I.

```{important}
Do not share code that includes sensitive credentials, such as API keys. The following work-around should only be used for personal code and never shared with others or pushed to a shared or public github repository.
```

The below example shows a case where the environment variables `NLR_API_KEY` and `NLR_API_EMAIL` are hard-coded prior to running Example 1 (`"nlr-api-key"` would be replaced with your API key and `"name@email.com"` would be replaced with your email)

```python
import os
from h2integrate import H2IntegrateModel

# Hard code environment variables
os.environ["NLR_API_KEY"] = "nlr-api-key" # replace with your api key
os.environ["NLR_API_EMAIL"] = "name@email.com" # replace with your email

model = H2IntegrateModel("01_onshore_steel_mn.yaml")
model.setup()
model.run()
```

Another way to set environment variables is shown below:

```python
from h2integrate.core.env_tools import set_env_var
from h2integrate import H2IntegrateModel


env_keys = {
    "NLR_API_KEY": "nlr-api-key" # replace with your api key
    "NLR_API_EMAIL": "name@email.com" # replace with your email
}

set_env_var(overwrite=True, **env_keys)

model = H2IntegrateModel("01_onshore_steel_mn.yaml")
model.setup()
model.run()
```
