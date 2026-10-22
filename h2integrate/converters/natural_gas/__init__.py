from h2integrate.core.lazy_imports import lazy_exports


__getattr__, __dir__ = lazy_exports(
    __name__,
    globals(),
    {
        "SimpleGasConsumerCost": "dummy_gas_components",
        "SimpleGasConsumerPerformance": "dummy_gas_components",
        "SimpleGasProducerCost": "dummy_gas_components",
        "SimpleGasProducerPerformance": "dummy_gas_components",
        "NaturalGasCostModel": "natural_gas_cc_ct",
        "NaturalGasPerformanceModel": "natural_gas_cc_ct",
        "SONGFuelCellPerformanceModel": "SO_NG_fuel_cell",
    },
)
