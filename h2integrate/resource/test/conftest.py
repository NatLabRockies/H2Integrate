import pytest

from test.conftest import temp_dir, pytest_collection_modifyitems  # noqa: F401


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


@pytest.fixture
def site_config(which, lat, lon, model, resource_year, model_name, elevation=0):
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
