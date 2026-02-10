import os
import tempfile
import unittest
from pathlib import Path

import yaml
import numpy as np
import pytest
from attrs import field, define

from h2integrate import ROOT_DIR, EXAMPLE_DIR, RESOURCE_DEFAULT_DIR
from h2integrate.core.utilities import (
    BaseConfig,
    get_path,
    find_file,
    make_unique_case_name,
    dict_to_yaml_formatting,
)


def test_get_path(subtests):
    current_cwd = Path.cwd()

    # 1. As an absolute path.
    file_abs_path = (
        EXAMPLE_DIR / "09_co2" / "direct_ocean_capture" / "tech_inputs" / "hopp_config.yaml"
    )
    file_abs_out_path = get_path(file_abs_path)
    with subtests.test("get_path: absolute filepath for file"):
        assert file_abs_out_path == file_abs_path

    # 2. Relative to the current working directory.
    os.chdir(EXAMPLE_DIR / "09_co2" / "direct_ocean_capture")
    file_cwd_rel_path = "tech_inputs/hopp_config.yaml"
    file_cwd_rel_out_path = get_path(file_cwd_rel_path)
    with subtests.test("get_path: filepath relative to cwd for file"):
        assert file_cwd_rel_out_path == file_abs_path

    # 3. Relative to the H2Integrate package.
    os.chdir(ROOT_DIR)
    file_h2i_rel_path = "examples/09_co2/direct_ocean_capture/tech_inputs/hopp_config.yaml"
    file_h2i_rel_out_path = get_path(file_h2i_rel_path)
    with subtests.test("get_path: filepath relative to H2I package for file"):
        assert file_h2i_rel_out_path == file_abs_path

    # 1. As an absolute path.
    dir_abs_path = EXAMPLE_DIR / "09_co2" / "direct_ocean_capture" / "tech_inputs"
    dir_abs_out_path = get_path(dir_abs_path)
    with subtests.test("get_path: absolute filepath for folder"):
        assert dir_abs_out_path == dir_abs_path

    # 2. Relative to the current working directory.
    os.chdir(EXAMPLE_DIR / "09_co2" / "direct_ocean_capture")
    dir_cwd_rel_path = "tech_inputs"
    dir_cwd_rel_out_path = get_path(dir_cwd_rel_path)
    with subtests.test("get_path: filepath relative to cwd for folder"):
        assert dir_cwd_rel_out_path == dir_abs_path

    # 3. Relative to the H2Integrate package.
    os.chdir(ROOT_DIR)
    dir_h2i_rel_path = "examples/09_co2/direct_ocean_capture/tech_inputs"
    dir_h2i_rel_out_path = get_path(dir_h2i_rel_path)
    with subtests.test("get_path: filepath relative to H2I package for folder"):
        assert dir_h2i_rel_out_path == dir_abs_path

    os.chdir(current_cwd)


def test_find_file(subtests):
    current_cwd = Path.cwd()

    # 1. As an absolute path.
    file_abs_path = (
        EXAMPLE_DIR / "09_co2" / "direct_ocean_capture" / "tech_inputs" / "hopp_config.yaml"
    )
    file_abs_out_path = find_file(file_abs_path)
    with subtests.test("find_file: absolute filepath"):
        assert file_abs_out_path == file_abs_path

    # 2. Relative to the current working directory.
    os.chdir(EXAMPLE_DIR / "09_co2" / "direct_ocean_capture")
    file_cwd_rel_path = "tech_inputs/hopp_config.yaml"
    file_cwd_rel_out_path = find_file(file_cwd_rel_path)
    with subtests.test("find_file: filepath relative to cwd"):
        assert file_cwd_rel_out_path == file_abs_path

    # 3. Relative to the H2Integrate package.
    os.chdir(ROOT_DIR / "core" / "inputs")
    file_h2i_rel_path = "examples/09_co2/direct_ocean_capture/tech_inputs/hopp_config.yaml"
    file_h2i_rel_out_path = find_file(file_h2i_rel_path)
    with subtests.test("find_file: filepath relative to H2I package"):
        assert file_h2i_rel_out_path == file_abs_path

    # 3. Relative to the root_folder (outside of it)
    file_root_rel_path = "../examples/09_co2/direct_ocean_capture/tech_inputs/hopp_config.yaml"
    file_root_rel_out_path = find_file(file_root_rel_path, root_folder=ROOT_DIR)
    with subtests.test("find_file: filepath relative (outside) of root_folder"):
        assert file_root_rel_out_path.resolve() == file_abs_path

    # 4. Relative to the root_folder (inside of it)
    file_root_in_rel_path = "tech_inputs/hopp_config.yaml"
    ex_root = EXAMPLE_DIR / "09_co2" / "direct_ocean_capture"
    file_root_in_rel_out_path = find_file(file_root_in_rel_path, root_folder=ex_root)
    with subtests.test("find_file: filepath relative (inside) to root_folder"):
        assert file_root_in_rel_out_path.resolve() == file_abs_path
    os.chdir(current_cwd)


def test_make_unique_filename(subtests):
    unique_yaml_name = make_unique_case_name(EXAMPLE_DIR, "tech_config.yaml", ".yaml")
    unique_py_name = make_unique_case_name(ROOT_DIR.parent, "conftest.py", ".py")
    unique_csv_name = make_unique_case_name(
        RESOURCE_DEFAULT_DIR, "34.22_-102.75_2013_wtk_v2_60min_local_tz.csv", ".csv"
    )

    yaml_files = list(Path(EXAMPLE_DIR).glob(f"**/{unique_yaml_name}"))
    py_files = list(Path(ROOT_DIR.parent).glob(f"**/{unique_py_name}"))
    csv_files = list(Path(RESOURCE_DEFAULT_DIR).glob(f"**/{unique_csv_name}"))

    with subtests.test("Uniquely named .yaml file"):
        assert len(yaml_files) == 0
    with subtests.test("Uniquely named .py file"):
        assert len(py_files) == 0
    with subtests.test("Uniquely named .csv file"):
        assert len(csv_files) == 0


class TestDictToYamlFormatting(unittest.TestCase):
    """Test cases for the dict_to_yaml_formatting function."""

    def setUp(self):
        """Set up test fixtures before each test method."""
        self.temp_dir = tempfile.mkdtemp()

    def tearDown(self):
        """Clean up test fixtures after each test method."""
        # Clean up temporary files
        for file in Path(self.temp_dir).glob("*.yaml"):
            file.unlink()
        Path(self.temp_dir).rmdir()

    def test_simple_numeric_conversion(self):
        """Test conversion of simple numeric values to float."""
        input_dict = {
            "int_value": 42,
            "float_value": 3.14,
            "numpy_int": np.int32(10),
            "numpy_float": np.float64(2.718),
        }

        result = dict_to_yaml_formatting(input_dict.copy())

        # int values should remain as int (str, bool, int are preserved)
        self.assertEqual(result["int_value"], 42)
        self.assertIsInstance(result["int_value"], int)

        # float values should remain as float
        self.assertEqual(result["float_value"], 3.14)
        self.assertIsInstance(result["float_value"], float)

        # numpy values should be converted to float
        self.assertEqual(result["numpy_int"], 10.0)
        self.assertIsInstance(result["numpy_int"], float)

        self.assertEqual(result["numpy_float"], 2.718)
        self.assertIsInstance(result["numpy_float"], float)

    def test_string_and_boolean_preservation(self):
        """Test that strings and booleans are preserved unchanged."""
        input_dict = {
            "string_value": "hello world",
            "bool_true": True,
            "bool_false": False,
            "empty_string": "",
        }

        result = dict_to_yaml_formatting(input_dict.copy())

        self.assertEqual(result["string_value"], "hello world")
        self.assertIsInstance(result["string_value"], str)

        self.assertEqual(result["bool_true"], True)
        self.assertIsInstance(result["bool_true"], bool)

        self.assertEqual(result["bool_false"], False)
        self.assertIsInstance(result["bool_false"], bool)

        self.assertEqual(result["empty_string"], "")
        self.assertIsInstance(result["empty_string"], str)

    def test_list_and_array_conversion(self):
        """Test conversion of lists and numpy arrays."""
        input_dict = {
            "int_list": [1, 2, 3, 4],
            "float_list": [1.1, 2.2, 3.3],
            "mixed_list": [1, 2.5, 3],
            "numpy_array": np.array([10, 20, 30]),
            "numpy_float_array": np.array([1.5, 2.5, 3.5]),
            "mixed_types_list": [1, "hello", True, 4.5],
        }

        result = dict_to_yaml_formatting(input_dict.copy())

        # Lists with numeric values should be converted to floats
        expected_int_list = [1.0, 2.0, 3.0, 4.0]
        self.assertEqual(result["int_list"], expected_int_list)

        expected_float_list = [1.1, 2.2, 3.3]
        self.assertEqual(result["float_list"], expected_float_list)

        expected_mixed_list = [1.0, 2.5, 3.0]
        self.assertEqual(result["mixed_list"], expected_mixed_list)

        # Numpy arrays should be converted to lists of floats
        expected_numpy = [10.0, 20.0, 30.0]
        self.assertEqual(result["numpy_array"], expected_numpy)
        self.assertIsInstance(result["numpy_array"], list)

        expected_numpy_float = [1.5, 2.5, 3.5]
        self.assertEqual(result["numpy_float_array"], expected_numpy_float)

        # Mixed types list - preserve strings and bools, convert numbers to float
        expected_mixed_types = [1.0, "hello", True, 4.5]
        self.assertEqual(result["mixed_types_list"], expected_mixed_types)

    def test_nested_dictionaries(self):
        """Test recursive processing of nested dictionaries."""
        input_dict = {
            "level1": {
                "level2": {
                    "numeric_value": np.int64(100),
                    "array_value": np.array([1, 2, 3]),
                    "string_value": "nested_string",
                },
                "simple_value": 42.0,
            },
            "top_level_array": [10, 20, 30],
        }

        result = dict_to_yaml_formatting(input_dict.copy())

        # Check nested conversion
        self.assertEqual(result["level1"]["level2"]["numeric_value"], 100.0)
        self.assertEqual(result["level1"]["level2"]["array_value"], [1.0, 2.0, 3.0])
        self.assertEqual(result["level1"]["level2"]["string_value"], "nested_string")
        self.assertEqual(result["level1"]["simple_value"], 42.0)
        self.assertEqual(result["top_level_array"], [10.0, 20.0, 30.0])

    def test_list_with_nested_dictionaries(self):
        """Test lists containing dictionaries."""
        input_dict = {
            "complex_list": [
                {"name": "item1", "value": np.int32(10)},
                {"name": "item2", "value": np.array([1, 2])},
                "simple_string",
                42,
            ]
        }

        result = dict_to_yaml_formatting(input_dict.copy())

        expected = [
            {"name": "item1", "value": 10.0},
            {"name": "item2", "value": [1.0, 2.0]},
            "simple_string",
            42.0,
        ]

        self.assertEqual(result["complex_list"], expected)

    def test_empty_containers(self):
        """Test handling of empty lists, arrays, and dictionaries."""
        input_dict = {
            "empty_list": [],
            "empty_array": np.array([]),
            "empty_dict": {},
            "dict_with_empty": {"empty_nested": []},
        }

        result = dict_to_yaml_formatting(input_dict.copy())

        self.assertEqual(result["empty_list"], [])
        self.assertEqual(result["empty_array"], [])
        self.assertEqual(result["empty_dict"], {})
        self.assertEqual(result["dict_with_empty"]["empty_nested"], [])

    def test_yaml_serialization_compatibility(self):
        """Test that the formatted dictionary can be properly serialized to YAML."""
        input_dict = {
            "plant_config": {
                "capacity": np.float64(100.5),
                "efficiency": np.array([0.85, 0.90, 0.95]),
                "technologies": ["wind", "solar"],
                "active": True,
                "metadata": {"version": "1.0", "parameters": np.array([1, 2, 3, 4])},
            },
            "cost_data": [
                {"component": "turbine", "cost": np.int32(1000000)},
                {"component": "inverter", "cost": np.float32(50000.5)},
            ],
        }

        # Format the dictionary
        formatted_dict = dict_to_yaml_formatting(input_dict.copy())

        # Try to serialize to YAML file
        temp_yaml_path = Path(self.temp_dir) / "test_output.yaml"

        with temp_yaml_path.open("w") as yaml_file:
            yaml.dump(formatted_dict, yaml_file, default_flow_style=False)

        # Verify file was created and can be read back
        self.assertTrue(temp_yaml_path.exists())

        with temp_yaml_path.open() as yaml_file:
            loaded_dict = yaml.safe_load(yaml_file)

        # Verify the loaded data matches expected structure
        self.assertEqual(loaded_dict["plant_config"]["capacity"], 100.5)
        self.assertEqual(loaded_dict["plant_config"]["efficiency"], [0.85, 0.90, 0.95])
        self.assertEqual(loaded_dict["plant_config"]["technologies"], ["wind", "solar"])
        self.assertEqual(loaded_dict["plant_config"]["active"], True)
        self.assertEqual(loaded_dict["plant_config"]["metadata"]["version"], "1.0")
        self.assertEqual(
            loaded_dict["plant_config"]["metadata"]["parameters"], [1.0, 2.0, 3.0, 4.0]
        )

    def test_numpy_dtypes_conversion(self):
        """Test conversion of various numpy data types."""
        input_dict = {
            "int8": np.int8(8),
            "int16": np.int16(16),
            "int32": np.int32(32),
            "int64": np.int64(64),
            "float16": np.float16(16.5),
            "float32": np.float32(32.5),
            "float64": np.float64(64.5),
            "bool_np": np.bool_(True),
        }

        result = dict_to_yaml_formatting(input_dict.copy())

        # All numeric numpy types should be converted to float
        self.assertEqual(result["int8"], 8.0)
        self.assertIsInstance(result["int8"], float)

        self.assertEqual(result["int16"], 16.0)
        self.assertIsInstance(result["int16"], float)

        self.assertEqual(result["int32"], 32.0)
        self.assertIsInstance(result["int32"], float)

        self.assertEqual(result["int64"], 64.0)
        self.assertIsInstance(result["int64"], float)

        self.assertEqual(result["float16"], 16.5)
        self.assertIsInstance(result["float16"], float)

        self.assertEqual(result["float32"], 32.5)
        self.assertIsInstance(result["float32"], float)

        self.assertEqual(result["float64"], 64.5)
        self.assertIsInstance(result["float64"], float)

        # numpy bool should be converted to float
        self.assertEqual(result["bool_np"], 1.0)
        self.assertIsInstance(result["bool_np"], float)

    def test_comprehensive_realistic_example(self):
        """Test with a realistic plant configuration example."""
        input_dict = {
            "plant_configuration": {
                "name": "Wind-Solar-H2 Plant",
                "location": {
                    "latitude": np.float64(39.7392),
                    "longitude": np.float64(-104.9903),
                    "elevation": np.int32(1609),
                },
                "technologies": {
                    "wind": {
                        "capacity_mw": np.array([50, 75, 100]),
                        "hub_height": np.float32(100.0),
                        "active": True,
                        "efficiency_curve": np.array([0.0, 0.25, 0.85, 0.95, 0.85, 0.0]),
                    },
                    "solar": {
                        "capacity_mw": np.int64(200),
                        "tilt_angle": np.float64(30.5),
                        "tracking": False,
                    },
                    "electrolyzer": {
                        "capacity_mw": np.float32(150.0),
                        "efficiency": np.array([0.65, 0.70, 0.75]),
                        "operating_pressure": np.int32(30),
                    },
                },
                "financial": {
                    "project_life": 25,
                    "discount_rate": np.float64(0.08),
                    "installation_costs": [
                        {"component": "wind", "cost_per_mw": np.int32(1500000)},
                        {"component": "solar", "cost_per_mw": np.int32(1000000)},
                    ],
                },
            }
        }

        result = dict_to_yaml_formatting(input_dict.copy())

        # Test that the result can be serialized to YAML
        temp_yaml_path = Path(self.temp_dir) / "comprehensive_test.yaml"

        with temp_yaml_path.open("w") as yaml_file:
            yaml.dump(result, yaml_file, default_flow_style=False)

        # Verify file exists and can be loaded
        self.assertTrue(temp_yaml_path.exists())

        with temp_yaml_path.open() as yaml_file:
            loaded_dict = yaml.safe_load(yaml_file)

        # Spot check some key values
        plant_config = loaded_dict["plant_configuration"]
        self.assertEqual(plant_config["name"], "Wind-Solar-H2 Plant")
        self.assertEqual(plant_config["location"]["latitude"], 39.7392)
        self.assertEqual(plant_config["location"]["elevation"], 1609.0)
        self.assertEqual(plant_config["technologies"]["wind"]["capacity_mw"], [50.0, 75.0, 100.0])
        self.assertEqual(plant_config["technologies"]["wind"]["active"], True)
        self.assertEqual(plant_config["financial"]["project_life"], 25)
        self.assertEqual(plant_config["financial"]["discount_rate"], 0.08)


@define
class DemoConfig(BaseConfig):
    """Test class for the basic functionality of `BaseConfig`."""

    x: int = field()
    y: str = field(default="y")


class BaseDemoModel:
    """Demo base model for testing."""

    def __init__(self, config: dict):
        self.config = DemoConfig.from_dict(
            config, strict=False, additional_cls_name=self.__class__.__name__
        )


class BaseDemoModelStrict:
    """Demo base model for testing."""

    def __init__(self, config: dict):
        self.config = DemoConfig.from_dict(config, strict=True)


class BaseDemoModelStrictAdditional:
    """Demo base model for testing."""

    def __init__(self, config: dict):
        self.config = DemoConfig.from_dict(
            config, strict=True, additional_cls_name=self.__class__.__name__
        )


class BaseDemoModelAdditional:
    """Demo base model for testing."""

    def __init__(self, config: dict):
        super().__init__(config)


def test_BaseConfig(subtests):
    """Tests the BaseConfig class."""

    with subtests.test("Check basic passing inputs"):
        demo = BaseDemoModel({"x": 1})
        assert demo.config.x == 1
        assert demo.config.y == "y"

    with subtests.test("Check allowed inputs overload"):
        demo = BaseDemoModel({"x": 1, "z": 2})
        assert demo.config.x == 1
        assert demo.config.y == "y"

    with subtests.test("Check prohibited inputs overload with additional"):
        msg = (
            "BaseDemoModelStrictAdditional setup failed as a result of DemoConfig"
            " receiving extraneous inputs"
        )
        with pytest.raises(AttributeError, match=msg):
            demo = BaseDemoModelStrictAdditional({"x": 1, "z": 2})

    with subtests.test("Check prohibited inputs overload w/o additional"):
        msg = "The initialization for DemoConfig" " was given extraneous inputs"
        with pytest.raises(AttributeError, match=msg):
            demo = BaseDemoModelStrict({"x": 1, "z": 2})
        assert demo.config.y == "y"

    with subtests.test("Check undefined inputs overload with additional"):
        msg = (
            "BaseDemoModelStrictAdditional setup failed as a result of DemoConfig"
            " missing the following inputs"
        )
        with pytest.raises(AttributeError, match=msg):
            demo = BaseDemoModelStrictAdditional({})

    with subtests.test("Check prohibited inputs overload w/o additional"):
        msg = "The class definition for DemoConfig is missing the following inputs"
        with pytest.raises(AttributeError, match=msg):
            demo = BaseDemoModelStrict({})


if __name__ == "__main__":
    unittest.main()
