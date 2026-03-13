import shutil
from copy import deepcopy
from pathlib import Path

import yaml
import numpy as np
import pytest

from h2integrate import EXAMPLE_DIR
from h2integrate.core.h2integrate_model import H2IntegrateModel
from h2integrate.core.inputs.validation import load_tech_yaml, load_plant_yaml, load_driver_yaml


@pytest.mark.unit
def test_custom_model_name_clash(temp_dir, subtests):
    # Path to the original tech_config.yaml and high-level yaml in the example directory
    orig_tech_config = EXAMPLE_DIR / "01_onshore_steel_mn" / "tech_config.yaml"
    temp_tech_config = temp_dir / "temp_tech_config.yaml"
    orig_highlevel_yaml = EXAMPLE_DIR / "01_onshore_steel_mn" / "01_onshore_steel_mn.yaml"
    temp_highlevel_yaml = temp_dir / "temp_01_onshore_steel_mn.yaml"

    driver_config = load_driver_yaml(EXAMPLE_DIR / "01_onshore_steel_mn" / "driver_config.yaml")
    plant_config = load_plant_yaml(EXAMPLE_DIR / "01_onshore_steel_mn" / "plant_config.yaml")

    # Copy the original tech_config.yaml and high-level yaml to temp files
    shutil.copy(orig_tech_config, temp_tech_config)
    shutil.copy(orig_highlevel_yaml, temp_highlevel_yaml)

    # Load the tech_config YAML content
    tech_config_data = load_tech_yaml(temp_tech_config)

    tech_config_data["technologies"]["electrolyzer"]["cost_model"] = {
        "model": "BasicElectrolyzerCostModel",
        "model_location": "dummy_path",  # path doesn't matter; just that `model_location` exists
    }

    # Save the modified tech_config YAML back
    with temp_tech_config.open("w") as f:
        yaml.safe_dump(tech_config_data, f)

    # Load the high-level YAML content
    with temp_highlevel_yaml.open() as f:
        highlevel_data = yaml.safe_load(f)
        highlevel_data["driver_config"] = driver_config
        highlevel_data["plant_config"] = plant_config

    # Modify the high-level YAML to point to the temp tech_config file
    highlevel_data["technology_config"] = str(temp_tech_config)

    # Save the modified high-level YAML back
    with temp_highlevel_yaml.open("w") as f:
        yaml.safe_dump(highlevel_data, f)

    with subtests.test("custom model name should not match built-in model names"):
        # Assert that a ValueError is raised with the expected message when running the model
        error_msg = (
            r"Custom model_class_name or model_location specified for '"
            r"BasicElectrolyzerCostModel', but 'BasicElectrolyzerCostModel' is a built-in "
            r"H2Integrate model\. "
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


@pytest.mark.unit
def test_custom_financial_model_grouping(temp_dir, subtests):
    orig_tech_config = EXAMPLE_DIR / "01_onshore_steel_mn" / "tech_config.yaml"
    temp_tech_config = temp_dir / "temp_tech_config.yaml"
    orig_highlevel_yaml = EXAMPLE_DIR / "01_onshore_steel_mn" / "01_onshore_steel_mn.yaml"
    temp_highlevel_yaml = temp_dir / "temp_01_onshore_steel_mn.yaml"

    driver_config = load_driver_yaml(EXAMPLE_DIR / "01_onshore_steel_mn" / "driver_config.yaml")
    plant_config = load_plant_yaml(EXAMPLE_DIR / "01_onshore_steel_mn" / "plant_config.yaml")

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
        highlevel_data["driver_config"] = driver_config
        highlevel_data["plant_config"] = plant_config

    # Modify the high-level YAML to point to the temp tech_config file
    highlevel_data["technology_config"] = str(temp_tech_config)

    # Save the modified high-level YAML back
    with temp_highlevel_yaml.open("w") as f:
        yaml.safe_dump(highlevel_data, f)

    # Run the model and check that it does not raise an error
    # (assuming custom financial_model is allowed)
    H2IntegrateModel(temp_highlevel_yaml)


# docs fencepost start: DO NOT REMOVE
@pytest.mark.unit
def test_unsupported_simulation_parameters(temp_dir):
    orig_plant_config = EXAMPLE_DIR / "01_onshore_steel_mn" / "plant_config.yaml"
    temp_plant_config_ntimesteps = temp_dir / "temp_plant_config_ntimesteps.yaml"
    temp_plant_config_dt = temp_dir / "temp_plant_config_dt.yaml"

    shutil.copy(orig_plant_config, temp_plant_config_ntimesteps)
    shutil.copy(orig_plant_config, temp_plant_config_dt)

    # Load the plant_config YAML content
    plant_config_data_ntimesteps = load_plant_yaml(temp_plant_config_ntimesteps)
    plant_config_data_dt = load_plant_yaml(temp_plant_config_dt)
    # docs fencepost end: DO NOT REMOVE

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


@pytest.mark.unit
def test_technology_connections(temp_dir):
    # Path to the original plant_config.yaml and high-level yaml in the example directory
    orig_plant_config = EXAMPLE_DIR / "01_onshore_steel_mn" / "plant_config.yaml"
    temp_plant_config = temp_dir / "temp_plant_config.yaml"
    orig_highlevel_yaml = EXAMPLE_DIR / "01_onshore_steel_mn" / "01_onshore_steel_mn.yaml"
    temp_highlevel_yaml = temp_dir / "temp_01_onshore_steel_mn.yaml"

    driver_config = load_driver_yaml(EXAMPLE_DIR / "01_onshore_steel_mn" / "driver_config.yaml")
    tech_config = load_tech_yaml(EXAMPLE_DIR / "01_onshore_steel_mn" / "tech_config.yaml")

    shutil.copy(orig_plant_config, temp_plant_config)
    shutil.copy(orig_highlevel_yaml, temp_highlevel_yaml)

    # Load the plant_config YAML content
    plant_config_data = load_plant_yaml(temp_plant_config)

    new_connection = (["finance_subgroup_electricity", "steel", ("LCOE", "electricity_cost")],)
    new_tech_interconnections = (
        plant_config_data["technology_interconnections"][0:4]
        + list(new_connection)
        + [plant_config_data["technology_interconnections"][4]]
    )
    plant_config_data["technology_interconnections"] = new_tech_interconnections

    # Save the modified tech_config YAML back
    with temp_plant_config.open("w") as f:
        yaml.safe_dump(plant_config_data, f)

    # Load the high-level YAML content
    with temp_highlevel_yaml.open() as f:
        highlevel_data = yaml.safe_load(f)
        highlevel_data["driver_config"] = driver_config
        highlevel_data["technology_config"] = tech_config

    # Modify the high-level YAML to point to the temp tech_config file
    highlevel_data["plant_config"] = str(temp_plant_config.name)

    # Save the modified high-level YAML back
    with temp_highlevel_yaml.open("w") as f:
        yaml.safe_dump(highlevel_data, f)

    h2i_model = H2IntegrateModel(temp_highlevel_yaml)
    demand_profile = np.ones(8760) * 720.0
    h2i_model.setup()
    h2i_model.prob.set_val("battery.electricity_demand", demand_profile, units="MW")
    h2i_model.run()


@pytest.mark.unit
def test_resource_connection_error_missing_connection(temp_dir):
    # Path to the original plant_config.yaml and high-level yaml in the example directory
    orig_plant_config = EXAMPLE_DIR / "08_wind_electrolyzer" / "plant_config.yaml"
    temp_plant_config = temp_dir / "temp_plant_config.yaml"
    orig_highlevel_yaml = EXAMPLE_DIR / "08_wind_electrolyzer" / "wind_plant_electrolyzer.yaml"
    temp_highlevel_yaml = temp_dir / "temp_08_wind_electrolyzer.yaml"

    driver_config = load_driver_yaml(EXAMPLE_DIR / "08_wind_electrolyzer" / "driver_config.yaml")
    tech_config = load_tech_yaml(EXAMPLE_DIR / "08_wind_electrolyzer" / "tech_config.yaml")

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
        highlevel_data["driver_config"] = driver_config
        highlevel_data["technology_config"] = tech_config

    # Modify the high-level YAML to point to the temp tech_config file
    highlevel_data["plant_config"] = str(temp_plant_config.name)

    # Save the modified high-level YAML back
    with temp_highlevel_yaml.open("w") as f:
        yaml.safe_dump(highlevel_data, f)

    with pytest.raises(ValueError) as excinfo:
        H2IntegrateModel(temp_highlevel_yaml)
        assert "Resource models ['wind_resource'] are not in" in str(excinfo.value)


@pytest.mark.unit
def test_resource_connection_error_missing_resource(temp_dir):
    # Path to the original plant_config.yaml and high-level yaml in the example directory
    orig_plant_config = EXAMPLE_DIR / "08_wind_electrolyzer" / "plant_config.yaml"
    temp_plant_config = temp_dir / "temp_plant_config.yaml"
    orig_highlevel_yaml = EXAMPLE_DIR / "08_wind_electrolyzer" / "wind_plant_electrolyzer.yaml"
    temp_highlevel_yaml = temp_dir / "temp_08_wind_electrolyzer.yaml"

    driver_config = load_driver_yaml(EXAMPLE_DIR / "08_wind_electrolyzer" / "driver_config.yaml")
    tech_config = load_tech_yaml(EXAMPLE_DIR / "08_wind_electrolyzer" / "tech_config.yaml")

    shutil.copy(orig_plant_config, temp_plant_config)
    shutil.copy(orig_highlevel_yaml, temp_highlevel_yaml)

    # Load the plant_config YAML content
    plant_config_data = load_plant_yaml(temp_plant_config)

    # Remove resource
    plant_config_data["sites"]["site"]["resources"].pop("wind_resource")

    # Save the modified tech_config YAML back
    with temp_plant_config.open("w") as f:
        yaml.safe_dump(plant_config_data, f)

    # Load the high-level YAML content
    with temp_highlevel_yaml.open() as f:
        highlevel_data = yaml.safe_load(f)
        highlevel_data["driver_config"] = driver_config
        highlevel_data["technology_config"] = tech_config

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


@pytest.mark.unit
def test_reports_turned_off(temp_dir):
    # Path to the original config files in the example directory
    orig_plant_config = EXAMPLE_DIR / "07_run_of_river_plant" / "plant_config.yaml"
    orig_driver_config = EXAMPLE_DIR / "07_run_of_river_plant" / "driver_config.yaml"
    orig_tech_config = EXAMPLE_DIR / "07_run_of_river_plant" / "tech_config.yaml"
    orig_highlevel_yaml = EXAMPLE_DIR / "07_run_of_river_plant" / "07_run_of_river.yaml"
    orig_csv = EXAMPLE_DIR / "07_run_of_river_plant" / "river_data.csv"

    # Create temporary config files
    temp_plant_config = temp_dir / "temp_plant_config.yaml"
    temp_driver_config = temp_dir / "temp_driver_config.yaml"
    temp_tech_config = temp_dir / "temp_tech_config.yaml"
    temp_highlevel_yaml = temp_dir / "temp_07_run_of_river.yaml"
    temp_csv = temp_dir / "river_data.csv"

    # Copy the original config files to temp files
    shutil.copy(orig_highlevel_yaml, temp_highlevel_yaml)
    shutil.copy(orig_plant_config, temp_plant_config)
    shutil.copy(orig_driver_config, temp_driver_config)
    shutil.copy(orig_tech_config, temp_tech_config)
    shutil.copy(orig_csv, temp_csv)

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
    with temp_plant_config.open("r") as f:
        plant_data = yaml.safe_load(f)
        plant_data["sites"]["site"]["resources"]["river_resource"]["resource_parameters"][
            "filename"
        ] = str(temp_csv)

    with temp_plant_config.open("w") as f:
        yaml.safe_dump(plant_data, f)

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


@pytest.mark.unit
def test_invalid_finance_group_combination(subtests):
    driver_config = load_driver_yaml(EXAMPLE_DIR / "01_onshore_steel_mn" / "driver_config.yaml")
    tech_config = load_tech_yaml(EXAMPLE_DIR / "01_onshore_steel_mn" / "tech_config.yaml")
    plant_config = load_plant_yaml(EXAMPLE_DIR / "01_onshore_steel_mn" / "plant_config.yaml")

    invalid_finance_subgroup = {
        "commodity": "steel",
        "finance_groups": ["steel", "profast_model"],
        "technologies": ["steel"],
    }

    plant_config["finance_parameters"]["finance_subgroups"].update(
        {"steel_buggy": invalid_finance_subgroup}
    )

    h2i_config = {
        "name": "H2I",
        "system_summary": "",
        "driver_config": driver_config,
        "technology_config": tech_config,
        "plant_config": plant_config,
    }

    with subtests.test("Test invalid finance groups"):
        expected_msg = (
            "Cannot run a tech-specific finance model (['steel']) in the "
            "same finance subgroup as a system-level finance model "
            "(['profast_model']). Please modify the finance_groups in finance "
            "subgroup steel_buggy."
        )

        with pytest.raises(ValueError) as excinfo:
            h2i = H2IntegrateModel(h2i_config)
            h2i.setup()
            assert expected_msg == str(excinfo.value)


@pytest.mark.unit
def test_system_order(subtests):
    driver_config = load_driver_yaml(EXAMPLE_DIR / "01_onshore_steel_mn" / "driver_config.yaml")
    tech_config = load_tech_yaml(EXAMPLE_DIR / "01_onshore_steel_mn" / "tech_config.yaml")
    plant_config = load_plant_yaml(EXAMPLE_DIR / "01_onshore_steel_mn" / "plant_config.yaml")

    h2i_config = {
        "name": "H2I",
        "system_summary": "",
        "driver_config": driver_config,
        "technology_config": tech_config,
        "plant_config": plant_config,
    }

    h2i = H2IntegrateModel(h2i_config)
    h2i.setup()

    expected_names = [
        "wind",
        "wind_to_combiner_cable",
        "solar",
        "solar_to_combiner_cable",
        "combiner",
        "combiner_to_battery_cable",
        "battery",
        "battery_to_electrolyzer_cable",
        "electrolyzer",
        "electrolyzer_to_h2_storage_pipe",
        "h2_storage",
        "steel",
        "finance_subgroup_electricity",
        "finance_subgroup_hydrogen",
        "finance_subgroup_steel",
    ]

    names = [sys.name for sys in h2i.model.plant.system_iter(include_self=False, recurse=False)]

    with subtests.test("Test expected names are all present"):
        assert sorted(names) == sorted(expected_names)

    with subtests.test("Test expected names are in the correct order"):
        assert names == expected_names
