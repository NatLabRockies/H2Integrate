from h2integrate.resource.river import RiverResource
from h2integrate.core.feedstocks import FeedstockCostModel, FeedstockPerformanceModel
from h2integrate.transporters.pipe import PipePerformanceModel
from h2integrate.transporters.cable import CablePerformanceModel
from h2integrate.converters.grid.grid import GridCostModel, GridPerformanceModel
from h2integrate.finances.profast_lco import ProFastLCO
from h2integrate.finances.profast_npv import ProFastNPV
from h2integrate.converters.steel.steel import SteelPerformanceModel, SteelCostAndFinancialModel
from h2integrate.converters.wind.floris import FlorisWindPlantPerformanceModel
from h2integrate.converters.iron.iron_mine import (
    IronMineCostComponent,
    IronMinePerformanceComponent,
)
from h2integrate.converters.iron.iron_plant import (
    IronPlantCostComponent,
    IronPlantPerformanceComponent,
)
from h2integrate.converters.wind.wind_pysam import PYSAMWindPlantPerformanceModel
from h2integrate.transporters.generic_summer import GenericSummerPerformanceModel
from h2integrate.converters.hopp.hopp_wrapper import HOPPComponent
from h2integrate.converters.iron.iron_wrapper import IronComponent
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
from h2integrate.storage.simple_generic_storage import SimpleGenericStorage
from h2integrate.converters.hydrogen.wombat_model import WOMBATElectrolyzerModel
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
from h2integrate.converters.ammonia.ammonia_synloop import (
    AmmoniaSynLoopCostModel,
    AmmoniaSynLoopPerformanceModel,
)
from h2integrate.storage.simple_storage_auto_sizing import StorageAutoSizingModel
from h2integrate.converters.water.desal.desalination import (
    ReverseOsmosisCostModel,
    ReverseOsmosisPerformanceModel,
)
from h2integrate.converters.hydrogen.basic_cost_model import BasicElectrolyzerCostModel
from h2integrate.converters.hydrogen.pem_electrolyzer import ECOElectrolyzerPerformanceModel
from h2integrate.converters.solar.atb_res_com_pv_cost import ATBResComPVCostModel
from h2integrate.converters.solar.atb_utility_pv_cost import ATBUtilityPVCostModel
from h2integrate.resource.wind.nrel_developer_wtk_api import WTKNRELDeveloperAPIWindResource
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
from h2integrate.converters.methanol.co2h_methanol_plant import (
    CO2HMethanolPlantCostModel,
    CO2HMethanolPlantFinanceModel,
    CO2HMethanolPlantPerformanceModel,
)
from h2integrate.converters.natural_gas.natural_gas_cc_ct import (
    NaturalGasCostModel,
    NaturalGasPerformanceModel,
)
from h2integrate.converters.hydrogen.singlitico_cost_model import SingliticoCostModel
from h2integrate.converters.co2.marine.direct_ocean_capture import DOCCostModel, DOCPerformanceModel
from h2integrate.control.control_strategies.pyomo_controllers import (
    HeuristicLoadFollowingController,
)
from h2integrate.converters.hydrogen.geologic.mathur_modified import GeoH2SubsurfaceCostModel
from h2integrate.resource.solar.nrel_developer_goes_api_models import (
    GOESTMYSolarAPI,
    GOESConusSolarAPI,
    GOESFullDiscSolarAPI,
    GOESAggregatedSolarAPI,
)
from h2integrate.converters.water_power.hydro_plant_run_of_river import (
    RunOfRiverHydroCostModel,
    RunOfRiverHydroPerformanceModel,
)
from h2integrate.converters.hydrogen.geologic.simple_natural_geoh2 import (
    NaturalGeoH2PerformanceModel,
)
from h2integrate.resource.solar.nrel_developer_himawari_api_models import (
    Himawari7SolarAPI,
    Himawari8SolarAPI,
    HimawariTMYSolarAPI,
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
from h2integrate.control.control_strategies.passthrough_openloop_controller import (
    PassThroughOpenLoopController,
)
from h2integrate.resource.solar.nrel_developer_meteosat_prime_meridian_models import (
    MeteosatPrimeMeridianSolarAPI,
    MeteosatPrimeMeridianTMYSolarAPI,
)
from h2integrate.control.control_strategies.storage.demand_openloop_controller import (
    DemandOpenLoopStorageController,
)
from h2integrate.control.control_strategies.converters.demand_openloop_controller import (
    DemandOpenLoopConverterController,
)
from h2integrate.control.control_strategies.converters.flexible_demand_openloop_controller import (
    FlexibleDemandOpenLoopConverterController,
)


supported_models = {
    # Resources
    "RiverResource": RiverResource,
    "WTKNRELDeveloperAPIWindResource": WTKNRELDeveloperAPIWindResource,
    "OpenMeteoHistoricalWindResource": OpenMeteoHistoricalWindResource,
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
    "ATBWindPlantCostModel": ATBWindPlantCostModel,
    "PYSAMWindPlantPerformanceModel": PYSAMWindPlantPerformanceModel,
    "FlorisWindPlantPerformanceModel": FlorisWindPlantPerformanceModel,
    "PYSAMSolarPlantPerformanceModel": PYSAMSolarPlantPerformanceModel,
    "ATBUtilityPVCostModel": ATBUtilityPVCostModel,
    "ATBResComPVCostModel": ATBResComPVCostModel,
    "RunOfRiverHydroPerformanceModel": RunOfRiverHydroPerformanceModel,
    "RunOfRiverHydroCostModel": RunOfRiverHydroCostModel,
    "ECOElectrolyzerPerformanceModel": ECOElectrolyzerPerformanceModel,
    "SingliticoCostModel": SingliticoCostModel,
    "BasicElectrolyzerCostModel": BasicElectrolyzerCostModel,
    "CustomElectrolyzerCostModel": CustomElectrolyzerCostModel,
    "WOMBATElectrolyzerModel": WOMBATElectrolyzerModel,
    "SimpleASUCostModel": SimpleASUCostModel,
    "SimpleASUPerformanceModel": SimpleASUPerformanceModel,
    "HOPPComponent": HOPPComponent,
    "IronComponent": IronComponent,
    "IronMinePerformanceComponent": IronMinePerformanceComponent,
    "IronMineCostComponent": IronMineCostComponent,
    "IronPlantPerformanceComponent": IronPlantPerformanceComponent,
    "IronPlantCostComponent": IronPlantCostComponent,
    "MartinIronMinePerformanceComponent": MartinIronMinePerformanceComponent,  # standalone model
    "MartinIronMineCostComponent": MartinIronMineCostComponent,  # standalone model
    "NaturalGasIronReductionPlantPerformanceComponent": NaturalGasIronReductionPlantPerformanceComponent,  # noqa: E501
    "NaturalGasIronReductionPlantCostComponent": NaturalGasIronReductionPlantCostComponent,  # standalone model  # noqa: E501
    "HydrogenIronReductionPlantPerformanceComponent": HydrogenIronReductionPlantPerformanceComponent,  # noqa: E501
    "HydrogenIronReductionPlantCostComponent": HydrogenIronReductionPlantCostComponent,  # standalone model  # noqa: E501
    "NaturalGasEAFPlantPerformanceComponent": NaturalGasEAFPlantPerformanceComponent,
    "NaturalGasEAFPlantCostComponent": NaturalGasEAFPlantCostComponent,  # standalone model
    "HydrogenEAFPlantPerformanceComponent": HydrogenEAFPlantPerformanceComponent,
    "HydrogenEAFPlantCostComponent": HydrogenEAFPlantCostComponent,  # standalone model
    "ReverseOsmosisPerformanceModel": ReverseOsmosisPerformanceModel,
    "ReverseOsmosisCostModel": ReverseOsmosisCostModel,
    "simple_ammonia_performance": SimpleAmmoniaPerformanceModel,
    "simple_ammonia_cost": SimpleAmmoniaCostModel,
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
    "NaturalGasCostModel": NaturalGasCostModel,
    # Transport
    "cable": CablePerformanceModel,
    "pipe": PipePerformanceModel,
    "combiner_performance": GenericCombinerPerformanceModel,
    "splitter_performance": GenericSplitterPerformanceModel,
    "iron_transport_performance": IronTransportPerformanceComponent,
    "iron_transport_cost": IronTransportCostComponent,
    # Simple Summers
    "GenericSummerPerformanceModel": GenericSummerPerformanceModel,
    # Storage
    "PySAMBatteryPerformanceModel": PySAMBatteryPerformanceModel,
    "StorageAutoSizingModel": StorageAutoSizingModel,
    "LinedRockCavernStorageCostModel": LinedRockCavernStorageCostModel,
    "SaltCavernStorageCostModel": SaltCavernStorageCostModel,
    "MCHTOLStorageCostModel": MCHTOLStorageCostModel,
    "PipeStorageCostModel": PipeStorageCostModel,
    "atb_battery_cost": ATBBatteryCostModel,
    "generic_storage_cost": GenericStorageCostModel,
    "simple_generic_storage": SimpleGenericStorage,
    # Control
    "pass_through_controller": PassThroughOpenLoopController,
    "demand_open_loop_storage_controller": DemandOpenLoopStorageController,
    "heuristic_load_following_controller": HeuristicLoadFollowingController,
    "demand_open_loop_converter_controller": DemandOpenLoopConverterController,
    "flexible_demand_open_loop_converter_controller": FlexibleDemandOpenLoopConverterController,
    # Dispatch
    "pyomo_dispatch_generic_converter": PyomoDispatchGenericConverter,
    "pyomo_dispatch_generic_storage": PyomoRuleStorageBaseclass,
    # Feedstock
    "feedstock_performance": FeedstockPerformanceModel,
    "feedstock_cost": FeedstockCostModel,
    # Grid
    "grid_performance": GridPerformanceModel,
    "grid_cost": GridCostModel,
    # Finance
    "ProFastComp": ProFastLCO,
    "ProFastNPV": ProFastNPV,
    "NumpyFinancialNPV": NumpyFinancialNPV,
}


def is_electricity_producer(tech_name: str) -> bool:
    """Check if a technology is an electricity producer.

    Args:
        tech_name: The name of the technology to check.
    Returns:
        True if tech_name starts with any of the known electricity producing
        tech prefixes (e.g., 'wind', 'solar', 'pv', 'grid_buy', etc.).
    Note:
        This uses prefix matching, so 'grid_buy_1' and 'grid_buy_2' would both
        be considered electricity producers. Be careful when naming technologies
        to avoid unintended matches (e.g., 'pv_battery' would be incorrectly
        identified as an electricity producer).
    """

    # add any new electricity producing technologies to this list
    electricity_producing_techs = [
        "wind",
        "solar",
        "pv",
        "river",
        "HOPPComponent",
        "natural_gas_plant",
        "grid_buy",
    ]

    return any(tech_name.startswith(elem) for elem in electricity_producing_techs)
