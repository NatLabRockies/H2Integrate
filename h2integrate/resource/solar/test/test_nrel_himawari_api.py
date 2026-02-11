from pathlib import Path

import pytest
import openmdao.api as om

from h2integrate.core.supported_models import supported_models


@pytest.fixture
def himawari_site_config(lat, lon, model, resource_year):
    site_config = {
        "latitude": lat,
        "longitude": lon,
        "resources": {
            "solar_resource": {
                "resource_model": model,
                "resource_parameters": {
                    "resource_year": resource_year,
                },
            }
        },
    }
    return site_config


@pytest.mark.unit
@pytest.mark.parametrize(
    "lat,lon,model,resource_year,model_name",
    [
        (-27.3649, 152.67935, "HimawariTMYSolarAPI", "tmy-2020", "himawari_tmy"),
        (-27.3649, 152.67935, "Himawari7SolarAPI", 2013, "himawari7"),
        (3.25735, 101.656312, "Himawari8SolarAPI", 2020, "himawari8"),
    ],
)
def test_himawari_tmy(
    subtests,
    plant_simulation_utc_start,
    himawari_site_config,
    lat,
    lon,
    model,
    resource_year,
    model_name,
):
    plant_config = {
        "site": himawari_site_config,
        "plant": plant_simulation_utc_start,
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
    data = prob.get_val("resource.solar_resource_data")

    name_expected = f"{lat}_{lon}_{resource_year}_{model_name}_v3_60min_utc_tz.csv"
    with subtests.test("Filename expected"):
        assert name_expected == (Path(data["filepath"])).name
