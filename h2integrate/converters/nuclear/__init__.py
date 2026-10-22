from h2integrate.core.lazy_imports import lazy_exports


__getattr__, __dir__ = lazy_exports(
    __name__,
    globals(),
    {
        "QuinnNuclearCostModel": "nuclear_plant",
        "QuinnNuclearPerformanceModel": "nuclear_plant",
        "SimpleThermalNuclearReactorCostModel": "nuclear_plant_thermal",
        "SimpleThermalNuclearReactorPerformanceModel": "nuclear_plant_thermal",
    },
)
