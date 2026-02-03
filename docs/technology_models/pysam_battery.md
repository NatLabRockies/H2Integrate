# PySAM Battery Model

The PySAM battery model in H2Integrate is a wrapper that integrates the NREL PySAM `BatteryStateful` model into
an OpenMDAO component. For full documentation see the [PySAM battery model documentation](https://nrel-pysam.readthedocs.io/en/main/modules/BatteryStateful.html).

The PySAM battery model simulates the response of the battery to control commands. However, the control commands may not be strictly followed. Specifically, the SOC bounds have been seen to be exceeded by nearly 4% SOC for the upper bound and close to 1% SOC on the lower bound.

To use the pysam battery model, specify `"PySAMBatteryPerformanceModel"` as the performance model. The PySAM battery wrapper is designed to be used with the [pyomo control framework](pyomo-control). If the [open-loop control framework](open-loop-control) is used with the pysam battery, the pysam battery will not respect the commands and the battery output will be ignored by the controller.
