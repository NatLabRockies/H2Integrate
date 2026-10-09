# Reverse Osmosis Desalination

`ReverseOsmosisPerformanceModel` represents a fixed-capacity reverse osmosis plant. Configure its
freshwater capacity in kg/h and choose `salinity: seawater` or `salinity: brackish`. The model
reports freshwater as `water_out` in m^3/h, along with `feedwater` and electricity demand. Its
current simplified assumptions use 50% recovery and 4 kWh/m^3 for seawater, and 75% recovery and
1.5 kWh/m^3 for brackish water.

`ReverseOsmosisCostModel` estimates capital and operating costs from the freshwater capacity using
the model's reference costs. Its cost configuration is fixed to 2013 USD. Both models require
hourly time steps.

```{eval-rst}
.. autoclass:: h2integrate.converters.water.desal.desalination.ReverseOsmosisPerformanceModelConfig
   :members:
   :no-index:

.. autoclass:: h2integrate.converters.water.desal.desalination.ReverseOsmosisCostModelConfig
   :members:
   :no-index:
```
