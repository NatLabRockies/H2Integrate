from h2integrate.core.lazy_imports import lazy_exports


__getattr__, __dir__ = lazy_exports(
    __name__,
    globals(),
    {
        "NumpyFinancialNPV": "numpy_financial_npv",
        "ProFastLCO": "profast_lco",
        "ProFastNPV": "profast_npv",
    },
)
