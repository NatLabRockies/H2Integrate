from pathlib import Path

import pytest
import openmdao.api as om
from pytest import fixture

from h2integrate import RESOURCE_DEFAULT_DIR
from h2integrate.converters.solar.solar_pysam import PYSAMSolarPlantPerformanceModel
from h2integrate.resource.solar.nlr_nsrdb_dataset_model import NSRDBDatasetH5


on_hpc = Path("/datasets/NSRDB").is_dir()
# from h2integrate.converters.solar.solar_pysam import PYSAMSolarPlantPerformanceModel


@fixture
def pysam_performance_model(timezone, dt, n_timesteps):
    pysam_options = {
        "SystemDesign": {
            "array_type": 2,
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
            "dt": dt,
            "n_timesteps": n_timesteps,
            "start_time": "01/01/1900 00:30:00",
            "timezone": timezone,
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


@pytest.fixture
def plant_simulation_config(timezone, dt, n_timesteps):
    plant = {
        "plant_life": 30,
        "simulation": {
            "dt": dt,
            "n_timesteps": n_timesteps,
            "start_time": "01/01/1900 00:30:00",
            "timezone": timezone,
        },
    }
    return plant


@pytest.fixture
def solar_site_config(site_gid, lat, lon, model, resource_year):
    site_config = {
        "latitude": lat,
        "longitude": lon,
        "resources": {
            "solar_resource": {
                "resource_model": model,
                "resource_parameters": {
                    "resource_year": resource_year,
                    "site_gid": site_gid,
                    "latitude": lat,
                    "longitude": lon,
                    "use_hsds": False,
                    "hsds_kwargs": {},
                },
            }
        },
    }
    return site_config


# AEP for 2023 with dt=3600: 478280.4037256231 MW*h/year
# AEP for 2023 with dt=1800: 478549.95174139587 MW*h/year
# AEP for 2024 with dt=1800: 487861.01335131214 MW*h/year
# AEP for 2024 with dt=3600: 487378.273467741 MW*h/year
# config = NSRDBDatasetH5Config.from_dict(resource_config)


# fmt: off
@pytest.mark.integration
@pytest.mark.parametrize(
    "model,site_gid,lat,lon,resource_year,timezone,dt,n_timesteps,loc_param,expected_aep",
    [
        ("NSRDBDatasetH5",478473, 39.7555, -105.2211, 2024, 0, 1800, 17520, "gid", 487861.01335131214), # noqa: E501
        ("NSRDBDatasetH5",478473, 39.7555, -105.2211, 2024, 0, 3600, 8760, "gid", 487378.273467741),
        ("NSRDBDatasetH5",-1, 39.7555, -105.2211, 2024, 0, 3600, 8760, "lat/lon", 487378.273467741),
        ],
    ids=[
        "NSRDBDatasetH5-30min-csv",
        "NSRDBDatasetH5-60min-csv",
        "NSRDBDatasetH5-60min-csv-lat/lon",
    ]
)
# fmt: on
def test_nsrdb_dataset_from_csv_pvwatts(
    subtests,
    pysam_performance_model,
    plant_simulation_config,
    solar_site_config,
    expected_aep,
    loc_param,
):

    resource_config = {
        # "latitude": 39.7555,
        # "longitude": -105.2211,
        # "timezone": 0,
        # "site_gid": 478473,
        "location_input": loc_param,
        "save_to_csv": False,
        "load_from_csv": True,
        "csv_output_dir": RESOURCE_DEFAULT_DIR/"solar",
        "use_hsds": False,
        "hsds_kwargs": {},
        # "resource_year": 2023,
    }
    solar_site_config["resources"]["solar_resource"]["resource_parameters"] |= resource_config

    plant_config = {
        "site": solar_site_config,
        "plant": plant_simulation_config,
    }

    prob = om.Problem()
    resource_comp = NSRDBDatasetH5(
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



# fmt: off
@pytest.mark.hpc
@pytest.mark.skipif(not on_hpc, reason="not running on HPC")
@pytest.mark.parametrize(
    "model,site_gid,lat,lon,resource_year,timezone,dt,n_timesteps,loc_param,expected_aep",
    [
        ("NSRDBDatasetH5",478473,39.7555, -105.2211, 2024, 0, 1800, 17520, "gid", 487861.01335131214), # noqa: E501
        ("NSRDBDatasetH5",2074501,-27.3649, 152.67935, 2024, 0, 3600, 8760, "gid", 487378.273467741), # noqa: E501
        ("NSRDBDatasetH5",-1,39.7555, -105.2211, 2024, 0, 3600, 8760, "lat/lon", 487378.273467741),
        ],
    ids=[
        "NSRDBDatasetH5-30min-gid",
        "NSRDBDatasetH5-60min-gid",
        "NSRDBDatasetH5-60min-lat/lon",
    ]
)
# fmt: on
def test_nsrdb_dataset_from_dataset_pvwatts(
    subtests,
    pysam_performance_model,
    plant_simulation_config,
    solar_site_config,
    expected_aep,
    loc_param,
):

    actual_lat = 39.7555
    actual_lon = -105.2211
    actual_gid = 478473
    resource_config = {
        # "latitude": 39.7555,
        # "longitude": -105.2211,
        # "timezone": 0,
        # "site_gid": 478473,
        "location_input": loc_param,
        "save_to_csv": False,
        "load_from_csv": False,
        # "csv_output_dir": RESOURCE_DEFAULT_DIR/"solar",
        "use_hsds": False,
        "hsds_kwargs": {},
        # "resource_year": 2023,
    }
    solar_site_config["resources"]["solar_resource"]["resource_parameters"] |= resource_config

    plant_config = {
        "site": solar_site_config,
        "plant": plant_simulation_config,
    }

    prob = om.Problem()
    resource_comp = NSRDBDatasetH5(
        plant_config=plant_config,
        resource_config=plant_config["site"]["resources"]["solar_resource"]["resource_parameters"],
        driver_config={},
    )

    prob.model.add_subsystem("solar_resource", resource_comp, promotes=["*"])
    prob.model.add_subsystem("pv_perf", pysam_performance_model, promotes=["*"])
    prob.setup()

    if loc_param == "lat/lon":
        prob.model.set_val("solar_resource.latitude", actual_lat, units="deg")
        prob.model.set_val("solar_resource.longitude", actual_lon, units="deg")
    if loc_param == "gid":
        prob.model.set_val("solar_resource.site_gid", actual_gid, units="unitless")

    prob.run_model()

    aep = prob.get_val("pv_perf.annual_electricity_produced", units="MW*h/year")[0]

    with subtests.test("AEP"):
        assert pytest.approx(aep, rel=1e-6) == expected_aep
