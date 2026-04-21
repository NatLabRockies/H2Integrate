from h2integrate.resource.river import RiverResource
from h2integrate.resource.tidal import TidalResource
from h2integrate.core.feedstocks import FeedstockCostModel, FeedstockPerformanceModel
from h2integrate.transporters.pipe import PipePerformanceModel
from h2integrate.transporters.cable import CablePerformanceModel
from h2integrate.converters.grid.grid import GridCostModel, GridPerformanceModel
from h2integrate.finances.profast_lco import ProFastLCO
from h2integrate.finances.profast_npv import ProFastNPV
from h2integrate.demand.generic_demand import GenericDemandComponent
from h2integrate.converters.steel.steel import SteelPerformanceModel, SteelCostAndFinancialModel
from h2integrate.converters.wind.floris import FlorisWindPlantPerformanceModel
from h2integrate.demand.flexible_demand import FlexibleDemandComponent
from h2integrate.converters.wind.wind_pysam import PYSAMWindPlantPerformanceModel
from h2integrate.transporters.generic_summer import GenericSummerPerformanceModel
from h2integrate.converters.hopp.hopp_wrapper import HOPPComponent
from h2integrate.converters.solar.solar_pysam import PYSAMSolarPlantPerformanceModel
from h2integrate.finances.numpy_financial_npv import NumpyFinancialNPV
from h2integrate.resource.wind.openmeteo_wind import OpenMeteoHistoricalWindResource
from h2integrate.storage.generic_storage_cost import GenericStorageCostModel
from h2integrate.storage.hydrogen.mch_storage import MCHTOLStorageCostModel
from h2integrate.converters.wind.atb_wind_cost import ATBWindPlantCostModel
from h2integrate.storage.battery.pysam_battery import PySAMBatteryPerformanceModel
from h2integrate.transporters.generic_combiner import GenericCombinerPerformanceModel
from h2integrate.transporters.generic_splitter import GenericSplitterPerformanceModel
from h2integrate.converters.iron.iron_dri_plant import (
    HydrogenIronReductionPlantCostComponent,
    NaturalGasIronReductionPlantCostComponent,
    HydrogenIronReductionPlantPerformanceComponent,
    NaturalGasIronReductionPlantPerformanceComponent,
)
from h2integrate.converters.iron.iron_transport import (
    IronTransportCostComponent,
    IronTransportPerformanceComponent,
)
from h2integrate.converters.nitrogen.simple_ASU import SimpleASUCostModel, SimpleASUPerformanceModel
from h2integrate.converters.wind.wind_plant_ard import ArdWindPlantModel
from h2integrate.resource.solar.openmeteo_solar import OpenMeteoHistoricalSolarResource
from h2integrate.converters.hydrogen.h2_fuel_cell import (
    H2FuelCellCostModel,
    LinearH2FuelCellPerformanceModel,
)
from h2integrate.converters.hydrogen.wombat_model import WOMBATElectrolyzerModel
from h2integrate.converters.nuclear.nuclear_plant import (
    QuinnNuclearCostModel,
    QuinnNuclearPerformanceModel,
)
from h2integrate.converters.steel.steel_eaf_plant import (
    HydrogenEAFPlantCostComponent,
    NaturalGasEAFPlantCostComponent,
    HydrogenEAFPlantPerformanceComponent,
    NaturalGasEAFPlantPerformanceComponent,
)
from h2integrate.storage.battery.atb_battery_cost import ATBBatteryCostModel
from h2integrate.storage.hydrogen.h2_storage_cost import (
    PipeStorageCostModel,
    SaltCavernStorageCostModel,
    LinedRockCavernStorageCostModel,
)
from h2integrate.transporters.gas_stream_combiner import GasStreamCombinerPerformanceModel
from h2integrate.transporters.generic_transporter import GenericTransporterPerformanceModel
from h2integrate.converters.generic_converter_cost import GenericConverterCostModel
from h2integrate.converters.iron.humbert_ewin_perf import HumbertEwinPerformanceComponent
from h2integrate.storage.storage_performance_model import StoragePerformanceModel
from h2integrate.converters.ammonia.ammonia_synloop import (
    AmmoniaSynLoopCostModel,
    AmmoniaSynLoopPerformanceModel,
)
from h2integrate.converters.water_power.tidal_pysam import PySAMTidalPerformanceModel
from h2integrate.storage.simple_storage_auto_sizing import StorageAutoSizingModel
from h2integrate.converters.water.desal.desalination import (
    ReverseOsmosisCostModel,
    ReverseOsmosisPerformanceModel,
)
from h2integrate.resource.wind.nlr_developer_wtk_api import WTKNLRDeveloperAPIWindResource
from h2integrate.converters.hydrogen.basic_cost_model import BasicElectrolyzerCostModel
from h2integrate.converters.hydrogen.pem_electrolyzer import ECOElectrolyzerPerformanceModel
from h2integrate.converters.solar.atb_res_com_pv_cost import ATBResComPVCostModel
from h2integrate.converters.solar.atb_utility_pv_cost import ATBUtilityPVCostModel
from h2integrate.converters.iron.martin_mine_cost_model import MartinIronMineCostComponent
from h2integrate.converters.iron.martin_mine_perf_model import MartinIronMinePerformanceComponent
from h2integrate.converters.methanol.smr_methanol_plant import (
    SMRMethanolPlantCostModel,
    SMRMethanolPlantFinanceModel,
    SMRMethanolPlantPerformanceModel,
)
from h2integrate.converters.ammonia.simple_ammonia_model import (
    SimpleAmmoniaCostModel,
    SimpleAmmoniaPerformanceModel,
)
from h2integrate.converters.iron.humbert_stinn_ewin_cost import HumbertStinnEwinCostComponent
from h2integrate.converters.methanol.co2h_methanol_plant import (
    CO2HMethanolPlantCostModel,
    CO2HMethanolPlantFinanceModel,
    CO2HMethanolPlantPerformanceModel,
)
from h2integrate.converters.natural_gas.natural_gas_cc_ct import (
    NaturalGasCostModel,
    NaturalGasPerformanceModel,
)
from h2integrate.converters.water_power.pysam_marine_cost import PySAMMarineCostModel
from h2integrate.converters.hydrogen.singlitico_cost_model import SingliticoCostModel
from h2integrate.converters.co2.marine.direct_ocean_capture import DOCCostModel, DOCPerformanceModel
from h2integrate.converters.hydrogen.steam_methane_reformer import (
    SteamMethaneReformerCostModel,
    SteamMethaneReformerPerformanceModel,
)
from h2integrate.converters.natural_gas.dummy_gas_components import (
    SimpleGasConsumerCost,
    SimpleGasProducerCost,
    SimpleGasConsumerPerformance,
    SimpleGasProducerPerformance,
)
from h2integrate.converters.hydrogen.geologic.mathur_modified import GeoH2SubsurfaceCostModel
from h2integrate.resource.solar.nlr_developer_goes_api_models import (
    GOESTMYSolarAPI,
    GOESConusSolarAPI,
    GOESFullDiscSolarAPI,
    GOESAggregatedSolarAPI,
)
from h2integrate.converters.water_power.hydro_plant_run_of_river import (
    RunOfRiverHydroCostModel,
    RunOfRiverHydroPerformanceModel,
)
from h2integrate.resource.solar.nlr_developer_himawari_api_models import (
    Himawari7SolarAPI,
    Himawari8SolarAPI,
    HimawariTMYSolarAPI,
)
from h2integrate.converters.hydrogen.geologic.simple_natural_geoh2 import (
    NaturalGeoH2PerformanceModel,
)
from h2integrate.control.control_rules.converters.generic_converter import (
    PyomoDispatchGenericConverter,
)
from h2integrate.converters.co2.marine.ocean_alkalinity_enhancement import (
    OAECostModel,
    OAEPerformanceModel,
    OAECostAndFinancialModel,
)
from h2integrate.converters.hydrogen.custom_electrolyzer_cost_model import (
    CustomElectrolyzerCostModel,
)
from h2integrate.converters.hydrogen.geologic.aspen_surface_processing import (
    AspenGeoH2SurfaceCostModel,
    AspenGeoH2SurfacePerformanceModel,
)
from h2integrate.converters.hydrogen.geologic.templeton_serpentinization import (
    StimulatedGeoH2PerformanceModel,
)
from h2integrate.control.control_rules.storage.pyomo_storage_rule_baseclass import (
    PyomoRuleStorageBaseclass,
)
from h2integrate.resource.solar.nlr_developer_meteosat_prime_meridian_models import (
    MeteosatPrimeMeridianSolarAPI,
    MeteosatPrimeMeridianTMYSolarAPI,
)
from h2integrate.control.control_strategies.storage.heuristic_pyomo_controller import (
    HeuristicLoadFollowingStorageController,
)
from h2integrate.control.control_strategies.storage.optimized_pyomo_controller import (
    OptimizedDispatchStorageController,
)
from h2integrate.control.control_strategies.storage.simple_openloop_controller import (
    SimpleStorageOpenLoopController,
)
from h2integrate.control.control_rules.storage.pyomo_storage_rule_min_operating_cost import (
    PyomoRuleStorageMinOperatingCosts,
)
from h2integrate.control.control_rules.converters.generic_converter_min_operating_cost import (
    PyomoDispatchGenericConverterMinOperatingCosts,
)
from h2integrate.control.control_strategies.storage.demand_openloop_storage_controller import (
    DemandOpenLoopStorageController,
)


supported_models = {
    # Resources
    "TidalResource": TidalResource,
    "RiverResource": RiverResource,
    "WTKNLRDeveloperAPIWindResource": WTKNLRDeveloperAPIWindResource,
    "OpenMeteoHistoricalWindResource": OpenMeteoHistoricalWindResource,
    "OpenMeteoHistoricalSolarResource": OpenMeteoHistoricalSolarResource,
    "GOESAggregatedSolarAPI": GOESAggregatedSolarAPI,
    "GOESConusSolarAPI": GOESConusSolarAPI,
    "GOESFullDiscSolarAPI": GOESFullDiscSolarAPI,
    "GOESTMYSolarAPI": GOESTMYSolarAPI,
    "MeteosatPrimeMeridianSolarAPI": MeteosatPrimeMeridianSolarAPI,
    "MeteosatPrimeMeridianTMYSolarAPI": MeteosatPrimeMeridianTMYSolarAPI,
    "Himawari7SolarAPI": Himawari7SolarAPI,
    "Himawari8SolarAPI": Himawari8SolarAPI,
    "HimawariTMYSolarAPI": HimawariTMYSolarAPI,
    # Converters
    "GenericConverterCostModel": GenericConverterCostModel,
    "ATBWindPlantCostModel": ATBWindPlantCostModel,
    "PYSAMWindPlantPerformanceModel": PYSAMWindPlantPerformanceModel,
    "FlorisWindPlantPerformanceModel": FlorisWindPlantPerformanceModel,
    "ArdWindPlantModel": ArdWindPlantModel,
    "PYSAMSolarPlantPerformanceModel": PYSAMSolarPlantPerformanceModel,
    "ATBUtilityPVCostModel": ATBUtilityPVCostModel,
    "ATBResComPVCostModel": ATBResComPVCostModel,
    "PySAMTidalPerformanceModel": PySAMTidalPerformanceModel,
    "PySAMMarineCostModel": PySAMMarineCostModel,
    "RunOfRiverHydroPerformanceModel": RunOfRiverHydroPerformanceModel,
    "RunOfRiverHydroCostModel": RunOfRiverHydroCostModel,
    "ECOElectrolyzerPerformanceModel": ECOElectrolyzerPerformanceModel,
    "SingliticoCostModel": SingliticoCostModel,
    "BasicElectrolyzerCostModel": BasicElectrolyzerCostModel,
    "CustomElectrolyzerCostModel": CustomElectrolyzerCostModel,
    "WOMBATElectrolyzerModel": WOMBATElectrolyzerModel,
    "LinearH2FuelCellPerformanceModel": LinearH2FuelCellPerformanceModel,
    "H2FuelCellCostModel": H2FuelCellCostModel,
    "SteamMethaneReformerPerformanceModel": SteamMethaneReformerPerformanceModel,
    "SteamMethaneReformerCostModel": SteamMethaneReformerCostModel,
    "SimpleASUCostModel": SimpleASUCostModel,
    "SimpleASUPerformanceModel": SimpleASUPerformanceModel,
    "HOPPComponent": HOPPComponent,
    "MartinIronMinePerformanceComponent": MartinIronMinePerformanceComponent,  # standalone model
    "MartinIronMineCostComponent": MartinIronMineCostComponent,  # standalone model
    "NaturalGasIronReductionPlantPerformanceComponent": NaturalGasIronReductionPlantPerformanceComponent,  # noqa: E501
    "NaturalGasIronReductionPlantCostComponent": NaturalGasIronReductionPlantCostComponent,  # standalone model  # noqa: E501
    "HydrogenIronReductionPlantPerformanceComponent": HydrogenIronReductionPlantPerformanceComponent,  # noqa: E501
    "HydrogenIronReductionPlantCostComponent": HydrogenIronReductionPlantCostComponent,  # standalone model  # noqa: E501
    "HumbertEwinPerformanceComponent": HumbertEwinPerformanceComponent,
    "HumbertStinnEwinCostComponent": HumbertStinnEwinCostComponent,
    "NaturalGasEAFPlantPerformanceComponent": NaturalGasEAFPlantPerformanceComponent,
    "NaturalGasEAFPlantCostComponent": NaturalGasEAFPlantCostComponent,  # standalone model
    "HydrogenEAFPlantPerformanceComponent": HydrogenEAFPlantPerformanceComponent,
    "HydrogenEAFPlantCostComponent": HydrogenEAFPlantCostComponent,  # standalone model
    "ReverseOsmosisPerformanceModel": ReverseOsmosisPerformanceModel,
    "ReverseOsmosisCostModel": ReverseOsmosisCostModel,
    "SimpleAmmoniaPerformanceModel": SimpleAmmoniaPerformanceModel,
    "SimpleAmmoniaCostModel": SimpleAmmoniaCostModel,
    "AmmoniaSynLoopPerformanceModel": AmmoniaSynLoopPerformanceModel,
    "AmmoniaSynLoopCostModel": AmmoniaSynLoopCostModel,
    "SteelPerformanceModel": SteelPerformanceModel,
    "SteelCostAndFinancialModel": SteelCostAndFinancialModel,
    "SMRMethanolPlantPerformanceModel": SMRMethanolPlantPerformanceModel,
    "SMRMethanolPlantCostModel": SMRMethanolPlantCostModel,
    "SMRMethanolPlantFinanceModel": SMRMethanolPlantFinanceModel,
    "CO2HMethanolPlantPerformanceModel": CO2HMethanolPlantPerformanceModel,
    "CO2HMethanolPlantCostModel": CO2HMethanolPlantCostModel,
    "CO2HMethanolPlantFinanceModel": CO2HMethanolPlantFinanceModel,
    "DOCPerformanceModel": DOCPerformanceModel,
    "DOCCostModel": DOCCostModel,
    "OAEPerformanceModel": OAEPerformanceModel,
    "OAECostModel": OAECostModel,
    "OAECostAndFinancialModel": OAECostAndFinancialModel,
    "NaturalGeoH2PerformanceModel": NaturalGeoH2PerformanceModel,
    "StimulatedGeoH2PerformanceModel": StimulatedGeoH2PerformanceModel,
    "GeoH2SubsurfaceCostModel": GeoH2SubsurfaceCostModel,
    "AspenGeoH2SurfacePerformanceModel": AspenGeoH2SurfacePerformanceModel,
    "AspenGeoH2SurfaceCostModel": AspenGeoH2SurfaceCostModel,
    "NaturalGasPerformanceModel": NaturalGasPerformanceModel,
    "QuinnNuclearPerformanceModel": QuinnNuclearPerformanceModel,
    "QuinnNuclearCostModel": QuinnNuclearCostModel,
    "NaturalGasCostModel": NaturalGasCostModel,
    # Transport
    "cable": CablePerformanceModel,
    "pipe": PipePerformanceModel,
    "GenericCombinerPerformanceModel": GenericCombinerPerformanceModel,
    "GenericSplitterPerformanceModel": GenericSplitterPerformanceModel,
    "GenericTransporterPerformanceModel": GenericTransporterPerformanceModel,
    "IronTransportPerformanceComponent": IronTransportPerformanceComponent,
    "IronTransportCostComponent": IronTransportCostComponent,
    # Simple Summers
    "GenericSummerPerformanceModel": GenericSummerPerformanceModel,
    # Storage
    "PySAMBatteryPerformanceModel": PySAMBatteryPerformanceModel,
    "StoragePerformanceModel": StoragePerformanceModel,
    "StorageAutoSizingModel": StorageAutoSizingModel,
    "LinedRockCavernStorageCostModel": LinedRockCavernStorageCostModel,
    "SaltCavernStorageCostModel": SaltCavernStorageCostModel,
    "MCHTOLStorageCostModel": MCHTOLStorageCostModel,
    "PipeStorageCostModel": PipeStorageCostModel,
    "ATBBatteryCostModel": ATBBatteryCostModel,
    "GenericStorageCostModel": GenericStorageCostModel,
    # Control
    "SimpleStorageOpenLoopController": SimpleStorageOpenLoopController,
    "DemandOpenLoopStorageController": DemandOpenLoopStorageController,
    "HeuristicLoadFollowingStorageController": HeuristicLoadFollowingStorageController,
    "OptimizedDispatchStorageController": OptimizedDispatchStorageController,
    "GenericDemandComponent": GenericDemandComponent,
    "FlexibleDemandComponent": FlexibleDemandComponent,
    # Dispatch
    "PyomoDispatchGenericConverter": PyomoDispatchGenericConverter,
    "PyomoRuleStorageBaseclass": PyomoRuleStorageBaseclass,
    "PyomoRuleStorageMinOperatingCosts": PyomoRuleStorageMinOperatingCosts,
    "PyomoDispatchGenericConverterMinOperatingCosts": PyomoDispatchGenericConverterMinOperatingCosts,  # noqa: E501
    # Feedstock
    "FeedstockPerformanceModel": FeedstockPerformanceModel,
    "FeedstockCostModel": FeedstockCostModel,
    # Grid
    "GridPerformanceModel": GridPerformanceModel,
    "GridCostModel": GridCostModel,
    # Finance
    "ProFastLCO": ProFastLCO,
    "ProFastNPV": ProFastNPV,
    "NumpyFinancialNPV": NumpyFinancialNPV,
    # Dummy components for multivariable stream demonstrations
    "SimpleGasProducerPerformance": SimpleGasProducerPerformance,
    "SimpleGasProducerCost": SimpleGasProducerCost,
    "SimpleGasConsumerPerformance": SimpleGasConsumerPerformance,
    "SimpleGasConsumerCost": SimpleGasConsumerCost,
    "GasStreamCombinerPerformanceModel": GasStreamCombinerPerformanceModel,
}


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
