import numpy as np
import pytest
import openmdao.api as om

from h2integrate import EXAMPLE_DIR
from h2integrate.core.utilities import load_yaml
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
        plant_config=plant_config,
        resource_config=plant_config["site"]["resources"]["wind_resource"]["resource_parameters"],
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
            pytest.approx(prob.get_val("wind_plant.total_capacity", units="MW"), rel=1e-6) == 600.0
        )

    with subtests.test("File runs with WindPower, check turbine size"):
        assert (
            pytest.approx(prob.get_val("wind_plant.wind_turbine_rating", units="MW"), rel=1e-6)
            == 6.0
        )

    with subtests.test("File runs with WindPower, check AEP"):
        assert (
            pytest.approx(prob.get_val("wind_plant.annual_energy", units="MW*h/yr")[0], rel=1e-6)
            == 2783152.10
        )


def test_floris_turbine_export(subtests):
    turbine_name = "NREL_6MW_196"
    output_fpath = export_turbine_to_floris_format(turbine_name)

    with subtests.test("File was created"):
        assert output_fpath.exists()
        assert output_fpath.is_file()

    # TODO: add test with floris model
    # with subtests.test("File runs with FLORIS model"):
    #     pass
