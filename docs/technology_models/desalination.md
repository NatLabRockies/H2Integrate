# Reverse Osmosis Desalination

`ReverseOsmosisPerformanceModel` represents a reverse osmosis plant that converts feedwater and
electricity into freshwater. At each timestep, freshwater production (`water_out`, m^3/h) is the
minimum of three limits:

- the plant capacity, `freshwater_capacity_kg_per_hr` (kg/h) divided by `freshwater_density`
   (kg/m^3)
- the available electricity, `electricity_in` (kW) divided by `specific_energy_consumption` (kWh/m^3)
- the available feedwater, `feedwater_in` (m^3/h) multiplied by `recovery_ratio`

`electricity_in` and `feedwater_in` are inputs with one value per timestep, so they may vary over
the simulation. The model reports the resources actually used as `electricity_consumed` and
`feedwater_consumed`, along with the system `mass` and `footprint`.

Choose `salinity: seawater` or `salinity: brackish` in the configuration. This sets the recovery
ratio and specific energy consumption:

| Salinity   | Recovery ratio | Specific energy consumption |
| ---------- | -------------- | --------------------------- |
| `seawater` | 0.5            | 4.0 kWh/m^3                 |
| `brackish` | 0.75           | 1.5 kWh/m^3                 |

The capacity and freshwater density are also OpenMDAO inputs, so they can be varied by a design of
experiments or optimization.

`ReverseOsmosisCostModel` estimates capital and operating costs from
`freshwater_capacity_kg_per_hr` using the model's reference costs. Its cost configuration is fixed
to 2013 USD.
Both models support time steps from 1 second to 1 hour. Rates (`water_out`, `electricity_in`,
`feedwater_in`, and the consumed quantities) are per hour regardless of time step, while
`total_water_produced` and `annual_water_produced` account for the time step length.

```{eval-rst}
.. autoclass:: h2integrate.converters.water.desal.desalination.ReverseOsmosisPerformanceModelConfig
   :members:
   :no-index:

.. autoclass:: h2integrate.converters.water.desal.desalination.ReverseOsmosisCostModelConfig
   :members:
   :no-index:
```
