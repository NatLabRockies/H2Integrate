from attrs import field, define

from h2integrate.core.utilities import merge_shared_inputs
from h2integrate.core.validators import must_equal
from h2integrate.converters.co2.marine.marine_carbon_capture_baseclass import (
    MarineCarbonCaptureCostBaseClass,
    MarineCarbonCapturePerformanceConfig,
    MarineCarbonCapturePerformanceBaseClass,
)


try:
    from mcm.capture import echem_mcc
except ImportError:
    echem_mcc = None


def setup_electrodialysis_inputs(config):
    """Helper function to set up electrodialysis inputs from the configuration."""
    return echem_mcc.ElectrodialysisInputs(
        P_ed1=config.power_single_ed_w,
        Q_ed1=config.flow_rate_single_ed_m3s,
        N_edMin=config.number_ed_min,
        N_edMax=config.number_ed_max,
        E_HCl=config.E_HCl,
        E_NaOH=config.E_NaOH,
        y_ext=config.y_ext,
        y_pur=config.y_pur,
        y_vac=config.y_vac,
        frac_EDflow=config.frac_ed_flow,
        use_storage_tanks=config.use_storage_tanks,
        store_hours=config.store_hours,
    )


@define(kw_only=True)
class DOCPerformanceConfig(MarineCarbonCapturePerformanceConfig):
    """Extended configuration for Direct Ocean Capture (DOC) performance model.

    Attributes:
        power_single_ed_w (float): Power requirement of a single electrodialysis (ED) unit (watts).
        flow_rate_single_ed_m3s (float): Flow rate of a single ED unit (cubic meters per second).
        E_HCl (float): Energy required per mole of HCl produced (kWh/mol).
        E_NaOH (float): Energy required per mole of NaOH produced (kWh/mol).
        y_ext (float): CO2 extraction efficiency (unitless fraction).
        y_pur (float): CO2 purity in the product stream (unitless fraction).
        y_vac (float): Vacuum pump efficiency (unitless fraction).
        frac_ed_flow (float): Fraction of intake flow directed to electrodialysis (unitless).
        temp_C (float): Temperature of input seawater (°C).
        sal (float): Salinity of seawater (ppt).
        dic_i (float): Initial dissolved inorganic carbon (mol/L).
        pH_i (float): Initial pH of seawater.
        initial_tank_volume_m3 (float): Initial volume of the tank (m³).
    """

    power_single_ed_w: float = field()
    flow_rate_single_ed_m3s: float = field()
    E_HCl: float = field()
    E_NaOH: float = field()
    y_ext: float = field()
    y_pur: float = field()
    y_vac: float = field()
    frac_ed_flow: float = field()
    temp_C: float = field()
    sal: float = field()
    dic_i: float = field()
    pH_i: float = field()
    initial_tank_volume_m3: float = field()


class DOCPerformanceModel(MarineCarbonCapturePerformanceBaseClass):
    """
    An OpenMDAO component for modeling the performance of a Direct Ocean Capture (DOC) plant.

    Extends:
        MarineCarbonCapturePerformanceBaseClass

    Computes:
        - co2_out: Hourly CO2 capture rate (kg/h)
        - co2_capture_mtpy: Annual CO2 capture (t/year)
        - total_tank_volume_m3: Total tank volume (m^3)
        - plant_mCC_capacity_mtph: Plant carbon capture capacity (t/h)
    """

    def initialize(self):
        super().initialize()
        if echem_mcc is None:
            raise ImportError(
                "The `mcm` package is required to use the Direct Ocean Capture model. "
                "Install it via:\n"
                "pip install git+https://github.com/NREL/MarineCarbonManagement.git"
            )

    def setup(self):
        self.config = DOCPerformanceConfig.from_dict(
            merge_shared_inputs(self.options["tech_config"]["model_inputs"], "performance")
        )
        super().setup()
        self.add_output(
            "plant_mCC_capacity_mtph",
            val=0.0,
            units="t/h",
            desc="Theoretical maximum CO₂ capture (t/h)",
        )
        self.add_output(
            "total_tank_volume_m3",
            val=0.0,
            units="m**3",
        )

    def compute(self, inputs, outputs):
        ED_inputs = setup_electrodialysis_inputs(self.config)

        co_2_outputs, range_outputs, ed_outputs = echem_mcc.run_electrodialysis_physics_model(
            power_profile_w=inputs["electricity_in"],
            initial_tank_volume_m3=self.config.initial_tank_volume_m3,
            electrodialysis_config=ED_inputs,
            pump_config=echem_mcc.PumpInputs(),
            seawater_config=echem_mcc.SeaWaterInputs(
                sal=self.config.sal,
                tempC=self.config.temp_C,
                dic_i=self.config.dic_i,
                pH_i=self.config.pH_i,
            ),
            save_outputs=True,
            save_plots=True,
            output_dir=self.options["driver_config"]["general"]["folder_output"],
            plot_range=[3910, 4030],
        )

        outputs["co2_out"] = ed_outputs.ED_outputs["mCC"] * 1000
        outputs["co2_capture_mtpy"] = max(ed_outputs.mCC_yr, 1e-6)  # Must be >0
        outputs["total_tank_volume_m3"] = range_outputs.V_aT_max + range_outputs.V_bT_max
        outputs["plant_mCC_capacity_mtph"] = max(range_outputs.S1["mCC"])


@define(kw_only=True)
class DOCCostModelConfig(DOCPerformanceConfig):
    """Configuration for the DOC cost model.

    Attributes:
        infrastructure_type (str): Type of infrastructure (e.g., "desal", "swCool", "new"").
        cost_year (int): dollar year corresponding to cost values
    """

    infrastructure_type: str = field()
    cost_year: int = field(default=2023, converter=int, validator=must_equal(2023))


class DOCCostModel(MarineCarbonCaptureCostBaseClass):
    """OpenMDAO component for computing capital (CapEx) and operational (OpEx) costs of a
        direct ocean capture (DOC) system.

    Computes:
        - CapEx (USD)
        - OpEx (USD/year)
    """

    def initialize(self):
        super().initialize()
        if echem_mcc is None:
            raise ImportError(
                "The `mcm` package is required to use the Direct Ocean Capture model. "
                "Install it via:\n"
                "pip install git+https://github.com/NREL/MarineCarbonManagement.git"
            )

    def setup(self):
        self.config = DOCCostModelConfig.from_dict(
            merge_shared_inputs(self.options["tech_config"]["model_inputs"], "cost")
        )

        super().setup()

        self.add_input(
            "total_tank_volume_m3",
            val=0.0,
            units="m**3",
        )

        self.add_input(
            "plant_mCC_capacity_mtph",
            val=0.0,
            units="t/h",
            desc="Theoretical plant maximum CO₂ capture (t/h)",
        )

    def compute(self, inputs, outputs, discrete_inputs, discrete_outputs):
        # Set up electrodialysis inputs
        ED_inputs = setup_electrodialysis_inputs(self.config)

        res = echem_mcc.electrodialysis_cost_model(
            echem_mcc.ElectrodialysisCostInputs(
                electrodialysis_inputs=ED_inputs,
                mCC_yr=inputs["co2_capture_mtpy"],
                total_tank_volume=inputs["total_tank_volume_m3"],
                infrastructure_type=self.config.infrastructure_type,
                max_theoretical_mCC=inputs["plant_mCC_capacity_mtph"],
            )
        )

        # Calculate CapEx
        outputs["CapEx"] = res.initial_capital_cost
        outputs["OpEx"] = res.yearly_operational_cost
