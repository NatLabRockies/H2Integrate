
(model-overview)=
# Model Overview
Currently, H2I recognizes four types of models:

- [Resource](#resource)
- [Converter](#converters)
- [Transport](#transport)
- [Storage](#storage)
- [Controllers](#controller)

(resource)=
## Resource
`Resource` models process resource data that is usually passed to a technology model. See [Resource models](#resource-models) for available models.


(converters)=
## Converters
`Converter` models are technologies that:
- converts energy available in the 'Primary Input' to another form of energy ('Primary Commodity') OR
- consumes the 'Primary Input' (and perhaps secondary inputs or feedstocks), which is converted to the 'Primary Commodity' through some process

```{note}
When the Primary Commodity is electricity, those converters are considered electricity producing technologies and their electricity production is summed for financial calculations.
```

See [Converter models](#converter-models) for the full list of available converter technologies.

(transport)=
## Transport
`Transport` models are used to either:
- connect the 'Transport Commodity' from a technology that produces the 'Transport Commodity' to a technology that consumes or stores the 'Transport Commodity' OR
- combine multiple input streams of the 'Transport Commodity' into a single stream
- split a single input stream of the 'Transport Commodity' into multiple output streams

Connection: `[source_tech, dest_tech, transport_commodity, transport_technology]`

See [Transport Models](#transport-models) for available models.

(storage)=
## Storage
`Storage` technologies input and output the 'Storage Commodity' at different times. These technologies can be filled or charged, then unfilled or discharged at some later time. These models are usually constrained by two key model parameters: storage capacity and charge/discharge rate.

See [Storage Models](#storage-models) for available models.

(control)=
(controller)=
## Control
`Control` models are used to control the `Storage` models and resource flows.

See [Control Models](#control-models) for available models.

(technology-models-overview)=
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
        + `WTKNLRDeveloperAPIWindResource`
        + `OpenMeteoHistoricalWindResource`
- `solar_resource`:
    - resource models:
        + `OpenMeteoHistoricalSolarResource`
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
        + `'CustomElectrolyzerCostModel'`
- `geoh2_well_subsurface`: geologic hydrogen well subsurface
    - performance models:
        + `'NaturalGeoH2PerformanceModel'`
        + `'StimulatedGeoH2PerformanceModel'`
    - cost models:
        + `'GeoH2SubsurfaceCostModel'`
- `geoh2_well_surface`: geologic hydrogen well surface processing
    - performance models:
        + `'AspenGeoH2SurfacePerformanceModel'`
    - cost models:
        + `'AspenGeoH2SurfaceCostModel'`
- `h2_fuel_cell`: hydrogen fuel cell
    - performance models:
        + `'LinearH2FuelCellPerformanceModel'`
    - cost models:
        + `'H2FuelCellCostModel'`
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
        + `'SimpleAmmoniaPerformanceModel'`
        + `'AmmoniaSynLoopPerformanceModel'`
    - cost models:
        + `'SimpleAmmoniaCostModel'`
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
    - SMR methanol:
        - performance models:
            + `'SMRMethanolPlantPerformanceModel'`
        - cost models:
            + `'SMRMethanolPlantCostModel'`
        - financial models:
            + `'SMRMethanolPlantFinanceModel'`
    - CO2-to-methanol:
        - performance models:
            + `'CO2HMethanolPlantPerformanceModel'`
        - cost models:
            + `'CO2HMethanolPlantCostModel'`
        - financial models:
            + `'CO2HMethanolPlantFinanceModel'`
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
    - cost models:
        + `'NaturalGasCostModel'`
- `nuclear`: nuclear power plant
    - performance models:
        + `'QuinnNuclearPerformanceModel'`
    - cost models:
        + `'QuinnNuclearCostModel'`
    - docs:
        + [../technology_models/nuclear.md](../technology_models/nuclear.md)
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
        + `'pipe'`: compatible with the commodities "hydrogen", "co2", "methanol", "ammonia", "nitrogen", "natural_gas", and "water"
- `combiner`:
    - performance models:
        + `'GenericCombinerPerformanceModel'`: can be used for any commodity
- `splitter`:
    - performance models:
        + `'GenericSplitterPerformanceModel'`: can be used for any commodity
- `generic_transport`:
    - performance models:
        + `'GenericTransporterPerformanceModel'`: can be used for any commodity
(storage-models)=
## Storage Models
- `h2_storage`: hydrogen storage
    - cost models:
        + `'LinedRockCavernStorageCostModel'`
        + `'SaltCavernStorageCostModel'`
        + `'MCHTOLStorageCostModel'`
        + `'PipeStorageCostModel'`
- `generic_storage`: any resource storage
    - performance models:
        + `'StoragePerformanceModel'`
        + `'StorageAutoSizingModel'`
    - cost models:
        + `'GenericStorageCostModel'`
- `battery`: battery storage
    - performance models:
        + `'PySAMBatteryPerformanceModel'`
    - cost models:
        + `'ATBBatteryCostModel'`
- `generic_storage_pyo`: storage for any commodity type that is compatible with the Pyomo controllers
    - performance models: `StoragePerformanceModel`

(basic-operations)=
## Basic Operations
- `production_summer`: sums the production profile of any commodity
- `consumption_summer`: sums the consumption profile of any feedstock


(control-models)=
## Control Models
- Storage Controllers:
    - `'SimpleStorageOpenLoopController'`: open-loop control; manages resource flow based on demand and input commodity
    - `'DemandOpenLoopStorageController'`: open-loop control; manages resource flow based on demand and storage constraints
    - `'HeuristicLoadFollowingController'`: open-loop control that works on a time window basis to set dispatch commands; uses Pyomo
- Converter Controllers:
    - `'DemandOpenLoopConverterController'`: open-loop control; manages resource flow based on demand constraints
    - `'FlexibleDemandOpenLoopConverterController'`: open-loop control; manages resource flow based on demand and flexibility constraints
- Optimized Dispatch:
    - `'OptimizedDispatchController'`: optimization-based dispatch using Pyomo
