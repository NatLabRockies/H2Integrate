(environment_variables:environment-variables)=
# Environment Variables
H2Integrate can pull data (such as wind and solar resource data, feedstock prices, etc) from public datasets accessible with API keys or user-specific tokens. Since API keys and tokens are unique to each user, these are accessed in H2Integrate as environment variables. These environment variables need to be set to use their corresponding functionality. Some environment variables can also be used to customize your workflow. The list of environment variables that may be used by H2Integrate are listed below:

- [NLR Developer Network](environment_variables:nlr_developer)
    - `NLR_API_KEY`
    - `NLR_API_EMAIL`
- [EIA Natural Gas Cost Data](environment_variables:eia_ng)
    - `EIA_API_KEY`
- [Customized Workflow](environment_variables:folders)
    - `RESOURCE_DIR`
    - `FEEDSTOCK_DIR`

```{note}
Tips on debugging environment variable related errors or issues can be found [here](#env_var_debug:intro)
```

To use models that require environment variables, [follow these instructions below](environment_variables:setting-environment-variables).

(environment_variables:setting-environment-variables)=
# Setting Environment Variables
We will use the environment variables needed for the NLR Developer Network (`NLR_API_KEY` and `NLR_API_EMAIL`) to showcase different methods of setting environment variables in this section.

In the following sections on setting these environment variables, `'api-key-value'` should be replaced with your NLR API key and `'email-for-api-key'` should be replaced with your email address.


The remaining sections outline different options for setting environment variables in H2Integrate:
- [Save environment variables with conda (preferred)](#save-environment-variables-with-conda-preferred)
- [Set environment variables with a .yml file](#set-environment-variables-with-yaml-file)
- [Set environment variables with a .env file](#set-environment-variables-with-env-file)

(save-environment-variables-with-conda-preferred)=
## Save Environment Variables with Conda (Preferred)

After creating the conda environment for H2Integrate, you can [save environment variables with conda](https://docs.conda.io/projects/conda/en/latest/user-guide/tasks/manage-environments.html#saving-environment-variables) within that environment.
This is the preferred method for setting environment variables for H2Integrate.

### Windows Instructions

If you are using a Windows machine, please follow the steps documented for conda on [saving environment variables on Windows](https://docs.conda.io/projects/conda/en/latest/user-guide/tasks/manage-environments.html#win-save-env-variables).
The specific variable names and values to set are listed below; use these for steps 3 and 4 from the conda installation instructions..

The `.\etc\conda\activate.d\env_vars.bat` file may look like below:
```bash
set NLR_API_KEY='api-key-value'
set NLR_API_EMAIL='email-for-api-key'
```

The `.\etc\conda\deactivate.d\env_vars.bat` file may look like below:
```bash
set NLR_API_KEY=
set NLR_API_EMAIL=
```

### macOS and Linux instructions

If you are using a macOS or Linux machine, please follow the steps documented for conda on [saving environment variables on macOS or Linux](https://docs.conda.io/projects/conda/en/latest/user-guide/tasks/manage-environments.html#macos-linux-save-env-variables)

The `./etc/conda/activate.d/env_vars.sh` file may look like below:
```bash
#!/bin/sh
export NLR_API_KEY='api-key-value'
export NLR_API_EMAIL='email-for-api-key'
```

The `./etc/conda/deactivate.d/env_vars.sh` file may look like below:
```bash
#!/bin/sh

unset NLR_API_KEY
unset NLR_API_EMAIL
```

(set-environment-variables-with-yaml-file)=
## Set Environment Variables with .yml file

1. In `environment.yml`, add the following lines to the bottom of the file, and replace the
    environment variable values with your information. Be sure that
    "variables" has no leading spaces.

    ```yaml
    variables:
        NLR_API_KEY='api-key-value'
        NLR_API_EMAIL='email-for-api-key'
    ```

2. After that, create a conda environment and install H2Integrate and all its dependencies using the modified `environment.yml` file with the command:

    ```bash
    conda env create -f environment.yml
    ```

(set-environment-variables-with-env-file)=
## Set Environment Variables with .env file

The ".env" file will be looked for in all of the following locations:
    - H2Integrate root directory (`/path/to/H2Integrate/h2integrate/`)
    - parent of H2Integrate root directory (`/path/to/H2Integrate/`) (preferred location to store your environment file)
    - current working directory (this is not a preferred location to store your environment file)
1. Choose which of the above directories you want to host your .env file, and create a file named ".env" in that folder.
2. Open the ".env" file and add the environment variables:
    ```bash
    NLR_API_KEY='api-key-value'
    NLR_API_EMAIL='email-for-api-key'
    ```
3. Save and close the ".env" file.


(environment_variables:nlr_developer)=
# NLR Developer Network Environment Variables

H2Integrate can pull weather resource datasets (e.g. data needed for wind or solar generation) automatically for a user-provided location.
To use resource datasets from the NLR developer network, you will need an NLR API key, which can be obtained from:
    [https://developer.nlr.gov/signup/](https://developer.nlr.gov/signup/).

You will need to set the API key and the email you used to get the API key to download resource data from the NLR developer network. The 40 character API key is referred to in following sections as the value for the `NLR_API_KEY` environment variable. The email used to get the API key is referred to in the following sections as the value for the `NLR_API_EMAIL` environment variable.

```{note}
The old environment variable names ``NREL_API_KEY`` and ``NREL_API_EMAIL`` are still supported
for backward compatibility, but are deprecated and will be removed in a future release.
Please migrate to ``NLR_API_KEY`` and ``NLR_API_EMAIL``.
```

(environment_variables:eia_ng)=
# EIA Natural Gas Cost
Further documentation on the EIA natural gas cost model can be [here](#feedstocks:eia_ng_price). This requires an API key obtained from the [EIA Open Data portal](https://www.eia.gov/opendata/). This API key should be set as the value for the environment variable `EIA_API_KEY`, i.e.,

```bash
EIA_API_KEY='api-key-value'
```

(environment_variables:folders)=
# Customized Directories for Resource and Feedstock data
Two **optional** environment variables are available to customize directories for saving and loading data from. These two environment variables are `RESOURCE_DIR` and `FEEDSTOCK_DIR` and should be set to filepaths:


```bash
RESOURCE_DIR='/path/to/my/resource/folder/'
FEEDSTOCK_DIR='/path/to/my/feedstock/folder/'
```

An optional environment variable is `RESOURCE_DIR`. If set, this will be used as the default folder to save resource data to that is downloaded from the API and load resource data from. By default, if `RESOURCE_DIR` is not set as an environment variable and no other folder is specified to a resource model, the default behavior for resource models is to use `DEFAULT_RESOURCE_DIR` which is the folder `/path/to/H2Integrate/resource_files/`.

Another optional environment variable is `FEEDSTOCK_DIR`. If set, this will be used as the default folder to save feedstock data to that is downloaded from the API. By default, if `FEEDSTOCK_DIR` is not set as an environment variable and no other folder is specified to a feedstock model, the default behavior for feedstock models is to use `DEFAULT_FEEDSTOCK_DIR` which is the folder `/path/to/H2Integrate/resource_files/feedstock_files/`.

```{important}
If setting either of these environment variables, please set its value as the full filepath to the folder you'd like to save resource files to, and ensure that the folder exists.
```
