from pathlib import Path

import pytest
import openmdao.api as om

from h2integrate import RESOURCE_DEFAULT_DIR
from h2integrate.core.supported_models import supported_models
from h2integrate.converters.wind.floris import FlorisWindPlantPerformanceModel
from h2integrate.converters.wind.wind_pysam import PYSAMWindPlantPerformanceModel


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
                    "hsds_kwargs": {},
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
