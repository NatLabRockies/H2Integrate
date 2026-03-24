from attrs import field, define
from mcm.capture import echem_mcc

from h2integrate.core.utilities import BaseConfig, merge_shared_inputs
from h2integrate.core.validators import gt_zero, contains, gte_zero, range_val, must_equal
from h2integrate.core.model_baseclasses import CostModelBaseClass, PerformanceModelBaseClass


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
class DOCPerformanceConfig(BaseConfig):
    """Extended configuration for Direct Ocean Capture (DOC) performance model.

    Attributes:
        number_ed_min (int): Minimum number of ED units to operate.
        number_ed_max (int): Maximum number of ED units available.
        use_storage_tanks (bool): Flag indicating whether to use storage tanks.
        store_hours (float): Number of hours of CO₂ storage capacity (hours).
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
        save_outputs (bool, optional): If true, save results to .csv files. Defaults to False.
        save_plots (bool, optional): If true, save plots of results. Defaults to False.
    """

    number_ed_min: int = field(validator=gt_zero)
    number_ed_max: int = field(validator=gt_zero)
    use_storage_tanks: bool = field()
    store_hours: float = field(validator=gte_zero)
    power_single_ed_w: float = field(validator=gte_zero)
    flow_rate_single_ed_m3s: float = field(validator=gt_zero)
    E_HCl: float = field(validator=gte_zero)
    E_NaOH: float = field(validator=gte_zero)
    y_ext: float = field(validator=range_val(0, 1))
    y_pur: float = field(validator=range_val(0, 1))
    y_vac: float = field(validator=range_val(0, 1))
    frac_ed_flow: float = field(validator=range_val(0, 1))
    temp_C: float = field(validator=gte_zero)
    sal: float = field(validator=gte_zero)
    dic_i: float = field(validator=gte_zero)
    pH_i: float = field(validator=gte_zero)
    initial_tank_volume_m3: float = field(validator=gte_zero)
    save_outputs: bool = field(default=False)
    save_plots: bool = field(default=False)


class DOCPerformanceModel(PerformanceModelBaseClass):
    """
    An OpenMDAO component for modeling the performance of a Direct Ocean Capture (DOC) plant.
    """

    def initialize(self):
        super().initialize()
        self.commodity = "co2"
        self.commodity_rate_units = "kg/h"
        self.commodity_amount_units = "kg"

    def setup(self):
        self.config = DOCPerformanceConfig.from_dict(
            merge_shared_inputs(self.options["tech_config"]["model_inputs"], "performance"),
            additional_cls_name=self.__class__.__name__,
        )
        super().setup()

        self.add_input(
            "electricity_in",
            val=0.0,
            shape=self.n_timesteps,
            units="W",
            desc="Hourly input electricity (W)",
        )

        self.add_output(
            "total_tank_volume",
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
            save_outputs=self.config.save_outputs,
            save_plots=self.config.save_plots,
            output_dir=self.options["driver_config"]["general"]["folder_output"],
            plot_range=[3910, 4030],
        )

        outputs["co2_out"] = ed_outputs.ED_outputs["mCC"] * 1000  # kg/h
        outputs["total_tank_volume"] = range_outputs.V_aT_max + range_outputs.V_bT_max

        outputs["rated_co2_production"] = (ed_outputs.mCC_yr_MaxPwr / 8760) * 1e3
        outputs["total_co2_produced"] = outputs["co2_out"].sum()

        outputs["capacity_factor"] = ed_outputs.doc_capacity_factor

        # convert from metric tons/year to kg/year
        outputs["annual_co2_produced"] = max(ed_outputs.mCC_yr * 1e3, 1e-6)


@define(kw_only=True)
class DOCCostModelConfig(DOCPerformanceConfig):
    """Configuration for the DOC cost model.

    Attributes:
        infrastructure_type (str): Type of infrastructure (e.g., "desal", "swCool", "new").
        cost_year (int): dollar year corresponding to cost values
    """

    infrastructure_type: str = field(validator=contains(["desal", "swCool", "new"]))
    cost_year: int = field(default=2023, converter=int, validator=must_equal(2023))


class DOCCostModel(CostModelBaseClass):
    """OpenMDAO component for computing capital (CapEx) and operational (OpEx) costs of a
    direct ocean capture (DOC) system.
    """

    def initialize(self):
        super().initialize()

    def setup(self):
        self.config = DOCCostModelConfig.from_dict(
            merge_shared_inputs(self.options["tech_config"]["model_inputs"], "cost"),
            additional_cls_name=self.__class__.__name__,
        )

        super().setup()
        plant_life = int(self.options["plant_config"]["plant"]["plant_life"])

        self.add_input(
            "total_tank_volume",
            val=0.0,
            units="m**3",
        )

        self.add_input(
            "annual_co2_produced",
            val=0.0,
            shape=plant_life,
            units="t/year",
            desc="Annual co2 captured",
        )

        self.add_input(
            "rated_co2_production",
            val=0.0,
            units="t/h",
            desc="Theoretical plant maximum CO₂ capture",
        )

    def compute(self, inputs, outputs, discrete_inputs, discrete_outputs):
        # Set up electrodialysis inputs
        ED_inputs = setup_electrodialysis_inputs(self.config)

        res = echem_mcc.electrodialysis_cost_model(
            echem_mcc.ElectrodialysisCostInputs(
                electrodialysis_inputs=ED_inputs,
                mCC_yr=inputs["annual_co2_produced"],
                total_tank_volume=inputs["total_tank_volume"],
                infrastructure_type=self.config.infrastructure_type,
                max_theoretical_mCC=inputs["rated_co2_production"],
            )
        )

        # Calculate CapEx
        outputs["CapEx"] = res.initial_capital_cost
        outputs["OpEx"] = res.yearly_operational_cost[0]
