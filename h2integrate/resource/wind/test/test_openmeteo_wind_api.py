from decimal import ROUND_HALF_UP, Decimal
from pathlib import Path

import pytest
import openmdao.api as om

from h2integrate.core.supported_models import supported_models


@pytest.mark.unit
@pytest.mark.parametrize(
    "model,which,lat,lon,resource_year,model_name,timezone,elevation",
    [("OpenMeteoHistoricalWindResource", "wind", 44.04218, -95.19757, 2023, "open-meteo", 0, 438)],
    ids=["Primary Example"],
)
def test_wind_resource_web_download(
    plant_simulation,
    site_config,
    subtests,
    model,
    lat,
    lon,
    resource_year,
    model_name,
    timezone,
    elevation,
):
    fn = (
        f"{model_name}-"
        f"{Decimal(abs(lat)).quantize(Decimal('0.01'), ROUND_HALF_UP)}{'N' if lat > 0 else 'S'}"
        f"{Decimal(abs(lon)).quantize(Decimal('0.01'), ROUND_HALF_UP)}{'E' if lon > 0 else 'W'}"
        f"{elevation}m.csv"
    )
    site_config["resources"]["wind_resource"]["resource_parameters"]["resource_filename"] = fn
    plant_config = {
        "site": site_config,
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
    wind_data = prob.get_val("resource.wind_resource_data")

    with subtests.test("filepath for data was found where expected"):
        assert Path(wind_data["filepath"]).exists()
        assert Path(wind_data["filepath"]).name == fn

    with subtests.test("Data timezone"):
        assert pytest.approx(wind_data["data_tz"], rel=1e-6) == timezone
    with subtests.test("Site Elevation"):
        assert pytest.approx(wind_data["elevation"], rel=1e-6) == elevation

    data_keys = [k for k, v in wind_data.items() if not isinstance(v, float | int | str)]
    for k in data_keys:
        with subtests.test(f"{k} resource data is 8760"):
            assert len(wind_data[k]) == 8760

    with subtests.test("theres 12 timeseries data keys"):
        assert len(data_keys) == 12
    with subtests.test("Start time"):
        assert wind_data["start_time"] == f"{resource_year}/01/01 00:00:00 (+0000)"
    with subtests.test("Time step"):
        assert wind_data["dt"] == plant_simulation["simulation"]["dt"]


# fmt: off
@pytest.mark.unit
@pytest.mark.parametrize(
    "model,which,lat,lon,resource_year,model_name,timezone,elevation",
    [("OpenMeteoHistoricalWindResource", "wind", 44.04218, -95.19757, 2023, "openmeteo_archive", -6, 449)],  # noqa: E501
    ids=["Non-UTC"],
)
# fmt: on
def test_wind_resource_h2i_download(
    plant_simulation,
    site_config,
    subtests,
    model,
    lat,
    lon,
    resource_year,
    model_name,
    timezone,
    elevation,
):
    plant_config = {
        "site": site_config,
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
    wind_data = prob.get_val("resource.wind_resource_data")

    expected_fn = f"{lat}_{lon}_{resource_year}_{model_name}_60min_local_tz.csv"
    with subtests.test("filepath for data was found where expected"):
        assert Path(wind_data["filepath"]).exists()
        assert Path(wind_data["filepath"]).name == expected_fn

    with subtests.test("Data timezone"):
        assert pytest.approx(wind_data["data_tz"], rel=1e-6) == timezone
    with subtests.test("Site Elevation"):
        assert pytest.approx(wind_data["elevation"], rel=1e-6) == elevation

    data_keys = [k for k, v in wind_data.items() if not isinstance(v, float | int | str)]
    for k in data_keys:
        with subtests.test(f"{k} resource data is 8760"):
            assert len(wind_data[k]) == 8760

    with subtests.test("theres 13 timeseries data keys"):
        assert len(data_keys) == 13
    with subtests.test("Start time"):
        assert wind_data["start_time"] == f"{resource_year}/01/01 00:00:00 (-0600)"
    with subtests.test("Time step"):
        assert wind_data["dt"] == plant_simulation["simulation"]["dt"]
