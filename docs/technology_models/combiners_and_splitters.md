# Combiners and Splitters

Combiners merge several upstream streams into one, and splitters divide one upstream stream into
two. They are technologies declared in `tech_config.yaml`, and `plant_config.yaml` connects
other technologies to them as source or destination technologies in `technology_interconnections`.

## Combiner

`GenericCombinerPerformanceModel` sums one commodity from multiple sources into one output. It
accepts `commodity`, `commodity_rate_units`, and optional `in_streams` (defaults to 2). Set
`in_streams` to the number of incoming connections when combining more than two sources.

```yaml
technologies:
  electricity_combiner:
    performance_model:
      model: GenericCombinerPerformanceModel
    model_inputs:
      performance_parameters:
        commodity: electricity
        commodity_rate_units: kW
        in_streams: 3
```

The combined commodity profile and rated production are sums of the input streams. The output
capacity factor is a rated-production-weighted average; it is zero when total rated production is
zero. Each input must provide its commodity profile, rated production, and capacity factor.

In `plant_config.yaml`, connect each source to the combiner, then connect the combiner to whatever
uses the combined stream. The combiner's output is `{commodity}_out`.

### Example: wind and natural gas

[Example 23](https://github.com/NatLabRockies/H2Integrate/tree/develop/examples/23_solar_wind_ng_demand)
combines variable renewable generation with natural gas generation. The renewable generation is
first combined in `combiner`, and `fin_combiner` then adds the output of the natural gas plant so
that the total plant output can be used for finance calculations:

```yaml
# tech_config.yaml
technologies:
  fin_combiner:
    performance_model:
      model: GenericCombinerPerformanceModel
    model_inputs:
      performance_parameters:
        commodity: electricity
        commodity_rate_units: kW
```

```yaml
# plant_config.yaml
technology_interconnections:
  - [combiner, fin_combiner, electricity, cable]
  - [natural_gas_plant, fin_combiner, electricity, cable]
```

### Example: solar and battery

[Example 24](https://github.com/NatLabRockies/H2Integrate/tree/develop/examples/24_solar_battery_grid)
combines the solar output with the battery output, so downstream technologies see the combined
electricity from both:

```yaml
# tech_config.yaml
technologies:
  bat_combiner:
    performance_model:
      model: GenericCombinerPerformanceModel
    model_inputs:
      performance_parameters:
        commodity: electricity
        commodity_rate_units: kW
```

```yaml
# plant_config.yaml
technology_interconnections:
  - [solar, battery, electricity, cable]
  - [solar, bat_combiner, electricity, cable]
  - [battery, bat_combiner, electricity, cable]
  - [bat_combiner, electrical_load_demand, electricity, cable]
```

## Splitter

`GenericSplitterPerformanceModel` takes one input and produces exactly two outputs. `out1` is the
priority branch; `out2` receives the remainder. Configure `commodity` and `commodity_rate_units`
under `model_inputs.performance_parameters`, together with one of these modes:

- `split_mode: fraction` requires `fraction_to_priority_tech`, between 0 and 1. `out1` receives that
  fraction of the input, and `out2` receives the rest.
- `split_mode: prescribed_commodity` requires `prescribed_commodity_to_priority_tech`, in the
  configured commodity rate units. `out1` receives the requested amount, limited to the available
  nonnegative input; `out2` receives the remainder.

```yaml
technologies:
  electricity_splitter:
    performance_model:
      model: GenericSplitterPerformanceModel
    model_inputs:
      performance_parameters:
        commodity: electricity
        commodity_rate_units: kW
        split_mode: fraction
        fraction_to_priority_tech: 0.7
```

Connect the two downstream technologies to the splitter in the same order as the intended `out1`
and `out2` branches.

### Example: splitting wind electricity

[Example 17](https://github.com/NatLabRockies/H2Integrate/tree/develop/examples/17_splitter_wind_doc_h2)
splits wind electricity between a direct ocean capture plant and an electrolyzer. The first
downstream technology listed receives `out1`, and the second receives `out2`:

```yaml
# plant_config.yaml
technology_interconnections:
  - [wind, electricity_splitter, electricity, cable]
  - [electricity_splitter, doc, electricity, cable]
  - [electricity_splitter, electrolyzer, electricity, cable]
```

## Multivariable gas streams

`GasStreamCombinerPerformanceModel` combines supported multivariable gas streams. It sums each
stream's mass flow and computes mass-weighted averages for intensive properties such as temperature,
pressure, and composition. Set `commodity` and `in_streams` in its performance parameters. The
connection syntax and stream variable names are covered in
{ref}`Connecting Technologies <transport-connections>`.

## API reference

```{eval-rst}
.. autoclass:: h2integrate.transporters.generic_combiner.GenericCombinerPerformanceConfig
   :members:
   :no-index:

.. autoclass:: h2integrate.transporters.generic_splitter.GenericSplitterPerformanceConfig
   :members:
   :no-index:

.. autoclass:: h2integrate.transporters.gas_stream_combiner.GasStreamCombinerPerformanceModelConfig
   :members:
   :no-index:
```

## Examples

- [Example 17: Splitter, wind, and direct ocean capture](https://github.com/NatLabRockies/H2Integrate/tree/develop/examples/17_splitter_wind_doc_h2)
- [Example 23: Solar, wind, and natural gas with demand](https://github.com/NatLabRockies/H2Integrate/tree/develop/examples/23_solar_wind_ng_demand)
- [Example 24: Solar, battery, and grid](https://github.com/NatLabRockies/H2Integrate/tree/develop/examples/24_solar_battery_grid)
- [Example 32: Multivariable gas streams](https://github.com/NatLabRockies/H2Integrate/tree/develop/examples/32_multivariable_streams)
