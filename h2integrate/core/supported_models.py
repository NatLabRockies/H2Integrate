import importlib


class _ModelRegistry(dict):
    """A dict subclass that imports model classes on first access.

    Stores entries as ``"ClassName": "relative.module.path:ClassName"``
    strings, where the module path is relative to the ``h2integrate``
    package (the ``h2integrate.`` prefix is prepended automatically).
    On first ``__getitem__``, ``get``, or iteration over values, the class
    is imported, cached, and returned.  This avoids importing every model
    module (and their heavy transitive dependencies) at package-load time,
    reducing computational cost of imports and running tests.
    """

    _PKG_PREFIX = "h2integrate."

    def _resolve(self, key):
        """Import and cache the class for :py:attr:`key`, returning the resolved class."""
        value = super().__getitem__(key)
        if isinstance(value, str):
            mod_path, attr_name = value.rsplit(":", 1)
            module = importlib.import_module(self._PKG_PREFIX + mod_path)
            cls = getattr(module, attr_name)
            super().__setitem__(key, cls)
            return cls
        return value

    def __getitem__(self, key):
        """Return the model class for *key*, importing it if needed."""
        return self._resolve(key)

    def get(self, key, default=None):
        """Return the model class for *key*, or *default* if not present."""
        if key in self:
            return self._resolve(key)
        return default

    def copy(self):
        """Return a new _ModelRegistry with the same (still-deferred) entries."""
        new = _ModelRegistry()
        for k in super().keys():
            new[k] = super().__getitem__(k)
        return new


supported_models = _ModelRegistry(
    {
        # Resources
        "TidalResource": "resource.tidal:TidalResource",
        "RiverResource": "resource.river:RiverResource",
        "WTKNLRDeveloperAPIWindResource": "resource.wind.nlr_developer_wtk_api:WTKNLRDeveloperAPIWindResource",
        "OpenMeteoHistoricalWindResource": "resource.wind.openmeteo_wind:OpenMeteoHistoricalWindResource",
        "OpenMeteoHistoricalSolarResource": "resource.solar.openmeteo_solar:OpenMeteoHistoricalSolarResource",
        "GOESAggregatedSolarAPI": "resource.solar.nlr_developer_goes_api_models:GOESAggregatedSolarAPI",
        "GOESConusSolarAPI": "resource.solar.nlr_developer_goes_api_models:GOESConusSolarAPI",
        "GOESFullDiscSolarAPI": "resource.solar.nlr_developer_goes_api_models:GOESFullDiscSolarAPI",
        "GOESTMYSolarAPI": "resource.solar.nlr_developer_goes_api_models:GOESTMYSolarAPI",
        "MeteosatPrimeMeridianSolarAPI": "resource.solar.nlr_developer_meteosat_prime_meridian_models:MeteosatPrimeMeridianSolarAPI",
        "MeteosatPrimeMeridianTMYSolarAPI": "resource.solar.nlr_developer_meteosat_prime_meridian_models:MeteosatPrimeMeridianTMYSolarAPI",
        "Himawari7SolarAPI": "resource.solar.nlr_developer_himawari_api_models:Himawari7SolarAPI",
        "Himawari8SolarAPI": "resource.solar.nlr_developer_himawari_api_models:Himawari8SolarAPI",
        "HimawariTMYSolarAPI": "resource.solar.nlr_developer_himawari_api_models:HimawariTMYSolarAPI",
        # Converters
        "GenericConverterCostModel": "converters.generic_converter_cost:GenericConverterCostModel",
        "ATBWindPlantCostModel": "converters.wind.atb_wind_cost:ATBWindPlantCostModel",
        "PYSAMWindPlantPerformanceModel": "converters.wind.wind_pysam:PYSAMWindPlantPerformanceModel",
        "FlorisWindPlantPerformanceModel": "converters.wind.floris:FlorisWindPlantPerformanceModel",
        "ArdWindPlantModel": "converters.wind.wind_plant_ard:ArdWindPlantModel",
        "PYSAMSolarPlantPerformanceModel": "converters.solar.solar_pysam:PYSAMSolarPlantPerformanceModel",
        "ATBUtilityPVCostModel": "converters.solar.atb_utility_pv_cost:ATBUtilityPVCostModel",
        "ATBResComPVCostModel": "converters.solar.atb_res_com_pv_cost:ATBResComPVCostModel",
        "PySAMTidalPerformanceModel": "converters.water_power.tidal_pysam:PySAMTidalPerformanceModel",
        "PySAMMarineCostModel": "converters.water_power.pysam_marine_cost:PySAMMarineCostModel",
        "RunOfRiverHydroPerformanceModel": "converters.water_power.hydro_plant_run_of_river:RunOfRiverHydroPerformanceModel",
        "RunOfRiverHydroCostModel": "converters.water_power.hydro_plant_run_of_river:RunOfRiverHydroCostModel",
        "ECOElectrolyzerPerformanceModel": "converters.hydrogen.pem_electrolyzer:ECOElectrolyzerPerformanceModel",
        "SingliticoCostModel": "converters.hydrogen.singlitico_cost_model:SingliticoCostModel",
        "BasicElectrolyzerCostModel": "converters.hydrogen.basic_cost_model:BasicElectrolyzerCostModel",
        "CustomElectrolyzerCostModel": "converters.hydrogen.custom_electrolyzer_cost_model:CustomElectrolyzerCostModel",
        "WOMBATElectrolyzerModel": "converters.hydrogen.wombat_model:WOMBATElectrolyzerModel",
        "LinearH2FuelCellPerformanceModel": "converters.hydrogen.h2_fuel_cell:LinearH2FuelCellPerformanceModel",
        "H2FuelCellCostModel": "converters.hydrogen.h2_fuel_cell:H2FuelCellCostModel",
        "SteamMethaneReformerPerformanceModel": "converters.hydrogen.steam_methane_reformer:SteamMethaneReformerPerformanceModel",
        "SteamMethaneReformerCostModel": "converters.hydrogen.steam_methane_reformer:SteamMethaneReformerCostModel",
        "SimpleASUCostModel": "converters.nitrogen.simple_ASU:SimpleASUCostModel",
        "SimpleASUPerformanceModel": "converters.nitrogen.simple_ASU:SimpleASUPerformanceModel",
        "HOPPComponent": "converters.hopp.hopp_wrapper:HOPPComponent",
        "MartinIronMinePerformanceComponent": "converters.iron.martin_mine_perf_model:MartinIronMinePerformanceComponent",
        "MartinIronMineCostComponent": "converters.iron.martin_mine_cost_model:MartinIronMineCostComponent",
        "NaturalGasIronReductionPlantPerformanceComponent": "converters.iron.iron_dri_plant:NaturalGasIronReductionPlantPerformanceComponent",
        "NaturalGasIronReductionPlantCostComponent": "converters.iron.iron_dri_plant:NaturalGasIronReductionPlantCostComponent",
        "HydrogenIronReductionPlantPerformanceComponent": "converters.iron.iron_dri_plant:HydrogenIronReductionPlantPerformanceComponent",
        "HydrogenIronReductionPlantCostComponent": "converters.iron.iron_dri_plant:HydrogenIronReductionPlantCostComponent",
        "HumbertEwinPerformanceComponent": "converters.iron.humbert_ewin_perf:HumbertEwinPerformanceComponent",
        "HumbertStinnEwinCostComponent": "converters.iron.humbert_stinn_ewin_cost:HumbertStinnEwinCostComponent",
        "NaturalGasEAFPlantPerformanceComponent": "converters.steel.steel_eaf_plant:NaturalGasEAFPlantPerformanceComponent",
        "NaturalGasEAFPlantCostComponent": "converters.steel.steel_eaf_plant:NaturalGasEAFPlantCostComponent",
        "HydrogenEAFPlantPerformanceComponent": "converters.steel.steel_eaf_plant:HydrogenEAFPlantPerformanceComponent",
        "HydrogenEAFPlantCostComponent": "converters.steel.steel_eaf_plant:HydrogenEAFPlantCostComponent",
        "CMUElectricArcFurnaceScrapOnlyPerformanceComponent": "converters.steel.cmu_electric_arc_furnace_scrap:CMUElectricArcFurnaceScrapOnlyPerformanceComponent",
        "CMUElectricArcFurnaceDRIPerformanceComponent": "converters.steel.cmu_electric_arc_furnace_dri:CMUElectricArcFurnaceDRIPerformanceComponent",
        "CMUElectricArcFurnaceCostModel": "converters.steel.cmu_eaf_cost:CMUElectricArcFurnaceCostModel",
        "ReverseOsmosisPerformanceModel": "converters.water.desal.desalination:ReverseOsmosisPerformanceModel",
        "ReverseOsmosisCostModel": "converters.water.desal.desalination:ReverseOsmosisCostModel",
        "SimpleAmmoniaPerformanceModel": "converters.ammonia.simple_ammonia_model:SimpleAmmoniaPerformanceModel",
        "SimpleAmmoniaCostModel": "converters.ammonia.simple_ammonia_model:SimpleAmmoniaCostModel",
        "AmmoniaSynLoopPerformanceModel": "converters.ammonia.ammonia_synloop:AmmoniaSynLoopPerformanceModel",
        "AmmoniaSynLoopCostModel": "converters.ammonia.ammonia_synloop:AmmoniaSynLoopCostModel",
        "SteelPerformanceModel": "converters.steel.steel:SteelPerformanceModel",
        "SteelCostAndFinancialModel": "converters.steel.steel:SteelCostAndFinancialModel",
        "SMRMethanolPlantPerformanceModel": "converters.methanol.smr_methanol_plant:SMRMethanolPlantPerformanceModel",
        "SMRMethanolPlantCostModel": "converters.methanol.smr_methanol_plant:SMRMethanolPlantCostModel",
        "SMRMethanolPlantFinanceModel": "converters.methanol.smr_methanol_plant:SMRMethanolPlantFinanceModel",
        "CO2HMethanolPlantPerformanceModel": "converters.methanol.co2h_methanol_plant:CO2HMethanolPlantPerformanceModel",
        "CO2HMethanolPlantCostModel": "converters.methanol.co2h_methanol_plant:CO2HMethanolPlantCostModel",
        "CO2HMethanolPlantFinanceModel": "converters.methanol.co2h_methanol_plant:CO2HMethanolPlantFinanceModel",
        "DOCPerformanceModel": "converters.co2.marine.direct_ocean_capture:DOCPerformanceModel",
        "DOCCostModel": "converters.co2.marine.direct_ocean_capture:DOCCostModel",
        "OAEPerformanceModel": "converters.co2.marine.ocean_alkalinity_enhancement:OAEPerformanceModel",
        "OAECostModel": "converters.co2.marine.ocean_alkalinity_enhancement:OAECostModel",
        "OAECostAndFinancialModel": "converters.co2.marine.ocean_alkalinity_enhancement:OAECostAndFinancialModel",
        "NaturalGeoH2PerformanceModel": "converters.hydrogen.geologic.simple_natural_geoh2:NaturalGeoH2PerformanceModel",
        "StimulatedGeoH2PerformanceModel": "converters.hydrogen.geologic.templeton_serpentinization:StimulatedGeoH2PerformanceModel",
        "GeoH2SubsurfaceCostModel": "converters.hydrogen.geologic.mathur_modified:GeoH2SubsurfaceCostModel",
        "AspenGeoH2SurfacePerformanceModel": "converters.hydrogen.geologic.aspen_surface_processing:AspenGeoH2SurfacePerformanceModel",
        "AspenGeoH2SurfaceCostModel": "converters.hydrogen.geologic.aspen_surface_processing:AspenGeoH2SurfaceCostModel",
        "NaturalGasPerformanceModel": "converters.natural_gas.natural_gas_cc_ct:NaturalGasPerformanceModel",
        "QuinnNuclearPerformanceModel": "converters.nuclear.nuclear_plant:QuinnNuclearPerformanceModel",
        "QuinnNuclearCostModel": "converters.nuclear.nuclear_plant:QuinnNuclearCostModel",
        "NaturalGasCostModel": "converters.natural_gas.natural_gas_cc_ct:NaturalGasCostModel",
        # Transport
        "cable": "transporters.cable:CablePerformanceModel",
        "pipe": "transporters.pipe:PipePerformanceModel",
        "GenericCombinerPerformanceModel": "transporters.generic_combiner:GenericCombinerPerformanceModel",
        "GenericSplitterPerformanceModel": "transporters.generic_splitter:GenericSplitterPerformanceModel",
        "GenericTransporterPerformanceModel": "transporters.generic_transporter:GenericTransporterPerformanceModel",
        "IronTransportPerformanceComponent": "converters.iron.iron_transport:IronTransportPerformanceComponent",
        "IronTransportCostComponent": "converters.iron.iron_transport:IronTransportCostComponent",
        # Simple Summers
        "GenericSummerPerformanceModel": "transporters.generic_summer:GenericSummerPerformanceModel",
        # Storage
        "PySAMBatteryPerformanceModel": "storage.battery.pysam_battery:PySAMBatteryPerformanceModel",
        "StoragePerformanceModel": "storage.storage_performance_model:StoragePerformanceModel",
        "StorageAutoSizingModel": "storage.simple_storage_auto_sizing:StorageAutoSizingModel",
        "LinedRockCavernStorageCostModel": "storage.hydrogen.h2_storage_cost:LinedRockCavernStorageCostModel",
        "CompressedGasStorageCostModel": "storage.hydrogen.h2_storage_cost:CompressedGasStorageCostModel",
        "SaltCavernStorageCostModel": "storage.hydrogen.h2_storage_cost:SaltCavernStorageCostModel",
        "MCHTOLStorageCostModel": "storage.hydrogen.mch_storage:MCHTOLStorageCostModel",
        "PipeStorageCostModel": "storage.hydrogen.h2_storage_cost:PipeStorageCostModel",
        "ATBBatteryCostModel": "storage.battery.atb_battery_cost:ATBBatteryCostModel",
        "GenericStorageCostModel": "storage.generic_storage_cost:GenericStorageCostModel",
        # Control
        "SimpleStorageOpenLoopController": "control.control_strategies.storage.simple_openloop_controller:SimpleStorageOpenLoopController",
        "DemandOpenLoopStorageController": "control.control_strategies.storage.demand_openloop_storage_controller:DemandOpenLoopStorageController",
        "PeakLoadManagementHeuristicOpenLoopStorageController": "control.control_strategies.storage.plm_openloop_storage_controller:PeakLoadManagementHeuristicOpenLoopStorageController",
        "PeakLoadManagementOptimizedStorageController": "control.control_strategies.storage.plm_optimized_storage_controller:PeakLoadManagementOptimizedStorageController",
        "HeuristicLoadFollowingStorageController": "control.control_strategies.storage.heuristic_pyomo_controller:HeuristicLoadFollowingStorageController",
        "OptimizedDispatchStorageController": "control.control_strategies.storage.optimized_pyomo_controller:OptimizedDispatchStorageController",
        "GenericDemandComponent": "demand.generic_demand:GenericDemandComponent",
        "FlexibleDemandComponent": "demand.flexible_demand:FlexibleDemandComponent",
        # Dispatch
        "PyomoDispatchGenericConverter": "control.control_rules.converters.generic_converter:PyomoDispatchGenericConverter",
        "PyomoRuleStorageBaseclass": "control.control_rules.storage.pyomo_storage_rule_baseclass:PyomoRuleStorageBaseclass",
        "PyomoRuleStorageMinOperatingCosts": "control.control_rules.storage.pyomo_storage_rule_min_operating_cost:PyomoRuleStorageMinOperatingCosts",
        "PyomoDispatchGenericConverterMinOperatingCosts": "control.control_rules.converters.generic_converter_min_operating_cost:PyomoDispatchGenericConverterMinOperatingCosts",
        # Feedstock
        "FeedstockPerformanceModel": "feedstocks:FeedstockPerformanceModel",
        "FeedstockCostModel": "feedstocks:FeedstockCostModel",
        "EIANaturalGasFeedstockCostModel": "feedstocks:EIANaturalGasFeedstockCostModel",
        # Grid
        "GridPerformanceModel": "converters.grid.grid:GridPerformanceModel",
        "GridCostModel": "converters.grid.grid:GridCostModel",
        # Finance
        "ProFastLCO": "finances.profast_lco:ProFastLCO",
        "ProFastNPV": "finances.profast_npv:ProFastNPV",
        "NumpyFinancialNPV": "finances.numpy_financial_npv:NumpyFinancialNPV",
        # Dummy components for multivariable stream demonstrations
        "SimpleGasProducerPerformance": "converters.natural_gas.dummy_gas_components:SimpleGasProducerPerformance",
        "SimpleGasProducerCost": "converters.natural_gas.dummy_gas_components:SimpleGasProducerCost",
        "SimpleGasConsumerPerformance": "converters.natural_gas.dummy_gas_components:SimpleGasConsumerPerformance",
        "SimpleGasConsumerCost": "converters.natural_gas.dummy_gas_components:SimpleGasConsumerCost",
        "GasStreamCombinerPerformanceModel": "transporters.gas_stream_combiner:GasStreamCombinerPerformanceModel",
    }
)


# This next section is to demarcate specific models that belong to certain categories that are
# relevant for processing in the model stackup. Right now, these designations are
# used in `h2integrate_model.py`.


# Model classes that do not contribute costs to the finance stackup because they are essentially
# internal-only models that aren't categorized as a specific technology (e.g. a generic combiner
# or splitter, or a model that is only used for performance modeling within another model and
# doesn't have an independent cost model).
no_cost_models = {
    "GenericSplitterPerformanceModel",
    "GenericCombinerPerformanceModel",
    "GasStreamCombinerPerformanceModel",
    "CablePerformanceModel",
    "PipePerformanceModel",
}

no_replacement_schedule_models = {
    "IronTransportPerformanceComponent",
}
