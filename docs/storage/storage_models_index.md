# Storage Models

Storage technologies input and output the 'Storage Commodity' (`commodity`) as a time series. These technologies can be both filled or charged and unfilled or discharged, resulting in a commodity stream that can be positive and negative.These models are usually constrained by two key model parameters: storage capacity and charge/discharge rate.

## Storage Performance Models

H2I currently supports the following storage performance models:
- [`StoragePerformanceModel`](#simple-generic-storage-performance)
- [`PySAMBatteryPerformanceModel`](#pysam-battery-performance)
- `StorageAutoSizingModel`

The following sections detail the inputs and outputs of the storage performance models.

### Automatic storage sizing

`StorageAutoSizingModel` calculates the storage capacity and charge/discharge rate required to
balance a commodity production profile against demand, then simulates the storage operation. Set
`set_demand_as_avg_commodity_in: true` to use average input as demand, or set it to `false` and
provide `demand_profile`. The model requires either `round_trip_efficiency`, or both
`charge_efficiency` and `discharge_efficiency`. `min_soc_fraction` and `max_soc_fraction` bound the
usable state of charge. It supports one-hour time steps.

```{eval-rst}
.. autoclass:: h2integrate.storage.simple_storage_auto_sizing.StorageSizingModelConfig
    :members:
    :no-index:
```

```{note}
The inputs and outputs of storage performance models are generalized here for any commodity. If input and output names include the word `commodity`, the actual variable name would be the commodity defined for that storage model. For example, the `PySAMBatteryPerformanceModel` can only be used for the commodity  `electricity`. Therefore, the `commodity_in` input to the `PySAMBatteryPerformanceModel` is actually named `electricity_in`.
```

### Inputs
- `commodity_in`: commodity available to use for charging storage

If using a **feedback control strategy** (this means that the controller received the actual storage state periodically), the control-related inputs for control to the storage performance include:
- `commodity_set_point`: the target set-point profile to satisfy with the storage performance model and the input commodity. This is passed to the control strategy through the `pyomo_dispatch_solver` method.
- `pyomo_dispatch_solver`: the control function from the storage controller that outputs dispatch commands to the storage performance model.

If using an **open-loop control strategy**, the control input to the storage performance model is:
- `commodity_command_value`: the dispatch commands to the storage performance model, negative values indicate charge commands and positive values indicate discharge commands

Some storage models may also have design inputs of `max_charge_rate`, `storage_capacity`, and `max_discharge_rate`.

### Calculations and Outputs
The storage performance models output timeseries profiles (length of `n_timesteps`):
- `commodity_out`: storage charge and discharge profile in `commodity_rate_units`, values are negative when charging and positive when discharging. This is equivalent to `storage_commodity_charge + storage_commodity_discharge`
- `storage_commodity_charge`: charge profile the storage, the values are either negative (when charging) or 0 (when doing nothing or discharging). In units of `commodity_rate_units`
- `storage_commodity_discharge`: discharge profile the storage, the values are either positive (when discharging) or 0 (when doing nothing or charging). In units of `commodity_rate_units`
- `SOC`: the storage state-of-charge in units of either `percent` (values between 0 and 100) or `unitless` (values between 0 and 1)

The aggregated or summarized performance outputs are (single values):
- `storage_duration`: the storage capacity divided by the storage discharge rate. Units are time-based, such as `h` (hours).
- `rated_commodity_production`: the storage discharge rate in units of `commodity_rate_units`.
- `total_commodity_produced`: the summation of `commodity_out` over the simulation in units of `commodity_amount_units`. This value may be negative if the storage charges more than discharges.

The results that are output per-year of the `plant_life` are:
- `annual_commodity_produced`: each value is the `total_commodity_produced` scaled to a 1-year (8760 hours) simulation. This value may be negative if the storage charges more than discharges.
- `capacity_factor`: the storage capacity factor which is calculated in the same way that capacity factors are calculated in converter technologies, which is a ratio of the sum of *`total_commodity_produced`* to the discharge rate (or `rated_commodity_production`). This value may be negative if the storage charges more than discharges.
    $
    CF = \frac{\sum_{t=0}^{n_{\text{timesteps}}}(\text{commodity_out}_t*dt)}{\text{\text{discharge}\_\text{rate}*n_{\text{timesteps}}*dt}
    $
- `standard_capacity_factor`: the storage capacity factor as defined by the [NLR ATB](https://atb.nlr.gov/electricity/2024b/utility-scale_battery_storage). The ratio of the total *commodity discharged* to the discharge rate (or `rated_commodity_production`). This value will always be greater than or equal to zero.
    $
    CF_{\text{standard}} = \frac{\sum_{t=0}^{n_{\text{timesteps}}}(\text{storage_commodity_discharge}_t*dt)}{\text{discharge_rate}*n_{\text{timesteps}}*dt}
    $


## Storage Cost models:

The available storage cost models are:
- `ATBBatteryCostModel`
- `GenericStorageCostModel`
- [Hydrogen storage cost models](#h2-storage-cost):
    - `LinedRockCavernStorageCostModel`
    - `SaltCavernStorageCostModel`
    - `PipeStorageCostModel`
    - `MCHTOLStorageCostModel`

    ### ATB battery cost model

    `ATBBatteryCostModel` uses separate energy and power capital costs from the NLR Annual Technology
    Baseline battery workbook. It derives storage duration from capacity and charge rate, calculates
    CapEx from the energy and power cost inputs, and calculates annual OpEx as a fraction of CapEx.
    `commodity_rate_units` must be a power unit based on watts; the default amount unit is the rate unit
    multiplied by hours.

    ```{eval-rst}
    .. autoclass:: h2integrate.storage.battery.atb_battery_cost.ATBBatteryCostConfig
        :members:
        :no-index:
    ```
