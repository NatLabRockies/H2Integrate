# Transport Components

Transport components connect technologies in `plant_config.yaml` through
`technology_interconnections`. The built-in cable, pipe, and generic transporter models pass their
input commodity profile through without losses. They do not model transport delays, pressure drop,
or other physical constraints.

## Cables and pipes

The registered transport types `cable` and `pipe` are selected in a plant interconnection, for
example:

```yaml
technology_interconnections:
  - [wind, battery, electricity, cable]
  - [hydrogen_producer, hydrogen_storage, hydrogen, pipe]
```

`cable` transports electricity. `pipe` supports hydrogen, carbon dioxide, methanol, ammonia,
nitrogen, natural gas, wellhead gas, water, oxygen, lignin, and diesel. Both are no-cost
pass-through components; add a separate cost model if transport cost is needed.

`GenericTransporterPerformanceModel` is a configurable pass-through for a commodity and its rate
units. It supports time steps from 1 second to $10^9$ seconds, unlike several production models
that require hourly simulation.

## Combiner

`GenericCombinerPerformanceModel` sums one commodity from multiple sources into one output. It
accepts `commodity`, `commodity_rate_units`, and optional `in_streams` (default 2). Set
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
and `out2` branches. The splitter does not combine sources; use a combiner upstream when multiple
technologies supply its input.

## Multivariable gas streams

`GasStreamCombinerPerformanceModel` combines supported multivariable gas streams. It sums each
stream's mass flow and computes mass-weighted averages for intensive properties such as temperature,
pressure, and composition. Set `commodity` and `in_streams` in its performance parameters. The
connection syntax and stream variable names are covered in
{ref}`Connecting Technologies <transport-connections>`.

## Transport cost models

  coordinates, then multiplies it by `capex_per_km` and `fixed_opex_per_km`. Connect site latitude
  and longitude to its `source_*` and `dest_*` inputs.
- `LinearMassTransportCostModel` uses geodesic distance, an optional `circuity_ratio` (default 1),
  and annual commodity throughput. Its input costs are `capex_per_mton_km` and
  `fixed_opex_per_mton_km`.

```{eval-rst}
.. autoclass:: h2integrate.transporters.generic_transporter.GenericTransporterPerformanceConfig
   :members:
   :no-index:

.. autoclass:: h2integrate.transporters.generic_combiner.GenericCombinerPerformanceConfig
   :members:
   :no-index:

.. autoclass:: h2integrate.transporters.generic_splitter.GenericSplitterPerformanceConfig
   :members:
   :no-index:

.. autoclass:: h2integrate.transporters.gas_stream_combiner.GasStreamCombinerPerformanceModelConfig
   :members:
   :no-index:

.. autoclass:: h2integrate.transporters.linear_transport_cost.LinearTransportCostConfig
   :members:
   :no-index:

.. autoclass:: h2integrate.transporters.linear_mass_transport_cost.LinearMassTransportCostConfig
   :members:
   :no-index:
```

## Examples

- [Example 17: Splitter, wind, and direct ocean capture](https://github.com/NatLabRockies/H2Integrate/tree/develop/examples/17_splitter_wind_doc_h2)
- [Example 32: Multivariable gas streams](https://github.com/NatLabRockies/H2Integrate/tree/develop/examples/32_multivariable_streams)
