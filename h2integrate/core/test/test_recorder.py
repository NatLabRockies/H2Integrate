import sys

import pytest

from h2integrate.core.h2integrate_model import H2IntegrateModel
from h2integrate.core.inputs.validation import load_driver_yaml


TEST_RECORDER_OUTPUT_FILE0 = "testingtesting_filename.sql"
TEST_RECORDER_OUTPUT_FILE1 = "testingtesting_filename0.sql"
TEST_RECORDER_OUTPUT_FILE2 = "testingtesting_filename1.sql"


@pytest.mark.unit
@pytest.mark.parametrize("example_folder,resource_example_folder", [("05_wind_h2_opt", None)])
def test_output_folder_creation_first_run(temp_copy_of_example_module_scope, subtests):
    """Test that the sql file is written to the output folder with the specified name."""

    # initialize H2I using non-optimization config
    example_folder = temp_copy_of_example_module_scope
    input_file = example_folder / "wind_plant_electrolyzer0.yaml"
    h2i = H2IntegrateModel(input_file)

    # load driver config for optimization run
    driver_config = load_driver_yaml(example_folder / "driver_config.yaml")

    # update driver config params with test variables
    filename_initial = TEST_RECORDER_OUTPUT_FILE0
    output_folder = example_folder / driver_config["general"]["folder_output"]
    driver_config["recorder"]["file"] = filename_initial
    driver_config["driver"]["optimization"]["max_iter"] = 5  # to prevent tests taking too long

    # reset the driver config in H2I
    h2i.driver_config = driver_config

    # reinitialize the driver model
    h2i.create_driver_model()

    # check if output folder and output files exist
    output_folder_exists = output_folder.exists()
    output_file_exists_prerun = (output_folder / filename_initial).exists()

    with subtests.test("Run 0: output folder exists"):
        assert output_folder_exists is True
    with subtests.test("Run 0: recorder output file does not exist yet"):
        assert output_file_exists_prerun is False

    # run the model
    h2i.run()

    # check that recorder file was created
    output_file_exists_postrun = (output_folder / filename_initial).exists()
    with subtests.test("Run 0: recorder output file exists after run"):
        assert output_file_exists_postrun is True


@pytest.mark.unit
@pytest.mark.parametrize("example_folder,resource_example_folder", [("05_wind_h2_opt", None)])
def test_output_new_recorder_filename_second_run(temp_copy_of_example_module_scope, subtests):
    """Test that the sql file is written to the output folder with the specified base name and
    an appended 0.
    """

    # initialize H2I using non-optimization config
    example_folder = temp_copy_of_example_module_scope
    input_file = example_folder / "wind_plant_electrolyzer0.yaml"
    h2i = H2IntegrateModel(input_file)

    # load driver config for optimization run
    driver_config = load_driver_yaml(example_folder / "driver_config.yaml")

    # update driver config params with test variables
    filename_initial = TEST_RECORDER_OUTPUT_FILE0
    filename_expected = TEST_RECORDER_OUTPUT_FILE1

    output_folder = example_folder / driver_config["general"]["folder_output"]
    driver_config["recorder"]["file"] = filename_initial
    driver_config["driver"]["optimization"]["max_iter"] = 5  # to prevent tests taking too long

    # reset the driver config in H2I
    h2i.driver_config = driver_config

    # reinitialize the driver model
    h2i.create_driver_model()

    # check if output folder and output files exist
    with subtests.test("Run 1: output folder exists"):
        assert output_folder.exists()
    with subtests.test("Run 1: initial recorder output file exists"):
        assert (output_folder / filename_initial).exists()

    # run the model
    h2i.run()

    # check that the new recorder file was created
    with subtests.test("Run 1: new recorder output file was made"):
        assert (output_folder / filename_expected).exists()


@pytest.mark.unit
@pytest.mark.parametrize("example_folder,resource_example_folder", [("05_wind_h2_opt", None)])
@pytest.mark.xfail(sys.platform == "win32", reason="OpenMDAO incorrectly ends SQL processes")
def test_output_new_recorder_overwrite_first_run(temp_copy_of_example_module_scope, subtests):
    # initialize H2I using non-optimization config
    example_folder = temp_copy_of_example_module_scope
    input_file = example_folder / "wind_plant_electrolyzer0.yaml"
    h2i = H2IntegrateModel(input_file)

    # load driver config for optimization run
    driver_config = load_driver_yaml(example_folder / "driver_config.yaml")

    # update driver config params with test variables
    filename_initial = TEST_RECORDER_OUTPUT_FILE0
    filename_exists_if_failed = TEST_RECORDER_OUTPUT_FILE2
    output_folder = example_folder / driver_config["general"]["folder_output"]
    driver_config["recorder"]["file"] = filename_initial

    # specify that we want the previous file overwritten rather
    # than create a new file
    driver_config["recorder"].update({"overwrite_recorder": True})
    driver_config["driver"]["optimization"]["max_iter"] = 5  # to prevent tests taking too long

    # reset the driver config in H2I
    h2i.driver_config = driver_config

    # reinitialize the driver model
    h2i.create_driver_model()

    # check if output folder and output files exist
    with subtests.test("Run 2: output folder exists"):
        assert output_folder.exists()
    with subtests.test("Run 2: initial recorder output file exists"):
        assert (output_folder / filename_initial).exists()

    # run the model
    h2i.run()

    # check that recorder file was overwritten
    with subtests.test("Run 2: initial output file was overwritten"):
        assert not (output_folder / filename_exists_if_failed).exists()


@pytest.mark.unit
@pytest.mark.parametrize("example_folder,resource_example_folder", [("05_wind_h2_opt", None)])
def test_output_new_recorder_filename_third_run(temp_copy_of_example_module_scope, subtests):
    # initialize H2I using non-optimization config
    example_folder = temp_copy_of_example_module_scope
    input_file = example_folder / "wind_plant_electrolyzer0.yaml"
    h2i = H2IntegrateModel(input_file)

    # load driver config for optimization run
    driver_config = load_driver_yaml(example_folder / "driver_config.yaml")

    # update driver config params with test variables
    filename_initial = TEST_RECORDER_OUTPUT_FILE0
    filename_second = TEST_RECORDER_OUTPUT_FILE1
    filename_expected = TEST_RECORDER_OUTPUT_FILE2
    output_folder = example_folder / driver_config["general"]["folder_output"]
    driver_config["recorder"]["file"] = filename_initial
    driver_config["driver"]["optimization"]["max_iter"] = 5  # to prevent tests taking too long

    # reset the driver config in H2I
    h2i.driver_config = driver_config

    # reinitialize the driver model
    h2i.create_driver_model()

    # check if output folder and output files exist
    with subtests.test("Run 3: output folder exists"):
        assert output_folder.exists()
    with subtests.test("Run 3: initial recorder output file exists"):
        assert (output_folder / filename_initial).exists()
    with subtests.test("Run 3: second recorder output file exists"):
        assert (output_folder / filename_second).exists()

    # run the model
    h2i.run()

    # check that the new recorder file was created
    with subtests.test("Run 3: new recorder output file was made"):
        assert (output_folder / filename_expected).exists()
