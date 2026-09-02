from pathlib import Path

import pytest
import openmdao.api as om
from pytest import fixture
from openmdao.utils.units import valid_units

from h2integrate import RESOURCE_DEFAULT_DIR
from h2integrate.converters.solar.solar_pysam import PYSAMSolarPlantPerformanceModel
from h2integrate.resource.solar.nlr_nsrdb_dataset_model import NSRDBDatasetH5


on_hpc = Path("/datasets/NSRDB").is_dir()


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
def solar_site_config(lat, lon, model, resource_year):
    site_config = {
        "latitude": lat,
        "longitude": lon,
        "resources": {
            "solar_resource": {
                "resource_model": model,
                "resource_parameters": {
                    "resource_year": resource_year,
                    "latitude": lat,
                    "longitude": lon,
                    "use_hsds": False,
                },
            }
        },
    }
    return site_config


# fmt: off
@pytest.mark.integration
@pytest.mark.parametrize(
    "model,lat,lon,resource_year,timezone,dt,n_timesteps,expected_aep",
    [
        ("NSRDBDatasetH5", 39.7555, -105.2211, 2024, 0, 1800, 17520, 487861.01335131214),
        ("NSRDBDatasetH5", 39.7555, -105.2211, 2024, 0, 3600, 8760, 487378.273467741),
        ],
    ids=[
        "NSRDBDatasetH5-30min-csv",
        "NSRDBDatasetH5-60min-csv",
    ]
)
# fmt: on
def test_nsrdb_dataset_from_csv_pvwatts(
    subtests,
    pysam_performance_model,
    plant_simulation_config,
    solar_site_config,
    expected_aep,
):

    resource_config = {
        "save_to_csv": False,
        "load_from_csv": True,
        "csv_output_dir": RESOURCE_DEFAULT_DIR/"solar",
        "use_hsds": False,
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
    "model,lat,lon,resource_year,timezone,dt,n_timesteps,expected_aep",
    [
        ("NSRDBDatasetH5",39.7555, -105.2211, 2024, 0, 1800, 17520, 487861.01335131214),
        ("NSRDBDatasetH5",33.7555, -102.2211, 2024, 0, 3600, 8760, 487378.273467741),
        ],
    ids=[
        "NSRDBDatasetH5-30min",
        "NSRDBDatasetH5-60min",
    ]
)
# fmt: on
def test_nsrdb_dataset_from_dataset_pvwatts(
    subtests,
    pysam_performance_model,
    plant_simulation_config,
    solar_site_config,
    expected_aep,
):

    actual_lat = 39.7555
    actual_lon = -105.2211
    resource_config = {
        "save_to_csv": False,
        "load_from_csv": False,
        "use_hsds": False,
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

    prob.model.set_val("solar_resource.latitude", actual_lat, units="deg")
    prob.model.set_val("solar_resource.longitude", actual_lon, units="deg")

    prob.run_model()

    aep = prob.get_val("pv_perf.annual_electricity_produced", units="MW*h/year")[0]

    with subtests.test("AEP"):
        assert pytest.approx(aep, rel=1e-6) == expected_aep


@pytest.mark.unit
@pytest.mark.parametrize(
    "model,lat,lon,resource_year,timezone,dt,n_timesteps",
    [
        ("NSRDBDatasetH5", 39.7555, -105.2211, 2024, 0, 3600, 8760),
        ],
    ids=[
        "NSRDBDatasetH5-60min-csv",
    ]
)
def test_nsrdb_dataset_resource(
    subtests,
    plant_simulation_config,
    solar_site_config,
):

    resource_config = {
        "save_to_csv": False,
        "load_from_csv": True,
        "csv_output_dir": RESOURCE_DEFAULT_DIR/"solar",
        "use_hsds": False,
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
    prob.setup()
    prob.run_model()
    resource_data = prob.model.get_val("solar_resource_data")
    units_data = resource_data.pop("units")

    ratio_data_to_check = ["aod", "asymmetry","surface_albedo"]

    with subtests.test("Data as ratios has all values < 1"):
        assert all(all(resource_data[k]<1.0) for k in ratio_data_to_check)

    with subtests.test("Data in percent units has some value > 1"):
        assert all(any(resource_data[k]>1.0) for k,v in units_data.items() if v=="percent")

    with subtests.test("Resource data exists"):
        assert bool(resource_data)
    with subtests.test("fill_flag timeseries exists"):
        assert len(resource_data["fill_flag"]) == 8760

    with subtests.test("fill_flag_mapper"):
        assert isinstance(resource_data["fill_flag_mapper"], dict)

    with subtests.test("irrandiance units"):
        assert all(units_data[k] == "W/m**2" for k in resource_data if k.endswith("ni"))

    with subtests.test("All resource units are valid"):
        assert all(valid_units(v) for k, v in units_data.items())

    with subtests.test("Data renamed properly"):
        assert all(k not in resource_data for k,v in resource_comp.columns_translation.items())
        assert all(v in resource_data for k,v in resource_comp.columns_translation.items())

    with subtests.test("All units keys are in resource data"):
        assert not bool(set(units_data) - set(resource_data))

    with subtests.test("dataset filepath"):
        assert resource_data["dataset_filepath"] == "/datasets/NSRDB/current/nsrdb_2024.h5"

    with subtests.test("site GID"):
        assert resource_data["id"] == 478473
