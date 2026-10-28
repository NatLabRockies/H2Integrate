(pysam-battery-performance)=
# PySAM Battery Model

The PySAM battery model in H2Integrate is a wrapper that integrates the NLR PySAM `BatteryStateful` model into
an OpenMDAO component. For full documentation see the [PySAM battery model documentation](https://nrel-pysam.readthedocs.io/en/main/modules/BatteryStateful.html).

The registered model is
{py:class}`~h2integrate.storage.battery.pysam_battery.PySAMBatteryPerformanceModel`, configured by
{py:class}`~h2integrate.storage.battery.pysam_battery.PySAMBatteryPerformanceModelConfig`. Its
configuration is shown below. It supports one-hour time steps.
Inputs include `electricity_in`, `storage_capacity`, `max_charge_rate`, and the applicable
storage control inputs; see the {ref}`common storage outputs <storage-performance-outputs>` for
flow, state-of-charge, and aggregate outputs. If capacity or charge rate is nonpositive, the
model reports zero flow and retains the configured initial SOC.

```{eval-rst}
.. autoclass:: h2integrate.storage.battery.pysam_battery.PySAMBatteryPerformanceModelConfig
   :members:
   :no-index:
```

The PySAM battery model simulates the response of the battery to control commands. However, the control commands may not be strictly followed. Specifically, the SOC bounds have been seen to be exceeded by nearly 4% SOC for the upper bound and close to 1% SOC on the lower bound.

To use the pysam battery model, specify `"PySAMBatteryPerformanceModel"` as the performance model. The PySAM battery wrapper is designed to be used with the [pyomo control framework](pyomo-control). If the [open-loop control framework](open-loop-control) is used with the pysam battery, the pysam battery will not respect the commands and the battery output will be ignored by the controller.

Additional PySAM `BatteryStateful` settings can be supplied under `performance_parameters.pysam_options`, grouped by their PySAM group names:

```yaml
model_inputs:
  performance_parameters:
    chemistry: LFPGraphite
    pysam_options:
      ParamsCell:
        calendar_a: 0.004
```

The dictionary is optional; leaving it out retains the existing PySAM defaults. Options are applied after battery sizing and before the PySAM model is set up. Sizing, charge and discharge controls, timestep, SOC bounds, and the existing `Cp`, `battery_h`, and `resistance` configuration fields remain managed by the battery wrapper and cannot be set in `pysam_options`. See the [PySAM BatteryStateful inputs](https://nrel-pysam.readthedocs.io/en/main/modules/BatteryStateful.html) for supported group and parameter names.
