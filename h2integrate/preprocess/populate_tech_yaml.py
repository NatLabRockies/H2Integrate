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

import attr
import yaml

from h2integrate.core.dict_utils import remove_numpy, split_shared_parameters
from h2integrate.core.file_utils import load_yaml
from h2integrate.core.supported_models import supported_models


MODEL_SECTION_NAMES = {
    "performance_model": "performance",
    "control_strategy": "control",
    "cost_model": "cost",
    "dispatch_rule_set": "dispatch",
}


def find_config_class(model_name: str, config_class_name: str | None = None):
    """Find the configuration class associated with a supported model.

    Args:
        model_name (str): Name of a model in ``supported_models``.
        config_class_name (str, optional): Explicit config class name to use
            instead of the standard naming convention. This is useful for
            models that intentionally share a base configuration class.

    Returns:
        type: The model's attrs configuration class.

    Raises:
        ValueError: If ``model_name`` is not supported.
        RuntimeError: If the configuration class cannot be found.
    """
    if model_name not in supported_models:
        raise ValueError(
            f"Model '{model_name}' not found in supported_models registry. "
            f"Available models: {sorted(supported_models.keys())}"
        )

    model_class = supported_models[model_name]
    if config_class_name:
        config_class_candidates = [(model_class.__module__, config_class_name)]
    else:
        config_class_candidates = [
            (model_class.__module__, f"{model_name}Config"),
            (model_class.__module__, model_name.replace("Model", "Config")),
            (model_class.__module__, model_name.replace("CostModel", "Config")),
            (model_class.__module__, f"{model_name}DesignConfig"),
        ]
        for base_class in model_class.__mro__[1:]:
            config_class_candidates.append((base_class.__module__, f"{base_class.__name__}Config"))

    config_class_candidates = list(dict.fromkeys(config_class_candidates))

    if not hasattr(model_class, "__module__"):
        raise RuntimeError(f"Model '{model_name}' has no __module__ attribute.")

    for module_name, candidate_name in config_class_candidates:
        model_module = __import__(module_name, fromlist=[candidate_name])
        if hasattr(model_module, candidate_name):
            config_class = getattr(model_module, candidate_name)
            if attr.has(config_class):
                return config_class

    raise RuntimeError(
        f"Could not find config class for model '{model_name}' "
        f"(searched in {model_class.__module__}). Tried: "
        f"{[candidate_name for _, candidate_name in config_class_candidates]}."
    )


def _validator_description(validator) -> str | None:
    """Convert a supported attrs validator into a concise YAML comment."""
    validator_type = type(validator).__name__

    if validator_type == "_OptionalValidator":
        description = _validator_description(validator.validator)
        return f"optional; {description}" if description else "optional"

    if validator_type == "_AndValidator":
        descriptions = [
            description
            for nested_validator in validator._validators
            if (description := _validator_description(nested_validator))
        ]
        return " and ".join(descriptions) if descriptions else None

    if validator_type == "_NumberValidator":
        return f"must be {validator.compare_op} {validator.bound}"

    if validator_type == "_InValidator":
        values = ", ".join(repr(value) for value in validator.options)
        return f"must be one of: {values}"

    if validator_type == "_InstanceOfValidator":
        return f"must be a {validator.type.__name__}"

    return None


def _model_validator_descriptions(model_name: str) -> dict[str, str]:
    """Return YAML comment text for the validators on a model config."""
    config_class = find_config_class(model_name)
    descriptions = {}
    for attribute in attr.fields(config_class):
        if attribute.validator is None:
            continue
        validators = (
            attribute.validator
            if isinstance(attribute.validator, tuple | list)
            else (attribute.validator,)
        )
        validator_descriptions = [
            description
            for validator in validators
            if (description := _validator_description(validator))
        ]
        if validator_descriptions:
            descriptions[attribute.name] = " and ".join(validator_descriptions)
    return descriptions


def _validator_comments(tech_config: dict) -> dict[tuple[str, str, str], str]:
    """Build comments keyed by technology, model-input section, and parameter."""
    comments = {}
    for tech_name, tech_info in tech_config.get("technologies", {}).items():
        for model_type, section_name in MODEL_SECTION_NAMES.items():
            model_info = tech_info.get(model_type, {})
            model_name = model_info.get("model")
            if not model_name:
                continue
            try:
                descriptions = _model_validator_descriptions(model_name)
            except (AttributeError, ImportError, RuntimeError, ValueError):
                continue
            for parameter, description in descriptions.items():
                key = (tech_name, f"{section_name}_parameters", parameter)
                comments.setdefault(key, description)
                shared_key = (tech_name, "shared_parameters", parameter)
                comments.setdefault(shared_key, description)
    return comments


def _dump_with_validator_comments(config: dict) -> str:
    """Serialize a config and append validator comments to model input scalars."""
    comments = _validator_comments(config)
    yaml_text = yaml.dump(config, default_flow_style=False, sort_keys=False)
    current_technology = None
    current_section = None
    output_lines = []

    for line in yaml_text.splitlines():
        stripped = line.strip()
        if line.startswith("  ") and not line.startswith("    ") and stripped.endswith(":"):
            current_technology = stripped[:-1]
            current_section = None
        elif current_technology and line.startswith("      ") and not line.startswith("        "):
            current_section = stripped[:-1] if stripped.endswith(":") else None
        elif current_technology and current_section and line.startswith("        "):
            parameter, separator, _value = stripped.partition(":")
            comment = comments.get((current_technology, current_section, parameter))
            if separator and comment and " # " not in line:
                line = f"{line}  # {comment}"
        output_lines.append(line)

    return "\n".join(output_lines) + "\n"


def extract_model_inputs(
    model_name: str,
    config_class_name: str | None = None,
) -> dict:
    """Extract all parameters from a model's config class.

    This function attempts to instantiate the model's config class with minimal
    input. If instantiation fails (due to required parameters), it falls back to
    introspecting the attrs class definition to extract all attribute names and
    their defaults.

    Args:
        model_name (str): Name of the model class (e.g., 'StoragePerformanceModel')
        config_class_name (str, optional): Explicit configuration class name when
            the model does not follow the standard naming convention.

    Returns:
        dict: Dictionary of all configurable parameters from the model class

    Raises:
        ValueError: If model_name not found in supported_models registry
        RuntimeError: If config class cannot be found or introspected
    """
    config_class = find_config_class(model_name, config_class_name)

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

    shared_parameters, section_only = split_shared_parameters(all_params_by_section)

    for section_name in ["performance", "control", "cost", "dispatch"]:
        section_key = f"{section_name}_parameters"
        section_only_params = section_only.get(section_name, {})
        if section_only_params:
            model_inputs[section_key] = section_only_params

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
        tech_config = load_yaml(config_path)
    except (OSError, ValueError, yaml.YAMLError) as e:
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
            f.write(_dump_with_validator_comments(populated_config))
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
