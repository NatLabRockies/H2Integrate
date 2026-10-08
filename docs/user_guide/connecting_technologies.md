(connecting_technologies:overview)=
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

##### Slice notation for mismatched shapes

3-element connections with different shared parameter names allow the user to append a NumPy-style slice in square brackets to the source and/or destination parameter name.
This is used to connect variables whose shapes differ, for example feeding a scalar finance output into a per-timestep input.
The slice is parsed into OpenMDAO `src_indices`, and the bracketed text is stripped from the parameter name before the connection is made.

```yaml
technology_interconnections: [
  # select a subset of the source to connect to the destination
  ["tech_a", "tech_b", ["source_param[0:100]", "dest_param"]],
  # tile a single source element across an 8760-length destination
  ["finance_subgroup_electricity", "grid_buy", ["LCOE[0]", "electricity_buy_price[0:8760]"]],
]
```

Behavior depends on which side carries a slice:

- **Source only** (`"source_param[0:100]"`): the slice selects source indices directly (supports start/stop/step, e.g. `[0:100:2]`, and `[:]` for the full range).
- **Destination only** or **both sides equal**: no `src_indices` are applied (the slice is treated as documentation of the target shape).
- **Both sides** (`"LCOE[0]"` → `"electricity_buy_price[0:8760]"`): the source indices are *tiled* to fill the destination length. A single index is repeated (e.g. `[0]` → 8760 copies) and a multi-index source such as `[0,1]` is cycled to fill the destination.

```{note}
When the destination has a slice, it must (1) start at `0` (a non-zero start raises a `ValueError`) and (2) include the destination length, e.g. `[0:8760]`. The length is required because the input shape is not known until `prob.setup()` has run.
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

(transport-connections)=
## Combiners, splitters, and transporters

The `cable`, `pipe`, generic transporter, combiner, and splitter models are documented in
[Transport Components](../technology_models/transport.md). This page focuses on how to express
their connections in `technology_interconnections`.
