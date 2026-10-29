
# Solar-PV model using Pvwattsv8 module in PySAM

This model uses the [Pvwattsv8 module](https://nrel-pysam.readthedocs.io/en/main/modules/Pvwattsv8.html) available in PySAM to simulate the performance of a solar-PV system.

To use this model, specify `"PYSAMSolarPlantPerformanceModel"` as the performance model. An example of how this may look in the `tech_config` file is shown below and details on the performance parameter inputs can be found [here](#performance-parameters).
See {py:class}`~h2integrate.converters.solar.solar_pysam.PYSAMSolarPlantPerformanceModel` and
{py:class}`~h2integrate.converters.solar.solar_pysam.PYSAMSolarPlantPerformanceModelConfig`.

The model receives the discrete `solar_resource_data` dictionary, `system_capacity_DC`, and
`dc_ac_ratio`, plus `tilt_angle` or `azimuth_angle` inputs when the respective setting is
`input`. It reports AC capacity, the electricity profile and production summaries. It supports
one-hour time steps. See [solar cost models](atb_costs_pv.md) for capacity-based cost options.

```yaml
technologies:
    pv:
        performance_model:
            model: "PYSAMSolarPlantPerformanceModel"
        model_inputs:
            performance_parameters:
                pv_capacity_kWdc: 1000.0
                dc_ac_ratio: 1.3
                create_model_from: "new" #"options are "default" and "new"
                tilt: #panel tilt angle to use if tilt_angle_setting is "input"
                tilt_angle_setting: "lat-func" #options are "lat-func", "lat", "input"
                config_name: #only used if create_model_from is "default"
                pysam_options: #user specified pysam inputs
                    SystemDesign:
                        array_type: 2
                        azimuth: 180
                        losses: 10.0
                    SolarResource:
                    Lifetime:
                    AdjustmentFactors:

```

(performance-parameters)=
## Performance Parameters
The configuration reference is generated from the class used by the model:

```{eval-rst}
.. autoclass:: h2integrate.converters.solar.solar_pysam.PYSAMSolarPlantPerformanceModelConfig
   :no-members:
   :no-index:
```

The DC-to-AC ratio converts PV capacity to inverter-rated AC power:

$$
\text{PV Capacity (kW-AC)} = \frac{\text{PV Capacity (kW-DC)}}{\text{dc_ac_ratio}}
$$

When tilt is determined by latitude, the `lat-func` mode uses:

$$
\theta =
\begin{cases}
    \text{lat} \cdot 0.87 & \text{if } \text{lat} \leq 25^\circ \\
    3.1 + \text{lat} \cdot 0.76 & \text{if } 25^\circ < \text{lat} \leq 50^\circ \\
    \text{lat} & \text{if } 50^\circ < \text{lat} \\
\end{cases}
$$

The latitude-based azimuth points north for negative latitudes and south for positive latitudes.
For available PySAM defaults, see the
[SAM defaults directory](https://github.com/NatLabRockies/SAM/tree/develop/api/api_autogen/library/defaults).

- `pysam_options` (dict): The top-level keys correspond to the Groups available in the [Pvwattsv8 module](https://nrel-pysam.readthedocs.io/en/main/modules/Pvwattsv8.html). The next level is the individual attributes a user could set and a full list is available through the PySAM documentation of Pvwattsv8 module. The Groups that users may want to specify specific options for are the:
    - [SystemDesign](#systemdesign-group)
    - [SolarResource](#solarresource-group)
    - [Lifetime](https://nrel-pysam.readthedocs.io/en/main/modules/Pvwattsv8.html#lifetime-group)
    - [Shading](https://nrel-pysam.readthedocs.io/en/main/modules/Pvwattsv8.html#shading-group)
    - [AdjustmentFactors](https://nrel-pysam.readthedocs.io/en/main/modules/Pvwattsv8.html#adjustmentfactors-group)

(systemdesign-group)=
### SystemDesign group
```{note}
Do not include the `system_capacity` parameter of the `SystemDesign` group. The system capacity should be set in the performance parameters with the variable `pv_capacity_kWdc`.
```

Some common design parameters that a user may want to specify within the [SystemDesign Group](https://nrel-pysam.readthedocs.io/en/main/modules/Pvwattsv8.html#systemdesign-group) are:
- `array_type` (int): Required if `create_model_from = 'new'`.
    - 0: fixed open rack
    - 1: fixed roof mount
    - 2: 1-axis tracking
    - 3: 1-axis backtracking
    - 4: 2-axis tracking
- `azimuth` (float): Angle representing the direction that the panels are facing. Required if `array_type<4` and `create_model_from = 'new'`.
    - East: 90
    - South: 180 (default for most Pvwattsv8 configurations)
    - West: 270
    - North: 360
- `bifaciality` (float): bifaciliaty factor of the panel in the range (0, 0.85). Defaults to 0.0.
- `gcr` (float): ground coverage ratio in the range (0.01, 0.99). Defaults to 0.0
- `inv_eff` (float): Inverter efficiency in percent in the range (90, 99.5). Linear power conversion loss from DC to AC. Defaults to 96.
- `losses` (float): DC power losses as a percent in range (-5, 99.0). Defaults to 14.0757 in most Pvwattsv8 configurations. Required if `create_model_from = 'new'`.
- `module_type` (int):
    - 0: standard, approximate efficiency of 19%
    - 1: premium, approximate efficiency of 21%
    - 2: thin film, approximate efficiency of 18%
- `rotlim` (float): rotational limit of panel in degrees (if tracking array type) in the range (0.0, 270.0). Defaults to 45.
- `tilt` (float | None): Panel tilt angle in the range (0.0, 90.0). Required if `array_type<4` and `create_model_from = 'new'`.
    - 0: panel is horizontal
    - 90: panel is vertical

    ```{note}
    Do not specify tilt angle in the SystemDesign Group parameters if the following parameters are specified in the performance_parameters:
    - `tilt_angle_setting` is set to either "lat" or "lat-func"
    - `tilt_angle_setting` is set to "input" and `tilt` is specified under the performance parameters.

    Do not specify azimuth angle in the SystemDesign Group parameters if the following parameters are specified in the performance_parameters:
    - `azimuth_angle_setting` is set to "lat-func"
    - `azimuth_angle_setting` is set to "input" and `azimuth` is specified under the performance parameters.
    ```

(solarresource-group)=
### SolarResource group
Solar resource data is downloaded from the [National Solar Resource Database](https://developer.nlr.gov/docs/solar/nsrdb/psm3-2-2-download/) and input as the `solar_resource_data` variable in the Pvwattsv8 SolarResource Group. Some other common resource parameters that a user may want to specify within the [SolarResource Group](https://nrel-pysam.readthedocs.io/en/main/modules/Pvwattsv8.html#solarresource-group) are:
- `use_wf_albedo` (bool): if True, use albedo from weather file (if valid). If False, use value for `albedo_default`. Defaults to True.
- `albedo_default` (float). Value in range (0,1) to use as the albedo if albedo value in weather file is invalid OR if `use_wf_albedo` is set to False.
