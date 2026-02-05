
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
| `RiverResource`  | river resource |
| `WTKNRELDeveloperAPIWindResource` | wind resource |
| `OpenMeteoHistoricalWindResource` | wind resource |
| `GOESAggregatedSolarAPI` | solar resource |
| `GOESConusSolarAPI` | solar resource |
| `GOESFullDiscSolarAPI` | solar resource |
| `GOESTMYSolarAPI` | solar resource |
| `MeteosatPrimeMeridianSolarAPI` | solar resource |
| `MeteosatPrimeMeridianTMYSolarAPI` | solar resource |
| `Himawari7SolarAPI` | solar resource |
| `Himawari8SolarAPI` | solar resource |
| `HimawariTMYSolarAPI` | solar resource |


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
| `HOPPComponent`           |  electricity  | N/A |
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
| `PassThroughOpenLoopController`      |  open-loop control. directly passes the input resource flow to the output without any modifications         |
| `DemandOpenLoopStorageController`  |  open-loop control. manages resource flow based on demand and storage constraints     |
| `DemandOpenLoopConverterController`  |  open-loop control. manages resource flow based on demand constraints     |
| `FlexibleDemandOpenLoopConverterController`  |  open-loop control. manages resource flow based on demand and flexibility constraints     |
| `HeuristicLoadFollowingController` | open-loop control that works on a time window basis to set dispatch commands. Uses pyomo |

# Technology Models Overview

Below summarizes the available performance, cost, and financial models for each model type. The list of supported models is also available in [supported_models.py](../../h2integrate/core/supported_models.py)
- [Model Overview](#model-overview)
  - [Resource](#resource)
  - [Converters](#converters)
  - [Transport](#transport)
  - [Storage](#storage)
  - [Control](#control)
- [Technology Models Overview](#technology-models-overview)
  - [Resource models](#resource-models)
  - [Converter models](#converter-models)
  - [Transport Models](#transport-models)
  - [Storage Models](#storage-models)
  - [Basic Operations](#basic-operations)
  - [Control Models](#control-models)

(resource-models)=
## Resource models
- `river`:
    - resource models:
        + `RiverResource`
- `wind_resource`:
    - resource models:
        + `WTKNRELDeveloperAPIWindResource`
        + `OpenMeteoHistoricalWindResource`
- `solar_resource`:
    - resource models:
        + `GOESAggregatedSolarAPI`
        + `GOESConusSolarAPI`
        + `GOESFullDiscSolarAPI`
        + `GOESTMYSolarAPI`
        + `MeteosatPrimeMeridianSolarAPI`
        + `MeteosatPrimeMeridianTMYSolarAPI`
        + `Himawari7SolarAPI`
        + `Himawari8SolarAPI`
        + `HimawariTMYSolarAPI`

(converter-models)=
## Converter models
- `wind`: wind turbine
    - performance models:
        + `'PYSAMWindPlantPerformanceModel'`
        + `'FlorisWindPlantPerformanceModel'`
    - cost models:
        + `'ATBWindPlantCostModel'`
    - combined models:
        + `'ArdWindPlantModel'`
- `solar`: solar-PV panels
    - performance models:
        + `'PYSAMSolarPlantPerformanceModel'`
    - cost models:
        + `'ATBUtilityPVCostModel'`
        + `'ATBResComPVCostModel'`
- `river`: hydropower
    - performance models:
        + `'RunOfRiverHydroPerformanceModel'`
    - cost models:
        + `'RunOfRiverHydroCostModel'`
- `hopp`: hybrid plant
    - combined performance and cost model:
        + `'HOPPComponent'`
- `electrolyzer`: hydrogen electrolysis
    - combined performance and cost:
        + `'WOMBATElectrolyzerModel'`
    - performance models:
        + `'ECOElectrolyzerPerformanceModel'`
    - cost models:
        + `'SingliticoCostModel'`
        + `'BasicElectrolyzerCostModel'`
- `geoh2_well_subsurface`: geologic hydrogen well subsurface
    - performance models:
        + `'NaturalGeoH2PerformanceModel'`
        + `'StimulatedGeoH2PerformanceModel'`
    - cost models:
        + `'GeoH2SubsurfaceCostModel'`
- `steel`: steel production
    - performance models:
        + `'SteelPerformanceModel'`
        + `'NaturalGasEAFPlantPerformanceComponent'`
        + `'HydrogenEAFPlantPerformanceComponent'`
    - combined cost and financial models:
        + `'SteelCostAndFinancialModel'`
    - cost models:
        + `'NaturalGasEAFPlantCostComponent'`
        + `'HydrogenEAFPlantCostComponent'`
- `ammonia`: ammonia synthesis
    - performance models:
        + `'simple_ammonia_performance'`
        + `'AmmoniaSynLoopPerformanceModel'`
    - cost models:
        + `'simple_ammonia_cost'`
        + `'AmmoniaSynLoopCostModel'`
- `doc`: direct ocean capture
    - performance models:
        + `'DOCPerformanceModel'`
    - cost models:
        + `'DOCCostModel'`
- `oae`: ocean alkalinity enhancement
    - performance models:
        + `'OAEPerformanceModel'`
    - cost models:
        + `'OAECostModel'`
    - financial models:
        + `'OAECostAndFinancialModel'`
- `methanol`: methanol synthesis
    - performance models:
        + `'SMRMethanolPlantPerformanceModel'`
    - cost models:
        + `'SMRMethanolPlantCostModel'`
    - financial models:
        + `'methanol_plant_financial'`
- `air_separator`: nitrogen separation from air
    - performance models:
        + `'SimpleASUPerformanceModel'`
    - cost models:
        + `'SimpleASUCostModel'`
- `desal`: water desalination
    - performance models:
        + `'ReverseOsmosisPerformanceModel'`
    - cost models:
        + `'ReverseOsmosisCostModel'`
- `natural_gas`: natural gas combined cycle and combustion turbine
    - performance models:
        + `'NaturalGasPerformanceModel'`
    - cost_models:
        + `'NaturalGasCostModel'`
- `grid`: electricity grid connection
    - performance models:
        + `'GridPerformanceModel'`
    - cost models:
        + `'GridCostModel'`
- `iron_ore`: iron ore mining and refining
    - performance models:
        + `'MartinIronMinePerformanceComponent'`
    - cost models:
        + `'MartinIronMineCostComponent'`
- `iron_dri`: iron ore direct reduction
    - performance models:
        + `'NaturalGasIronReductionPlantPerformanceComponent'`
        + `'HydrogenIronReductionPlantPerformanceComponent'`
        + `'HumbertEwinPerformanceComponent'`
    - cost models:
        + `'NaturalGasIronReductionPlantCostComponent'`
        + `'HydrogenIronReductionPlantCostComponent'`
- `iron_ewin`: iron electrowinning
    - performance models:
        + `'HumbertEwinPerformanceComponent'`
    - cost models:
        + `'HumbertStinnEwinCostComponent'`


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
        + `'GenericCombinerPerformanceModel'`: can be used for any commodity
- `splitter`:
    - performance models:
        + `'GenericSplitterPerformanceModel'`: can be used for any commodity

(storage-models)=
## Storage Models
- `h2_storage`: hydrogen storage
    - performance models:
        + `'hydrogen_tank_performance'`
    - cost models:
        + `'LinedRockCavernStorageCostModel'`
        + `'SaltCavernStorageCostModel'`
        + `'MCHTOLStorageCostModel'`
        + `'PipeStorageCostModel'`
- `generic_storage`: any resource storage
    - performance models:
        + `'SimpleGenericStorage'`
        + `'StorageAutoSizingModel'`
    - cost models:
        + `'GenericStorageCostModel'`
- `battery`: battery storage
    - performance models:
        + `'PySAMBatteryPerformanceModel'`
    - cost models:
        + `'ATBBatteryCostModel'`

(basic-operations)=
## Basic Operations
- `production_summer`: sums the production profile of any commodity
- `consumption_summer`: sums the consumption profile of any feedstock


(control-models)=
## Control Models
- `'PassThroughOpenLoopController'`
- Storage Controllers:
    - `'DemandOpenLoopStorageController'`
    - `'HeuristicLoadFollowingController'`
- Converter Controllers:
    - `'DemandOpenLoopConverterController`
    - `'FlexibleDemandOpenLoopConverterController'`
