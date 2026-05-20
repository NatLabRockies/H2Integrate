import pytest
import openmdao.api as om
from pytest import fixture

from h2integrate.core.supported_models import supported_models
from h2integrate.converters.solar.solar_pysam import PYSAMSolarPlantPerformanceModel


@fixture
def pysam_performance_model():
    pysam_options = {
        "SystemDesign": {
            "array_type": 2,
            "azimuth": 180,
            "bifaciality": 0.65,
            "inv_eff": 96.0,
            "losses": 14.0757,
            "module_type": 0,
            "rotlim": 45.0,
            "gcr": 0.3,
        },
    }
    pysam_options["SystemDesign"].update({"tilt": 0.0})
    pv_design_dict = {
        "pv_capacity_kWdc": 250000.0,
        "dc_ac_ratio": 1.23,
        "create_model_from": "default",
        "config_name": "PVWattsSingleOwner",
        "tilt": 0.0,
        "tilt_angle_func": "none",  # "lat-func",
        "pysam_options": pysam_options,
    }

    tech_config_dict = {
        "model_inputs": {
            "performance_parameters": pv_design_dict,
        }
    }

    plant = {
        "plant_life": 30,
        "simulation": {
            "dt": 3600,
            "n_timesteps": 8760,
            "start_time": "01/01/1900 00:30:00",
            "timezone": 0,
        },
    }

    plant_config = {
        "plant": plant,
        "site": {"latitude": 30.6617, "longitude": -101.7096, "resources": {}},
    }

    comp = PYSAMSolarPlantPerformanceModel(
        plant_config=plant_config,
        tech_config=tech_config_dict,
        driver_config={},
    )

    return comp


# fmt: off
@pytest.mark.integration
@pytest.mark.parametrize(
    "model,which,lat,lon,resource_year,model_name,timezone,lon_tol,expected_aep",
    [
        ("Himawari7SolarAPI", "solar", -27.3649, 152.67935, 2013, "himawari7_v3", 0, 2e-2, 473577.280269),  # noqa: E501
        ("Himawari8SolarAPI", "solar", 3.25735, 101.656312, 2020, "himawari8_v3", 0, 1e-2, 411251.781327),  # noqa: E501
        ("HimawariTMYSolarAPI", "solar", -27.3649, 152.67935, "tmy-2020", "himawari_tmy_v3", 0, 2e-2, 510709.633402),  # noqa: E501
        ("MeteosatPrimeMeridianSolarAPI", "solar", 41.9077, 12.4368, 2008, "nsrdb_msg_v4", 0, 2e-2, 410211.9419),  # noqa: E501
        pytest.param("MeteosatPrimeMeridianTMYSolarAPI", "solar", -27.3649, 152.67935, "tmy-2022", "himawari_tmy_v3", 0, 1e-3, 510709.633402, marks=pytest.mark.xfail(reason="Longitude mismatch")),  # noqa: E501
        ("OpenMeteoHistoricalSolarResource", "solar", 44.04218, -95.19757, 2023, "openmeteo_archive_solar", 0, 1e-3, 443558.17053592583),  # noqa: E501
        ("OpenMeteoHistoricalSolarResource", "solar", -28.454864, 114.551749, 2024, "openmeteo_archive_solar", 8, 2e-2, 192656.49240723),  # noqa: E501
    ],
    ids=[
        "Himawari7SolarAPI",
        "Himawari8SolarAPI",
        "HimawariTMYSolarAPI",
        "MeteosatPrimeMeridianSolarAPI",
        "MeteosatPrimeMeridianTMYSolarAPI",
        "OpenMeteoHistoricalSolarResource",
        "OpenMeteoHistoricalSolarResource-LeapYear",
    ]
)
# fmt: on
def test_pvwatts_integration(
    subtests,
    pysam_performance_model,
    model,
    which,
    resource_year,
    plant_simulation,
    site_config,
    lon_tol,
    expected_aep,
):
    plant_config = {
        "site": site_config,
        "plant": plant_simulation,
    }

    prob = om.Problem()
    resource_comp = supported_models[model](
        plant_config=plant_config,
        resource_config=plant_config["site"]["resources"]["solar_resource"]["resource_parameters"],
        driver_config={},
    )

    prob.model.add_subsystem("solar_resource", resource_comp, promotes=["*"])
    prob.model.add_subsystem("pv_perf", pysam_performance_model, promotes=["*"])
    prob.setup()
    prob.run_model()

    aep = prob.get_val("pv_perf.annual_electricity_produced", units="MW*h/year")[0]

    with subtests.test("AEP"):
        assert pytest.approx(aep, rel=1e-6) == expected_aep

    with subtests.test("Site latitude"):
        resource_lat = prob.get_val("pv_perf.solar_resource_data").get("site_lat", 0)
        assert pytest.approx(resource_lat, rel=1e-3) == site_config["latitude"]

    with subtests.test("Site longitude"):
        resource_lon = prob.get_val("pv_perf.solar_resource_data").get("site_lon", 0)
        assert pytest.approx(resource_lon, abs=lon_tol) == site_config["longitude"]
