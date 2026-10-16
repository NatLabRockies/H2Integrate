# FLORIS Wind Plant

`FlorisWindPlantPerformanceModel` wraps the [FLORIS](https://github.com/NatLabRockies/floris) wind farm
model to calculate wind-farm electrical output from wind resource data and turbine configuration.
It supports a single turbine design per farm and uses one-hour time steps.

The model requires a FLORIS wake configuration and a turbine configuration [formatted for FLORIS](https://natlabrockies.github.io/floris/). The `floris_wake_config` is a dictionary containing the [FLORIS wake parameters](https://natlabrockies.github.io/floris/wake_models.html), with an example in the H2I library named [`floris_v4_default_template.yaml`](https://github.com/NatLabRockies/H2Integrate/blob/develop/library/floris_v4_default_template.yaml). The `floris_turbine_config` is a dictionary containing [FLORIS wind turbine design information](https://natlabrockies.github.io/floris/input_reference_turbine.html), with some examples provided in the [H2I library](https://github.com/NatLabRockies/H2Integrate/tree/develop/library), with filenames starting with `floris_turbine_`. Please see the [section below](turbine-file-preprocessing) on some tips to create the floris turbine input files.


The configurations can be included from YAML files as in [Example 26](https://github.com/NatLabRockies/H2Integrate/tree/develop/examples/26_floris).
The `layout` configuration selects a layout generator and its options; do not also set turbine
coordinates in `floris_wake_config.farm.layout_x` or `layout_y`, because the layout settings create
those coordinates. Multiple turbine designs in the same farm are not currently supported.

Resource data is supplied through the plant's site resource configuration and
`site_to_tech_connections`. The model selects or averages the resource heights around the turbine
hub height using `resource_data_averaging_method` (`weighted_average`, `average`, or `nearest`).
Turbulence intensity can be taken from the resource data or supplied as a default (defined as a fraction, with a value between 0 and 1). Additional farm losses are applied based on the `operational_losses` input (which is represented as a percent, with a value between 0 and 100)

FLORIS calculations can be expensive for larger wind farms and more complicated wake models, so caching is enabled by default. `cache_dir` selects the
cache location when caching is enabled. Cache entries are based on the model configuration and
simulation inputs; disable caching with `enable_caching: false` when debugging or when cache reuse
is not desired.

(turbine-file-preprocessing)=
## Turbine file preprocessing

The `h2integrate.preprocess.wind_turbine_file_tools` module can create turbine files from the
[turbine-models](https://github.com/NatLabRockies/turbine-models) library, so you do not have to
write them by hand:

- `export_turbine_to_floris_format(turbine_name)` writes a FLORIS turbine YAML file (named
  `floris_turbine_{turbine_name}.yaml` by default) to the H2I library folder, or to `output_folder`
  if given. Use its path as the FLORIS turbine configuration for this model.
- `FlorisTurbineDefaults` holds the defaults (`TSR`, `ref_air_density`, `ref_tilt`, and the
  cosine loss exponents) that fill in values FLORIS requires but are not provided by the turbine-models
  library. Pass a `FlorisTurbineDefaults` object or a dictionary as `floris_defaults` to override them.
- `export_turbine_to_pysam_format(turbine_name)` does the same for the PySAM Windpower model used
  by `PYSAMWindPlantPerformanceModel`.

See [Turbine Models Library Pre-Processing](../misc_resources/turbine_models_library_preprocessing.md)
for a worked example that exports a turbine, updates the `tech_config`, and runs Example 26.

```{eval-rst}
.. autofunction:: h2integrate.preprocess.wind_turbine_file_tools.export_turbine_to_floris_format
   :no-index:

.. autoclass:: h2integrate.preprocess.wind_turbine_file_tools.FlorisTurbineDefaults
   :members:
   :no-index:

.. autofunction:: h2integrate.preprocess.wind_turbine_file_tools.export_turbine_to_pysam_format
   :no-index:
```

```{eval-rst}
.. autoclass:: h2integrate.converters.wind.floris.FlorisWindPlantPerformanceModelConfig
   :members:
   :no-index:
```
