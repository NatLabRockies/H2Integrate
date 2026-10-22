from h2integrate.core.lazy_imports import lazy_exports


__getattr__, __dir__ = lazy_exports(
    __name__,
    globals(),
    {
        "HumbertEwinPerformanceComponent": "humbert_ewin_perf",
        "HumbertStinnEwinCostComponent": "humbert_stinn_ewin_cost",
        "HydrogenIronReductionPlantCostComponent": "iron_dri_plant",
        "HydrogenIronReductionPlantPerformanceComponent": "iron_dri_plant",
        "NaturalGasIronReductionPlantCostComponent": "iron_dri_plant",
        "NaturalGasIronReductionPlantPerformanceComponent": "iron_dri_plant",
        "IronTransportCostComponent": "iron_transport",
        "IronTransportPerformanceComponent": "iron_transport",
        "NRRIIronMineCostComponent": "nrri_iron_mine",
        "NRRIIronMinePerformanceComponent": "nrri_iron_mine",
        "SimpleIronMineCostComponent": "simple_mine_cost_model",
        "SimpleIronMinePerformanceComponent": "simple_mine_perf_model",
    },
)
