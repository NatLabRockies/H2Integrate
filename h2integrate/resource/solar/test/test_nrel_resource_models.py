from pathlib import Path

import pytest
import openmdao.api as om

from h2integrate.core.supported_models import supported_models


@pytest.mark.unit
@pytest.mark.parametrize(
    "lat,lon,model,resource_year,model_name",
    [
        (34.22, -102.75, "GOESAggregatedSolarAPI", 2012, "goes_aggregated_v4"),
        (-27.3649, 152.67935, "HimawariTMYSolarAPI", "tmy-2020", "himawari_tmy_v3"),
        (-27.3649, 152.67935, "Himawari7SolarAPI", 2013, "himawari7_v3"),
        (3.25735, 101.656312, "Himawari8SolarAPI", 2020, "himawari8_v3"),
        (-27.3649, 152.67935, "MeteosatPrimeMeridianTMYSolarAPI", "tmy-2022", "himawari_tmy_v3"),
        (41.9077, 12.4368, "MeteosatPrimeMeridianSolarAPI", 2008, "nsrdb_msg_v4"),
    ],
)
def test_nrel_solar_resource_file_downloads(
    subtests,
    plant_simulation_utc_start,
    site_config,
    lat,
    lon,
    model,
    resource_year,
    model_name,
):
    plant_config = {
        "site": site_config,
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

    name_expected = f"{lat}_{lon}_{resource_year}_{model_name}_60min_utc_tz.csv"
    with subtests.test("Filename expected"):
        assert name_expected == (Path(data["filepath"])).name
