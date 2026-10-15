# Data Center Models

H2Integrate includes two data center model pairs, implemented in
{mod}`h2integrate.converters.data_center`. Both produce a `compute_load` commodity (in MW)
and calculate the electricity and water the data center consumes to serve a compute
load profile. An example that runs both model pairs with an hourly AI training workload
is provided in `examples/38_data_center/`.

| Model | Type | Description |
| --- | --- | --- |
| `DataCenterPerformanceModel` | Performance | Electricity demand from a compute electrical efficiency and a cooling load ratio |
| `DataCenterCostModel` | Cost | CapEx, fixed OpEx, and variable OpEx per MWh of compute load |
| `DataCenterPUEWUEPerformanceModel` | Performance | Electricity and water demand from Power Usage Effectiveness (PUE) and Water Usage Effectiveness (WUE) |
| `DataCenterPUEWUECostModel` | Cost | CapEx, fixed OpEx, and electricity and water costs |

## Simple Data Center Model

### Performance

`DataCenterPerformanceModel` caps the compute load demand (`compute_load_demand`) at the
data center capacity (`system_capacity_mw`). The total electricity demand is the compute
load scaled by the compute electrical efficiency, plus a cooling load proportional to the
electrical compute load:

```{math}
P_{\text{elec}} = \frac{P_{\text{compute}}}{\eta_{\text{compute}}} \left(1 + r_{\text{cooling}}\right)
```

where $\eta_{\text{compute}}$ is `compute_electrical_efficiency` and $r_{\text{cooling}}$ is
`cooling_load_ratio`. Water demand is the compute load multiplied by
`water_use_gal_per_mwh`, limited by the available `water_in`.

Any electricity demand that is not met by `electricity_in` is reported as
`unmet_electricity_demand_out`, which can be connected to a grid model's
`electricity_set_point` to purchase the required electricity.

### Cost

`DataCenterCostModel` calculates:

- CapEx: `capex_per_mw` $\times$ `system_capacity_mw`
- Fixed OpEx: `fixed_opex_per_mw_per_year` $\times$ `system_capacity_mw`
- Variable OpEx: `variable_opex_per_mwh` $\times$ total compute load (MWh)

## PUE/WUE Data Center Model

### Performance

`DataCenterPUEWUEPerformanceModel` uses industry-standard efficiency metrics to determine
facility power and water use from a compute IT workload (`compute_it_workload`):

```{math}
P_{\text{facility}} = P_{\text{IT}} \times \text{PUE}
```

```{math}
\dot{V}_{\text{water}} = E_{\text{IT}} \times \text{WUE}
```

where PUE is the ratio of total facility power to IT equipment power, and WUE is the water
consumed in liters per kWh of IT energy.

PUE and WUE can be provided in one of three ways:

1. **Directly**: supply both `pue` and `wue`.
2. **By climate zone**: supply an IECC `climate_zone` (for example, `"4A"`), and PUE/WUE
   are looked up from the climate- and technology-specific estimates of
   Lei and Masanet (2022) [^lei2022].
3. **By site location**: supply none of the above, and the IECC climate zone is determined
   from the site `latitude` and `longitude` in the plant configuration using the
   [`eeweather`](https://github.com/openeemeter/eeweather) package.

For options 2 and 3, `efficiency_level` selects the 5th-percentile (`"efficient"`) or
95th-percentile (`"inefficient"`) estimates. The cooling configuration can be set with
`cooling_configuration`:

| Case | Size category | Cooling configuration |
| --- | --- | --- |
| 1 | Large-scale | Airside economizer + adiabatic cooling + (water-cooled chiller) |
| 2 | Large-scale | Waterside economizer + (water-cooled chiller) |
| 3 | Midsize | Airside economizer + (water-cooled chiller) |
| 4 | Midsize | Waterside economizer + (water-cooled chiller) |
| 5 | Midsize | Water-cooled chiller |
| 6 | Midsize | Airside economizer + (air-cooled chiller) |
| 7 | Midsize | Air-cooled chiller |
| 8 | Small | Water-cooled chiller |
| 9 | Small | Air-cooled chiller |
| 10 | Small | Direct expansion system |
| 11 | Large-scale or midsize | Direct-to-chip liquid loop + dry cooling + adiabatic cooling + (air-cooled chiller) |
| 12 | Large-scale or midsize | Direct-to-chip liquid loop + waterside economizer + (water-cooled chiller) |

If `cooling_configuration` is not set, the configuration with the lowest PUE (or lowest WUE
when `optimize_for: wue`) is selected automatically. Providing `size_sqft` restricts the
automatic selection to configurations valid for that size category: large-scale
(> 20,000 sqft), midsize (1,000 - 20,000 sqft), or small (< 1,000 sqft).

Unmet electricity and water demands are reported as `unmet_electricity_demand` and
`unmet_water_demand`.

### Cost

`DataCenterPUEWUECostModel` calculates:

- CapEx: `capex_per_mw` $\times$ `system_capacity_mw`
- Fixed OpEx: `fixed_opex_per_mw_per_year` $\times$ `system_capacity_mw`
- Electricity cost: `electricity_rate` $\times$ total facility energy (kWh)
- Water cost: `water_rate` $\times$ total water consumed (gal)

If electricity and water are purchased through separate technologies (for example, a grid
model and a water feedstock), set `electricity_rate` and `water_rate` to zero to avoid
counting those costs twice.

[^lei2022]: Lei, N., and Masanet, E. "Climate- and technology-specific PUE and WUE
estimations for U.S. data centers using a hybrid statistical and thermodynamics-based
approach." *Resources, Conservation and Recycling* 182 (2022): 106323.
