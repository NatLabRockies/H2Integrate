(wave_performance)=
# Wave Energy Models

## PySAM Wave Performance Model

The **PySAM Wave Performance Model** simulates electricity generation from **wave energy converter (WEC) devices** using a timeseries wave resource. The model wraps the [PySAM MhkWave module](https://nrel-pysam.readthedocs.io/en/main/modules/MhkWave.html) implementation of the wave energy performance model used in the [System Advisor Model (SAM)](https://sam.nlr.gov/).

This component integrates the PySAM **MhkWave** module into an H2I performance model. To use this model, specify `"PySAMWavePerformanceModel"` as the performance model.

The model converts a wave resource timeseries (significant wave height and energy period) and a device power matrix into:
- timeseries electricity generation
- total energy production over the simulation period
- annualized energy production
- system capacity factor

### Model Overview

The model represents an array of wave energy converters operating in an ocean wave resource. Electricity production is calculated at each timestep by looking up device power output in the wave power matrix using the instantaneous significant wave height (Hs) and energy period (Te), then scaling by the number of devices.

The model operates in timeseries mode (`wave_resource_model_choice = 1`) and requires hourly Hs and Te arrays. Use the {ref}`wave_resource` component to read and interpolate wave data files to the required hourly resolution.

(pysam-options-wave)=
#### PySAM Options

A user can specify any of the attributes available within the [MhkWave module](https://nrel-pysam.readthedocs.io/en/main/modules/MhkWave.html) using the `pysam_options` dictionary. The top-level keys correspond to the variable groups in the MhkWave module.

The most common use is to override the default loss parameters:

```yaml
pysam_options:
  MHKWave:
    loss_array_spacing: 0.0       # array-spacing loss [%]
    loss_resource_overprediction: 0.0  # resource overprediction loss [%]
    loss_transmission: 2.0        # transmission loss [%]
    loss_downtime: 5.0            # availability loss [%]
    loss_additional: 0.0          # additional loss [%]
```

By default all losses are set to zero. Override via `pysam_options` to model realistic system availability.

#### Wave Power Matrix

The `wave_power_matrix` is a 2-D lookup table of device power output [kW] as a function of significant wave height Hs [m] and energy period Te [s]. It must be provided as a list of rows:

- Row 0: Te bin centers [s] (header row; first element is 0.0)
- Rows 1+: Each row starts with the Hs bin center [m], followed by the device power output [kW] at each Te bin

Example (3-row excerpt):

```yaml
wave_power_matrix:
  - [0.0,  0.5,  1.5,  2.5,  3.5,  4.5,  5.5,  6.5,  7.5,  8.5,  9.5]
  - [0.25, 0.0,  0.0,  0.0,  0.0,  0.4,  0.6,  0.8,  1.0,  1.1,  1.1]
  - [0.75, 0.0,  0.0,  0.0,  0.0,  3.2,  5.3,  7.4,  9.1,  9.8,  9.5]
```

The power matrix format follows the SAM convention and can be exported from SAM for any supported reference model.
