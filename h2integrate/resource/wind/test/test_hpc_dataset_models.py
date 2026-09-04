from pathlib import Path

import pytest
import openmdao.api as om
from openmdao.utils.units import valid_units

from h2integrate import RESOURCE_DEFAULT_DIR
from h2integrate.core.supported_models import supported_models
from h2integrate.converters.wind.floris import FlorisWindPlantPerformanceModel
from h2integrate.converters.wind.wind_pysam import PYSAMWindPlantPerformanceModel
from h2integrate.resource.wind.nlr_hrrr_met_toolkit_dataset_model import WTKHRRRMETDatasetH5Config


on_hpc = Path("/datasets/WIND").is_dir()


@pytest.fixture
def wind_site_config(lat, lon, model, resource_year):
    site_config = {
        "latitude": lat,
        "longitude": lon,
        "resources": {
            "wind_resource": {
                "resource_model": model,
                "resource_parameters": {
                    "resource_year": resource_year,
                    "latitude": lat,
                    "longitude": lon,
                    "use_hsds": False,
                    "save_to_csv": True,
                    "load_from_csv": True,
                    "csv_output_dir": RESOURCE_DEFAULT_DIR / "wind",
                },
            }
        },
    }
    return site_config


@pytest.mark.integration
@pytest.mark.parametrize(
    "model,lat,lon,resource_year,timezone,expected_aep",
    [
        (
            "WTKHRRRMETDatasetH5",
            37.3376,
            -105.7076,
            2025,
            0,
            439285.87881150434,
        ),
    ],
    ids=[
        "HRRRMETToolkitWindAPI-813606",
    ],
)
# fmt: on
def test_pysam_windpower_integration(
    subtests, plant_simulation, wind_site_config, wind_plant_config, model, expected_aep
):
    prob = om.Problem()

    plant_config = {
        "site": wind_site_config,
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
        assert pytest.approx(aep, rel=1e-6, abs=0.5) == expected_aep


@pytest.mark.integration
@pytest.mark.parametrize(
    "model,lat,lon,resource_year,timezone,expected_aep",
    [
        ("WTKHRRRMETDatasetH5", 37.3376, -105.7076, 2025, 0, 16278.222138130743),
    ],
    ids=[
        "HRRRMETToolkitWindAPI-813606",
    ],
)
# fmt: on
def test_floris_integration(
    subtests, plant_simulation, wind_site_config, floris_config, model, expected_aep
):
    prob = om.Problem()

    plant_config = {
        "site": wind_site_config,
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


@pytest.mark.hpc
@pytest.mark.skipif(not on_hpc, reason="not running on HPC")
@pytest.mark.parametrize(
    "model,lat,lon,resource_year,timezone,expected_aep",
    [
        (
            "WTKHRRRMETDatasetH5",
            39.7555,
            -105.2211,
            2024,
            0,
            284248.8972640701,
        ),
        (
            "WTKHRRRMETDatasetH5",
            37.3376,
            -105.7076,
            2025,
            0,
            439285.87881150434,
        ),
    ],
    ids=[
        "HRRRMETToolkitWindAPI-852124",
        "HRRRMETToolkitWindAPI-813606",
    ],
)
# fmt: on
def test_hpc_integration_with_pysam(
    subtests, plant_simulation, wind_site_config, wind_plant_config, model, expected_aep
):
    wind_site_config["resources"]["wind_resource"]["resource_parameters"]["save_to_csv"] = False
    wind_site_config["resources"]["wind_resource"]["resource_parameters"]["load_from_csv"] = False
    wind_site_config["resources"]["wind_resource"]["resource_parameters"]["csv_output_dir"] = None
    prob = om.Problem()

    plant_config = {
        "site": wind_site_config,
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
        assert pytest.approx(aep, rel=1e-6, abs=0.5) == expected_aep


@pytest.mark.hpc
@pytest.mark.skipif(not on_hpc, reason="not running on HPC")
@pytest.mark.parametrize(
    "model,lat,lon,resource_year,timezone,expected_aep",
    [
        (
            "WTKHRRRMETDatasetH5",
            39.7555,
            -105.2211,
            2024,
            0,
            9294.347553939786,
        ),
        ("WTKHRRRMETDatasetH5", 37.3376, -105.7076, 2025, 0, 16278.222138130743),
    ],
    ids=[
        "HRRRMETToolkitWindAPI-852124",
        "HRRRMETToolkitWindAPI-813606",
    ],
)
# fmt: on
def test_hpc_integration_with_floris(
    subtests, plant_simulation, wind_site_config, floris_config, model, expected_aep
):
    wind_site_config["resources"]["wind_resource"]["resource_parameters"]["save_to_csv"] = False
    wind_site_config["resources"]["wind_resource"]["resource_parameters"]["load_from_csv"] = False
    wind_site_config["resources"]["wind_resource"]["resource_parameters"]["csv_output_dir"] = None

    prob = om.Problem()

    plant_config = {
        "site": wind_site_config,
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


@pytest.mark.unit
def test_wtk_hrrr_config(subtests, temp_dir):
    config_dict = {
        "latitude": 35.2018863,
        "longitude": -101.945027,
        "resource_year": 2020,
        "timezone": 0,
        "save_to_csv": False,
        "load_from_csv": True,
        "csv_output_dir": RESOURCE_DEFAULT_DIR,
    }

    config = WTKHRRRMETDatasetH5Config.from_dict(config_dict)

    with subtests.test("Output directory is updated to have resource-subfolder"):
        assert config.csv_output_dir == RESOURCE_DEFAULT_DIR / "wind"

    config_dict["csv_output_dir"] = RESOURCE_DEFAULT_DIR / "wind"
    config = WTKHRRRMETDatasetH5Config.from_dict(config_dict)

    with subtests.test("Output directory has resource-subfolder"):
        assert config.csv_output_dir == RESOURCE_DEFAULT_DIR / "wind"

    # make temp csv file with dataset name
    fake_resource_fpath = temp_dir / "10000-32.202_-101.945_2020_hrrr_met_v1_60min_utc.csv"
    with fake_resource_fpath.open(mode="w", encoding="utf-8") as f:
        # Write the header to a csv file
        f.write("temp_file")

    config_dict["csv_output_dir"] = temp_dir
    config = WTKHRRRMETDatasetH5Config.from_dict(config_dict)

    with subtests.test("Output directory does not have resource-subfolder"):
        assert config.csv_output_dir == temp_dir


@pytest.mark.unit
@pytest.mark.parametrize(
    "model,lat,lon,resource_year,timezone",
    [("WTKHRRRMETDatasetH5", 37.3376, -105.7076, 2025, 0)],
    ids=["HRRRMETToolkitWindAPI-813606"],
)
def test_wtk_hrrr_dataset_resource_data(subtests, plant_simulation, wind_site_config):
    prob = om.Problem()

    plant_config = {
        "site": wind_site_config,
        "plant": plant_simulation,
    }

    resource_comp = supported_models["WTKHRRRMETDatasetH5"](
        plant_config=plant_config,
        resource_config=plant_config["site"]["resources"]["wind_resource"]["resource_parameters"],
        driver_config={},
    )

    prob.model.add_subsystem("wind_resource", resource_comp, promotes=["*"])
    prob.setup()
    prob.run_model()

    resource_data = prob.model.get_val("wind_resource_data")
    with subtests.test("Resource data"):
        assert bool(resource_data)

    units_data = resource_data.pop("units")

    with subtests.test("18 wind speed heights"):
        assert len([k for k in resource_data if "wind_speed_" in k]) == 18
    with subtests.test("18 wind direction heights"):
        assert len([k for k in resource_data if "wind_direction_" in k]) == 18
    with subtests.test("19 temperature heights"):
        assert len([k for k in resource_data if k.startswith("temperature_")]) == 19
    with subtests.test("4 pressure heights"):
        assert len([k for k in resource_data if k.startswith("pressure_")]) == 4

    with subtests.test("Wind speed units"):
        assert all(units_data[k] == "m/s" for k in resource_data if "wind_speed_" in k)
    with subtests.test("Wind direction units"):
        assert all(units_data[k] == "deg" for k in resource_data if "wind_direction_" in k)
    with subtests.test("Temperature units"):
        assert all(units_data[k] == "degC" for k in resource_data if k.startswith("temperature_"))
    with subtests.test("Pressure units"):
        assert all(units_data[k] == "atm" for k in resource_data if k.startswith("pressure_"))
    with subtests.test("Pressure was converted from hPa to atm"):
        assert all(all(v < 1.125) for k, v in resource_data.items() if k.startswith("pressure_"))
    with subtests.test("All resource units are valid"):
        assert all(valid_units(v) for k, v in units_data.items())
