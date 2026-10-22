from h2integrate.core.lazy_imports import lazy_exports


__getattr__, __dir__ = lazy_exports(
    __name__,
    globals(),
    {
        "AspenGeoH2SurfaceCostModel": "aspen_surface_processing",
        "AspenGeoH2SurfacePerformanceModel": "aspen_surface_processing",
        "GeoH2SubsurfaceCostModel": "mathur_modified",
        "NaturalGeoH2PerformanceModel": "simple_natural_geoh2",
        "StimulatedGeoH2PerformanceModel": "templeton_serpentinization",
    },
)
