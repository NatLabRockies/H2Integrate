# Populate Tech Config - Technology Configuration Generator

## Overview

`populate_tech_yaml` is a command-line utility and Python module that automatically generates the `model_inputs` section for H2Integrate technology configuration files.

When building a new H2Integrate model, you often start with a "skeleton" tech config containing just the model class names (e.g., `StoragePerformanceModel`, `DemandOpenLoopStorageController`). This utility inspects those model classes and extracts all their configurable parameters, organizing them into the appropriate sections:

- `shared_parameters` - Parameters used by multiple models
- `performance_parameters` - Performance model-specific inputs
- `cost_parameters` - Cost model-specific inputs
- `control_parameters` - Control strategy-specific inputs
- `dispatch_parameters` - Dispatch rule-specific inputs

## Why Use This?

**Problem:** Storage models (and many other converters) require careful organization of parameters across multiple configuration sections. When changing models, you need to shuffle parameters between `control_parameters`, `performance_parameters`, `cost_parameters`, and `shared_parameters`. This is error-prone and time-consuming.

**Solution:** `populate_tech_yaml` automatically:
1. Inspects all model classes you specified
2. Extracts their configuration parameters and defaults
3. Determines which parameters are shared vs. model-specific
4. Generates a complete template with all parameters in the right sections
5. You then fill in values specific to your use case

## Usage

### Command Line (Recommended)

Basic usage:
```bash
populate_tech_config path/to/skeleton_tech_config.yaml
```

Or run as a Python module:
```bash
python -m h2integrate.preprocess.populate_tech_yaml path/to/skeleton_tech_config.yaml
```

With output to a different file:
```bash
populate_tech_config path/to/skeleton_tech_config.yaml \
    --output-path path/to/populated_tech_config.yaml
```

### Python API

```python
from h2integrate.preprocess.populate_tech_yaml import populate_tech_yaml_from_file

# Load skeleton, populate, and save
populated_config = populate_tech_yaml_from_file(
    "path/to/skeleton_tech_config.yaml",
    output_path="path/to/output_tech_config.yaml",
)
```

Or work directly with dictionaries:
```python
from h2integrate.preprocess.populate_tech_yaml import populate_tech_config

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

populated = populate_tech_config(skeleton_config)
# Now populated["technologies"]["battery"]["model_inputs"] is fully organized
```

## Workflow Example

### Step 1: Create Skeleton Config

Create a minimal tech config with just model names:

**skeleton_tech_config.yaml:**
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

### Step 2: Run populate_tech_yaml

```bash
python -m h2integrate.preprocess.populate_tech_yaml skeleton_tech_config.yaml \
    --output-path populated_tech_config.yaml
```

Output:
```
Loading tech config from skeleton_tech_config.yaml...
Populating model_inputs sections...
Populated model_inputs for 'wind'
Populated model_inputs for 'battery'
Populated model_inputs for 'electrolyzer'
Writing populated config to populated_tech_config.yaml...
Success! Populated config written to populated_tech_config.yaml
```

### Step 3: Fill in the Generated Template

The generated `populated_tech_config.yaml` will look like:

```yaml
name: my_hydrogen_plant
technologies:
  wind:
    performance_model:
      model: PYSAMWindPlantPerformanceModel
    cost_model:
      model: ATBWindPlantCostModel
    model_inputs:
      performance_parameters:
        num_turbines: null
        hub_height: null
        rotor_diameter: null
        turbine_rating_kw: null
        # ... model defaults may also be included

  battery:
    performance_model:
      model: StoragePerformanceModel
    cost_model:
      model: ATBBatteryCostModel
    control_strategy:
      model: DemandOpenLoopStorageController
    model_inputs:
      cost_parameters:
        cost_year: null
        energy_capex: null
        power_capex: null
        opex_fraction: null
      shared_parameters:
        commodity_rate_units: null
        max_capacity: null
        init_soc_fraction: null
        charge_efficiency: null
        round_trip_efficiency: null
        max_charge_rate: null
        charge_equals_discharge: true
        max_soc_fraction: null
        commodity_amount_units: null
        discharge_efficiency: null
        min_soc_fraction: null
        commodity: null
        max_discharge_rate: null
        demand_profile: null
```

Replace the `null` placeholders with values for your use case. The utility retains a
small number of behavior-defining model defaults, such as `charge_equals_discharge`.

## Understanding the Output

### Parameter Organization

The utility organizes parameters using this logic:

1. **Shared Parameters**: If a parameter appears in 2+ model configs, it's placed in `shared_parameters`
   - Example: `commodity`, `max_capacity` are used by both storage performance and control models

2. **Model-Specific Parameters**: Unique to one model type
   - `performance_parameters`: For performance models only
   - `cost_parameters`: For cost models only
   - `control_parameters`: For control strategies only

3. **Template Values**: Required parameters use `null` placeholders. Some model
  defaults are retained when they define behavior and do not require user input.

### Example: Storage Model Parameters

For a storage system with performance + cost + control:

```yaml
model_inputs:
  shared_parameters:
    # These appear in 2+ model configs
    commodity: null  # Used by perf + control models
    max_capacity: null  # Used by perf + cost models
    max_charge_rate: null  # Used by perf + cost models

  performance_parameters:
    # Unique to StoragePerformanceModel
    round_trip_efficiency: null

  cost_parameters:
    # Unique to ATBBatteryCostModel
    energy_capex: null
    power_capex: null

  control_parameters:
    # Unique to DemandOpenLoopStorageController
    demand_profile: null
```

## Troubleshooting

### "Model not found in supported_models registry"
- Check spelling of model name
- Run `python -c "from h2integrate.core.supported_models import supported_models; print(sorted(supported_models.keys()))"` to list all available models

### "Could not find config class"
- Ensure the model has a configuration class following naming convention `ModelNameConfig` or `ModelConfig`
- This is usually in the same module as the model class

### "Failed to instantiate config"
- This usually means the model has required parameters
- The utility will still extract parameters via attrs introspection
- You'll see `null` for required fields

### Parameter Not Appearing
- Verify the parameter is declared in the config class with `@attr.define` or similar
- Non-init attributes are skipped (as they shouldn't be configured)

## Advanced Usage

### Extract Parameters Programmatically

```python
from h2integrate.preprocess.populate_tech_yaml import extract_model_inputs

# Get all configurable parameters for a single model
params = extract_model_inputs(
    model_name="StoragePerformanceModel",
)

for param_name, param_value in params.items():
    print(f"  {param_name}: {param_value}")
```

## Design Details

### How It Works

1. **Model Discovery**: Loads model class from `supported_models` registry
2. **Config Class Location**: Finds config class following naming patterns:
   - Primary: `{ModelName}Config` (e.g., `StoragePerformanceModelConfig`)
   - Fallback: Model name with `Model` replaced by `Config`
3. **Parameter Extraction**: Attempts to instantiate config with empty dict
   - If successful: calls `config.as_dict()` to get parameters with defaults
   - If fails (required fields): Uses attrs introspection to get all field names
4. **Parameter Organization**: Groups parameters by model type using Counter to detect overlaps
5. **YAML Output**: Writes organized parameters to YAML with null placeholders

### Configuration Classes

All H2Integrate models use `@attr.define` decorated configuration classes:

```python
from attrs import define, field
from h2integrate.core.utilities import BaseConfig

@define(kw_only=True)
class MyModelConfig(BaseConfig):
    """Configuration for MyModel."""
    required_param: float = field()  # No default = required
    optional_param: float = field(default=42.0)  # Has default = optional
```

When `populate_tech_yaml` processes this:
- `required_param: null` (user must supply)
- `optional_param: 42.0` (uses default, user can override)

## See Also

- [Technology Configuration Guide](tech_config.md) - Full tech config structure
- [Model Base Classes](../api/core/model_baseclasses.md) - Config class patterns
- [Storage Models Documentation](../storage/storage_models.md) - Storage-specific configs
- [Example 99: populate_tech_yaml](../../examples/99_populate_tech_yaml/) - Working example
