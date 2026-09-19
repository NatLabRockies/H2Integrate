# Populate Tech YAML from a Skeleton

## Overview

`populate_tech_yaml` is a command-line utility and Python module for generating
the `model_inputs` section of an H2Integrate technology configuration file.

Start with a skeleton that names the models used by each technology. The utility
then:

1. Finds each model's attrs-based configuration class.
2. Extracts configurable fields, defaults, and required fields.
3. Groups fields into performance, cost, control, dispatch, and shared sections.
4. Writes a complete YAML template with `null` placeholders where values are required.
5. Adds inline comments for supported attrs validators when writing the YAML file.

The Python dictionary returned by the API contains values only. YAML comments are
added when `populate_tech_yaml_from_file()` writes the output file.

## Why Use This?

Technology configurations can use several model types at once. A parameter used
by multiple models belongs under `shared_parameters`; a parameter used by only
one model belongs under its model-specific section. Building these sections by
hand is error-prone, particularly for storage and controller configurations.

`populate_tech_yaml` derives the organization from the configuration classes so
the generated file can be used as a starting template. Review the generated
values before running a model: a `null` value usually means that a required input
still needs to be supplied, while a retained default is a behavior-defining
default from the configuration class.

## Command Line

Populate a skeleton in place:

```bash
populate_tech_yaml path/to/skeleton_tech_config.yaml
```

Write the populated configuration to another file:

```bash
populate_tech_yaml path/to/skeleton_tech_config.yaml \
    --output-path path/to/populated_tech_config.yaml
```

The module form is equivalent:

```bash
python -m h2integrate.preprocess.populate_tech_yaml \
    path/to/skeleton_tech_config.yaml \
    --output-path path/to/populated_tech_config.yaml
```

The `--output-path` option can also be written as `-o`. If it is omitted, the
input file is overwritten.

## Python API

Use the file API when you want to load, populate, and save a YAML file:

```python
from h2integrate.preprocess.populate_tech_yaml import populate_tech_yaml_from_file

populated_config = populate_tech_yaml_from_file(
    "path/to/skeleton_tech_config.yaml",
    output_path="path/to/populated_tech_config.yaml",
)
```

Use the dictionary API when you want to inspect or further modify the result
without writing a file:

```python
from h2integrate.preprocess.populate_tech_yaml import populate_tech_yaml

skeleton_config = {
    "technologies": {
        "battery": {
            "performance_model": {"model": "StoragePerformanceModel"},
            "cost_model": {"model": "ATBBatteryCostModel"},
            "control_strategy": {"model": "DemandOpenLoopStorageController"},
            "model_inputs": {},
        }
    }
}

populated = populate_tech_yaml(skeleton_config)
model_inputs = populated["technologies"]["battery"]["model_inputs"]
```

For a single model, use `extract_model_inputs()`:

```python
from h2integrate.preprocess.populate_tech_yaml import extract_model_inputs

params = extract_model_inputs("StoragePerformanceModel")
```

If a model uses a deliberately non-standard or shared configuration class, pass
its explicit class name:

```python
params = extract_model_inputs(
    "GenericDemandComponent",
    config_class_name="DemandComponentBaseConfig",
)
```

## Skeleton Example

Create a minimal file containing the model names:

```yaml
name: my_hydrogen_plant
description: Simple hydrogen production plant

technologies:
  wind:
    performance_model:
      model: PYSAMWindPlantPerformanceModel
    cost_model:
      model: ATBWindPlantCostModel
    model_inputs: {}

  battery:
    performance_model:
      model: StoragePerformanceModel
    cost_model:
      model: ATBBatteryCostModel
    control_strategy:
      model: DemandOpenLoopStorageController
    model_inputs: {}

  electrolyzer:
    performance_model:
      model: ECOElectrolyzerPerformanceModel
    cost_model:
      model: BasicElectrolyzerCostModel
    model_inputs: {}
```

Run the utility:

```bash
python -m h2integrate.preprocess.populate_tech_yaml skeleton_tech_config.yaml \
    --output-path populated_tech_config.yaml
```

The command reports the technologies it populates and the output path it writes.

## Generated YAML and Validator Comments

When writing YAML, the utility adds concise comments for validators that it can
describe. The comments are documentation for the generated template; they do
not change the parsed YAML values.

For example, fields with numeric bounds or allowed values may look like this:

```yaml
model_inputs:
  performance_parameters:
    num_turbines: null  # must be >= 0
    max_capacity: null  # must be > 0
    config_name: WindPowerSingleOwner  # must be one of: 'WindPowerSingleOwner', 'WindPowerCommercial'
  shared_parameters:
    charge_efficiency: null  # optional; must be >= 0 and must be <= 1
```

The current comment formatter recognizes these attrs validator forms:

- `validators.ge(value)` and `validators.gt(value)`
- `validators.le(value)` and `validators.lt(value)`
- `validators.in_([...])` and other allowed-value collections
- `validators.optional(...)`
- combined validators such as `(validators.ge(0), validators.le(1))`
- `validators.instance_of(type)`

Comments are emitted for scalar model-input lines in the generated YAML. If a
validator is custom or cannot be described safely, the value is still extracted;
the line simply has no validator comment.

```{note}
The in-memory result from `populate_tech_yaml()` and the dictionary returned by
`populate_tech_yaml_from_file()` do not contain comments because YAML comments
are not represented in a normal Python dictionary. Reloading the written file
with `yaml.safe_load()` returns the same configuration values without the comments.
```

## Parameter Organization

The utility compares parameter names across the model configuration classes for
each technology:

- `shared_parameters`: a parameter appears in at least two model configurations.
- `performance_parameters`: a parameter appears only in the performance model.
- `cost_parameters`: a parameter appears only in the cost model.
- `control_parameters`: a parameter appears only in the control strategy.
- `dispatch_parameters`: a parameter appears only in the dispatch rule set.

For example, a storage performance model and storage controller may both use
`max_capacity`, so it is placed in `shared_parameters`. A demand profile used
only by the controller remains under `control_parameters`.

The utility keeps the first value encountered for a shared parameter. The
generated template should be reviewed when multiple models declare the same
field with different defaults or semantics.

## Defaults and Required Fields

The utility first attempts to create the configuration class from an empty input
dictionary. If required fields prevent instantiation, it introspects the attrs
class directly. Fields without defaults are emitted as `null`; fields with
defaults are emitted with their defaults when they can be serialized.

Factory defaults are evaluated when possible. NumPy values are converted to
ordinary Python values before YAML serialization.

Some configuration classes perform additional validation or post-initialization
checks that require related fields. In those cases, the generated template may
contain placeholders even though the eventual model configuration requires a
particular combination of values.

## Configuration-Class Discovery

Models are resolved through the `supported_models` registry. The utility looks
for an attrs configuration class in the model module using these conventions:

1. `{ModelName}Config`
2. The model name with `Model` replaced by `Config`
3. The model name with `CostModel` replaced by `Config`
4. `{ModelName}DesignConfig`
5. A configuration class named after an attrs-bearing base class in the model's
   method-resolution order

Only attrs classes are accepted as configuration classes. This prevents a model
class from being mistaken for its configuration when a string replacement does
not change the name.

Most current models now use a direct model-to-config name. Some models
intentionally share a base configuration or use a legacy configuration
mechanism. For those models, `find_config_class()` may require an explicit
`config_class_name`, or the utility may report that no configuration class is
available.

You can inspect a class directly:

```python
from h2integrate.preprocess.populate_tech_yaml import find_config_class

config_class = find_config_class("StoragePerformanceModel")
print(config_class.__name__)
```

## Troubleshooting

### Model not found in `supported_models`

Check the spelling and capitalization of the model name. To list available
names:

```bash
python -c "from h2integrate.core.supported_models import supported_models; print(sorted(supported_models.keys()))"
```

### Could not find config class

The model may use a non-standard or inherited config class, or it may not expose
an attrs configuration class at all. If you know the class name, try:

```python
extract_model_inputs(
    "GenericDemandComponent",
    config_class_name="DemandComponentBaseConfig",
)
```

Models without attrs configuration classes cannot be populated by this utility
until a suitable configuration class is added. The utility skips failed model
extractions during multi-model organization and prints a warning.

### Failed to instantiate config

This is expected when required fields are missing from an empty dictionary. The
utility falls back to attrs introspection and emits required fields as `null`.

### Parameter is missing

Confirm that the parameter is an `init` field on the selected attrs config class.
Non-init attrs fields are intentionally skipped. Also check whether the model
uses a shared or inherited base configuration.

### YAML comments are missing

Comments are written only by `populate_tech_yaml_from_file()`. The dictionary
APIs cannot retain comments. Also, only validator types that the formatter can
describe produce comments; unsupported custom validators do not fail extraction.

### Existing values were replaced

`populate_tech_yaml()` regenerates `model_inputs` for technologies it can
populate. Keep a skeleton copy if you need to preserve an existing populated
configuration, and review the generated output before using it.

## Design Details

The implementation uses the repository's `load_yaml()` helper for input files,
`supported_models` for model discovery, attrs metadata for configuration
introspection, and `remove_numpy()` before serialization. Shared-parameter
organization is centralized in `split_shared_parameters()` so the generator and
runtime input validation use the same overlap rule.

The generated YAML is serialized with ordinary PyYAML output and then receives
validator comments on matching model-input lines. Comments are intentionally
kept out of the returned dictionaries so downstream configuration handling sees
normal Python data.

## See Also

- [Set Up an Analysis](how_to_set_up_an_analysis.md) - H2Integrate configuration workflow
- [Class Structure](../developer_guide/class_structure.md) - Model and configuration class patterns
- [Storage Models Documentation](../storage/storage_models_index.md) - Storage-specific configs
