
# Model Overview
Currently, H2I recognizes four types of models:

- [Resource](#resource)
- [Converter](#converters)
- [Transport](#transport)
- [Storage](#storage)
- [Controllers](#controller)

(resource)=
## Resource
`Resource` models process resource data that is usually passed to a technology model.

| Resource name     | Resource Type  |
| :---------------- | :---------------: |
| `river_resource`  | river resource |
| `wind_toolkit_v2_api` | wind resource |
| `openmeteo_wind_api` | wind resource |
| `goes_aggregated_solar_v4_api` | solar resource |
| `goes_conus_solar_v4_api` | solar resource |
| `goes_fulldisc_solar_v4_api` | solar resource |
| `goes_tmy_solar_v4_api` | solar resource |
| `meteosat_solar_v4_api` | solar resource |
| `meteosat_tmy_solar_v4_api` | solar resource |
| `himawari7_solar_v3_api` | solar resource |
| `himawari8_solar_v3_api` | solar resource |
| `himawari_tmy_solar_v3_api` | solar resource |


(converters)=
## Converters
`Converter` models are technologies that:
- converts energy available in the 'Primary Input' to another form of energy ('Primary Commodity') OR
- consumes the 'Primary Input' (and perhaps secondary inputs or feedstocks), which is converted to the 'Primary Commodity' through some process

The inputs, outputs, and corresponding technology that are currently available in H2I are listed below:

| Technology name   | Primary Commodity | Primary Input(s) |
| :---------------- | :-----------: | ------------: |
| `wind`           |  electricity  | wind resource |
| `solar`          |  electricity  | solar resource |
| `river`          |  electricity  | river resource |
| `hopp`           |  electricity  | N/A |
| `electrolyzer`   |  hydrogen     | electricity |
| `geoh2`          |  hydrogen     | rock type |
| `steel`          |  steel        | iron ore |
| `ammonia`        |  ammonia      | nitrogen, hydrogen |
| `doc`   |  co2     | electricity |
| `oae`   |  co2     | electricity |
| `methanol`   |  methanol     | ??? |
| `air_separator`   |  nitrogen     | electricity |
| `desal`   |  water     | electricity |
| `natural_gas`   |  electricity     | natural gas |

```{note}
When the Primary Commodity is electricity, those converters are considered electricity producing technologies and their electricity production is summed for financial calculations.
```

(transport)=
## Transport
`Transport` models are used to either:
- connect the 'Transport Commodity' from a technology that produces the 'Transport Commodity' to a technology that consumes or stores the 'Transport Commodity' OR
- combine multiple input streams of the 'Transport Commodity' into a single stream
- split a single input stream of the 'Transport Commodity' into multiple output streams



| Technology        | Transport Commodity |
| :---------------- | :---------------: |
| `cable`         |  electricity      |
| `pipe`      |  most mass-based commodities         |
| `combiner`      | Any    |
| `splitter` |  Any|

Connection: `[source_tech, dest_tech, transport_commodity, transport_technology]`

(storage)=
## Storage
`Storage` technologies input and output the 'Storage Commodity' at different times. These technologies can be filled or charged, then unfilled or discharged at some later time. These models are usually constrained by two key model parameters: storage capacity and charge/discharge rate.

| Technology        | Storage Commodity |
| :---------------- | :---------------: |
| `h2_storage`      |  hydrogen         |
| `battery`         |  electricity      |
| `generic_storage` |  Any              |

(control)=
## Control
`Control` models are used to control the `Storage` models and resource flows.

| Controller        | Control Method |
| :----------------------------- | :---------------: |
| `pass_through_controller`      |  open-loop control. directly passes the input resource flow to the output without any modifications         |
| `demand_open_loop_storage_controller`  |  open-loop control. manages resource flow based on demand and storage constraints     |
| `demand_open_loop_converter_controller`  |  open-loop control. manages resource flow based on demand constraints     |
| `flexible_demand_open_loop_converter_controller`  |  open-loop control. manages resource flow based on demand and flexibility constraints     |
| `heuristic_load_following_controller` | open-loop control that works on a time window basis to set dispatch commands. Uses pyomo |

# Technology Models Overview

Below summarizes the available performance, cost, and financial models for each model type. The list of supported models is also available in [supported_models.py](../../h2integrate/core/supported_models.py)
- [Resource](#resource-models)
- [Converters](#converter-models)
- [Transport](#transport-models)
- [Storage](#storage-models)
- [Basic Operations](#basic-operations)
- [Control](#control-models)

(resource-models)=
## Resource models
- `river`:
    - resource models:
        + `river_resource`
- `wind_resource`:
    - resource models:
        + `wind_toolkit_v2_api`
        + `openmeteo_wind_api`
- `solar_resource`:
    - resource models:
        + `goes_aggregated_solar_v4_api`
        + `goes_conus_solar_v4_api`
        + `goes_fulldisc_solar_v4_api`
        + `goes_tmy_solar_v4_api`
        + `meteosat_solar_v4_api`
        + `meteosat_tmy_solar_v4_api`
        + `himawari7_solar_v3_api`
        + `himawari8_solar_v3_api`
        + `himawari_tmy_solar_v3_api`

(converter-models)=
## Converter models
- `wind`: wind turbine
    - performance models:
        + `'pysam_wind_plant_performance'`
        + `'floris_wind_plant_performance'`
    - cost models:
        + `'atb_wind_cost'`
- `solar`: solar-PV panels
    - performance models:
        + `'pysam_solar_plant_performance'`
    - cost models:
        + `'atb_utility_pv_cost'`
        + `'atb_comm_res_pv_cost'`
- `river`: hydropower
    - performance models:
        + `'run_of_river_hydro_performance'`
    - cost models:
        + `'run_of_river_hydro_cost'`
- `hopp`: hybrid plant
    - combined performance and cost model:
        + `'hopp'`
- `electrolyzer`: hydrogen electrolysis
    - combined performance and cost:
        + `'wombat'`
    - performance models:
        + `'eco_pem_electrolyzer_performance'`
    - cost models:
        + `'singlitico_electrolyzer_cost'`
        + `'basic_electrolyzer_cost'`
- `geoh2_well_subsurface`: geologic hydrogen well subsurface
    - performance models:
        + `'simple_natural_geoh2_performance'`
        + `'templeton_serpentinization_geoh2_performance'`
    - cost models:
        + `'mathur_modified_geoh2_cost'`
- `steel`: steel production
    - performance models:
        + `'steel_performance'`
        + `'ng_eaf_performance_rosner'`
        + `'h2_eaf_performance_rosner'`
    - combined cost and financial models:
        + `'steel_cost'`
    - cost models:
        + `'ng_eaf_cost_rosner'`
        + `'h2_eaf_cost_rosner'`
- `ammonia`: ammonia synthesis
    - performance models:
        + `'simple_ammonia_performance'`
        + `'synloop_ammonia_performance'`
    - cost models:
        + `'simple_ammonia_cost'`
        + `'synloop_ammonia_cost'`
- `doc`: direct ocean capture
    - performance models:
        + `'direct_ocean_capture_performance'`
    - cost models:
        + `'direct_ocean_capture_cost'`
- `oae`: ocean alkalinity enhancement
    - performance models:
        + `'ocean_alkalinity_enhancement_performance'`
    - cost models:
        + `'ocean_alkalinity_enhancement_cost'`
    - financial models:
        + `'ocean_alkalinity_enhancement_cost_financial'`
- `methanol`: methanol synthesis
    - performance models:
        + `'smr_methanol_plant_performance'`
    - cost models:
        + `'smr_methanol_plant_cost'`
    - financial models:
        + `'methanol_plant_financial'`
- `air_separator`: nitrogen separation from air
    - performance models:
        + `'simple_ASU_performance'`
    - cost models:
        + `'simple_ASU_cost'`
- `desal`: water desalination
    - performance models:
        + `'reverse_osmosis_desalination_performance'`
    - cost models:
        + `'reverse_osmosis_desalination_cost'`
- `natural_gas`: natural gas combined cycle and combustion turbine
    - performance models:
        + `'natural_gas_performance'`
    - cost_models:
        + `'natural_gas_cost'`
- `grid`: electricity grid connection
    - performance models:
        + `'grid_performance'`
    - cost models:
        + `'grid_cost'`
- `iron_ore`: iron ore mining and refining
    - performance models:
        + `'iron_mine_performance_martin'`
    - cost models:
        + `'iron_mine_cost_martin'`
- `iron_dri`: direct reduced iron
    - performance models:
        + `'ng_dri_performance_rosner'`
        + `'h2_dri_performance_rosner'`
    - cost models:
        + `'ng_dri_cost_rosner'`
        + `'h2_dri_cost_rosner'`
- `iron_ewin`: iron electrowinning
    - performance models:
        + `'humbert_electrowinning_performance'`
    - cost models:
        + `'humbert_stinn_electrowinning_cost'`

(transport-models)=
## Transport Models
- `cable`
    - performance models:
        + `'cable'`: specific to `electricity` commodity
- `pipe`:
    - performance models:
        + `'pipe'`: currently compatible with the commodities "hydrogen", "co2", "methanol", "ammonia", "nitrogen", "natural_gas", "pig_iron", "reformer_catalyst", "water", "carbon", "iron_ore", and "lime"
- `combiner`:
    - performance models:
        + `'combiner_performance'`: can be used for any commodity
- `splitter`:
    - performance models:
        + `'splitter_performance'`: can be used for any commodity

(storage-models)=
## Storage Models
- `h2_storage`: hydrogen storage
    - performance models:
        + `'hydrogen_tank_performance'`
    - cost models:
        + `'hydrogen_tank_cost'`
        + `'lined_rock_cavern_h2_storage_cost'`
        + `'salt_cavern_h2_storage_cost'`
        + `'mch_tol_h2_storage_cost'`
        + `'buried_pipe_h2_storage_cost'`
- `generic_storage`: any resource storage
    - performance models:
        + `'simple_generic_storage'`
        + `'storage_auto_sizing'`
    - cost models:
        + `'generic_storage_cost'`
- `battery`: battery storage
    - performance models:
        + `'pysam_battery'`
    - cost models:
        + `'atb_battery_cost'`

(basic-operations)=
## Basic Operations
- `production_summer`: sums the production profile of any commodity
- `consumption_summer`: sums the consumption profile of any feedstock


(control-models)=
## Control Models
- `'pass_through_controller'`
- Storage Controllers:
    - `'demand_open_loop_storage_controller'`
    - `'heuristic_load_following_controller'`
- Converter Controllers:
    - `'demand_open_loop_converter_controller`
    - `'flexible_demand_open_loop_converter_controller'`
