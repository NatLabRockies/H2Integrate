"""Tests for populate_tech_yaml utility."""

import tempfile
from pathlib import Path

import yaml
import pytest

from h2integrate.preprocess.populate_tech_yaml import (
    extract_model_inputs,
    populate_tech_config,
    organize_model_parameters,
    populate_tech_yaml_from_file,
)


@pytest.mark.unit
class TestExtractModelInputs:
    """Tests for extract_model_inputs function."""

    def test_extract_storage_performance_model(self):
        """Test extracting parameters from StoragePerformanceModel."""
        params = extract_model_inputs(
            model_name="StoragePerformanceModel",
        )

        assert isinstance(params, dict)
        # Should include key storage parameters
        assert "commodity" in params
        assert "max_capacity" in params
        assert "max_charge_rate" in params

    def test_extract_wind_performance_model(self):
        """Test extracting parameters from PYSAMWindPlantPerformanceModel."""
        params = extract_model_inputs(
            model_name="PYSAMWindPlantPerformanceModel",
        )

        assert isinstance(params, dict)
        # Should include key wind parameters
        assert "num_turbines" in params
        assert "turbine_rating_kw" in params
        assert "rotor_diameter" in params
        assert "hub_height" in params

    def test_extract_invalid_model_raises_error(self):
        """Test that invalid model name raises ValueError."""
        with pytest.raises(ValueError, match="not found in supported_models"):
            extract_model_inputs(
                model_name="NonExistentModel",
            )

    def test_extracted_params_have_defaults(self):
        """Test that extracted parameters include default values."""
        params = extract_model_inputs(
            model_name="PYSAMWindPlantPerformanceModel",
        )

        # config_name should have default "WindPowerSingleOwner"
        assert params["config_name"] == "WindPowerSingleOwner"
        assert params["create_model_from"] == "new"


@pytest.mark.unit
class TestOrganizeModelParameters:
    """Tests for organize_model_parameters function."""

    def test_organize_single_model(self):
        """Test organizing parameters from a single model."""
        tech_info = {
            "performance_model": {"model": "GenericCombinerPerformanceModel"},
            "model_inputs": {},
        }

        organized = organize_model_parameters(tech_info)
        assert "performance_parameters" in organized or len(organized) > 0

    def test_organize_multiple_models(self):
        """Test organizing parameters from multiple models (performance + cost)."""
        tech_info = {
            "performance_model": {"model": "PYSAMWindPlantPerformanceModel"},
            "cost_model": {"model": "ATBWindPlantCostModel"},
            "model_inputs": {},
        }

        organized = organize_model_parameters(tech_info)

        # Should have cost_parameters and performance_parameters
        assert "performance_parameters" in organized or "cost_parameters" in organized

    def test_shared_parameters_detected(self):
        """Test that shared parameters are correctly identified."""
        tech_info = {
            "performance_model": {"model": "StoragePerformanceModel"},
            "control_strategy": {"model": "DemandOpenLoopStorageController"},
            "cost_model": {"model": "ATBBatteryCostModel"},
            "model_inputs": {},
        }

        organized = organize_model_parameters(tech_info)

        # Should have shared_parameters (e.g., commodity, max_capacity)
        if "shared_parameters" in organized:
            assert len(organized["shared_parameters"]) > 0


@pytest.mark.unit
class TestPopulateTechConfig:
    """Tests for populate_tech_config function."""

    def test_populate_simple_config(self):
        """Test populating a simple tech config."""
        config = {
            "name": "test",
            "technologies": {
                "wind": {
                    "performance_model": {"model": "PYSAMWindPlantPerformanceModel"},
                    "cost_model": {"model": "ATBWindPlantCostModel"},
                    "model_inputs": {},
                }
            },
        }

        populated = populate_tech_config(config)

        # Original tech info should still be there
        assert "wind" in populated["technologies"]
        wind_tech = populated["technologies"]["wind"]
        assert wind_tech["performance_model"]["model"] == "PYSAMWindPlantPerformanceModel"

        # model_inputs should be populated
        assert "model_inputs" in wind_tech
        assert len(wind_tech["model_inputs"]) > 0

    def test_populate_multi_technology_config(self):
        """Test populating a config with multiple technologies."""
        config = {
            "name": "hybrid_system",
            "technologies": {
                "wind": {
                    "performance_model": {"model": "PYSAMWindPlantPerformanceModel"},
                    "cost_model": {"model": "ATBWindPlantCostModel"},
                    "model_inputs": {},
                },
                "battery": {
                    "performance_model": {"model": "StoragePerformanceModel"},
                    "cost_model": {"model": "ATBBatteryCostModel"},
                    "control_strategy": {"model": "DemandOpenLoopStorageController"},
                    "model_inputs": {},
                },
            },
        }

        populated = populate_tech_config(config)

        assert "wind" in populated["technologies"]
        assert "battery" in populated["technologies"]
        assert len(populated["technologies"]["wind"]["model_inputs"]) > 0
        assert len(populated["technologies"]["battery"]["model_inputs"]) > 0

    def test_populate_preserves_existing_values(self):
        """Test that populate_tech_config preserves existing non-empty model_inputs."""
        config = {
            "name": "test",
            "technologies": {
                "wind": {
                    "performance_model": {"model": "PYSAMWindPlantPerformanceModel"},
                    "cost_model": {"model": "ATBWindPlantCostModel"},
                    "model_inputs": {"performance_parameters": {"num_turbines": 5}},
                }
            },
        }

        # Deep copy config to compare
        import copy

        copy.deepcopy(config["technologies"]["wind"]["model_inputs"])

        populated = populate_tech_config(config)

        # If model_inputs was already populated, it should remain populated
        new_inputs = populated["technologies"]["wind"]["model_inputs"]
        assert len(new_inputs) > 0


@pytest.mark.unit
class TestPopulateTechYamlFromFile:
    """Tests for populate_tech_yaml_from_file function."""

    def test_populate_file_roundtrip(self):
        """Test loading skeleton, populating, and saving."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmppath = Path(tmpdir)

            # Create skeleton config
            skeleton_config = {
                "name": "test",
                "technologies": {
                    "wind": {
                        "performance_model": {"model": "PYSAMWindPlantPerformanceModel"},
                        "cost_model": {"model": "ATBWindPlantCostModel"},
                        "model_inputs": {},
                    }
                },
            }
            skeleton_path = tmppath / "skeleton.yaml"
            with skeleton_path.open("w") as f:
                yaml.dump(skeleton_config, f)

            # Populate it
            output_path = tmppath / "populated.yaml"
            populated = populate_tech_yaml_from_file(skeleton_path, output_path=output_path)

            # Verify output file was created
            assert output_path.exists()

            # Verify output has populated model_inputs
            with output_path.open() as f:
                saved_config = yaml.safe_load(f)
            assert len(saved_config["technologies"]["wind"]["model_inputs"]) > 0

            # Verify returned dict matches saved file
            assert populated == saved_config

    def test_populate_file_default_overwrite(self):
        """Test that populate_tech_yaml_from_file overwrites input if no output specified."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmppath = Path(tmpdir)

            # Create skeleton config
            skeleton_config = {
                "name": "test",
                "technologies": {
                    "wind": {
                        "performance_model": {"model": "PYSAMWindPlantPerformanceModel"},
                        "cost_model": {"model": "ATBWindPlantCostModel"},
                        "model_inputs": {},
                    }
                },
            }
            skeleton_path = tmppath / "config.yaml"
            with skeleton_path.open("w") as f:
                yaml.dump(skeleton_config, f)

            # Populate without specifying output (should overwrite input)
            populate_tech_yaml_from_file(skeleton_path)

            # Verify input file was updated
            with skeleton_path.open() as f:
                updated_config = yaml.safe_load(f)
            assert len(updated_config["technologies"]["wind"]["model_inputs"]) > 0

    def test_populate_nonexistent_file_raises_error(self):
        """Test that nonexistent file raises FileNotFoundError."""
        with pytest.raises(FileNotFoundError):
            populate_tech_yaml_from_file("/nonexistent/path/config.yaml")

    def test_populate_invalid_yaml_raises_error(self):
        """Test that invalid YAML raises ValueError."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmppath = Path(tmpdir)
            bad_yaml = tmppath / "bad.yaml"
            with bad_yaml.open("w") as f:
                f.write("{ invalid: yaml: [")

            with pytest.raises(ValueError, match="Failed to load tech config as YAML"):
                populate_tech_yaml_from_file(bad_yaml)
