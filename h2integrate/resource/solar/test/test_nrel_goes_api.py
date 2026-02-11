from pathlib import Path

import pytest
import openmdao.api as om

from h2integrate import RESOURCE_DEFAULT_DIR
from h2integrate.core.supported_models import supported_models


@pytest.mark.unit
@pytest.mark.parametrize(
    "lat,lon,model,resource_year,model_name",
    [
        (34.22, -102.75, "GOESAggregatedSolarAPI", 2012, "goes_aggregated_v4"),
        (34.22, -102.75, "GOESConusSolarAPI", 2012, "goes_aggregated_v4"),
        (34.22, -102.75, "GOESTMYSolarAPI", 2012, "goes_aggregated_v4"),
        (34.22, -102.75, "GOESFullDiscSolarAPI", 2012, "goes_aggregated_v4"),
    ],
)
def test_goes_resource_models(
    subtests,
    plant_simulation_utc_start,
    site_config,
    lat,
    lon,
    model,
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
        "plant": plant_simulation_utc_start,
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
