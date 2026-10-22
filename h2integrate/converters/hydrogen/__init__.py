from h2integrate.core.lazy_imports import lazy_exports


__getattr__, __dir__ = lazy_exports(
    __name__,
    globals(),
    {
        "BasicElectrolyzerCostModel": "basic_cost_model",
        "CustomElectrolyzerCostModel": "custom_electrolyzer_cost_model",
        "H2FuelCellCostModel": "h2_fuel_cell",
        "LinearH2FuelCellPerformanceModel": "h2_fuel_cell",
        "HTSECostModel": "htse_electrolyzer",
        "HTSEPerformanceModel": "htse_electrolyzer",
        "ECOElectrolyzerPerformanceModel": "pem_electrolyzer",
        "PEMH2FuelCellPerformanceModel": "PEM_h2_fuel_cell",
        "SingliticoCostModel": "singlitico_cost_model",
        "SteamMethaneReformerCostModel": "steam_methane_reformer",
        "SteamMethaneReformerPerformanceModel": "steam_methane_reformer",
        "WOMBATElectrolyzerModel": "wombat_model",
    },
)
