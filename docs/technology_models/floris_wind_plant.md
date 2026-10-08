# FLORIS Wind Plant

`FlorisWindPlantPerformanceModel` wraps the FLORIS wake model to calculate wind-farm electrical
output from wind resource data and turbine configuration. It supports a single turbine design per
farm and uses one-hour time steps.

The model requires a FLORIS wake configuration and a turbine configuration formatted for FLORIS.
The configurations can be included from YAML files as in [Example 26](https://github.com/NatLabRockies/H2Integrate/tree/develop/examples/26_floris).
The `layout` configuration selects a layout generator and its options; do not also set turbine
coordinates in `floris_wake_config.farm.layout_x` or `layout_y`, because the layout settings create
those coordinates. Multiple turbine designs in the same farm are not currently supported.

Resource data is supplied through the plant's site resource configuration and
`site_to_tech_connections`. The model selects or averages the resource heights around the turbine
hub height using `resource_data_averaging_method` (`weighted_average`, `average`, or `nearest`).
Turbulence intensity can be taken from the resource data or supplied as a default.

FLORIS calculations can be expensive, so caching is enabled by default. `cache_dir` selects the
cache location when caching is enabled. Cache entries are based on the model configuration and
simulation inputs; disable caching with `enable_caching: false` when debugging or when cache reuse
is not desired.

```{eval-rst}
.. autoclass:: h2integrate.converters.wind.floris.FlorisWindPlantPerformanceModelConfig
   :members:
   :no-index:
```
