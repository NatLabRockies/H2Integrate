# Wind Plant model using Windpower module in PySAM

This model uses the [Windpower module](https://nrel-pysam.readthedocs.io/en/main/modules/Windpower.html) available in PySAM to simulate the performance of a wind power plant.

To use this model, specify `"PYSAMWindPlantPerformanceModel"` as the performance model. An example of how this may look in the `tech_config` file is shown below and details on the performance parameter inputs can be found [here](#windpower-performance-parameters).
See {py:class}`~h2integrate.converters.wind.wind_pysam.PYSAMWindPlantPerformanceModel`,
{py:class}`~h2integrate.converters.wind.wind_pysam.PYSAMWindPlantPerformanceModelConfig`, and
{py:class}`~h2integrate.converters.wind.wind_pysam.PySAMPowerCurveCalculationInputs`.

The model receives a discrete `wind_resource_data` dictionary, `num_turbines`,
`wind_turbine_rating`, `rotor_diameter`, and `hub_height`. It reports an electricity profile
and production summaries and supports one-hour time steps. The current setup requires a `layout`
section in the performance parameters. See [wind cost models](atb_costs_wind.md) for a
capacity-based cost option.

```yaml
technologies:
  wind:
         performance_model:
             model: "PYSAMWindPlantPerformanceModel"
     model_inputs:
         performance_parameters:
            num_turbines: 10
            hub_height: 100.0
            rotor_diameter: 120.0
            turbine_rating_kw: 2500.0
            create_model_from: new #options are "default" and "new"
            config_name: #only used if create_model_from is "default", default is "WindPowerSingleOwner"
            layout:
              layout_mode: basicgrid #currently only "basicgrid" is supported
              layout_options:
                 row_D_spacing: 7.0
                 turbine_D_spacing: 7.0
                 rotation_angle_deg: 0.0
                 row_phase_offset: 0.0
                 layout_shape: square #options "square" or "rectangle"
            powercurve_calc_config: #optional configuration for power curve calculation
              elevation: 0
              wind_default_max_cp: 0.45
              wind_default_cut_in_speed: 4.0
              wind_default_cut_out_speed: 25.0
            run_recalculate_power_curve: True
            pysam_options: #user specified pysam inputs
              Turbine:
                 wind_turbine_max_cp: 0.45
                 wind_turbine_thrust_coeff: [0.8, 0.8, 0.8]
              Farm:
                 wind_farm_wake_model: 0
              Resource:
              Losses:
                 wind_farm_losses_percent: 8.0
              AdjustmentFactors:
```

(windpower-performance-parameters)=
## Performance Parameters
The configuration reference is generated from the class used by the model:

```{eval-rst}
.. autoclass:: h2integrate.converters.wind.wind_pysam.PYSAMWindPlantPerformanceModelConfig
   :no-members:
   :no-index:
```

For PySAM default configurations, see the
[SAM defaults directory](https://github.com/NatLabRockies/SAM/tree/develop/api/api_autogen/library/defaults).

(layout-parameters)=
## Layout Parameters
The `layout` dictionary selects `layout_mode: basicgrid` and provides `layout_options` using:

```{eval-rst}
.. autoclass:: h2integrate.converters.wind.layout.simple_grid_layout.BasicGridLayoutConfig
   :no-members:
   :no-index:
```

(powercurve-calc-parameters)=
## Power Curve Calculation Parameters
The `powercurve_calc_config` section uses:

```{eval-rst}
.. autoclass:: h2integrate.converters.wind.wind_pysam.PySAMPowerCurveCalculationInputs
   :no-members:
   :no-index:
```

(pysam-options-windpower)=
## PySAM Options
- `pysam_options` (dict): The top-level keys correspond to the Groups available in the [Windpower module](https://nrel-pysam.readthedocs.io/en/main/modules/Windpower.html). The next level is the individual attributes a user could set and a full list is available through the PySAM documentation of Windpower module. The Groups that users may want to specify specific options for are the:
    - [Turbine](#turbine-group)
    - [Farm](#farm-group)
    - [Resource](#resource-group)
    - [Losses](https://nrel-pysam.readthedocs.io/en/main/modules/Windpower.html#losses-group)
    - [AdjustmentFactors](https://nrel-pysam.readthedocs.io/en/main/modules/Windpower.html#adjustmentfactors-group)
    - [Uncertainty](https://nrel-pysam.readthedocs.io/en/main/modules/Windpower.html#uncertainty-group)


(turbine-group)=
### Turbine group
```{note}
Do not include the `wind_turbine_hub_ht` or `wind_turbine_rotor_diameter` parameters in the `Turbine` group. These should be set in the performance parameters with the variables `hub_height` and `rotor_diameter`.
```

Some common turbine parameters that a user may want to specify within the [Turbine Group](https://nrel-pysam.readthedocs.io/en/main/modules/Windpower.html#turbine-group) are:
- `wind_turbine_max_cp` (float): maximum power coefficient. Defaults to 0.45.
- `wind_turbine_thrust_coeff` (list): thrust coefficient as a function of wind speed. Must be same length as wind speed array.
- `wind_turbine_powercurve_windspeeds` (list): wind speeds for power curve in m/s.
- `wind_turbine_powercurve_powerout` (list): power output for power curve in kW. Must be same length as wind speed array.

(farm-group)=
### Farm group
Some common farm parameters that a user may want to specify within the [Farm Group](https://nrel-pysam.readthedocs.io/en/main/modules/Windpower.html#farm-group) are:
- `wind_farm_wake_model` (int): wake model selection.
    - 0: Original Park model
    - 1: Park model with wind speed-dependent wake decay constant
    - 2: Eddy-viscosity model
    - 3: Constant wake decay constant
- `wind_farm_wake_loss_percent` (float): wake losses as percentage of annual energy. Range (0, 50).

(resource-group)=
### Resource group
Wind resource data is automatically formatted from the wind resource database and input as the `wind_resource_data` variable in the Windpower Resource Group. Some other common resource parameters that a user may want to specify within the [Resource Group](https://nrel-pysam.readthedocs.io/en/main/modules/Windpower.html#resource-group) are:
- `wind_resource_shear` (float): shear exponent for wind profile.
- `wind_resource_turbulence_coeff` (float): turbulence coefficient.

## Model Outputs
The wind plant PySAM model provides the following outputs:
- `electricity_out`: hourly electricity generation in kW
- `total_capacity`: total wind farm capacity in kW
- `annual_energy`: total annual energy production in kWh/year

## Wind Resource Data Format
The model automatically formats wind resource data from the H2I wind resource database into the format required by PySAM Windpower module. The data includes:
- Ambient temperature in degrees Celsius
- Atmospheric pressure in atmospheres
- Wind speed in meters per second (m/s)
- Wind direction in degrees east of north

The model handles interpolation between available resource heights to match the specified hub height and uses the closest available data when exact matches are not available.

## Turbine file preprocessing
The `h2integrate.preprocess.wind_turbine_file_tools` module can create turbine files from the
[turbine-models](https://github.com/NatLabRockies/turbine-models) library, so you do not have to
write them by hand:

- `export_turbine_to_pysam_format(turbine_name)` writes a PySAM options turbine YAML file (named `pysam_options_{turbine_name}.yaml` by default) to the H2I library folder, or to `output_folder`
if given. Use its path as the `pysam_options` turbine configuration input for this model.

See [Turbine Models Library Pre-Processing](../misc_resources/turbine_models_library_preprocessing.md)
for a worked example that exports a turbine, updates the `tech_config`, and runs [Example 26](https://github.com/NatLabRockies/H2Integrate/tree/develop/examples/26_floris).
