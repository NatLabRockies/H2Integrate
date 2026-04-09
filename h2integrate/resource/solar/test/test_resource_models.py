from pathlib import Path

import pytest
import openmdao.api as om

from h2integrate import RESOURCE_DEFAULT_DIR
from h2integrate.core.supported_models import supported_models


# docs fencepost start: DO NOT REMOVE
# fmt: off
@pytest.mark.unit
@pytest.mark.parametrize(
    "model,which,lat,lon,resource_year,model_name,timezone",
    [
        ("GOESAggregatedSolarAPI", "solar", 34.22, -102.75, 2012, "goes_aggregated_v4", 0),
        ("Himawari7SolarAPI", "solar", -27.3649, 152.67935, 2013, "himawari7_v3", 0),
        ("Himawari8SolarAPI", "solar", 3.25735, 101.656312, 2020, "himawari8_v3", 0),
        ("HimawariTMYSolarAPI", "solar", -27.3649, 152.67935, "tmy-2020", "himawari_tmy_v3", 0),
        ("MeteosatPrimeMeridianSolarAPI", "solar", 41.9077, 12.4368, 2008, "nsrdb_msg_v4", 0),
        ("MeteosatPrimeMeridianTMYSolarAPI", "solar", -27.3649, 152.67935, "tmy-2022", "himawari_tmy_v3", 0),  # noqa: E501
    ],
    ids=[
        "GOESAggregatedSolarAPI",
        "Himawari7SolarAPI",
        "Himawari8SolarAPI",
        "HimawariTMYSolarAPI",
        "MeteosatPrimeMeridianSolarAPI",
        "MeteosatPrimeMeridianTMYSolarAPI",
    ]
)
# fmt: on
def test_nlr_solar_resource_file_downloads(
    subtests,
    plant_simulation,
    site_config,
    model,
    which,
    lat,
    lon,
    resource_year,
    model_name,
):
    file_resource_year = None
    if model == "MeteosatPrimeMeridianTMYSolarAPI" and resource_year == "tmy-2022":
        file_resource_year = "tmy-2020"
    plant_config = {
        "site": site_config,
        "plant": plant_simulation,
    }
    # docs fencepost end: DO NOT REMOVE

    prob = om.Problem()
    comp = supported_models[model](
        plant_config=plant_config,
        resource_config=plant_config["site"]["resources"]["solar_resource"]["resource_parameters"],
        driver_config={},
    )
    prob.model.add_subsystem("resource", comp)
    prob.setup()
    prob.run_model()
    data = prob.get_val("resource.solar_resource_data")

    year = resource_year if file_resource_year is None else file_resource_year
    name_expected = f"{lat}_{lon}_{year}_{model_name}_60min_utc_tz.csv"
    with subtests.test("Filename expected"):
        assert name_expected == (Path(data["filepath"])).name


@pytest.mark.unit
@pytest.mark.parametrize(
    "model,which,lat,lon,resource_year,model_name,timezone",
    [
        ("GOESAggregatedSolarAPI", "solar", 34.22, -102.75, 2012, "goes_aggregated_v4", 0),
        ("GOESConusSolarAPI", "solar", 34.22, -102.75, 2012, "goes_aggregated_v4", 0),
        ("GOESFullDiscSolarAPI", "solar", 34.22, -102.75, 2012, "goes_aggregated_v4", 0),
        ("GOESTMYSolarAPI", "solar", 34.22, -102.75, 2012, "goes_aggregated_v4", 0),
    ],
    ids=[
        "GOESAggregatedSolarAPI",
        "GOESConusSolarAPI",
        "GOESFullDiscSolarAPI",
        "GOESTMYSolarAPI",
    ]
)
def test_goes_resource_models(
    subtests,
    plant_simulation,
    site_config,
    model,
    which,
    lat,
    lon,
    resource_year,
    model_name,
):
    if model in ("GOESConusSolarAPI", "GOESFullDiscSolarAPI", "GOESTMYSolarAPI"):
        fn = f"{lat}_{lon}_{resource_year}_{model_name}_60min_utc_tz.csv"
        site_config["resources"]["solar_resource"]["resource_parameters"].setdefault(
            "resource_filename", fn
        )
        year = "tmy-2022" if model == "GOESTMYSolarAPI" else 2020
        site_config["resources"]["solar_resource"]["resource_parameters"]["resource_year"] = year

    plant_config = {
        "site": site_config,
        "plant": plant_simulation,
    }

    with subtests.test("Load from default directory"):
        prob = om.Problem()
        comp = supported_models[model](
            plant_config=plant_config,
            resource_config=plant_config["site"]["resources"]["solar_resource"][
                "resource_parameters"
            ],
            driver_config={},
        )
        prob.model.add_subsystem("resource", comp)
        prob.setup()
        prob.run_model()
        data = prob.get_val("resource.solar_resource_data")

    with subtests.test("Data file was found where expected"):
        name_expected = f"{lat}_{lon}_{resource_year}_{model_name}_60min_utc_tz.csv"
        assert name_expected == (Path(data["filepath"])).name
        assert Path(data["filepath"]).exists()
        assert Path(data["filepath"]).parent == RESOURCE_DEFAULT_DIR / "solar"

    data_keys = [
        "ghi",
        "dhi",
        "dni",
        "temperature",
        "pressure",
        "dew_point",
        "wind_speed",
        "wind_direction",
    ]
    for k in data_keys:
        with subtests.test(f"{k} resource data is 8760"):
            assert len(data[k]) == 8760


# fmt: off
@pytest.mark.unit
@pytest.mark.parametrize(
    "model,which,lat,lon,resource_year,model_name,timezone",
    [("OpenMeteoHistoricalSolarResource", "solar", 44.04218, -95.19757, 2023, "openmeteo_archive_solar", 0)],  # noqa: E501
    ids=["OpenMeteoHistoricalSolarResource"]
)
# fmt: on
def test_solar_resource_h2i_download(
    plant_simulation,
    site_config,
    subtests,
    model,
    which,
    lat,
    lon,
    resource_year,
    model_name,
):
    plant_config = {
        "site": site_config,
        "plant": plant_simulation,
    }

    prob = om.Problem()
    comp = supported_models[model](
        plant_config=plant_config,
        resource_config=plant_config["site"]["resources"]["solar_resource"]["resource_parameters"],
        driver_config={},
    )
    prob.model.add_subsystem("resource", comp)
    prob.setup()
    prob.run_model()
    solar_data = prob.get_val("resource.solar_resource_data")
    name_expected = f"{lat}_{lon}_{resource_year}_{model_name}_60min_utc_tz.csv"
    with subtests.test("filepath for data was found where expected"):
        assert Path(solar_data["filepath"]).exists()
        assert Path(solar_data["filepath"]).name == name_expected

    with subtests.test("Data timezone"):
        assert pytest.approx(solar_data["data_tz"], rel=1e-6) == 0
    with subtests.test("Site Elevation"):
        assert pytest.approx(solar_data["elevation"], rel=1e-6) == 449

    data_keys = [k for k, v in solar_data.items() if not isinstance(v, float | int | str)]
    for k in data_keys:
        with subtests.test(f"{k} resource data is 8760"):
            assert len(solar_data[k]) == 8760

    with subtests.test("There are 16 timeseries data keys"):
        assert len(data_keys) == 16
    with subtests.test("Start time"):
        assert solar_data["start_time"] == f"{resource_year}/01/01 00:00:00 (+0000)"
    with subtests.test("Time step"):
        assert solar_data["dt"] == plant_simulation["simulation"]["dt"]



# fmt: off
@pytest.mark.unit
@pytest.mark.parametrize(
    "model,which,lat,lon,resource_year,model_name,timezone",
    [("OpenMeteoHistoricalSolarResource", "solar",  -28.454864, 114.551749, 2024, "openmeteo_archive_solar", 8)],  # noqa: E501
    ids=["OpenMeteoHistoricalSolarResource-LeapYear"]
)
# fmt: on
def test_solar_resource_h2i_download_leap_year(
    plant_simulation,
    site_config,
    subtests,
    model,
    which,
    lat,
    lon,
    resource_year,
    model_name,
):
    plant_config = {
        "site": site_config,
        "plant": plant_simulation,
    }

    prob = om.Problem()
    comp = supported_models[model](
        plant_config=plant_config,
        resource_config=plant_config["site"]["resources"]["solar_resource"]["resource_parameters"],
        driver_config={},
    )
    prob.model.add_subsystem("resource", comp)
    prob.setup()
    prob.run_model()
    solar_data = prob.get_val("resource.solar_resource_data")
    name_expected = f"{lat}_{lon}_{resource_year}_{model_name}_60min_local_tz.csv"
    with subtests.test("filepath for data was found where expected"):
        assert Path(solar_data["filepath"]).exists()
        assert Path(solar_data["filepath"]).name == name_expected

    with subtests.test("Data timezone"):
        assert pytest.approx(solar_data["data_tz"], rel=1e-6) == 8
    with subtests.test("Site Elevation"):
        assert pytest.approx(solar_data["elevation"], rel=1e-6) == 71

    data_keys = [k for k, v in solar_data.items() if not isinstance(v, float | int | str)]
    for k in data_keys:
        with subtests.test(f"{k} resource data is 8760"):
            assert len(solar_data[k]) == 8760

    with subtests.test("There are 16 timeseries data keys"):
        assert len(data_keys) == 16
    with subtests.test("Start time"):
        assert solar_data["start_time"] == f"{resource_year}/01/01 00:00:00 (+0800)"
    with subtests.test("Time step"):
        assert solar_data["dt"] == plant_simulation["simulation"]["dt"]
