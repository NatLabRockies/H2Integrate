from h2integrate.core.lazy_imports import lazy_exports


__getattr__, __dir__ = lazy_exports(
    __name__,
    globals(),
    {
        "CMUElectricArcFurnaceCostModel": "cmu_eaf_cost",
        "CMUElectricArcFurnaceDRIPerformanceComponent": "cmu_electric_arc_furnace_dri",
        "CMUElectricArcFurnaceScrapOnlyPerformanceComponent": "cmu_electric_arc_furnace_scrap",
        "SteelCostAndFinancialModel": "steel",
        "SteelPerformanceModel": "steel",
        "HydrogenEAFPlantCostComponent": "steel_eaf_plant",
        "HydrogenEAFPlantPerformanceComponent": "steel_eaf_plant",
        "NaturalGasEAFPlantCostComponent": "steel_eaf_plant",
        "NaturalGasEAFPlantPerformanceComponent": "steel_eaf_plant",
    },
)
