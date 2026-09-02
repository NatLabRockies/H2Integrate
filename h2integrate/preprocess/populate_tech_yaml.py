"""Populate technology configuration with model input templates.

This utility ingests a tech config file containing model names (but minimal or empty
model_inputs sections) and auto-generates the model_inputs sections by:

1. Instantiating each model's config class
2. Extracting required and optional parameters from the config
3. Organizing parameters into control_parameters, performance_parameters,
   cost_parameters, shared_parameters, and dispatch_parameters
4. Writing out the populated tech config as YAML

This greatly simplifies the process of building tech configs, especially for
storage models where parameters must be carefully organized across multiple
configuration sections.

Usage (CLI):
    python -m h2integrate.preprocess.populate_tech_yaml \\
        <path_to_skeleton_tech_config.yaml> \\
        [--output-path <output_path>]

    Or use the command-line entry point:
    populate_tech_yaml <path_to_skeleton_tech_config.yaml> \\
        [--output-path <output_path>]

Usage (Python):
    from h2integrate.preprocess.populate_tech_yaml import populate_tech_yaml_from_file
    populated_config = populate_tech_yaml_from_file(
        "path/to/skeleton_tech_config.yaml",
        output_path="path/to/output_tech_config.yaml",
    )
"""

import copy
import argparse
from pathlib import Path
from collections import Counter

import attr
import yaml

from h2integrate.core.dict_utils import remove_numpy
from h2integrate.core.supported_models import supported_models


def extract_model_inputs(
    model_name: str,
) -> dict:
    """Extract all parameters from a model's config class.

    This function attempts to instantiate the model's config class with minimal
    input. If instantiation fails (due to required parameters), it falls back to
    introspecting the attrs class definition to extract all attribute names and
    their defaults.

    Args:
        model_name (str): Name of the model class (e.g., 'StoragePerformanceModel')

    Returns:
        dict: Dictionary of all configurable parameters from the model class

    Raises:
        ValueError: If model_name not found in supported_models registry
        RuntimeError: If config class cannot be found or introspected
    """
    if model_name not in supported_models:
        raise ValueError(
            f"Model '{model_name}' not found in supported_models registry. "
            f"Available models: {sorted(supported_models.keys())}"
        )

    try:
        model_class = supported_models[model_name]
    except Exception as e:
        raise ValueError(f"Failed to load model '{model_name}': {e}") from e

    # Find the config class (convention: ModelClass -> ModelClassConfig)
    # Try multiple naming patterns: ModelNameConfig, ModelConfig, ModelNameConfigClass, etc.
    config_class_candidates = [
        f"{model_name}Config",  # Standard: StoragePerformanceModelConfig
        model_name.replace("Model", "Config"),  # Alternate: StoragePerformanceConfig
    ]

    if not hasattr(model_class, "__module__"):
        raise RuntimeError(
            f"Model '{model_name}' has no __module__ attribute. Is it a proper class?"
        )

    # Try to find config class in the model's module
    config_class = None
    last_error = None
    for config_class_name in config_class_candidates:
        try:
            model_module = __import__(model_class.__module__, fromlist=[config_class_name])
            if hasattr(model_module, config_class_name):
                config_class = getattr(model_module, config_class_name)
                break
        except (ImportError, AttributeError) as e:
            last_error = e
            continue

    if config_class is None:
        raise RuntimeError(
            f"Could not find config class for model '{model_name}' "
            f"(searched in {model_class.__module__}). "
            f"Tried: {config_class_candidates}. "
            f"Ensure the config class follows naming convention ModelNameConfig."
        ) from last_error

    params_dict = {}

    # Try to instantiate the config class with minimal input
    try:
        config_dict = {}
        config_instance = config_class.from_dict(config_dict, strict=False)
        params_dict = config_instance.as_dict()
    except (AttributeError, KeyError, TypeError, ValueError):
        # If instantiation fails (due to required fields), introspect attrs class directly
        try:
            if not attr.has(config_class):
                raise RuntimeError(
                    f"{config_class_name} is not an attrs class. "
                    f"Config classes must use @attrs.define decorator."
                )

            # Extract all attributes from the attrs class
            for attribute in attr.fields(config_class):
                if not attribute.init:
                    continue  # Skip non-init attributes

                # Use the default value if available, else use None as placeholder
                if attribute.default != attr.NOTHING:
                    if isinstance(attribute.default, attr.Factory):
                        # Try to call the factory, or use None
                        try:
                            params_dict[attribute.name] = attribute.default.factory()
                        except (AttributeError, KeyError, TypeError, ValueError):
                            params_dict[attribute.name] = None
                    else:
                        params_dict[attribute.name] = attribute.default
                else:
                    # Required field with no default - use None as placeholder
                    params_dict[attribute.name] = None

        except (AttributeError, KeyError, TypeError, ValueError) as e:
            raise RuntimeError(
                f"Failed to introspect {config_class_name} for '{model_name}'. " f"Error: {e}"
            ) from e

    # Clean up numpy types for YAML serialization
    params_dict = remove_numpy(params_dict)

    return params_dict


def organize_model_parameters(
    tech_info: dict,
) -> dict:
    """Organize model parameters into appropriate config sections.

    When a technology has multiple models (e.g., performance + control + cost),
    this function determines which parameters belong in:
    - shared_parameters (used by 2+ models)
    - performance_parameters
    - control_parameters
    - cost_parameters
    - dispatch_parameters

    Args:
        tech_info (dict): Technology info dict containing model names and existing model_inputs

    Returns:
        dict: Organized model_inputs with shared_parameters, control_parameters, etc.
    """
    model_inputs = {}
    all_params_by_section = {
        "performance": {},
        "control": {},
        "cost": {},
        "dispatch": {},
    }

    # Extract parameters from each model type
    for model_type_key in [
        "performance_model",
        "control_strategy",
        "cost_model",
        "dispatch_rule_set",
    ]:
        if model_type_key not in tech_info:
            continue

        model_name = tech_info[model_type_key].get("model")
        if not model_name:
            continue

        # Map model_type_key to section name
        section_map = {
            "performance_model": "performance",
            "control_strategy": "control",
            "cost_model": "cost",
            "dispatch_rule_set": "dispatch",
        }
        section_name = section_map[model_type_key]

        try:
            params = extract_model_inputs(model_name)
            all_params_by_section[section_name] = params
        except (RuntimeError, ValueError) as e:
            print(f"Warning: Failed to extract parameters for {model_type_key}='{model_name}': {e}")
            continue

    # Determine shared parameters: those that appear in 2+ model types
    all_params_flat = {}
    for section_params in all_params_by_section.values():
        all_params_flat.update(section_params)

    param_counts = Counter()
    for section_params in all_params_by_section.values():
        for param_key in section_params:
            param_counts[param_key] += 1

    # Parameters appearing in 2+ sections should be shared
    shared_param_keys = {k for k, v in param_counts.items() if v > 1}

    # Organize into sections
    shared_parameters = {}
    for section_name in ["performance", "control", "cost", "dispatch"]:
        section_key = f"{section_name}_parameters"
        section_params = all_params_by_section[section_name]

        # Remove shared params from this section
        section_only = {k: v for k, v in section_params.items() if k not in shared_param_keys}

        if section_only:
            model_inputs[section_key] = section_only

        # Collect shared params (take first occurrence)
        for param_key in shared_param_keys:
            if param_key in section_params and param_key not in shared_parameters:
                shared_parameters[param_key] = section_params[param_key]

    # Add shared_parameters if any exist
    if shared_parameters:
        model_inputs["shared_parameters"] = shared_parameters

    return model_inputs


def populate_tech_yaml(tech_config: dict) -> dict:
    """Populate a skeleton tech config with model_inputs.

    Args:
        tech_config (dict): Skeleton tech config with model names but empty/minimal model_inputs

    Returns:
        dict: Updated tech config with populated model_inputs sections
    """
    populated = copy.deepcopy(tech_config)

    if "technologies" not in populated:
        raise ValueError("tech_config must contain 'technologies' section")

    for tech_name, tech_info in populated["technologies"].items():
        if not tech_info:
            continue

        # Skip if no models are defined
        if not any(
            model_key in tech_info
            for model_key in [
                "performance_model",
                "control_strategy",
                "cost_model",
                "dispatch_rule_set",
            ]
        ):
            print(f"Skipping '{tech_name}': no model definitions found")
            continue

        # Organize and populate model_inputs
        organized_inputs = organize_model_parameters(tech_info)
        if organized_inputs:
            tech_info["model_inputs"] = organized_inputs
            print(f"Populated model_inputs for '{tech_name}'")
        else:
            print(f"No model_inputs extracted for '{tech_name}'")

    return populated


def populate_tech_yaml_from_file(
    config_path: str | Path,
    output_path: str | Path | None = None,
) -> dict:
    """Load, populate, and optionally save a tech config file.

    Args:
        config_path (str | Path): Path to skeleton tech_config.yaml
        output_path (str | Path, optional): Path to write populated config.
            If not provided, overwrites input file.

    Returns:
        dict: The populated tech config dictionary

    Raises:
        FileNotFoundError: If config_path does not exist
        ValueError: If config_path is not valid YAML
    """
    config_path = Path(config_path)
    if not config_path.exists():
        raise FileNotFoundError(f"Tech config file not found: {config_path}")

    # Load the skeleton config
    print(f"Loading tech config from {config_path}...")
    try:
        with config_path.open() as f:
            tech_config = yaml.safe_load(f)
    except (OSError, yaml.YAMLError) as e:
        raise ValueError(f"Failed to load tech config as YAML: {e}") from e

    if not tech_config:
        raise ValueError("Tech config is empty")

    # Populate it
    print("Populating model_inputs sections...")
    populated_config = populate_tech_yaml(tech_config)

    # Clean up description field formatting (remove extra newlines)
    if "description" in populated_config and isinstance(populated_config["description"], str):
        populated_config["description"] = " ".join(populated_config["description"].split())

    # Write output
    if output_path is None:
        output_path = config_path

    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    print(f"Writing populated config to {output_path}...")
    try:
        with output_path.open("w") as f:
            yaml.dump(populated_config, f, default_flow_style=False, sort_keys=False)
        print(f"Success! Populated config written to {output_path}")
    except (OSError, yaml.YAMLError) as e:
        raise RuntimeError(f"Failed to write config to {output_path}: {e}") from e

    return populated_config


def main():
    """Command-line entry point for populate_tech_yaml."""
    parser = argparse.ArgumentParser(
        description="Populate technology configuration with model input templates.",
        epilog=("Example: " "populate_tech_yaml path/to/skeleton_tech_config.yaml"),
    )
    parser.add_argument(
        "config_path",
        type=str,
        help="Path to skeleton tech_config.yaml file with model names defined",
    )
    parser.add_argument(
        "--output-path",
        "-o",
        type=str,
        default=None,
        help="Output path for populated config (default: overwrite input file)",
    )

    args = parser.parse_args()

    try:
        populate_tech_yaml_from_file(
            args.config_path,
            output_path=args.output_path,
        )
    except (FileNotFoundError, OSError, RuntimeError, ValueError) as e:
        print(f"Error: {e}")
        exit(1)


if __name__ == "__main__":
    main()
