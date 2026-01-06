(connecting_technologies)=
# Connecting technologies

This guide covers how to connect different technologies within H2Integrate, focusing on the `technology_interconnections` configuration and the power combiner and splitter components that enable complex system architectures.

## Technology interconnections overview

The `technology_interconnections` section in your plant configuration file defines how different technologies are connected within your system.
This is how the H2I framework establishes the necessary OpenMDAO connections between your components based on these specifications.

### Configuration format

Technology interconnections are defined as an array of arrays in your `plant_config.yaml`:

```yaml
technology_interconnections: [
  ["source_tech", "destination_tech", "variable_name", "transport_type"],
  ["tech_a", "tech_b", "shared_parameter"],
  ["tech_a", "tech_b", ["tech_a_param_name", "tech_b_param_name"]],
  # ... more connections
]
```

There are two connection formats:

#### 4-element connections (transport components)
```yaml
["source_tech", "destination_tech", "variable_name", "transport_type"]
```

- **source_tech**: Name of the technology providing the output
- **destination_tech**: Name of the technology receiving the input
- **variable_name**: The type of variable being transported (e.g., "electricity", "hydrogen", "ammonia")
- **transport_type**: The transport component to use (e.g., "cable", "pipeline")

#### 3-element connections (direct connections)
##### Same shared parameter name
```yaml
["source_tech", "destination_tech", "shared_parameter"]
```

- **source_tech**: Name of the technology providing the output
- **destination_tech**: Name of the technology receiving the input
- **shared_parameter**: The exact parameter name to connect (e.g., "capacity_factor", "electrolyzer_degradation")

##### Different shared parameter names
```yaml
["source_tech", "destination_tech", ("source_parameter", "destination_parameter")]
```

- **source_tech**: Name of the technology providing the output
- **destination_tech**: Name of the technology receiving the input
- **source_parameter**: The name of the parameter within ``"source_tech"``
- **destination_parameter**: The name of the parameter within ``"destination_tech"``


### Internal connection logic

H2Integrate processes these connections in the `connect_technologies()` method of `h2integrate_model.py`. Here's what happens internally:

1. **Transport component creation**: For 4-element connections, H2Integrate creates a transport component instance and adds it to the OpenMDAO model with a unique name like `{source}_to_{dest}_{transport_type}`.

2. **Special handling for combiners and splitters**: The system automatically tracks connection counts for combiners and splitters to handle their multiple inputs/outputs:
   - **Splitters**: Outputs are connected as `electricity_out1`, `electricity_out2`, etc.
   - **Combiners**: Inputs are connected as `electricity_input1`, `electricity_input2`, etc.

3. **Automatic OpenMDAO connections**: The system creates the appropriate `model.connect()` calls to link the technologies through the transport components.

### Example connection flow

For a simple splitter configuration:
```yaml
technology_interconnections: [
  ["wind_farm", "electricity_splitter", "electricity", "cable"],
  ["electricity_splitter", "electrolyzer", "electricity", "cable"],
  ["electricity_splitter", "doc", "electricity", "cable"],
]
```

This creates:
1. `wind_farm_to_electricity_splitter_cable` component
2. `electricity_splitter_to_electrolyzer_cable` component
3. `electricity_splitter_to_doc_cable` component

And automatically connects:
- `wind_farm.electricity_out` → `wind_farm_to_electricity_splitter_cable.electricity_in`
- `wind_farm_to_electricity_splitter_cable.electricity_out` → `electricity_splitter.electricity_in`
- `electricity_splitter.electricity_out1` → `electricity_splitter_to_electrolyzer_cable.electricity_in`
- `electricity_splitter.electricity_out2` → `electricity_splitter_to_doc_cable.electricity_in`

## Generic combiner

The generic combiner is a simple but essential component that takes a single commodity from multiple sources and combines the sources into a single output without losses. The following example uses power (kW) as the commodity, but streams of any single commodity can be combined. Any number of sources may be combined, not just two as in the example.

### Configuration

Add the combiner to your `tech_config.yaml`:

```yaml
technologies:
  combiner:
    performance_model:
      model: "combiner_performance"
    model_inputs:
      performance_parameters:
        commodity: "electricity"
        commodity_units: "kW"
```

No additional configuration parameters are needed in the `tech_config.yaml` - the combiner simply adds the input streams.

### Inputs and outputs

- **Inputs**:
  - `<commidty_name>_in1`: Power from the first source (kW)
  - `<commidty_name>_in2`: Power from the second source (kW)
- **Output**:
  - `<commidty_name>_out`: Combined power output (kW)

The relationship is straightforward: `<commidty_name>_out = <commidty_name>_in1 + <commidty_name>_in2`

### Usage example

```yaml
technology_interconnections: [
  ["wind_farm", "combiner", "electricity", "cable"],
  ["solar_farm", "combiner", "electricity", "cable"],
  ["combiner", "electrolyzer", "electricity", "cable"],
]
```

This configuration combines wind and solar power before sending it to an electrolyzer.

## Power splitter

The power splitter is a more sophisticated component that takes electricity from one source and splits it between two outputs. It offers two operating modes to handle different system requirements.

### Configuration

Add the splitter to your `tech_config.yaml`:

```yaml
technologies:
  electricity_splitter:
    performance_model:
      model: "splitter_performance"
      config:
        commodity: "electricity"
        commodity_units: "kW"
        split_mode: "fraction"  # or "prescribed_electricity"
        fraction_to_priority_tech: 0.7  # for fraction mode
        # OR
        prescribed_electricity_to_priority_tech: 500.0  # for prescribed mode
```

### Split modes

#### Fraction mode (`split_mode: "fraction"`)

In fraction mode, you specify what fraction of the input power goes to the first technology:

```yaml
config:
  split_mode: "fraction"
  fraction_to_priority_tech: 0.3  # 30% to first tech, 70% to second
```

- **Input parameter**: `fraction_to_priority_tech` (0.0 to 1.0)
- **Behavior**:
  - `electricity_out1 = electricity_in × fraction`
  - `electricity_out2 = electricity_in × (1 - fraction)`

#### Prescribed electricity mode (`split_mode: "prescribed_electricity"`)

In prescribed electricity mode, you specify an exact amount of power to send to the first technology:

```yaml
config:
  split_mode: "prescribed_electricity"
  prescribed_electricity_to_priority_tech: 200.0  # 200 kW to first tech
```

- **Input parameter**: `prescribed_electricity_to_priority_tech` (kW)
- **Behavior**:
  - `electricity_out1 = min(prescribed_amount, available_power)`
  - `electricity_out2 = electricity_in - electricity_out1`
- **Smart limiting**: If you request more power than available, the first output gets all available power and the second output gets zero

```{note}
The `prescribed_electricity_to_priority_tech` parameter can be provided as either a scalar value (constant for all time steps) or as a time-series array that varies throughout the simulation. This allows for sophisticated control strategies where you're meeting a desired load profile, or when the power split changes over time based on operational requirements, market conditions.
```

### Inputs and outputs

- **Input**:
  - `electricity_in`: Total power input (kW)
  - Mode-specific inputs: either `fraction_to_priority_tech` or `prescribed_electricity_to_priority_tech`
- **Outputs**:
  - `electricity_out1`: Power sent to the first technology (kW)
  - `electricity_out2`: Power sent to the second technology (remainder) (kW)

### Usage example

```yaml
technology_interconnections: [
  ["offshore_wind", "electricity_splitter", "electricity", "cable"],
  ["electricity_splitter", "doc", "electricity", "cable"],      # first output
  ["electricity_splitter", "electrolyzer", "electricity", "cable"],    # second output
]
```

This sends part of the offshore wind power to a direct ocean capture system and the remainder to an electrolyzer.

```{note}
Each splitter handles exactly two inputs. For more complex architectures, you can chain multiple components together.
```
