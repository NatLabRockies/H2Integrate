from h2integrate.core.lazy_imports import lazy_exports


__getattr__, __dir__ = lazy_exports(
    __name__,
    globals(),
    {
        "HRRRMETToolkitWindAPI": "nlr_developer_wtk_api_models",
        "WTKNLRDeveloperAPIWindResource": "nlr_developer_wtk_api_models",
        "WTKHRRRMETDatasetH5": "nlr_hrrr_met_toolkit_dataset_model",
        "OpenMeteoHistoricalWindResource": "openmeteo_wind",
    },
)
