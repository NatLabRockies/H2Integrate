import os
import shutil
from pathlib import Path

import yaml
import pytest

from h2integrate import EXAMPLE_DIR
from h2integrate.core.h2integrate_model import H2IntegrateModel
from h2integrate.core.inputs.validation import load_tech_yaml, load_plant_yaml


examples_dir = Path(__file__).resolve().parent.parent.parent.parent / "examples/."


def test_custom_model_name_clash(subtests):
    # Change the current working directory to the example's directory
    os.chdir(examples_dir / "01_onshore_steel_mn")

    # Path to the original tech_config.yaml and high-level yaml in the example directory
    orig_tech_config = Path.cwd() / "tech_config.yaml"
    temp_tech_config = Path.cwd() / "temp_tech_config.yaml"
    orig_highlevel_yaml = Path.cwd() / "01_onshore_steel_mn.yaml"
    temp_highlevel_yaml = Path.cwd() / "temp_01_onshore_steel_mn.yaml"

    # Copy the original tech_config.yaml and high-level yaml to temp files
    shutil.copy(orig_tech_config, temp_tech_config)
    shutil.copy(orig_highlevel_yaml, temp_highlevel_yaml)

    # Load the tech_config YAML content
    tech_config_data = load_tech_yaml(temp_tech_config)

    tech_config_data["technologies"]["electrolyzer"]["cost_model"] = {
        "model": "basic_electrolyzer_cost",
        "model_location": "dummy_path",  # path doesn't matter; just that `model_location` exists
    }

    # Save the modified tech_config YAML back
    with temp_tech_config.open("w") as f:
        yaml.safe_dump(tech_config_data, f)

    # Load the high-level YAML content
    with temp_highlevel_yaml.open() as f:
        highlevel_data = yaml.safe_load(f)

    # Modify the high-level YAML to point to the temp tech_config file
    highlevel_data["technology_config"] = str(temp_tech_config.name)

    # Save the modified high-level YAML back
    with temp_highlevel_yaml.open("w") as f:
        yaml.safe_dump(highlevel_data, f)

    with subtests.test("custom model name should not match built-in model names"):
        # Assert that a ValueError is raised with the expected message when running the model
        error_msg = (
            r"Custom model_class_name or model_location specified for 'basic_electrolyzer_cost', "
            r"but 'basic_electrolyzer_cost' is a built-in H2Integrate model\. "
            r"Using built-in model instead is not allowed\. "
            r"If you want to use a custom model, please rename it in your configuration\."
        )
        with pytest.raises(ValueError, match=error_msg):
            H2IntegrateModel(temp_highlevel_yaml)

    with subtests.test(
        "custom models must use different model names for different class definitions"
    ):
        # Load the tech_config YAML content
        tech_config_data = load_tech_yaml(temp_tech_config)

        tech_config_data["technologies"]["electrolyzer"]["cost_model"] = {
            "model": "new_electrolyzer_cost",
            "model_location": "dummy_path",  # path doesn't matter; `model_location` must exist
        }

        from copy import deepcopy

        tech_config_data["technologies"]["electrolyzer2"] = deepcopy(
            tech_config_data["technologies"]["electrolyzer"]
        )
        tech_config_data["technologies"]["electrolyzer2"]["cost_model"] = {
            "model": "new_electrolyzer_cost",
            "model_class_name": "DummyClass",
            "model_location": "dummy_path",  # path doesn't matter; `model_location` must exist
        }
        # Save the modified tech_config YAML back
        with temp_tech_config.open("w") as f:
            yaml.safe_dump(tech_config_data, f)

        # Load the high-level YAML content
        with temp_highlevel_yaml.open() as f:
            highlevel_data = yaml.safe_load(f)

        # Modify the high-level YAML to point to the temp tech_config file
        highlevel_data["technology_config"] = str(temp_tech_config.name)

        # Save the modified high-level YAML back
        with temp_highlevel_yaml.open("w") as f:
            yaml.safe_dump(highlevel_data, f)

        # Assert that a ValueError is raised with the expected message when running the model
        error_msg = (
            r"User has specified two custom models using the same model"
            r"name ('new_electrolyzer_cost'), but with different model classes\. "
            r"Technologies defined with different"
            r"classes must have different technology names\."
        )

    # Clean up temporary YAML files
    temp_tech_config.unlink(missing_ok=True)
    temp_highlevel_yaml.unlink(missing_ok=True)


def test_custom_financial_model_grouping(subtests):
    # Change the current working directory to the example's directory
    os.chdir(examples_dir / "01_onshore_steel_mn")

    # Path to the original tech_config.yaml and high-level yaml in the example directory
    orig_tech_config = Path.cwd() / "tech_config.yaml"
    temp_tech_config = Path.cwd() / "temp_tech_config.yaml"
    orig_highlevel_yaml = Path.cwd() / "01_onshore_steel_mn.yaml"
    temp_highlevel_yaml = Path.cwd() / "temp_01_onshore_steel_mn.yaml"

    # Copy the original tech_config.yaml and high-level yaml to temp files
    shutil.copy(orig_tech_config, temp_tech_config)
    shutil.copy(orig_highlevel_yaml, temp_highlevel_yaml)

    # Load the tech_config YAML content
    tech_config_data = load_tech_yaml(temp_tech_config)

    # Modify the financial_model entry for one of the technologies
    tech_config_data["technologies"]["steel"]["finance_model"]["group"] = "test_financial_group"
    tech_config_data["technologies"]["electrolyzer"].pop("financial_model", None)

    # Save the modified tech_config YAML back
    with temp_tech_config.open("w") as f:
        yaml.safe_dump(tech_config_data, f)

    # Load the high-level YAML content
    with temp_highlevel_yaml.open() as f:
        highlevel_data = yaml.safe_load(f)

    # Modify the high-level YAML to point to the temp tech_config file
    highlevel_data["technology_config"] = str(temp_tech_config.name)

    # Save the modified high-level YAML back
    with temp_highlevel_yaml.open("w") as f:
        yaml.safe_dump(highlevel_data, f)

    # Run the model and check that it does not raise an error
    # (assuming custom financial_model is allowed)
    H2IntegrateModel(temp_highlevel_yaml)

    # Clean up temporary YAML files
    temp_tech_config.unlink(missing_ok=True)
    temp_highlevel_yaml.unlink(missing_ok=True)


def test_unsupported_simulation_parameters():
    orig_plant_config = EXAMPLE_DIR / "01_onshore_steel_mn" / "plant_config.yaml"
    temp_plant_config_ntimesteps = Path.cwd() / "temp_plant_config_ntimesteps.yaml"
    temp_plant_config_dt = Path.cwd() / "temp_plant_config_dt.yaml"

    shutil.copy(orig_plant_config, temp_plant_config_ntimesteps)
    shutil.copy(orig_plant_config, temp_plant_config_dt)

    # Load the plant_config YAML content
    plant_config_data_ntimesteps = load_plant_yaml(temp_plant_config_ntimesteps)
    plant_config_data_dt = load_plant_yaml(temp_plant_config_dt)

    # Modify the n_timesteps entry for the temp_plant_config_ntimesteps
    plant_config_data_ntimesteps["plant"]["simulation"]["n_timesteps"] = 8759
    # Modify the dt entry for the temp_plant_config_dt
    plant_config_data_dt["plant"]["simulation"]["dt"] = 3601

    # Save the modified plant_configs YAML back
    with temp_plant_config_ntimesteps.open("w") as f:
        yaml.safe_dump(plant_config_data_ntimesteps, f)
    with temp_plant_config_dt.open("w") as f:
        yaml.safe_dump(plant_config_data_dt, f)

    # check that error is thrown when loading config with invalid number of timesteps
    with pytest.raises(ValueError, match="greater than 1-year"):
        load_plant_yaml(plant_config_data_ntimesteps)

    # check that error is thrown when loading config with invalid time interval
    with pytest.raises(ValueError, match="with a time step that"):
        load_plant_yaml(plant_config_data_dt)

    # Clean up temporary YAML files
    temp_plant_config_ntimesteps.unlink(missing_ok=True)
    temp_plant_config_dt.unlink(missing_ok=True)


def test_technology_connections():
    os.chdir(examples_dir / "01_onshore_steel_mn")

    # Path to the original plant_config.yaml and high-level yaml in the example directory
    orig_plant_config = Path.cwd() / "plant_config.yaml"
    temp_plant_config = Path.cwd() / "temp_plant_config.yaml"
    orig_highlevel_yaml = Path.cwd() / "01_onshore_steel_mn.yaml"
    temp_highlevel_yaml = Path.cwd() / "temp_01_onshore_steel_mn.yaml"

    shutil.copy(orig_plant_config, temp_plant_config)
    shutil.copy(orig_highlevel_yaml, temp_highlevel_yaml)

    # Load the plant_config YAML content
    plant_config_data = load_plant_yaml(temp_plant_config)

    new_connection = (["finance_subgroup_electricity", "steel", ("LCOE", "electricity_cost")],)
    new_tech_interconnections = (
        plant_config_data["technology_interconnections"][0:3]
        + list(new_connection)
        + [plant_config_data["technology_interconnections"][3]]
    )
    plant_config_data["technology_interconnections"] = new_tech_interconnections

    # Save the modified tech_config YAML back
    with temp_plant_config.open("w") as f:
        yaml.safe_dump(plant_config_data, f)

    # Load the high-level YAML content
    with temp_highlevel_yaml.open() as f:
        highlevel_data = yaml.safe_load(f)

    # Modify the high-level YAML to point to the temp tech_config file
    highlevel_data["plant_config"] = str(temp_plant_config.name)

    # Save the modified high-level YAML back
    with temp_highlevel_yaml.open("w") as f:
        yaml.safe_dump(highlevel_data, f)

    h2i_model = H2IntegrateModel(temp_highlevel_yaml)

    h2i_model.run()

    # Clean up temporary YAML files
    temp_plant_config.unlink(missing_ok=True)
    temp_highlevel_yaml.unlink(missing_ok=True)


def test_resource_connection_error_missing_connection():
    os.chdir(examples_dir / "08_wind_electrolyzer")

    # Path to the original plant_config.yaml and high-level yaml in the example directory
    orig_plant_config = Path.cwd() / "plant_config.yaml"
    temp_plant_config = Path.cwd() / "temp_plant_config.yaml"
    orig_highlevel_yaml = Path.cwd() / "wind_plant_electrolyzer.yaml"
    temp_highlevel_yaml = Path.cwd() / "temp_08_wind_electrolyzer.yaml"

    shutil.copy(orig_plant_config, temp_plant_config)
    shutil.copy(orig_highlevel_yaml, temp_highlevel_yaml)

    # Load the plant_config YAML content
    plant_config_data = load_plant_yaml(temp_plant_config)

    # Remove resource to tech connection
    plant_config_data.pop("resource_to_tech_connections")

    # Save the modified tech_config YAML back
    with temp_plant_config.open("w") as f:
        yaml.safe_dump(plant_config_data, f)

    # Load the high-level YAML content
    with temp_highlevel_yaml.open() as f:
        highlevel_data = yaml.safe_load(f)

    # Modify the high-level YAML to point to the temp tech_config file
    highlevel_data["plant_config"] = str(temp_plant_config.name)

    # Save the modified high-level YAML back
    with temp_highlevel_yaml.open("w") as f:
        yaml.safe_dump(highlevel_data, f)

    with pytest.raises(ValueError) as excinfo:
        H2IntegrateModel(temp_highlevel_yaml)
        assert "Resource models ['wind_resource'] are not in" in str(excinfo.value)

    # Clean up temporary YAML files
    temp_plant_config.unlink(missing_ok=True)
    temp_highlevel_yaml.unlink(missing_ok=True)


def test_resource_connection_error_missing_resource():
    os.chdir(examples_dir / "08_wind_electrolyzer")

    # Path to the original plant_config.yaml and high-level yaml in the example directory
    orig_plant_config = Path.cwd() / "plant_config.yaml"
    temp_plant_config = Path.cwd() / "temp_plant_config.yaml"
    orig_highlevel_yaml = Path.cwd() / "wind_plant_electrolyzer.yaml"
    temp_highlevel_yaml = Path.cwd() / "temp_08_wind_electrolyzer.yaml"

    shutil.copy(orig_plant_config, temp_plant_config)
    shutil.copy(orig_highlevel_yaml, temp_highlevel_yaml)

    # Load the plant_config YAML content
    plant_config_data = load_plant_yaml(temp_plant_config)

    # Remove resource
    plant_config_data["site"]["resources"].pop("wind_resource")

    # Save the modified tech_config YAML back
    with temp_plant_config.open("w") as f:
        yaml.safe_dump(plant_config_data, f)

    # Load the high-level YAML content
    with temp_highlevel_yaml.open() as f:
        highlevel_data = yaml.safe_load(f)

    # Modify the high-level YAML to point to the temp tech_config file
    highlevel_data["plant_config"] = str(temp_plant_config.name)

    # Save the modified high-level YAML back
    with temp_highlevel_yaml.open("w") as f:
        yaml.safe_dump(highlevel_data, f)

    with pytest.raises(ValueError) as excinfo:
        H2IntegrateModel(temp_highlevel_yaml)
        assert "Missing resource(s) are ['wind_resource']." in str(excinfo.value)

    # Clean up temporary YAML files
    temp_plant_config.unlink(missing_ok=True)
    temp_highlevel_yaml.unlink(missing_ok=True)


def test_reports_turned_off():
    # Change the current working directory to the example's directory
    os.chdir(examples_dir / "07_run_of_river_plant")

    # Path to the original config files in the example directory
    orig_plant_config = Path.cwd() / "plant_config.yaml"
    orig_driver_config = Path.cwd() / "driver_config.yaml"
    orig_tech_config = Path.cwd() / "tech_config.yaml"
    orig_highlevel_yaml = Path.cwd() / "07_run_of_river.yaml"

    # Create temporary config files
    temp_plant_config = Path.cwd() / "temp_plant_config.yaml"
    temp_driver_config = Path.cwd() / "temp_driver_config.yaml"
    temp_tech_config = Path.cwd() / "temp_tech_config.yaml"
    temp_highlevel_yaml = Path.cwd() / "temp_07_run_of_river.yaml"

    # Copy the original config files to temp files
    shutil.copy(orig_plant_config, temp_plant_config)
    shutil.copy(orig_driver_config, temp_driver_config)
    shutil.copy(orig_tech_config, temp_tech_config)
    shutil.copy(orig_highlevel_yaml, temp_highlevel_yaml)

    # Load and modify the driver config to turn off reports
    with temp_driver_config.open() as f:
        driver_data = yaml.safe_load(f)

    if "general" not in driver_data:
        driver_data["general"] = {}
    driver_data["general"]["create_om_reports"] = False

    # Save the modified driver config
    with temp_driver_config.open("w") as f:
        yaml.safe_dump(driver_data, f)

    # Load the high-level YAML content and point to temp config files
    with temp_highlevel_yaml.open() as f:
        highlevel_data = yaml.safe_load(f)

    # Modify the high-level YAML to point to the temp config files
    highlevel_data["plant_config"] = str(temp_plant_config.name)
    highlevel_data["driver_config"] = str(temp_driver_config.name)
    highlevel_data["technology_config"] = str(temp_tech_config.name)

    # Save the modified high-level YAML back
    with temp_highlevel_yaml.open("w") as f:
        yaml.safe_dump(highlevel_data, f)

    # Record initial files before running the model
    initial_files = set(Path.cwd().rglob("*"))

    # Run the model
    h2i_model = H2IntegrateModel(temp_highlevel_yaml)
    h2i_model.run()

    # Check that no OpenMDAO report directories were created
    final_files = set(Path.cwd().rglob("*"))
    new_files = final_files - initial_files
    report_dirs = [f for f in new_files if f.is_dir() and "reports" in f.name.lower()]

    # Assert that no report directories were created due to create_om_reports=False
    assert (
        len(report_dirs) == 0
    ), f"Report directories were created despite create_om_reports=False: {report_dirs}"

    # Clean up temporary YAML files
    temp_plant_config.unlink(missing_ok=True)
    temp_driver_config.unlink(missing_ok=True)
    temp_tech_config.unlink(missing_ok=True)
    temp_highlevel_yaml.unlink(missing_ok=True)
