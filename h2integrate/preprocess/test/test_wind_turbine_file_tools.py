import shutil

import numpy as np
import pytest
import openmdao.api as om

from h2integrate import EXAMPLE_DIR
from h2integrate.core.utilities import load_yaml
from h2integrate.converters.wind.floris import FlorisWindPlantPerformanceModel
from h2integrate.core.inputs.validation import load_tech_yaml, load_plant_yaml
from h2integrate.converters.wind.wind_pysam import PYSAMWindPlantPerformanceModel
from h2integrate.preprocess.wind_turbine_file_tools import (
    export_turbine_to_pysam_format,
    export_turbine_to_floris_format,
)
from h2integrate.resource.wind.nrel_developer_wtk_api import WTKNRELDeveloperAPIWindResource


def test_turbine_export_error(subtests):
    invalid_turbine_name = "NREL_1.5MW"
    with pytest.raises(ValueError) as excinfo:
        export_turbine_to_pysam_format(invalid_turbine_name)
        assert f"Turbine {invalid_turbine_name} was not found" in str(excinfo.value)

    with pytest.raises(ValueError) as excinfo:
        export_turbine_to_floris_format(invalid_turbine_name)
        assert f"Turbine {invalid_turbine_name} was not found" in str(excinfo.value)


def test_pysam_turbine_export(subtests):
    turbine_name = "NREL_6MW_196"
    output_fpath = export_turbine_to_pysam_format(turbine_name)

    with subtests.test("File was created"):
        assert output_fpath.exists()
        assert output_fpath.is_file()

    pysam_options = load_yaml(output_fpath)

    plant_config_path = EXAMPLE_DIR / "05_wind_h2_opt" / "plant_config.yaml"
    tech_config_path = EXAMPLE_DIR / "05_wind_h2_opt" / "tech_config.yaml"

    plant_config = load_plant_yaml(plant_config_path)
    tech_config = load_tech_yaml(tech_config_path)

    plant_config_for_resource = {k: v for k, v in plant_config.items() if k != "sites"}
    plant_config_for_resource.update(plant_config["sites"])

    updated_parameters = {
        "turbine_rating_kw": np.max(
            pysam_options["Turbine"].get("wind_turbine_powercurve_powerout")
        ),
        "rotor_diameter": pysam_options["Turbine"].pop("wind_turbine_rotor_diameter"),
        "hub_height": pysam_options["Turbine"].pop("wind_turbine_hub_ht"),
        "pysam_options": pysam_options,
    }

    tech_config["technologies"]["wind"]["model_inputs"]["performance_parameters"].update(
        updated_parameters
    )

    prob = om.Problem()
    wind_resource = WTKNRELDeveloperAPIWindResource(
        plant_config=plant_config_for_resource,
        resource_config=plant_config["sites"]["site"]["resources"]["wind_resource"][
            "resource_parameters"
        ],
        driver_config={},
    )

    wind_plant = PYSAMWindPlantPerformanceModel(
        plant_config=plant_config,
        tech_config=tech_config["technologies"]["wind"],
        driver_config={},
    )

    prob.model.add_subsystem("wind_resource", wind_resource, promotes=["*"])
    prob.model.add_subsystem("wind_plant", wind_plant, promotes=["*"])
    prob.setup()
    prob.run_model()

    with subtests.test("File runs with WindPower, check total capacity"):
        assert (
            pytest.approx(
                prob.get_val("wind_plant.rated_electricity_production", units="MW"), rel=1e-6
            )
            == 300.0
        )

    with subtests.test("File runs with WindPower, check turbine size"):
        assert (
            pytest.approx(prob.get_val("wind_plant.wind_turbine_rating", units="MW"), rel=1e-6)
            == 6.0
        )

    with subtests.test("File runs with WindPower, check AEP"):
        assert (
            pytest.approx(
                prob.get_val("wind_plant.annual_electricity_produced", units="MW*h/yr")[0], rel=1e-6
            )
            == 1391425.64
        )


def test_floris_turbine_export(subtests):
    turbine_name = "NREL_6MW_196"
    output_fpath = export_turbine_to_floris_format(turbine_name)

    with subtests.test("File was created"):
        assert output_fpath.exists()
        assert output_fpath.is_file()

    floris_options = load_yaml(output_fpath)

    plant_config_path = EXAMPLE_DIR / "05_wind_h2_opt" / "plant_config.yaml"
    tech_config_path = EXAMPLE_DIR / "26_floris" / "tech_config.yaml"

    plant_config = load_plant_yaml(plant_config_path)
    tech_config = load_tech_yaml(tech_config_path)

    cache_dir = tech_config_path.parent / "test_cache"
    plant_config_for_resource = {k: v for k, v in plant_config.items() if k != "sites"}
    plant_config_for_resource.update(plant_config["sites"])

    updated_parameters = {
        "hub_height": -1,
        "floris_turbine_config": floris_options,
        "enable_caching": True,
        "cache_dir": cache_dir,
    }

    tech_config["technologies"]["distributed_wind_plant"]["model_inputs"][
        "performance_parameters"
    ].update(updated_parameters)

    prob = om.Problem()
    wind_resource = WTKNRELDeveloperAPIWindResource(
        plant_config=plant_config_for_resource,
        resource_config=plant_config["sites"]["site"]["resources"]["wind_resource"][
            "resource_parameters"
        ],
        driver_config={},
    )

    wind_plant = FlorisWindPlantPerformanceModel(
        plant_config=plant_config,
        tech_config=tech_config["technologies"]["distributed_wind_plant"],
        driver_config={},
    )

    prob.model.add_subsystem("wind_resource", wind_resource, promotes=["*"])
    prob.model.add_subsystem("wind_plant", wind_plant, promotes=["*"])
    prob.setup()
    prob.run_model()

    with subtests.test("File runs with Floris, check total capacity"):
        assert (
            pytest.approx(
                prob.get_val("wind_plant.rated_electricity_production", units="MW"), rel=1e-6
            )
            == 600.0
        )

    with subtests.test("File runs with Floris, check turbine size"):
        assert (
            pytest.approx(prob.get_val("wind_plant.num_turbines", units="unitless"), rel=1e-6)
            == 100
        )

    with subtests.test("File runs with Floris, check hub-height"):
        assert pytest.approx(prob.get_val("wind_plant.hub_height", units="m"), rel=1e-6) == 140.0

    with subtests.test("File runs with Floris, check capacity factor"):
        assert (
            pytest.approx(prob.get_val("wind_plant.capacity_factor", units="percent")[0], rel=1e-6)
            == 53.556784
        )

    with subtests.test("File runs with Floris, check total electricity produced"):
        assert (
            pytest.approx(
                prob.get_val("wind_plant.total_electricity_produced", units="MW*h")[0], rel=1e-6
            )
            == 2814944.574
        )

    with subtests.test("File runs with Floris, check AEP"):
        assert (
            pytest.approx(
                prob.get_val("wind_plant.annual_electricity_produced", units="MW*h/yr")[0], rel=1e-6
            )
            == 2814944.574
        )

    # delete cache dir if it exists
    if cache_dir.exists():
        shutil.rmtree(cache_dir)
