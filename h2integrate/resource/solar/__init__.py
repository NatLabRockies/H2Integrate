from h2integrate.core.lazy_imports import lazy_exports


__getattr__, __dir__ = lazy_exports(
    __name__,
    globals(),
    {
        "GOESAggregatedSolarAPI": "nlr_developer_goes_api_models",
        "GOESConusSolarAPI": "nlr_developer_goes_api_models",
        "GOESFullDiscSolarAPI": "nlr_developer_goes_api_models",
        "GOESTMYSolarAPI": "nlr_developer_goes_api_models",
        "Himawari7SolarAPI": "nlr_developer_himawari_api_models",
        "Himawari8SolarAPI": "nlr_developer_himawari_api_models",
        "HimawariTMYSolarAPI": "nlr_developer_himawari_api_models",
        "MeteosatPrimeMeridianSolarAPI": "nlr_developer_meteosat_prime_meridian_models",
        "MeteosatPrimeMeridianTMYSolarAPI": "nlr_developer_meteosat_prime_meridian_models",
        "NSRDBDatasetH5": "nlr_nsrdb_dataset_model",
        "OpenMeteoHistoricalSolarResource": "openmeteo_solar",
    },
)
