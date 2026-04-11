from attrs import field, define
from mcm.capture import echem_oae

from h2integrate.core.utilities import BaseConfig, merge_shared_inputs
from h2integrate.core.validators import gt_zero, contains, gte_zero, range_val, must_equal
from h2integrate.core.model_baseclasses import (
    CostModelBaseClass,
    CostModelBaseConfig,
    PerformanceModelBaseClass,
)


def setup_ocean_alkalinity_enhancement_inputs(config):
    """Helper function to set up ocean alkalinity enhancement inputs from the configuration."""
    return echem_oae.OAEInputs(
        N_edMin=config.number_ed_min,
        N_edMax=config.number_ed_max,
        assumed_CDR_rate=config.assumed_CDR_rate,
        Q_edMax=config.max_ed_system_flow_rate_m3s,
        frac_baseFlow=config.frac_base_flow,
        use_storage_tanks=config.use_storage_tanks,
        store_hours=config.store_hours,
        acid_disposal_method=config.acid_disposal_method,
    )


@define(kw_only=True)
class OAEPerformanceConfig(BaseConfig):
    """Extended configuration for Ocean Alkalinity Enhancement (OAE) performance model.

    Attributes:
        number_ed_min (int): Minimum number of ED units to operate.
        number_ed_max (int): Maximum number of ED units available.
        use_storage_tanks (bool): Flag indicating whether to use storage tanks.
        store_hours (float): Number of hours of CO₂ storage capacity (hours).
        assumed_CDR_rate (float): Mole of CO2 per mole of NaOH (unitless).
        frac_base_flow (float): Fraction of base flow in the system (unitless).
        max_ed_system_flow_rate_m3s (float): Maximum flow rate through the ED system (m³/s).
        initial_temp_C (float): Temperature of input seawater (°C).
        initial_salinity_ppt (float): Initial salinity of seawater (ppt).
        initial_dic_mol_per_L (float): Initial dissolved inorganic carbon (mol/L).
        initial_pH (float): Initial pH of seawater.
        initial_tank_volume_m3 (float): Initial volume of the tank (m³).
        acid_disposal_method (str): Method for acid disposal. Options are
            "sell acid", "sell rca", "acid disposal".
        save_outputs (bool, optional): If true, save results to .csv files. Defaults to False.
        save_plots (bool, optional): If true, save plots of results. Defaults to False.
    """

    number_ed_min: int = field(validator=gt_zero)
    number_ed_max: int = field(validator=gt_zero)
    use_storage_tanks: bool = field()
    store_hours: float = field(validator=gte_zero)
    assumed_CDR_rate: float = field(validator=range_val(0, 1))
    frac_base_flow: float = field(validator=range_val(0, 1))
    max_ed_system_flow_rate_m3s: float = field(validator=gt_zero)
    initial_temp_C: float = field(validator=gte_zero)
    initial_salinity_ppt: float = field(validator=gte_zero)
    initial_dic_mol_per_L: float = field(validator=gte_zero)
    initial_pH: float = field(validator=gte_zero)
    initial_tank_volume_m3: float = field(validator=gte_zero)
    acid_disposal_method: str = field(
        validator=contains(["sell acid", "sell rca", "acid disposal"])
    )
    save_outputs: bool = field(default=False)
    save_plots: bool = field(default=False)


class OAEPerformanceModel(PerformanceModelBaseClass):
    """OpenMDAO component for modeling Ocean Alkalinity Enhancement (OAE) performance."""

    _time_step_bounds = (3600, 3600)  # (min, max) time step lengths compatible with this model

    def initialize(self):
        super().initialize()
        self.commodity = "co2"
        self.commodity_rate_units = "kg/h"
        self.commodity_amount_units = "kg"

    def setup(self):
        self.config = OAEPerformanceConfig.from_dict(
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
            "alkaline_seawater_flow_rate",
            shape=self.n_timesteps,
            val=0.0,
            units="m**3/s",
            desc="Alkaline seawater flow rate",
        )
        self.add_output(
            "alkaline_seawater_pH",
            val=0.0,
            shape=self.n_timesteps,
            units="unitless",
            desc="pH of the alkaline seawater",
        )
        self.add_output(
            "alkaline_seawater_dic",
            val=0.0,
            shape=self.n_timesteps,
            units="mol/L",
            desc="Dissolved inorganic carbon concentration in the alkaline seawater",
        )
        self.add_output(
            "alkaline_seawater_ta",
            val=0.0,
            shape=self.n_timesteps,
            units="mol/L",
            desc="Total alkalinity of the alkaline seawater",
        )
        self.add_output(
            "alkaline_seawater_salinity",
            val=0.0,
            shape=self.n_timesteps,
            units="ppt",
            desc="Salinity of the alkaline seawater",
        )
        self.add_output(
            "alkaline_seawater_temp",
            val=0.0,
            shape=self.n_timesteps,
            units="degC",
            desc="Temperature of the alkaline seawater",
        )
        self.add_output(
            "excess_acid",
            val=0.0,
            shape=self.n_timesteps,
            units="m**3",
            desc="Excess acid produced",
        )
        self.add_output(
            "mass_sellable_product",
            val=0.0,
            units="t/year",
            desc="Mass of sellable product (acid or RCA) produced per year",
        )
        self.add_output(
            "value_products",
            val=0.0,
            units="USD/year",
            desc="Value of products (acid or RCA)",
        )
        self.add_output(
            "mass_acid_disposed",
            val=0.0,
            units="t/year",
            desc="Mass of acid disposed per year",
        )
        self.add_output(
            "cost_acid_disposal",
            val=0.0,
            units="USD/year",
            desc="Cost of acid disposal",
        )
        self.add_output(
            "based_added_seawater_max_power",
            val=0.0,
            units="mol/year",
            desc="Maximum power for base added seawater per year",
        )
        self.add_output(
            "mass_rca",
            val=0.0,
            units="g",
            desc="Mass of RCA tumbler slurry produced",
        )
        self.add_output(
            "unused_energy",
            val=0.0,
            shape=self.n_timesteps,
            units="W",
            desc="Unused energy unused by OAE system",
        )

    def compute(self, inputs, outputs):
        OAE_inputs = setup_ocean_alkalinity_enhancement_inputs(self.config)

        # Call the OAE calculation method from the echem_oae module
        range_outputs, oae_outputs = echem_oae.run_ocean_alkalinity_enhancement_physics_model(
            power_profile_w=inputs["electricity_in"],
            power_capacity_w=max(
                inputs["electricity_in"]
            ),  # TODO: get an electricity capacity from H2I to input
            initial_tank_volume_m3=self.config.initial_tank_volume_m3,
            oae_config=OAE_inputs,
            pump_config=echem_oae.PumpInputs(),
            seawater_config=echem_oae.SeaWaterInputs(
                sal_ppt_i=self.config.initial_salinity_ppt,
                tempC=self.config.initial_temp_C,
                dic_i=self.config.initial_dic_mol_per_L,
                pH_i=self.config.initial_pH,
            ),
            rca=echem_oae.RCALoadingCalculator(
                oae=OAE_inputs,
                seawater=echem_oae.SeaWaterInputs(
                    sal_ppt_i=self.config.initial_salinity_ppt,
                    tempC=self.config.initial_temp_C,
                    dic_i=self.config.initial_dic_mol_per_L,
                    pH_i=self.config.initial_pH,
                ),
            ),
            save_outputs=self.config.save_outputs,
            save_plots=self.config.save_plots,
            output_dir=self.options["driver_config"]["general"]["folder_output"],
            plot_range=[3910, 4030],
        )

        outputs["co2_out"] = oae_outputs.OAE_outputs["mass_CO2_absorbed"]
        outputs["rated_co2_production"] = (oae_outputs.M_co2cap / 8760) * 1e3  # kg/h
        outputs["total_co2_produced"] = outputs["co2_out"].sum()  # kg

        outputs["annual_co2_produced"] = (
            oae_outputs.M_co2est * 1e3
        )  # convert from metric tons/year to kg/year
        outputs["capacity_factor"] = oae_outputs.oae_capacity_factor
        outputs["alkaline_seawater_flow_rate"] = oae_outputs.OAE_outputs["Qout"]
        outputs["alkaline_seawater_pH"] = oae_outputs.OAE_outputs["pH_f"]
        outputs["alkaline_seawater_dic"] = oae_outputs.OAE_outputs["dic_f"]
        outputs["alkaline_seawater_ta"] = oae_outputs.OAE_outputs["ta_f"]
        outputs["alkaline_seawater_salinity"] = oae_outputs.OAE_outputs["sal_f"]
        outputs["alkaline_seawater_temp"] = oae_outputs.OAE_outputs["temp_f"]
        outputs["excess_acid"] = oae_outputs.OAE_outputs["volExcessAcid"]
        outputs["mass_sellable_product"] = oae_outputs.M_rev_yr
        outputs["value_products"] = oae_outputs.X_rev_yr
        outputs["mass_acid_disposed"] = oae_outputs.M_disposed_yr
        outputs["cost_acid_disposal"] = oae_outputs.X_disp
        outputs["based_added_seawater_max_power"] = oae_outputs.mol_OH_yr_MaxPwr
        outputs["mass_rca"] = oae_outputs.slurry_mass_max
        outputs["unused_energy"] = oae_outputs.OAE_outputs["P_xs"]


@define(kw_only=True)
class OAECostModelConfig(CostModelBaseConfig):
    """Configuration for the OAE cost model.

    Attributes:
        cost_year (int): dollar year corresponding to cost values
    """

    cost_year: int = field(default=2024, converter=int, validator=must_equal(2024))


class OAECostModel(CostModelBaseClass):
    """OpenMDAO component for computing capital (CapEx) and operational (OpEx) costs of a
    ocean alkalinity enhancement (OAE) system.
    """

    _time_step_bounds = (3600, 3600)  # (min, max) time step lengths compatible with this model

    def initialize(self):
        super().initialize()

    def setup(self):
        if "cost" in self.options["tech_config"]["model_inputs"]:
            self.config = OAECostModelConfig.from_dict(
                merge_shared_inputs(self.options["tech_config"]["model_inputs"], "cost"),
                additional_cls_name=self.__class__.__name__,
            )
        else:
            self.config = OAECostModelConfig.from_dict(
                data={},
                additional_cls_name=self.__class__.__name__,
            )
        super().setup()
        plant_life = int(self.options["plant_config"]["plant"]["plant_life"])

        self.add_input(
            "annual_co2_produced",
            val=0.0,
            shape=plant_life,
            units="t/year",
        )
        self.add_input(
            "mass_sellable_product",
            val=0.0,
            units="t/year",
            desc="Mass of sellable product (acid or RCA) produced per year",
        )
        self.add_input(
            "value_products",
            val=0.0,
            units="USD/year",
            desc="Value of products (acid or RCA)",
        )
        self.add_input(
            "mass_acid_disposed",
            val=0.0,
            units="t/year",
            desc="Mass of acid disposed per year",
        )
        self.add_input(
            "cost_acid_disposal",
            val=0.0,
            units="USD/year",
            desc="Cost of acid disposal",
        )
        self.add_input(
            "based_added_seawater_max_power",
            val=0.0,
            units="mol/year",
            desc="Maximum power for base added seawater per year",
        )
        self.add_input(
            "mass_rca",
            val=0.0,
            units="g",
            desc="Mass of RCA tumbler slurry produced",
        )

    def compute(self, inputs, outputs, discrete_inputs, discrete_outputs):
        costs = echem_oae.OAECosts(
            mass_product=inputs["mass_sellable_product"][0],
            value_product=inputs["value_products"][0],
            waste_mass=inputs["mass_acid_disposed"][0],
            waste_disposal_cost=inputs["cost_acid_disposal"][0],
            estimated_cdr=inputs["annual_co2_produced"][0],
            base_added_seawater_max_power=inputs["based_added_seawater_max_power"][0],
            mass_rca=inputs["mass_rca"][0],
            annual_energy_cost=0,  # Energy costs are calculated within H2I and added to LCOC calc
        )

        results = costs.run()

        # Calculate CapEx
        outputs["CapEx"] = results["Capital Cost (CAPEX) ($)"]
        outputs["OpEx"] = results["Annual Operating Cost ($/yr)"]


class OAECostAndFinancialModel(CostModelBaseClass):
    """OpenMDAO component for calculating costs and financial metrics of an
        Ocean Alkalinity Enhancement (OAE) system.
    The financial model calculates the carbon credit value that would be required to achieve a
        net present value (NPV) of zero for the overall system costs.

    Computes:
        - CapEx
        - OpEx
        - NPV
        - Carbon Credit Value
    """

    _time_step_bounds = (3600, 3600)  # (min, max) time step lengths compatible with this model

    def initialize(self):
        super().initialize()

    def setup(self):
        if "cost" in self.options["tech_config"]["model_inputs"]:
            self.config = OAECostModelConfig.from_dict(
                merge_shared_inputs(self.options["tech_config"]["model_inputs"], "cost"),
                additional_cls_name=self.__class__.__name__,
            )
        else:
            self.config = OAECostModelConfig.from_dict(
                data={},
                additional_cls_name=self.__class__.__name__,
            )
        super().setup()
        n_timesteps = self.options["plant_config"]["plant"]["simulation"]["n_timesteps"]
        plant_life = int(self.options["plant_config"]["plant"]["plant_life"])

        self.add_input(
            "annual_co2_produced",
            val=0.0,
            shape=plant_life,
            units="t/year",
            desc="Annual co2 captured",
        )
        self.add_input(
            "LCOE",
            val=0.0,
            units="USD/(kW*h)",
            desc="Levelized cost of electricity",
        )
        self.add_input(
            "annual_input_electricity",
            val=0.0,
            shape=plant_life,
            units="kW*h/year",
            desc="Annual energy input to the OAE",
        )
        self.add_input(
            "unused_energy",
            val=0.0,
            shape=n_timesteps,
            units="kW",
            desc="Unused energy unused by OAE system",
        )
        self.add_input(
            "mass_sellable_product",
            val=0.0,
            units="t/year",
            desc="Mass of sellable product (acid or RCA) produced per year",
        )
        self.add_input(
            "value_products",
            val=0.0,
            units="USD/year",
            desc="Value of products (acid or RCA)",
        )
        self.add_input(
            "mass_acid_disposed",
            val=0.0,
            units="t/year",
            desc="Mass of acid disposed per year",
        )
        self.add_input(
            "cost_acid_disposal",
            val=0.0,
            units="USD/year",
            desc="Cost of acid disposal",
        )
        self.add_input(
            "based_added_seawater_max_power",
            val=0.0,
            units="mol/year",
            desc="Maximum power for base added seawater per year",
        )
        self.add_input(
            "mass_rca",
            val=0.0,
            units="g",
            desc="Mass of RCA tumbler slurry produced",
        )

        self.add_output(
            "NPV",
            val=0.0,
            units="USD",
            desc="Net Present Value of the OAE system",
        )
        self.add_output(
            "carbon_credit_value",
            val=0.0,
            units="USD/t",
            desc="Carbon credit value required to achieve NPV of zero",
        )

    def compute(self, inputs, outputs, discrete_inputs, discrete_outputs):
        """Model assume that you only pay for the energy you use for OAE."""
        if not inputs["annual_input_electricity"][0]:
            msg = (
                "the annual_input_electricity needs to be connected to "
                "an annual electricity stream in the technology_interconnections "
                "in the plant_config."
            )
            raise AttributeError(msg)
        annual_energy_cost_usd_yr = inputs["LCOE"] * (
            inputs["annual_input_electricity"][0] - (sum(inputs["unused_energy"]))
        )  # remove unused power from the annual energy cost only used power considered
        costs = echem_oae.OAECosts(
            mass_product=inputs["mass_sellable_product"][0],
            value_product=inputs["value_products"][0],
            waste_mass=inputs["mass_acid_disposed"][0],
            waste_disposal_cost=inputs["cost_acid_disposal"][0],
            estimated_cdr=inputs["annual_co2_produced"][0],
            base_added_seawater_max_power=inputs["based_added_seawater_max_power"][0],
            mass_rca=inputs["mass_rca"][0],
            annual_energy_cost=annual_energy_cost_usd_yr[0],
        )

        results = costs.run()

        # Calculate CapEx
        outputs["CapEx"] = results["Capital Cost (CAPEX) ($)"]
        outputs["OpEx"] = results["Annual Operating Cost ($/yr)"]
        outputs["NPV"] = results["Net Present Value (NPV) ($)"]
        outputs["carbon_credit_value"] = results["Carbon Credit Value ($/tCO2)"]
