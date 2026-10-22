from h2integrate.core.lazy_imports import lazy_exports


__getattr__, __dir__ = lazy_exports(
    __name__,
    globals(),
    {
        "DOCCostModel": "direct_ocean_capture",
        "DOCPerformanceModel": "direct_ocean_capture",
        "OAECostAndFinancialModel": "ocean_alkalinity_enhancement",
        "OAECostModel": "ocean_alkalinity_enhancement",
        "OAEPerformanceModel": "ocean_alkalinity_enhancement",
    },
)
