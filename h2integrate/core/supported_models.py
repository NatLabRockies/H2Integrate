from h2integrate.resource.river import RiverResource
from h2integrate.core.feedstocks import FeedstockCostModel, FeedstockPerformanceModel
from h2integrate.transporters.pipe import PipePerformanceModel
from h2integrate.transporters.cable import CablePerformanceModel
from h2integrate.converters.grid.grid import GridCostModel, GridPerformanceModel
from h2integrate.finances.profast_lco import ProFastLCO
from h2integrate.finances.profast_npv import ProFastNPV
from h2integrate.converters.steel.steel import SteelPerformanceModel, SteelCostAndFinancialModel
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
from h2integrate.storage.hydrogen.tank_baseclass import (
    HydrogenTankCostModel,
    HydrogenTankPerformanceModel,
)
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
    "river_resource": RiverResource,
    "wind_toolkit_v2_api": WTKNRELDeveloperAPIWindResource,
    "openmeteo_wind_api": OpenMeteoHistoricalWindResource,
    "goes_aggregated_solar_v4_api": GOESAggregatedSolarAPI,
    "goes_conus_solar_v4_api": GOESConusSolarAPI,
    "goes_fulldisc_solar_v4_api": GOESFullDiscSolarAPI,
    "goes_tmy_solar_v4_api": GOESTMYSolarAPI,
    "meteosat_solar_v4_api": MeteosatPrimeMeridianSolarAPI,
    "meteosat_tmy_solar_v4_api": MeteosatPrimeMeridianTMYSolarAPI,
    "himawari7_solar_v3_api": Himawari7SolarAPI,
    "himawari8_solar_v3_api": Himawari8SolarAPI,
    "himawari_tmy_solar_v3_api": HimawariTMYSolarAPI,
    # Converters
    "atb_wind_cost": ATBWindPlantCostModel,
    "pysam_wind_plant_performance": PYSAMWindPlantPerformanceModel,
    "pysam_solar_plant_performance": PYSAMSolarPlantPerformanceModel,
    "atb_utility_pv_cost": ATBUtilityPVCostModel,
    "atb_comm_res_pv_cost": ATBResComPVCostModel,
    "run_of_river_hydro_performance": RunOfRiverHydroPerformanceModel,
    "run_of_river_hydro_cost": RunOfRiverHydroCostModel,
    "eco_pem_electrolyzer_performance": ECOElectrolyzerPerformanceModel,
    "singlitico_electrolyzer_cost": SingliticoCostModel,
    "basic_electrolyzer_cost": BasicElectrolyzerCostModel,
    "custom_electrolyzer_cost": CustomElectrolyzerCostModel,
    "wombat": WOMBATElectrolyzerModel,
    "simple_ASU_cost": SimpleASUCostModel,
    "simple_ASU_performance": SimpleASUPerformanceModel,
    "hopp": HOPPComponent,
    "iron": IronComponent,
    "iron_mine_performance": IronMinePerformanceComponent,
    "iron_mine_cost": IronMineCostComponent,
    "iron_plant_performance": IronPlantPerformanceComponent,
    "iron_plant_cost": IronPlantCostComponent,
    "iron_mine_performance_martin": MartinIronMinePerformanceComponent,  # standalone model
    "iron_mine_cost_martin": MartinIronMineCostComponent,  # standalone model
    "ng_dri_performance_rosner": NaturalGasIronReductionPlantPerformanceComponent,
    "ng_dri_cost_rosner": NaturalGasIronReductionPlantCostComponent,  # standalone model
    "h2_dri_performance_rosner": HydrogenIronReductionPlantPerformanceComponent,
    "h2_dri_cost_rosner": HydrogenIronReductionPlantCostComponent,  # standalone model
    "ng_eaf_performance_rosner": NaturalGasEAFPlantPerformanceComponent,
    "ng_eaf_cost_rosner": NaturalGasEAFPlantCostComponent,  # standalone model
    "h2_eaf_performance_rosner": HydrogenEAFPlantPerformanceComponent,
    "h2_eaf_cost_rosner": HydrogenEAFPlantCostComponent,  # standalone model
    "reverse_osmosis_desalination_performance": ReverseOsmosisPerformanceModel,
    "reverse_osmosis_desalination_cost": ReverseOsmosisCostModel,
    "simple_ammonia_performance": SimpleAmmoniaPerformanceModel,
    "simple_ammonia_cost": SimpleAmmoniaCostModel,
    "synloop_ammonia_performance": AmmoniaSynLoopPerformanceModel,
    "synloop_ammonia_cost": AmmoniaSynLoopCostModel,
    "steel_performance": SteelPerformanceModel,
    "steel_cost": SteelCostAndFinancialModel,
    "smr_methanol_plant_performance": SMRMethanolPlantPerformanceModel,
    "smr_methanol_plant_cost": SMRMethanolPlantCostModel,
    "smr_methanol_plant_financial": SMRMethanolPlantFinanceModel,
    "co2h_methanol_plant_performance": CO2HMethanolPlantPerformanceModel,
    "co2h_methanol_plant_cost": CO2HMethanolPlantCostModel,
    "co2h_methanol_plant_financial": CO2HMethanolPlantFinanceModel,
    "direct_ocean_capture_performance": DOCPerformanceModel,
    "direct_ocean_capture_cost": DOCCostModel,
    "ocean_alkalinity_enhancement_performance": OAEPerformanceModel,
    "ocean_alkalinity_enhancement_cost": OAECostModel,
    "ocean_alkalinity_enhancement_cost_financial": OAECostAndFinancialModel,
    "simple_natural_geoh2_performance": NaturalGeoH2PerformanceModel,
    "templeton_serpentinization_geoh2_performance": StimulatedGeoH2PerformanceModel,
    "mathur_modified_geoh2_cost": GeoH2SubsurfaceCostModel,
    "aspen_geoh2_performance": AspenGeoH2SurfacePerformanceModel,
    "aspen_geoh2_cost": AspenGeoH2SurfaceCostModel,
    "natural_gas_performance": NaturalGasPerformanceModel,
    "natural_gas_cost": NaturalGasCostModel,
    # Transport
    "cable": CablePerformanceModel,
    "pipe": PipePerformanceModel,
    "combiner_performance": GenericCombinerPerformanceModel,
    "splitter_performance": GenericSplitterPerformanceModel,
    "iron_transport_performance": IronTransportPerformanceComponent,
    "iron_transport_cost": IronTransportCostComponent,
    # Simple Summers
    "summer": GenericSummerPerformanceModel,
    # Storage
    "pysam_battery": PySAMBatteryPerformanceModel,
    "hydrogen_tank_performance": HydrogenTankPerformanceModel,
    "hydrogen_tank_cost": HydrogenTankCostModel,
    "storage_auto_sizing": StorageAutoSizingModel,
    "lined_rock_cavern_h2_storage_cost": LinedRockCavernStorageCostModel,
    "salt_cavern_h2_storage_cost": SaltCavernStorageCostModel,
    "mch_tol_h2_storage_cost": MCHTOLStorageCostModel,
    "buried_pipe_h2_storage_cost": PipeStorageCostModel,
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
        "hopp",
        "natural_gas_plant",
        "grid_buy",
    ]

    return any(tech_name.startswith(elem) for elem in electricity_producing_techs)
