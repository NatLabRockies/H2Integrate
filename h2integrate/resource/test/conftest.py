import os

import pytest

from h2integrate.resource.utilities.nrel_developer_api_keys import set_nrel_key_dot_env

from test.conftest import temp_dir, pytest_collection_modifyitems  # noqa: F401


# docs fencepost start: DO NOT REMOVE
@pytest.fixture
def plant_simulation(timezone):
    plant = {
        "plant_life": 30,
        "simulation": {
            "dt": 3600,
            "n_timesteps": 8760,
            "start_time": "01/01/1900 00:30:00",
            "timezone": timezone,
        },
    }
    return plant


# docs fencepost end: DO NOT REMOVE


@pytest.fixture
def site_config(which, lat, lon, model, resource_year, model_name):
    site_config = {
        "latitude": lat,
        "longitude": lon,
        "resources": {
            f"{which}_resource": {
                "resource_model": model,
                "resource_parameters": {
                    "resource_year": resource_year,
                },
            }
        },
    }
    match model:
        case "MeteosatPrimeMeridianTMYSolarAPI":
            resource_year = "tmy-2020" if resource_year == "tmy-2022" else resource_year
            fn = f"{lat}_{lon}_{resource_year}_{model_name}_60min_utc_tz.csv"
            site_config["resources"]["solar_resource"]["resource_parameters"].setdefault(
                "resource_filename", fn
            )
        case str(x) if "GOES" in x:
            additional = {"latitude": lat, "longitude": lon}
            site_config["resources"]["solar_resource"]["resource_parameters"].update(additional)
        case "WTKNRELDeveloperAPIWindResource":
            additional = {"latitude": lat, "longitude": lon}
            site_config["resources"]["wind_resource"]["resource_parameters"].update(additional)
        case _:
            pass
    return site_config


def pytest_sessionstart(session):
    initial_om_report_setting = os.getenv("OPENMDAO_REPORTS")
    if initial_om_report_setting is not None:
        os.environ["TMP_OPENMDAO_REPORTS"] = initial_om_report_setting

    os.environ["OPENMDAO_REPORTS"] = "none"

    # Set a dummy API key
    os.environ["NREL_API_KEY"] = "a" * 40
    set_nrel_key_dot_env()

    # Set RESOURCE_DIR to None so pulls example files from default DIR
    initial_resource_dir = os.getenv("RESOURCE_DIR")
    # if user provided a resource directory, save it to a temp variable
    # this allows tests to run as expected while not causing
    # unexpected behavior afterwards
    if initial_resource_dir is not None:
        os.environ["TEMP_RESOURCE_DIR"] = f"{initial_resource_dir}"

    os.environ.pop("RESOURCE_DIR", None)


def pytest_sessionfinish(session, exitstatus):
    # if user provided a resource directory, load it from the temp variable
    # and reset the original environment variable
    # this prevents unexpected behavior after running tests

    user_dir = os.getenv("TEMP_RESOURCE_DIR")
    if user_dir is not None:
        os.environ["RESOURCE_DIR"] = user_dir
    os.environ.pop("TEMP_RESOURCE_DIR", None)

    initial_om_report_setting = os.getenv("TMP_OPENMDAO_REPORTS")
    if initial_om_report_setting is not None:
        os.environ["OPENMDAO_REPORTS"] = initial_om_report_setting
    os.environ.pop("TMP_OPENMDAO_REPORTS", None)
