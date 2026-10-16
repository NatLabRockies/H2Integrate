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
units. It supports time steps from 1 second to $10^9$ seconds.

Combiners and splitters are documented separately in
[Combiners and Splitters](combiners_and_splitters.md).

## Transport cost models

- `LinearDistanceCostModel` calculates the geodesic distance between source and destination
  coordinates, then multiplies it by `capex_per_km` and `fixed_opex_per_km`. Connect site latitude
  and longitude to its `source_*` and `dest_*` inputs.
- `LinearMassTransportCostModel` uses geodesic distance, an optional `circuity_ratio` (default 1),
  and annual commodity throughput. Its input costs are `capex_per_mton_km` and
  `fixed_opex_per_mton_km`.

```{eval-rst}
.. autoclass:: h2integrate.transporters.generic_transporter.GenericTransporterPerformanceConfig
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

- [Example 22: Site DOE with transport cost](https://github.com/NatLabRockies/H2Integrate/tree/develop/examples/22_site_doe)
