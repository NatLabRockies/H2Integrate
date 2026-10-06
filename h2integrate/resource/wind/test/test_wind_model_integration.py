import pytest
import openmdao.api as om

from h2integrate.core.supported_models import supported_models
from h2integrate.converters.wind.floris import FlorisWindPlantPerformanceModel
from h2integrate.converters.wind.wind_pysam import PYSAMWindPlantPerformanceModel


@pytest.mark.integration
@pytest.mark.parametrize(
    "model,which,lat,lon,resource_year,model_name,timezone,expected_aep",
    [
        (
            "WTKNLRDeveloperAPIWindResource",
            "wind",
            35.2018863,
            -101.945027,
            2012,
            "wtk_api_v2",
            0,
            1014129.048439629,
        ),
        (
            "HRRRMETToolkitWindAPI",
            "wind",
            37.3376,
            -105.7076,
            2025,
            "hrrr_met_toolkit",
            0,
            439285.35435542057,
        ),
        (
            "OpenMeteoHistoricalWindResource",
            "wind",
            44.04218,
            -95.19757,
            2023,
            "openmeteo_archive",
            -6,
            900890.9995006532,
        ),
    ],
    ids=[
        "WTKNLRDeveloperAPIWindResource",
        "HRRRMETToolkitWindAPI",
        "OpenMeteoHistoricalWindResource",
    ],
)
# fmt: on
def test_pysam_windpower_integration(
    subtests, plant_simulation, site_config, wind_plant_config, model, expected_aep
):
    prob = om.Problem()

    plant_config = {
        "site": site_config,
        "plant": plant_simulation,
    }

    resource_comp = supported_models[model](
        plant_config=plant_config,
        resource_config=plant_config["site"]["resources"]["wind_resource"]["resource_parameters"],
        driver_config={},
    )

    wind_plant = PYSAMWindPlantPerformanceModel(
        plant_config=plant_config,
        tech_config={"model_inputs": {"performance_parameters": wind_plant_config}},
        driver_config={},
    )

    prob.model.add_subsystem("wind_resource", resource_comp, promotes=["*"])
    prob.model.add_subsystem("wind_perf", wind_plant, promotes=["*"])
    prob.setup()
    prob.run_model()

    aep = prob.get_val("wind_perf.annual_electricity_produced", units="MW*h/year")[0]

    with subtests.test("AEP"):
        assert pytest.approx(aep, rel=1e-6) == expected_aep

    with subtests.test("Site latitude"):
        resource_lat = prob.get_val("wind_perf.wind_resource_data").get("site_lat", 0)
        assert pytest.approx(resource_lat, rel=1e-3) == site_config["latitude"]

    with subtests.test("Site longitude"):
        resource_lon = prob.get_val("wind_perf.wind_resource_data").get("site_lon", 0)
        assert pytest.approx(resource_lon, rel=1e-3) == site_config["longitude"]


@pytest.mark.integration
@pytest.mark.parametrize(
    "model,which,lat,lon,resource_year,model_name,timezone,expected_aep",
    [
        (
            "WTKNLRDeveloperAPIWindResource",
            "wind",
            35.2018863,
            -101.945027,
            2012,
            "wtk_api_v2",
            0,
            37007.33639643173,
        ),
        (
            "HRRRMETToolkitWindAPI",
            "wind",
            37.3376,
            -105.7076,
            2025,
            "hrrr_met_toolkit",
            0,
            16278.222138130743,
        ),
        (
            "OpenMeteoHistoricalWindResource",
            "wind",
            44.04218,
            -95.19757,
            2023,
            "openmeteo_archive",
            -6,
            36457.44603023616864,
        ),
    ],
    ids=[
        "WTKNLRDeveloperAPIWindResource",
        "HRRRMETToolkitWindAPI",
        "OpenMeteoHistoricalWindResource",
    ],
)
# fmt: on
def test_floris_integration(
    subtests, plant_simulation, site_config, floris_config, model, expected_aep
):
    prob = om.Problem()

    plant_config = {
        "site": site_config,
        "plant": plant_simulation,
    }

    resource_comp = supported_models[model](
        plant_config=plant_config,
        resource_config=plant_config["site"]["resources"]["wind_resource"]["resource_parameters"],
        driver_config={},
    )

    wind_plant = FlorisWindPlantPerformanceModel(
        plant_config=plant_config,
        tech_config={"model_inputs": {"performance_parameters": floris_config}},
        driver_config={},
    )

    prob.model.add_subsystem("wind_resource", resource_comp, promotes=["*"])
    prob.model.add_subsystem("wind_perf", wind_plant, promotes=["*"])
    prob.setup()
    prob.run_model()

    aep = prob.get_val("wind_perf.annual_electricity_produced", units="MW*h/year")[0]

    with subtests.test("AEP"):
        assert pytest.approx(aep, rel=1e-6) == expected_aep

    with subtests.test("Site latitude"):
        resource_lat = prob.get_val("wind_perf.wind_resource_data").get("site_lat", 0)
        assert pytest.approx(resource_lat, rel=1e-3) == site_config["latitude"]

    with subtests.test("Site longitude"):
        resource_lon = prob.get_val("wind_perf.wind_resource_data").get("site_lon", 0)
        assert pytest.approx(resource_lon, rel=1e-3) == site_config["longitude"]
