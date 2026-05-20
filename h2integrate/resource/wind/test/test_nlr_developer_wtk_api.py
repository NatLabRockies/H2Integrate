import shutil
import hashlib
from pathlib import Path

import pytest
import openmdao.api as om

from h2integrate import RESOURCE_DEFAULT_DIR
from h2integrate.core.supported_models import supported_models


@pytest.fixture
def wtk_site_config(site_config, lat2, lon2):
    site_config["resources"]["wind_resource"]["resource_parameters"]["latitude"] = lat2
    site_config["resources"]["wind_resource"]["resource_parameters"]["longitude"] = lon2
    return site_config


# fmt: off
@pytest.mark.unit
@pytest.mark.parametrize(
    "model,which,lat,lon,lat2,lon2,resource_year,model_name,timezone",
    [("WTKNLRDeveloperAPIWindResource", "wind", 34.22, -102.75, 35.2018863, -101.945027, 2012, "wtk_api_v2", 0)],  # noqa: E501
    ids=["WTKNLRDeveloperAPIWindResource"],
)
# fmt: on
def test_wind_resource_loaded_from_default_dir(
    subtests,
    plant_simulation,
    wtk_site_config,
    lat,
    lon,
    model,
    resource_year,
):
    plant_config = {
        "site": wtk_site_config,
        "plant": plant_simulation,
    }
    prob = om.Problem()
    comp = supported_models[model](
        plant_config=plant_config,
        resource_config=plant_config["site"]["resources"]["wind_resource"]["resource_parameters"],
        driver_config={},
    )
    prob.model.add_subsystem("resource", comp)
    prob.setup()
    prob.run_model()
    wtk_data = prob.get_val("resource.wind_resource_data")

    wind_dir = RESOURCE_DEFAULT_DIR / "wind"
    with subtests.test("filepath for data was found where expected"):
        assert Path(wtk_data["filepath"]).exists()
        assert Path(wtk_data["filepath"]).parent == wind_dir

    temp_keys = [k for k in list(wtk_data.keys()) if "temperature" in k]
    wdir_keys = [k for k in list(wtk_data.keys()) if "wind_direction" in k]
    wspd_keys = [k for k in list(wtk_data.keys()) if "wind_speed" in k]
    pressure_keys = [k for k in list(wtk_data.keys()) if "pressure" in k]

    with subtests.test("more than 3 wind speed keys"):
        assert len(wspd_keys) > 0
    with subtests.test("same number of wind direction keys and wind speed"):
        assert len(wdir_keys) == len(wspd_keys)
    with subtests.test("same number of temperature keys and wind speed"):
        assert len(temp_keys) == len(wspd_keys)
    with subtests.test("3 heights for pressure data"):
        assert len(pressure_keys) == len(pressure_keys)
    with subtests.test("Start time"):
        assert wtk_data["start_time"] == f"{resource_year}/01/01 00:30:00 (+0000)"
    with subtests.test("Time step"):
        assert wtk_data["dt"] == plant_simulation["simulation"]["dt"]

    data_keys = temp_keys + wdir_keys + wspd_keys + pressure_keys
    with subtests.test("resource data is 8760 in length"):
        assert all(len(wtk_data[k]) == 8760 for k in data_keys)

    # check that minor changes to the data will create a unique hash
    hash_init = hashlib.md5(str(wtk_data).encode("utf-8")).hexdigest()
    wtk_data["start_time"] = "2013/01/01 00:30:00 (+0000)"
    hash_modified = hashlib.md5(str(wtk_data).encode("utf-8")).hexdigest()
    with subtests.test("Unique hash with modified start time"):
        assert hash_init != hash_modified


# fmt: off
@pytest.mark.unit
@pytest.mark.parametrize(
    "model,which,lat,lon,lat2,lon2,resource_year,model_name,timezone",
    [("WTKNLRDeveloperAPIWindResource", "wind", 34.22, -102.75, 35.2018863, -101.945027, 2012, "wtk_v2", 0)],  # noqa: E501
    ids=["WTKNLRDeveloperAPIWindResource"],
)
# fmt: on
def test_wind_resource_loaded_from_weather_dir(
    temp_dir,
    plant_simulation,
    wtk_site_config,
    subtests,
    model,
    lat2,
    lon2,
    resource_year,
    model_name
):

    wtk_site_config["resources"]["wind_resource"]["resource_parameters"]["resource_dir"] = temp_dir
    plant_config = {
        "site": wtk_site_config,
        "plant": plant_simulation,
    }

    source_fn = f"{lat2}_{lon2}_{resource_year}_{model_name}_60min_utc_tz.csv"
    source_fpath = RESOURCE_DEFAULT_DIR / "wind" / source_fn
    destination_fpath = temp_dir / source_fn

    # If the destination fpath doesn't exist, copy the file there
    if not destination_fpath.is_file():
        shutil.copyfile(source_fpath, destination_fpath)

    prob = om.Problem()
    comp = supported_models[model](
        plant_config=plant_config,
        resource_config=plant_config["site"]["resources"]["wind_resource"]["resource_parameters"],
        driver_config={},
    )
    prob.model.add_subsystem("resource", comp)
    prob.setup()
    prob.run_model()
    wtk_data = prob.get_val("resource.wind_resource_data")

    with subtests.test("filepath for data was found where expected"):
        assert Path(wtk_data["filepath"]).exists()
        assert Path(wtk_data["filepath"]).parent == destination_fpath.parent
        assert Path(wtk_data["filepath"]).name == destination_fpath.name
