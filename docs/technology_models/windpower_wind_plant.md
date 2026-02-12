# Wind Plant model using Windpower module in PySAM

This model uses the [Windpower module](https://nrel-pysam.readthedocs.io/en/main/modules/Windpower.html) available in PySAM to simulate the performance of a wind power plant.

To use this model, specify `"PYSAMWindPlantPerformanceModel"` as the performance model. An example of how this may look in the `tech_config` file is shown below and details on the performance parameter inputs can be found [here](#performance-parameters).

```yaml
technologies:
  wind:
     performance_model: "PYSAMWindPlantPerformanceModel"
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

(performance-parameters)=
## Performance Parameters
- `num_turbines` (required): number of wind turbines in the wind farm
- `hub_height` (required): wind turbine hub height in meters
- `rotor_diameter` (required): wind turbine rotor diameter in meters
- `turbine_rating_kw` (required): rated power of individual wind turbine in kW
- `create_model_from`: this can either be set to `"new"` or `"default"` and defaults to `"new"`. If `create_model_from` is `"new"`, the wind model is initialized using `Windpower.new()` and *populated* with parameters specified in `pysam_options`. If `create_model_from` is `"default"`, the wind model is initialized using `Windpower.default(config_name)` (`config_name` is also an input parameter) then *updated* with parameters specified in `pysam_options`.
- `config_name`: this is only used if `create_model_from` is `"default"`. The default value for this is `"WindPowerSingleOwner"`. The available options and their default parameters are listed below:
    - [WindPowerAllEquityPartnershipFlip](https://github.com/NREL/SAM/blob/develop/api/api_autogen/library/defaults/Windpower_WindPowerAllEquityPartnershipFlip.json)
    - [WindPowerCommercial](https://github.com/NREL/SAM/blob/develop/api/api_autogen/library/defaults/Windpower_WindPowerCommercial.json)
    - [WindPowerLeveragedPartnershipFlip](https://github.com/NREL/SAM/blob/develop/api/api_autogen/library/defaults/Windpower_WindPowerLeveragedPartnershipFlip.json)
    - [WindPowerMerchantPlant](https://github.com/NREL/SAM/blob/develop/api/api_autogen/library/defaults/Windpower_WindPowerMerchantPlant.json)
    - [WindPowerNone](https://github.com/NREL/SAM/blob/develop/api/api_autogen/library/defaults/Windpower_WindPowerNone.json)
    - [WindPowerResidential](https://github.com/NREL/SAM/blob/develop/api/api_autogen/library/defaults/Windpower_WindPowerResidential.json)
    - [WindPowerSaleLeaseback](https://github.com/NREL/SAM/blob/develop/api/api_autogen/library/defaults/Windpower_WindPowerSaleLeaseback.json)
    - [WindPowerSingleOwner](https://github.com/NREL/SAM/blob/develop/api/api_autogen/library/defaults/Windpower_WindPowerSingleOwner.json)
- `run_recalculate_power_curve` (optional): Flag whether to recalculate the wind turbine
        power curve. defaults to True.

(layout-parameters)=
## Layout Parameters
- `layout` (dict): configuration for wind turbine layout within the wind farm
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

(powercurve-calc-parameters)=
## Power Curve Calculation Parameters
The `powercurve_calc_config` section allows customization of the turbine power curve calculation:

- `elevation` (float): elevation in meters. Required if using Weibull resource model, otherwise should be zero. Defaults to 0.
- `wind_default_max_cp` (float): maximum power coefficient. Defaults to 0.45.
- `wind_default_max_tip_speed` (float): maximum tip speed in m/s. Defaults to 60.
- `wind_default_max_tip_speed_ratio` (float): maximum tip-speed ratio. Defaults to 8.
- `wind_default_cut_in_speed` (float): cut-in wind speed in m/s. Defaults to 4.
- `wind_default_cut_out_speed` (float): cut-out wind speed in m/s. Defaults to 25.
- `wind_default_drive_train` (int): integer representing wind turbine drive train type. Defaults to 0. The mapping is:
    - 0: 3 Stage Planetary
    - 1: Single Stage - Low Speed Generator
    - 2: Multi-Generator
    - 3: Direct Drive

(pysam-options)=
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
