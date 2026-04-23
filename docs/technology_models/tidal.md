(tidal_performance)=
# Tidal Models

## PySAM Tidal Performance Model

The **PySAM Tidal Performance Model** simulates electricity generation from **tidal current energy devices** using a time-series tidal velocity resource. The model wraps the [PySAM MhkTidal module](https://nrel-pysam.readthedocs.io/en/main/modules/MhkTidal.html) implementation of the tidal performance model used in the [System Advisor Model (SAM)](https://sam.nlr.gov/).

This component integrates the PySAM **MhkTidal** module into an **OpenMDAO-compatible performance model**, allowing it to be used within hybrid energy system simulations. To use this model, specify `"PYSAMTidalPerformanceModel"` as the performance model.

The model converts a **tidal velocity resource time series** and **device power curve** into:
- time-series electricity generation
- annual energy production
- system capacity factor

### Model Overview

The model represents an array of tidal energy devices operating in a tidal current resource. Electricity production is calculated by mapping the instantaneous tidal velocity to the device power curve, scaling by the number of devices, and integrating over time.

Key capabilities include:
- Time-series tidal resource simulation
- Device-array scaling
- Custom tidal power curves
- Optional automatic power curve scaling to match device rating
- Integration with hybrid energy system simulations

(pysam-options)=
#### PySAM Options
A user can specify any of the attributes available within the [MhkTidal module](https://nrel-pysam.readthedocs.io/en/main/modules/MhkTidal.html). They can do this using the `pysam_options` dictionary in the when setting up the `PySAMTidalPerformanceModel`.

The top-level keys of the dictionary correspond to the Groups available in the [MhkTidal module](https://nrel-pysam.readthedocs.io/en/main/modules/MhkTidal.html). The next level is the individual attributes a user could set and a full list is available through the PySAM documentation of MhkTidal module.

#### Power Curve Scaling

If `run_recalculate_power_curve=True`, the model rescales the power curve to match the specified device rating. The power curve will be internally scaled based on the new device rating so if the original tidal device rating is updated to a different rating, the model can use the original power curve and scale it if a new power curve is not available.

Scaling is performed using:

$$P_{\text{scaled}}(v) =
P_{\text{original}}(v)
\times
\frac{\text{device_rating}}{P_{\text{rated, original}}}$$

where:

- $P_{\text{original}}(v)$ is the original power curve value at velocity \(v\)
- $P_{\text{rated, original}}$ is the maximum value of the original power curve
- `device_rating` is the rated power of the device specified in the configuration


This allows a generic power curve to be adapted to different device ratings.
