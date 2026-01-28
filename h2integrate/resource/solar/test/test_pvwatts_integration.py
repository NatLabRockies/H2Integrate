import pytest
import openmdao.api as om
from pytest import fixture

from h2integrate.converters.solar.solar_pysam import PYSAMSolarPlantPerformanceModel
from h2integrate.resource.solar.openmeteo_solar import OpenMeteoHistoricalSolarResource
from h2integrate.resource.solar.nrel_developer_himawari_api_models import (
    Himawari7SolarAPI,
    Himawari8SolarAPI,
    HimawariTMYSolarAPI,
)
from h2integrate.resource.solar.nrel_developer_meteosat_prime_meridian_models import (
    MeteosatPrimeMeridianSolarAPI,
    MeteosatPrimeMeridianTMYSolarAPI,
)


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


@fixture
def plant_simulation_config():
    plant = {
        "plant_life": 30,
        "simulation": {
            "dt": 3600,
            "n_timesteps": 8760,
            "start_time": "01/01/1900 00:30:00",
            "timezone": 0,
        },
    }
    return plant


@fixture
def meteosat_prime_meridian_site():
    # Rome, Italy
    # filename: 41.9077_12.4368_2008_nsrdb_msg_v4_60min_utc_tz.csv
    meteosat_site = {
        "latitude": 41.9077,
        "longitude": 12.4368,
        "resources": {
            "solar_resource": {
                "resource_model": "meteosat_solar_v3_api",
                "resource_parameters": {
                    "resource_year": 2008,
                },
            }
        },
    }
    return meteosat_site


@fixture
def tmy_site_config():
    # Brisbane, Australia
    tmy_file = "-27.3649_152.67935_tmy-2020_himawari_tmy_v3_60min_utc_tz.csv"
    australia_site = {
        "latitude": -27.3649,
        "longitude": 152.67935,
        "resources": {
            "solar_resource": {
                "resource_model": "meteosat_tmy_solar_v3_api",
                "resource_parameters": {
                    "resource_year": "tmy-2022",
                    "resource_filename": tmy_file,
                },
            }
        },
    }
    return australia_site


@fixture
def himawari7_site_config_tmy():
    # Brisbane, Australia
    himawari7_site_tmy = {
        "latitude": -27.3649,
        "longitude": 152.67935,
        "resources": {
            "solar_resource": {
                "resource_model": "himawari_tmy_solar_v3_api",
                "resource_parameters": {
                    "resource_year": "tmy-2020",
                },
            }
        },
    }
    return himawari7_site_tmy


@fixture
def himawari7_site_config():
    # Brisbane, Australia
    himawari7_site_tmy = {
        "latitude": -27.3649,
        "longitude": 152.67935,
        "resources": {
            "solar_resource": {
                "resource_model": "himawari7_solar_v3_api",
                "resource_parameters": {
                    "resource_year": 2013,
                },
            }
        },
    }
    return himawari7_site_tmy


@fixture
def himawari8_site_config():
    # KL, Malaysia
    himawari8_site = {
        "latitude": 3.25735,
        "longitude": 101.656312,
        "resources": {
            "solar_resource": {
                "resource_model": "himawari8_solar_v3_api",
                "resource_parameters": {
                    "resource_year": 2020,
                },
            }
        },
    }
    return himawari8_site


@fixture
def openmeteo_site_config():
    site = {
        "latitude": 44.04218,
        "longitude": -95.19757,
        "resources": {
            "solar_resource": {
                "resource_model": "openmeteo_solar_api",
                "resource_parameters": {
                    "resource_year": 2023,
                },
            }
        },
    }
    return site


def test_pvwatts_with_himawari7(
    pysam_performance_model, plant_simulation_config, himawari7_site_config, subtests
):
    plant_config = {
        "site": himawari7_site_config,
        "plant": plant_simulation_config,
    }

    prob = om.Problem()
    resource_comp = Himawari7SolarAPI(
        plant_config=plant_config,
        resource_config=plant_config["site"]["resources"]["solar_resource"]["resource_parameters"],
        driver_config={},
    )

    prob.model.add_subsystem("solar_resource", resource_comp, promotes=["*"])
    prob.model.add_subsystem("pv_perf", pysam_performance_model, promotes=["*"])
    prob.setup()
    prob.run_model()

    aep = prob.get_val("pv_perf.annual_energy", units="MW*h/year")[0]

    with subtests.test("AEP"):
        assert pytest.approx(aep, rel=1e-6) == 473577.280269

    with subtests.test("Site latitude"):
        resource_lat = prob.get_val("pv_perf.solar_resource_data").get("site_lat", 0)
        assert pytest.approx(resource_lat, rel=1e-3) == himawari7_site_config["latitude"]

    with subtests.test("Site longitude"):
        resource_lat = prob.get_val("pv_perf.solar_resource_data").get("site_lon", 0)
        assert pytest.approx(resource_lat, rel=1e-3) == himawari7_site_config["longitude"]


def test_pvwatts_with_himawari8(
    pysam_performance_model, plant_simulation_config, himawari8_site_config, subtests
):
    plant_config = {
        "site": himawari8_site_config,
        "plant": plant_simulation_config,
    }

    prob = om.Problem()
    resource_comp = Himawari8SolarAPI(
        plant_config=plant_config,
        resource_config=plant_config["site"]["resources"]["solar_resource"]["resource_parameters"],
        driver_config={},
    )

    prob.model.add_subsystem("solar_resource", resource_comp, promotes=["*"])
    prob.model.add_subsystem("pv_perf", pysam_performance_model, promotes=["*"])
    prob.setup()
    prob.run_model()

    aep = prob.get_val("pv_perf.annual_energy", units="MW*h/year")[0]

    with subtests.test("AEP"):
        assert pytest.approx(aep, rel=1e-6) == 411251.781327

    with subtests.test("Site latitude"):
        resource_lat = prob.get_val("pv_perf.solar_resource_data").get("site_lat", 0)
        assert pytest.approx(resource_lat, rel=1e-3) == himawari8_site_config["latitude"]

    with subtests.test("Site longitude"):
        resource_lat = prob.get_val("pv_perf.solar_resource_data").get("site_lon", 0)
        assert pytest.approx(resource_lat, rel=1e-3) == himawari8_site_config["longitude"]


def test_pvwatts_with_meteosat_pm(
    pysam_performance_model, plant_simulation_config, meteosat_prime_meridian_site, subtests
):
    plant_config = {
        "site": meteosat_prime_meridian_site,
        "plant": plant_simulation_config,
    }

    prob = om.Problem()
    resource_comp = MeteosatPrimeMeridianSolarAPI(
        plant_config=plant_config,
        resource_config=plant_config["site"]["resources"]["solar_resource"]["resource_parameters"],
        driver_config={},
    )

    prob.model.add_subsystem("solar_resource", resource_comp, promotes=["*"])
    prob.model.add_subsystem("pv_perf", pysam_performance_model, promotes=["*"])
    prob.setup()
    prob.run_model()

    aep = prob.get_val("pv_perf.annual_energy", units="MW*h/year")[0]

    with subtests.test("AEP"):
        assert pytest.approx(aep, rel=1e-6) == 410211.9419

    with subtests.test("Site latitude"):
        resource_lat = prob.get_val("pv_perf.solar_resource_data").get("site_lat", 0)
        assert pytest.approx(resource_lat, rel=1e-3) == meteosat_prime_meridian_site["latitude"]

    with subtests.test("Site longitude"):
        resource_lat = prob.get_val("pv_perf.solar_resource_data").get("site_lon", 0)
        assert (
            pytest.approx(resource_lat, abs=2 * 1e-2) == meteosat_prime_meridian_site["longitude"]
        )


def test_pvwatts_with_himawari_tmy(
    pysam_performance_model, plant_simulation_config, himawari7_site_config_tmy, subtests
):
    plant_config = {
        "site": himawari7_site_config_tmy,
        "plant": plant_simulation_config,
    }

    prob = om.Problem()
    resource_comp = HimawariTMYSolarAPI(
        plant_config=plant_config,
        resource_config=plant_config["site"]["resources"]["solar_resource"]["resource_parameters"],
        driver_config={},
    )

    prob.model.add_subsystem("solar_resource", resource_comp, promotes=["*"])
    prob.model.add_subsystem("pv_perf", pysam_performance_model, promotes=["*"])
    prob.setup()
    prob.run_model()

    aep = prob.get_val("pv_perf.annual_energy", units="MW*h/year")[0]

    with subtests.test("AEP"):
        assert pytest.approx(aep, rel=1e-6) == 510709.633402

    with subtests.test("Site latitude"):
        resource_lat = prob.get_val("pv_perf.solar_resource_data").get("site_lat", 0)
        assert pytest.approx(resource_lat, rel=1e-3) == himawari7_site_config_tmy["latitude"]

    with subtests.test("Site longitude"):
        resource_lat = prob.get_val("pv_perf.solar_resource_data").get("site_lon", 0)
        assert pytest.approx(resource_lat, rel=1e-3) == himawari7_site_config_tmy["longitude"]


def test_pvwatts_with_meteosat_pm_tmy(
    pysam_performance_model, plant_simulation_config, tmy_site_config, subtests
):
    plant_config = {
        "site": tmy_site_config,
        "plant": plant_simulation_config,
    }

    prob = om.Problem()
    resource_comp = MeteosatPrimeMeridianTMYSolarAPI(
        plant_config=plant_config,
        resource_config=plant_config["site"]["resources"]["solar_resource"]["resource_parameters"],
        driver_config={},
    )

    prob.model.add_subsystem("solar_resource", resource_comp, promotes=["*"])
    prob.model.add_subsystem("pv_perf", pysam_performance_model, promotes=["*"])
    prob.setup()
    prob.run_model()

    aep = prob.get_val("pv_perf.annual_energy", units="MW*h/year")[0]

    with subtests.test("AEP"):
        assert pytest.approx(aep, rel=1e-6) == 510709.633402

    with subtests.test("Site latitude"):
        resource_lat = prob.get_val("pv_perf.solar_resource_data").get("site_lat", 0)
        assert pytest.approx(resource_lat, rel=1e-3) == tmy_site_config["latitude"]

    with subtests.test("Site longitude"):
        resource_lat = prob.get_val("pv_perf.solar_resource_data").get("site_lon", 0)
        assert pytest.approx(resource_lat, rel=1e-3) == tmy_site_config["longitude"]


def test_pvwatts_with_openmeteo_solar(
    pysam_performance_model, plant_simulation_config, openmeteo_site_config, subtests
):
    plant_config = {
        "site": openmeteo_site_config,
        "plant": plant_simulation_config,
    }

    prob = om.Problem()
    resource_comp = OpenMeteoHistoricalSolarResource(
        plant_config=plant_config,
        resource_config=plant_config["site"]["resources"]["solar_resource"]["resource_parameters"],
        driver_config={},
    )

    prob.model.add_subsystem("solar_resource", resource_comp, promotes=["*"])
    prob.model.add_subsystem("pv_perf", pysam_performance_model, promotes=["*"])
    prob.setup()
    prob.run_model()

    aep = prob.get_val("pv_perf.annual_energy", units="MW*h/year")[0]

    with subtests.test("AEP"):
        assert pytest.approx(aep, rel=1e-6) == 443558.17053592583

    with subtests.test("Site latitude"):
        resource_lat = prob.get_val("pv_perf.solar_resource_data").get("site_lat", 0)
        assert pytest.approx(resource_lat, rel=1e-3) == openmeteo_site_config["latitude"]

    with subtests.test("Site longitude"):
        resource_lat = prob.get_val("pv_perf.solar_resource_data").get("site_lon", 0)
        assert pytest.approx(resource_lat, rel=1e-3) == openmeteo_site_config["longitude"]
