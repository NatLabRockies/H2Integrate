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
- **transport_type**: The transport component to use (e.g., "cable", "pipe")

```{note}
"cable" and "pipe" are transport components that are internal to H2I and do not need to be defined in the technology configuration file. The "cable" can only transport electricity, and the "pipe" can transport a handful of commodities that are commonly used in H2I models (such as hydrogen, co2, methanol, ammonia, water, etc). To transport a commodity that is *not* supported with by "cable" or "pipe" transporters, the `GenericTransporterPerformanceModel` can be used instead. Example usage of the generic transporter is available in Example 21.
```

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
["source_tech", "destination_tech", ["source_parameter", "destination_parameter"]]
```

- **source_tech**: Name of the technology providing the output
- **destination_tech**: Name of the technology receiving the input
- **source_parameter**: The name of the parameter within ``"source_tech"``
- **destination_parameter**: The name of the parameter within ``"destination_tech"``

```{note}
The `source_parameter` and `destination_parameter` should be input into the array as another array. If it's input as a tuple the model will raise an error.
```

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

## Multivariable streams

Standard connections in H2Integrate transport a single commodity between technologies (e.g., electricity in kW, hydrogen in kg/h).
*Multivariable streams* extend this by bundling several related variables into a single named stream, so that one connection specification in `technology_interconnections` expands into connections for every constituent variable automatically.

A typical use-case is a gas mixture where you need to transport the mass flow rate, composition fractions, temperature, and pressure together between a producer, a combiner, and a consumer.

### Defining a multivariable stream

Multivariable streams are defined in `commodity_stream_definitions.py`. Each stream has a name and a dictionary of constituent variables with their units and descriptions:

```{literalinclude} ../../h2integrate/core/commodity_stream_definitions.py
:language: python
:lines: 11-35
:caption: Built-in stream definition from commodity_stream_definitions.py
```

To add a new multivariable stream type, add another entry to the `multivariable_streams` dictionary with the stream name as the key and the constituent variables as the value.

### Variable naming convention

Multivariable stream variables follow the naming convention `<stream_name>:<var_name>_in` for inputs and `<stream_name>:<var_name>_out` for outputs.
The colon separates the stream name from the constituent variable name, making it clear which stream a variable belongs to.


### Using multivariable streams in components

Two helper functions are provided to register all constituent variables of a multivariable stream on an OpenMDAO component:

```python
from h2integrate.core.commodity_stream_definitions import (
    add_multivariable_output,
    add_multivariable_input,
)

class MyProducer(PerformanceModelBaseClass):
    def setup(self):
        super().setup()
        # Adds all wellhead_gas_mixture variables as outputs
        add_multivariable_output(self, "wellhead_gas_mixture", self.n_timesteps)

class MyConsumer(PerformanceModelBaseClass):
    def setup(self):
        super().setup()
        # Adds all wellhead_gas_mixture variables as inputs
        add_multivariable_input(self, "wellhead_gas_mixture", self.n_timesteps)
```

These helper functions replace the need for manually iterating over the stream definition dictionary, reducing boilerplate code and ensuring consistency when adding new stream types.

### Connecting multivariable streams

Multivariable streams are connected using the same `technology_interconnections` syntax as standard connections.
When H2Integrate encounters a stream name that matches a key in `multivariable_streams`, it automatically expands the connection into individual connections for each constituent variable.

#### 4-element connections

```yaml
technology_interconnections: [
  ["gas_producer", "gas_consumer", "wellhead_gas_mixture", "pipe"],
]
```

This single line expands into five OpenMDAO connections:
- `gas_producer.wellhead_gas_mixture:mass_flow_out` → `gas_consumer.wellhead_gas_mixture:mass_flow_in`
- `gas_producer.wellhead_gas_mixture:hydrogen_mass_fraction_out` → `gas_consumer.wellhead_gas_mixture:hydrogen_mass_fraction_in`
- `gas_producer.wellhead_gas_mixture:oxygen_mass_fraction_out` → `gas_consumer.wellhead_gas_mixture:oxygen_mass_fraction_in`
- `gas_producer.wellhead_gas_mixture:temperature_out` → `gas_consumer.wellhead_gas_mixture:temperature_in`
- `gas_producer.wellhead_gas_mixture:pressure_out` → `gas_consumer.wellhead_gas_mixture:pressure_in`


#### 3-element connections

Three-element connections also support multivariable streams:

```yaml
technology_interconnections: [
  ["gas_producer", "gas_consumer", "wellhead_gas_mixture"],
]
```

This expands into the same set of individual connections as the 4-element version above.

#### Combiner and splitter connections

Multivariable streams work with combiners and splitters using the same naming conventions as standard commodity connections.
The system auto-increments stream indices for combiners and splitters:

```yaml
technology_interconnections: [
  ["gas_producer_1", "gas_combiner", "wellhead_gas_mixture"],
  ["gas_producer_2", "gas_combiner", "wellhead_gas_mixture"],
  ["gas_combiner", "gas_consumer", "wellhead_gas_mixture"],
]
```

For the combiner inputs, variables are indexed as `wellhead_gas_mixture:<var_name>_in1`, `wellhead_gas_mixture:<var_name>_in2`, etc.
For the splitter outputs, variables are indexed as `wellhead_gas_mixture:<var_name>_out1`, `wellhead_gas_mixture:<var_name>_out2`, etc.

### Example

See [Example 32](https://github.com/NatLabRockies/H2Integrate/tree/main/examples/32_multivariable_streams) for a complete working example that demonstrates two gas producers with different properties feeding into a gas stream combiner, which then feeds a consumer.

## Generic combiner

The generic combiner is a simple but essential component that takes a single commodity from multiple sources and combines the sources into a single output without losses. The following example uses power (kW) as the commodity, but streams of any single commodity can be combined. Any number of sources may be combined, not just two as in the example.

### Configuration

Add the combiner to your `tech_config.yaml`:

```yaml
technologies:
  combiner:
    performance_model:
      model: "GenericCombinerPerformanceModel"
    model_inputs:
      performance_parameters:
        commodity: "electricity"
        commodity_units: "kW"
```

No additional configuration parameters are needed in the `tech_config.yaml` - the combiner simply adds the input streams.

### Inputs and outputs

For each input stream *i* (numbered 1, 2, …, `in_streams`):

- **Inputs** (per stream):
  - `<commodity>_in<i>`: Time-series commodity profile from source *i* (commodity units)
  - `rated_<commodity>_production<i>`: Rated (nameplate) production of source *i* (commodity units, scalar)
  - `<commodity>_capacity_factor<i>`: Annual capacity factor of source *i* (unitless, shape = plant life)

- **Outputs**:
  - `<commodity>_out`: Combined commodity time-series profile — element-wise sum of all inputs
  - `rated_<commodity>_production`: Total rated production — sum of all input rated productions
  - `<commodity>_capacity_factor`: Combined capacity factor (unitless, shape = plant life)

### Commodity output

The combined output profile is the element-wise sum of all input profiles:

`<commodity>_out = <commodity>_in1 + <commodity>_in2 + …`

### Capacity factor calculation

The combined capacity factor is a **weighted average** of the input capacity factors, weighted by each stream's rated production:

`CF_out = (CF1 × S1 + CF2 × S2 + …) / (S1 + S2 + …)`

where `CF_i` is the capacity factor and `S_i` is the rated commodity production of input stream *i*. This weighting ensures that larger sources contribute proportionally more to the combined capacity factor. If the total rated production is zero, the output capacity factor is set to zero.

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
      model: "GenericSplitterPerformanceModel"
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
