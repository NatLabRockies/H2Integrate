(cost:cost_years)=
# Cost year of cost models
Cost models report the dollar year associated with their cost outputs. Plant-level finance parameters can adjust these costs to a common `target_dollar_year`. Some models use fixed source years; others require a year alongside user-provided cost data.

(cost-models-with-inherent-cost-year)=
## Cost models with inherent cost year

### Models with fixed source cost years
| Registered cost model | Source cost year |
| :--- | :---: |
| `ReverseOsmosisCostModel` | 2013 |
| `BasicElectrolyzerCostModel` | 2016 |
| `CompressedGasStorageCostModel`, `LinedRockCavernStorageCostModel`, `PipeStorageCostModel`, `SaltCavernStorageCostModel` | 2018 |
| `HumbertStinnEwinCostComponent` | 2018 |
| `SingliticoCostModel` | 2021 |
| `CMUElectricArcFurnaceCostModel`, `PySAMMarineCostModel`, `SimpleAmmoniaCostModel`, `SteelCostAndFinancialModel` | 2022 |
| `DOCCostModel` | 2023 |
| `PaperMillCostModel`, `SAFCostModel` | 2023 |
| `MCHTOLStorageCostModel`, `OAECostModel`, `OAECostAndFinancialModel` | 2024 |

`SimpleIronMineCostComponent` and `NRRIIronMineCostComponent` use 2021 source costs and adjust them to the plant's `target_dollar_year`.

(cost-models-with-user-input-cost-year)=
## Cost models with user input cost year

### Models with user-provided cost years
Provide the cost year for user-supplied cost data in `model_inputs.cost_parameters`. `AmmoniaSynLoopCostModel` uses the parameter `base_cost_year` for its source data. The following registered models use a configurable cost year:

| Model area | Registered cost models |
| :--- | :--- |
| ATB-based costs | `ATBBatteryCostModel`, `ATBResComPVCostModel`, `ATBUtilityPVCostModel`, `ATBWindPlantCostModel` |
| Carbon, feedstocks, and generic costs | `AspenGeoH2SurfaceCostModel`, `CO2HMethanolPlantCostModel`, `EIANaturalGasFeedstockCostModel`, `FeedstockCostModel`, `GenericConverterCostModel`, `GenericStorageCostModel`, `GridCostModel`, `NaturalGasCostModel` |
| Hydrogen | `CustomElectrolyzerCostModel`, `GeoH2SubsurfaceCostModel`, `H2FuelCellCostModel`, `HTSECostModel`, `SMRMethanolPlantCostModel`, `SteamMethaneReformerCostModel`, `WOMBATElectrolyzerModel` |
| Iron and steel | `HydrogenEAFPlantCostComponent`, `HydrogenIronReductionPlantCostComponent`, `IronTransportCostComponent`, `NaturalGasEAFPlantCostComponent`, `NaturalGasIronReductionPlantCostComponent` |
| Other generation, transport, and storage | `DieselGeneratorCostModel`, `LinearDistanceCostModel`, `LinearMassTransportCostModel`, `QuinnNuclearCostModel`, `RunOfRiverHydroCostModel`, `SimpleASUCostModel`, `SimpleThermalNuclearReactorCostModel` |

Some configurable models provide a default year, such as `HTSECostModel` and `SimpleThermalNuclearReactorCostModel`; confirm that it matches the year of the costs you provide.

### Example tech_config input for user-input cost year
```yaml
technologies:
  solar:
    performance_model:
      model: "PYSAMSolarPlantPerformanceModel"
    cost_model:
      model: "ATBUtilityPVCostModel"
    model_inputs:
        performance_parameters:
            pv_capacity_kWdc: 100000
            dc_ac_ratio: 1.34
            ...
        cost_parameters:
            capex_per_kWac: 1044
            opex_per_kWac_per_year: 18
            cost_year: 2022
```
