# FLORIS Wind Plant

`FlorisWindPlantPerformanceModel` wraps the [FLORIS](https://github.com/NatLabRockies/floris) wind farm
model to calculate wind-farm electrical output from wind resource data and turbine configuration.
It supports a single turbine design per farm and uses one-hour time steps.

The model requires a FLORIS wake configuration and a turbine configuration [formatted for
FLORIS](https://natlabrockies.github.io/floris/).
The configurations can be included from YAML files as in [Example 26](https://github.com/NatLabRockies/H2Integrate/tree/develop/examples/26_floris).
The `layout` configuration selects a layout generator and its options; do not also set turbine
coordinates in `floris_wake_config.farm.layout_x` or `layout_y`, because the layout settings create
those coordinates. Multiple turbine designs in the same farm are not currently supported.

Resource data is supplied through the plant's site resource configuration and
`site_to_tech_connections`. The model selects or averages the resource heights around the turbine
hub height using `resource_data_averaging_method` (`weighted_average`, `average`, or `nearest`).
Turbulence intensity can be taken from the resource data or supplied as a default.

FLORIS calculations can be expensive for larger wind farms and more complicated wake models, so caching is enabled by default. `cache_dir` selects the
cache location when caching is enabled. Cache entries are based on the model configuration and
simulation inputs; disable caching with `enable_caching: false` when debugging or when cache reuse
is not desired.

The `tech_config` performance parameters for this model are detailed [below](#floris-performance-parameters).

(floris-performance-parameters)=
## Performance Parameters

- `num_turbines` (required): number of wind turbines in the wind farm.
- `floris_wake_config` (required):  dictionary containing wake parameters and options formatted for [FLORIS](https://natlabrockies.github.io/floris/wake_models.html). An example is provided in the H2I library named [`floris_v4_default_template.yaml`](https://github.com/NatLabRockies/H2Integrate/blob/develop/library/floris_v4_default_template.yaml)
- `floris_turbine_config` (required): dictionary containing wind turbine design information in the [FLORIS format](https://natlabrockies.github.io/floris/input_reference_turbine.html). Some examples are provided in the [H2I library](https://github.com/NatLabRockies/H2Integrate/tree/develop/library), with filenames starting with `floris_turbine_`. Please see the [section below](turbine-file-preprocessing) on some tips to create these files.
- `default_turbulence_intensity` (required): default turbulence intensity to use if not available in the wind resoure data, should be represented as a fraction (a value between 0 and 1).
- `operational_losses` (required): operational losses of the wind farm as a percentage (between 0 and 100).
- `hub_height` (optional): wind turbine hub height in meters. Can use -1 to indicate that the hub_height should be pulled from the `floris_turbine_config`
- `adjust_air_density_for_elevation` (optional): whether to adjust the air density for the elevation of the site (requires that elevation is available in the wind resource data). Defaults to False.
- `resource_data_averaging_method` (optional): The method to use to adjust or select resource data if no resource data is available at a height exactly equal to the turbine hub-height. Defaults to `'weighted_average'`. The available options are:
   - `'weighted_average`: average the resource data at the heights that most closelu bound the hub-height, weighted by the difference between the resource heights and the hub-height.
   - `'average'`: average the resource data at the heights that most closely bound the hub-height.
   - `'nearest'`: use the resource data at the height closest to the hub-height.
- `operation_model`: FLORIS turbine operation model, defaults to `'cosine-loss'`.
- `layout` (optional): configuration for wind turbine layout within the wind farm
    - `layout_mode` (str): currently only `"basicgrid"` is supported
    - `layout_options` (dict): options specific to the layout mode
        - For `"basicgrid"` mode:
            - `row_D_spacing` (float): rotor diameter multiplier for spacing between rows of
            turbines (y direction).
            - `rotation_angle_deg` (float, Optional): rotation angle of layout in degrees where 0 is North, increasing counter-clockwise. 90 degrees is East, 180 degrees is South,
            270 degrees is West. Defaults to 0.0.
            - `row_phase_offset` (float, Optional): offset of turbines along row from one row to the next. Value must be between 0 and 1. Defaults to 0.0.
            - `layout_shape` (str, optional): layout shape with respect to the number of turbines. Must be either 'square' or 'rectangle'. Defaults to 'square'.
            - `turbine_aspect_ratio` (float, optional): ratio of number turbines per row / number of rows if using a 'rectangle' layout_shape. Unused for 'square' layout_shape.
- `enable_caching` (optional): whether to save and FLORIS performance results to a file to future usage and whether to use previously cached performance results. The cache filename is based on the resource data, configuration inputs, and the openmdao inputs.
- `cache_dir` (optional): directory to save cached floris results to.

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
