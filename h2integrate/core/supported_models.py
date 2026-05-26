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
        "WTKNLRDeveloperAPIWindResource": "resource.wind:WTKNLRDeveloperAPIWindResource",
        "OpenMeteoHistoricalWindResource": "resource.wind:OpenMeteoHistoricalWindResource",
        "OpenMeteoHistoricalSolarResource": "resource.solar:OpenMeteoHistoricalSolarResource",
        "GOESAggregatedSolarAPI": "resource.solar:GOESAggregatedSolarAPI",
        "GOESConusSolarAPI": "resource.solar:GOESConusSolarAPI",
        "GOESFullDiscSolarAPI": "resource.solar:GOESFullDiscSolarAPI",
        "GOESTMYSolarAPI": "resource.solar:GOESTMYSolarAPI",
        "MeteosatPrimeMeridianSolarAPI": "resource.solar:MeteosatPrimeMeridianSolarAPI",
        "MeteosatPrimeMeridianTMYSolarAPI": "resource.solar:MeteosatPrimeMeridianTMYSolarAPI",
        "Himawari7SolarAPI": "resource.solar:Himawari7SolarAPI",
        "Himawari8SolarAPI": "resource.solar:Himawari8SolarAPI",
        "HimawariTMYSolarAPI": "resource.solar:HimawariTMYSolarAPI",
        # Converters
        "GenericConverterCostModel": "converters:GenericConverterCostModel",
        "ATBWindPlantCostModel": "converters.wind:ATBWindPlantCostModel",
        "PYSAMWindPlantPerformanceModel": "converters.wind:PYSAMWindPlantPerformanceModel",
        "FlorisWindPlantPerformanceModel": "converters.wind:FlorisWindPlantPerformanceModel",
        "ArdWindPlantModel": "converters.wind:ArdWindPlantModel",
        "PYSAMSolarPlantPerformanceModel": "converters.solar:PYSAMSolarPlantPerformanceModel",
        "ATBUtilityPVCostModel": "converters.solar:ATBUtilityPVCostModel",
        "ATBResComPVCostModel": "converters.solar:ATBResComPVCostModel",
        "PySAMTidalPerformanceModel": "converters.water_power:PySAMTidalPerformanceModel",
        "PySAMMarineCostModel": "converters.water_power:PySAMMarineCostModel",
        "RunOfRiverHydroPerformanceModel": "converters.water_power:RunOfRiverHydroPerformanceModel",
        "RunOfRiverHydroCostModel": "converters.water_power:RunOfRiverHydroCostModel",
        "ECOElectrolyzerPerformanceModel": "converters.hydrogen:ECOElectrolyzerPerformanceModel",
        "SingliticoCostModel": "converters.hydrogen:SingliticoCostModel",
        "BasicElectrolyzerCostModel": "converters.hydrogen:BasicElectrolyzerCostModel",
        "CustomElectrolyzerCostModel": "converters.hydrogen:CustomElectrolyzerCostModel",
        "WOMBATElectrolyzerModel": "converters.hydrogen:WOMBATElectrolyzerModel",
        "LinearH2FuelCellPerformanceModel": "converters.hydrogen:LinearH2FuelCellPerformanceModel",
        "H2FuelCellCostModel": "converters.hydrogen:H2FuelCellCostModel",
        "SteamMethaneReformerPerformanceModel": "converters.hydrogen:SteamMethaneReformerPerformanceModel",
        "SteamMethaneReformerCostModel": "converters.hydrogen:SteamMethaneReformerCostModel",
        "SimpleASUCostModel": "converters.nitrogen:SimpleASUCostModel",
        "SimpleASUPerformanceModel": "converters.nitrogen:SimpleASUPerformanceModel",
        "HOPPComponent": "converters.hopp:HOPPComponent",
        "MartinIronMinePerformanceComponent": "converters.iron:MartinIronMinePerformanceComponent",
        "MartinIronMineCostComponent": "converters.iron:MartinIronMineCostComponent",
        "NaturalGasIronReductionPlantPerformanceComponent": "converters.iron:NaturalGasIronReductionPlantPerformanceComponent",
        "NaturalGasIronReductionPlantCostComponent": "converters.iron:NaturalGasIronReductionPlantCostComponent",
        "HydrogenIronReductionPlantPerformanceComponent": "converters.iron:HydrogenIronReductionPlantPerformanceComponent",
        "HydrogenIronReductionPlantCostComponent": "converters.iron:HydrogenIronReductionPlantCostComponent",
        "HumbertEwinPerformanceComponent": "converters.iron:HumbertEwinPerformanceComponent",
        "HumbertStinnEwinCostComponent": "converters.iron:HumbertStinnEwinCostComponent",
        "NaturalGasEAFPlantPerformanceComponent": "converters.steel:NaturalGasEAFPlantPerformanceComponent",
        "NaturalGasEAFPlantCostComponent": "converters.steel:NaturalGasEAFPlantCostComponent",
        "HydrogenEAFPlantPerformanceComponent": "converters.steel:HydrogenEAFPlantPerformanceComponent",
        "HydrogenEAFPlantCostComponent": "converters.steel:HydrogenEAFPlantCostComponent",
        "CMUElectricArcFurnaceScrapOnlyPerformanceComponent": "converters.steel:CMUElectricArcFurnaceScrapOnlyPerformanceComponent",
        "CMUElectricArcFurnaceDRIPerformanceComponent": "converters.steel:CMUElectricArcFurnaceDRIPerformanceComponent",
        "CMUElectricArcFurnaceCostModel": "converters.steel:CMUElectricArcFurnaceCostModel",
        "ReverseOsmosisPerformanceModel": "converters.water.desal:ReverseOsmosisPerformanceModel",
        "ReverseOsmosisCostModel": "converters.water.desal:ReverseOsmosisCostModel",
        "SimpleAmmoniaPerformanceModel": "converters.ammonia:SimpleAmmoniaPerformanceModel",
        "SimpleAmmoniaCostModel": "converters.ammonia:SimpleAmmoniaCostModel",
        "AmmoniaSynLoopPerformanceModel": "converters.ammonia:AmmoniaSynLoopPerformanceModel",
        "AmmoniaSynLoopCostModel": "converters.ammonia:AmmoniaSynLoopCostModel",
        "SteelPerformanceModel": "converters.steel:SteelPerformanceModel",
        "SteelCostAndFinancialModel": "converters.steel:SteelCostAndFinancialModel",
        "SMRMethanolPlantPerformanceModel": "converters.methanol:SMRMethanolPlantPerformanceModel",
        "SMRMethanolPlantCostModel": "converters.methanol:SMRMethanolPlantCostModel",
        "SMRMethanolPlantFinanceModel": "converters.methanol:SMRMethanolPlantFinanceModel",
        "CO2HMethanolPlantPerformanceModel": "converters.methanol:CO2HMethanolPlantPerformanceModel",
        "CO2HMethanolPlantCostModel": "converters.methanol:CO2HMethanolPlantCostModel",
        "CO2HMethanolPlantFinanceModel": "converters.methanol:CO2HMethanolPlantFinanceModel",
        "DOCPerformanceModel": "converters.co2.marine:DOCPerformanceModel",
        "DOCCostModel": "converters.co2.marine:DOCCostModel",
        "OAEPerformanceModel": "converters.co2.marine:OAEPerformanceModel",
        "OAECostModel": "converters.co2.marine:OAECostModel",
        "OAECostAndFinancialModel": "converters.co2.marine:OAECostAndFinancialModel",
        "NaturalGeoH2PerformanceModel": "converters.hydrogen.geologic:NaturalGeoH2PerformanceModel",
        "StimulatedGeoH2PerformanceModel": "converters.hydrogen.geologic:StimulatedGeoH2PerformanceModel",
        "GeoH2SubsurfaceCostModel": "converters.hydrogen.geologic:GeoH2SubsurfaceCostModel",
        "AspenGeoH2SurfacePerformanceModel": "converters.hydrogen.geologic:AspenGeoH2SurfacePerformanceModel",
        "AspenGeoH2SurfaceCostModel": "converters.hydrogen.geologic:AspenGeoH2SurfaceCostModel",
        "NaturalGasPerformanceModel": "converters.natural_gas:NaturalGasPerformanceModel",
        "QuinnNuclearPerformanceModel": "converters.nuclear:QuinnNuclearPerformanceModel",
        "QuinnNuclearCostModel": "converters.nuclear:QuinnNuclearCostModel",
        "NaturalGasCostModel": "converters.natural_gas:NaturalGasCostModel",
        # Transport
        "cable": "transporters:CablePerformanceModel",
        "pipe": "transporters:PipePerformanceModel",
        "GenericCombinerPerformanceModel": "transporters:GenericCombinerPerformanceModel",
        "GenericSplitterPerformanceModel": "transporters:GenericSplitterPerformanceModel",
        "GenericTransporterPerformanceModel": "transporters:GenericTransporterPerformanceModel",
        "IronTransportPerformanceComponent": "converters.iron:IronTransportPerformanceComponent",
        "IronTransportCostComponent": "converters.iron:IronTransportCostComponent",
        # Simple Summers
        "GenericSummerPerformanceModel": "transporters:GenericSummerPerformanceModel",
        # Storage
        "PySAMBatteryPerformanceModel": "storage.battery:PySAMBatteryPerformanceModel",
        "StoragePerformanceModel": "storage:StoragePerformanceModel",
        "StorageAutoSizingModel": "storage:StorageAutoSizingModel",
        "LinedRockCavernStorageCostModel": "storage.hydrogen:LinedRockCavernStorageCostModel",
        "CompressedGasStorageCostModel": "storage.hydrogen:CompressedGasStorageCostModel",
        "SaltCavernStorageCostModel": "storage.hydrogen:SaltCavernStorageCostModel",
        "MCHTOLStorageCostModel": "storage.hydrogen:MCHTOLStorageCostModel",
        "PipeStorageCostModel": "storage.hydrogen:PipeStorageCostModel",
        "ATBBatteryCostModel": "storage.battery:ATBBatteryCostModel",
        "GenericStorageCostModel": "storage:GenericStorageCostModel",
        # Control
        "SimpleStorageOpenLoopController": "control.control_strategies.storage:SimpleStorageOpenLoopController",
        "DemandOpenLoopStorageController": "control.control_strategies.storage:DemandOpenLoopStorageController",
        "PeakLoadManagementHeuristicOpenLoopStorageController": "control.control_strategies.storage:PeakLoadManagementHeuristicOpenLoopStorageController",
        "PeakLoadManagementOptimizedStorageController": "control.control_strategies.storage:PeakLoadManagementOptimizedStorageController",
        "HeuristicLoadFollowingStorageController": "control.control_strategies.storage:HeuristicLoadFollowingStorageController",
        "OptimizedDispatchStorageController": "control.control_strategies.storage:OptimizedDispatchStorageController",
        "GenericDemandComponent": "demand:GenericDemandComponent",
        "FlexibleDemandComponent": "demand:FlexibleDemandComponent",
        # Dispatch
        "PyomoDispatchGenericConverter": "control.control_rules.converters:PyomoDispatchGenericConverter",
        "PyomoRuleStorageBaseclass": "control.control_rules.storage:PyomoRuleStorageBaseclass",
        "PyomoRuleStorageMinOperatingCosts": "control.control_rules.storage:PyomoRuleStorageMinOperatingCosts",
        "PyomoDispatchGenericConverterMinOperatingCosts": "control.control_rules.converters:PyomoDispatchGenericConverterMinOperatingCosts",
        # Feedstock
        "FeedstockPerformanceModel": "feedstocks:FeedstockPerformanceModel",
        "FeedstockCostModel": "feedstocks:FeedstockCostModel",
        "EIANaturalGasFeedstockCostModel": "feedstocks:EIANaturalGasFeedstockCostModel",
        # Grid
        "GridPerformanceModel": "converters.grid:GridPerformanceModel",
        "GridCostModel": "converters.grid:GridCostModel",
        # Finance
        "ProFastLCO": "finances:ProFastLCO",
        "ProFastNPV": "finances:ProFastNPV",
        "NumpyFinancialNPV": "finances:NumpyFinancialNPV",
        # Dummy components for multivariable stream demonstrations
        "SimpleGasProducerPerformance": "converters.natural_gas:SimpleGasProducerPerformance",
        "SimpleGasProducerCost": "converters.natural_gas:SimpleGasProducerCost",
        "SimpleGasConsumerPerformance": "converters.natural_gas:SimpleGasConsumerPerformance",
        "SimpleGasConsumerCost": "converters.natural_gas:SimpleGasConsumerCost",
        "GasStreamCombinerPerformanceModel": "transporters:GasStreamCombinerPerformanceModel",
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
