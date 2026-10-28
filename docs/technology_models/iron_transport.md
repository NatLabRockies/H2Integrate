# Iron Transport Models

`IronTransportPerformanceComponent` estimates the land and water distances needed to ship iron ore
to a Great Lakes port. It reads the mine location from `plant_config.sites.site` and uses built-in
port coordinates and shipping waypoints. Set `find_closest_ship_site: true` and
`shipment_site: "None"` to select the shortest modeled route, or set `find_closest_ship_site: false`
and choose `Duluth`, `Chicago`, `Cleveland`, or `Buffalo` explicitly.
See {py:class}`~h2integrate.converters.iron.iron_transport.IronTransportPerformanceComponent` and
{py:class}`~h2integrate.converters.iron.iron_transport.IronTransportPerformanceComponentConfig`.

The performance component reports `land_transport_distance`, `water_transport_distance`, and
`total_transport_distance` in kilometers. `IronTransportCostComponent` uses these distances and the
`iron_ore_in` profile to calculate transport cost outputs. Its `transport_year` and `marginal_cost`
inputs are configured in the technology's cost parameters; the cost year is set from the plant's
`target_dollar_year`.
See {py:class}`~h2integrate.converters.iron.iron_transport.IronTransportCostComponent` and
{py:class}`~h2integrate.converters.iron.iron_transport.IronTransportCostComponentConfig`.
The cost component passes `iron_ore_in` through as `iron_ore_out` and reports
`iron_transport_cost`, `ore_profit_margin`, and `VarOpEx`. It divides by total input ore when
computing the unit cost, so a zero-throughput profile leads to division by zero.

Both models require hourly time steps. See the iron DRI and mine documentation for their use in
complete flowsheets.

```{eval-rst}
.. autoclass:: h2integrate.converters.iron.iron_transport.IronTransportPerformanceComponentConfig
   :members:
   :no-index:

.. autoclass:: h2integrate.converters.iron.iron_transport.IronTransportCostComponentConfig
   :members:
   :no-index:
```

## Examples

The model is used by the iron mine, DRI, electrowinning, and mapping configurations in
[Example 21](https://github.com/NatLabRockies/H2Integrate/tree/develop/examples/21_iron_examples).
