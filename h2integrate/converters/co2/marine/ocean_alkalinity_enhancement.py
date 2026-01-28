from attrs import field, define

from h2integrate.core.utilities import BaseConfig, merge_shared_inputs
from h2integrate.core.validators import must_equal
from h2integrate.converters.co2.marine.marine_carbon_capture_baseclass import (
    MarineCarbonCaptureCostBaseClass,
    MarineCarbonCapturePerformanceConfig,
    MarineCarbonCapturePerformanceBaseClass,
)


try:
    from mcm.capture import echem_oae
except ImportError:
    echem_oae = None


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
class OAEPerformanceConfig(MarineCarbonCapturePerformanceConfig):
    """Extended configuration for Ocean Alkalinity Enhancement (OAE) performance model.

    Attributes:
        assumed_CDR_rate (float): Mole of CO2 per mole of NaOH (unitless).
        frac_base_flow (float): Fraction of base flow in the system (unitless).
        max_ed_system_flow_rate_m3s (float): Maximum flow rate through the ED system (m³/s).
        initial_temp_C (float): Temperature of input seawater (°C).
        initial_salinity_ppt (float): Initial salinity of seawater (ppt).
        initial_dic_mol_per_L (float): Initial dissolved inorganic carbon (mol/L).
        initial_pH (float): Initial pH of seawater.
        initial_tank_volume_m3 (float): Initial volume of the tank (m³).
        acid_disposal_method (str): Method for acid disposal.
    """

    assumed_CDR_rate: float = field()
    frac_base_flow: float = field()
    max_ed_system_flow_rate_m3s: float = field()
    initial_temp_C: float = field()
    initial_salinity_ppt: float = field()
    initial_dic_mol_per_L: float = field()
    initial_pH: float = field()
    initial_tank_volume_m3: float = field()
    acid_disposal_method: str = field()


class OAEPerformanceModel(MarineCarbonCapturePerformanceBaseClass):
    """OpenMDAO component for modeling Ocean Alkalinity Enhancement (OAE) performance.

    Extends:
        MarineCarbonCapturePerformanceBaseClass

    Computes:
        - co2_out: Hourly CO₂ capture rate (kg/h).
        - co2_capture_mtpy: Annual CO₂ captured in metric tons per year.

    Notes:
        This component requires the mcm.capture.echem_oae module for calculations.
    """

    def initialize(self):
        super().initialize()
        if echem_oae is None:
            raise ImportError(
                "The `mcm` package is required to use the Ocean Alkalinity Enhancement model. "
                "Install it via:\n"
                "pip install git+https://github.com/NREL/MarineCarbonManagement.git"
            )

    def setup(self):
        self.config = OAEPerformanceConfig.from_dict(
            merge_shared_inputs(self.options["tech_config"]["model_inputs"], "performance")
        )
        super().setup()
        n_timesteps = self.options["plant_config"]["plant"]["simulation"]["n_timesteps"]

        self.add_output(
            "plant_mCC_capacity_mtph",
            val=0.0,
            units="t/h",
            desc="Theoretical maximum CO₂ capture (t/h)",
        )
        self.add_output(
            "alkaline_seawater_flow_rate",
            shape=n_timesteps,
            val=0.0,
            units="m**3/s",
            desc="Alkaline seawater flow rate (m³/s)",
        )
        self.add_output(
            "alkaline_seawater_pH", val=0.0, shape=n_timesteps, desc="pH of the alkaline seawater"
        )
        self.add_output(
            "alkaline_seawater_dic",
            val=0.0,
            shape=n_timesteps,
            units="mol/L",
            desc="Dissolved inorganic carbon concentration in the alkaline seawater",
        )
        self.add_output(
            "alkaline_seawater_ta",
            val=0.0,
            shape=n_timesteps,
            units="mol/L",
            desc="Total alkalinity of the alkaline seawater",
        )
        self.add_output(
            "alkaline_seawater_salinity",
            val=0.0,
            shape=n_timesteps,
            units="ppt",
            desc="Salinity of the alkaline seawater",
        )
        self.add_output(
            "alkaline_seawater_temp",
            val=0.0,
            shape=n_timesteps,
            units="C",
            desc="Temperature of the alkaline seawater (°C)",
        )
        self.add_output(
            "excess_acid",
            val=0.0,
            shape=n_timesteps,
            units="m**3",
            desc="Excess acid produced (m³)",
        )
        self.add_output(
            "mass_sellable_product",
            val=0.0,
            units="t/year",
            desc="Mass of sellable product (acid or RCA) produced per year (tonnes)",
        )
        self.add_output(
            "value_products",
            val=0.0,
            units="USD/year",
            desc="Value of products (acid or RCA) (USD/year)",
        )
        self.add_output(
            "mass_acid_disposed",
            val=0.0,
            units="t/year",
            desc="Mass of acid disposed per year (tonnes)",
        )
        self.add_output(
            "cost_acid_disposal",
            val=0.0,
            units="USD/year",
            desc="Cost of acid disposal (USD/year)",
        )
        self.add_output(
            "based_added_seawater_max_power",
            val=0.0,
            units="mol/year",
            desc="Maximum power for base added seawater per year (mol/year)",
        )
        self.add_output(
            "mass_rca",
            val=0.0,
            units="g",
            desc="Mass of RCA tumbler slurry produced (grams)",
        )
        self.add_output(
            "unused_energy",
            val=0.0,
            shape=n_timesteps,
            units="W",
            desc="Unused energy unused by OAE system (W)",
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
            save_outputs=True,
            save_plots=True,
            output_dir=self.options["driver_config"]["general"]["folder_output"],
            plot_range=[3910, 4030],
        )

        outputs["co2_out"] = oae_outputs.OAE_outputs["mass_CO2_absorbed"]
        outputs["co2_capture_mtpy"] = oae_outputs.M_co2est
        outputs["plant_mCC_capacity_mtph"] = max(range_outputs.S1["mass_CO2_absorbed"] / 1000)
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
class OAECostModelConfig(BaseConfig):
    """Configuration for the OAE cost model.

    Attributes:
        cost_year (int): dollar year corresponding to cost values
    """

    cost_year: int = field(default=2024, converter=int, validator=must_equal(2024))


class OAECostModel(MarineCarbonCaptureCostBaseClass):
    """OpenMDAO component for computing capital (CapEx) and operational (OpEx) costs of a
        ocean alkalinity enhancement (OAE) system.

    Computes:
        - CapEx (USD)
        - OpEx (USD/year)
    """

    def initialize(self):
        super().initialize()
        if echem_oae is None:
            raise ImportError(
                "The `mcm` package is required to use the Ocean Alkalinity Enhancement model. "
                "Install it via:\n"
                "pip install git+https://github.com/NREL/MarineCarbonManagement.git"
            )

    def setup(self):
        if "cost" in self.options["tech_config"]["model_inputs"]:
            self.config = OAECostModelConfig.from_dict(
                merge_shared_inputs(self.options["tech_config"]["model_inputs"], "cost")
            )
        else:
            self.config = OAECostModelConfig.from_dict(data={})
        super().setup()
        self.add_input(
            "mass_sellable_product",
            val=0.0,
            units="t/year",
            desc="Mass of sellable product (acid or RCA) produced per year (tonnes)",
        )
        self.add_input(
            "value_products",
            val=0.0,
            units="USD/year",
            desc="Value of products (acid or RCA) (USD/year)",
        )
        self.add_input(
            "mass_acid_disposed",
            val=0.0,
            units="t/year",
            desc="Mass of acid disposed per year (tonnes)",
        )
        self.add_input(
            "cost_acid_disposal",
            val=0.0,
            units="USD/year",
            desc="Cost of acid disposal (USD/year)",
        )
        self.add_input(
            "based_added_seawater_max_power",
            val=0.0,
            units="mol/year",
            desc="Maximum power for base added seawater per year (mol/year)",
        )
        self.add_input(
            "mass_rca",
            val=0.0,
            units="g",
            desc="Mass of RCA tumbler slurry produced (grams)",
        )

    def compute(self, inputs, outputs, discrete_inputs, discrete_outputs):
        costs = echem_oae.OAECosts(
            mass_product=inputs["mass_sellable_product"],
            value_product=inputs["value_products"],
            waste_mass=inputs["mass_acid_disposed"],
            waste_disposal_cost=inputs["cost_acid_disposal"],
            estimated_cdr=inputs["co2_capture_mtpy"],
            base_added_seawater_max_power=inputs["based_added_seawater_max_power"],
            mass_rca=inputs["mass_rca"],
            annual_energy_cost=0,  # Energy costs are calculated within H2I and added to LCOC calc
        )

        results = costs.run()

        # Calculate CapEx
        outputs["CapEx"] = results["Capital Cost (CAPEX) ($)"]
        outputs["OpEx"] = results["Annual Operating Cost ($/yr)"]


class OAECostAndFinancialModel(MarineCarbonCaptureCostBaseClass):
    """OpenMDAO component for calculating costs and financial metrics of an
        Ocean Alkalinity Enhancement (OAE) system.
    The financial model calculates the carbon credit value that would be required to achieve a
        net present value (NPV) of zero for the overall system costs.

    Computes:
        - CapEx (USD)
        - OpEx (USD/year)
        - NPV ($)
        - Carbon Credit Value (USD/tCO2)
    """

    def initialize(self):
        super().initialize()
        if echem_oae is None:
            raise ImportError(
                "The `mcm` package is required to use the Ocean Alkalinity Enhancement model. "
                "Install it via:\n"
                "pip install git+https://github.com/NREL/MarineCarbonManagement.git"
            )

    def setup(self):
        if "cost" in self.options["tech_config"]["model_inputs"]:
            self.config = OAECostModelConfig.from_dict(
                merge_shared_inputs(self.options["tech_config"]["model_inputs"], "cost")
            )
        else:
            self.config = OAECostModelConfig.from_dict(data={})
        super().setup()
        n_timesteps = self.options["plant_config"]["plant"]["simulation"]["n_timesteps"]
        self.add_input(
            "LCOE",
            val=0.0,
            units="USD/(kW*h)",
            desc="Levelized cost of electricity (USD/kWh)",
        )
        self.add_input(
            "annual_energy",
            val=0.0,
            units="kW*h/year",
            desc="Annual energy production in kWac",
        )
        self.add_input(
            "unused_energy",
            val=0.0,
            shape=n_timesteps,
            units="W",
            desc="Unused energy unused by OAE system (W)",
        )
        self.add_input(
            "mass_sellable_product",
            val=0.0,
            units="t/year",
            desc="Mass of sellable product (acid or RCA) produced per year (tonnes)",
        )
        self.add_input(
            "value_products",
            val=0.0,
            units="USD/year",
            desc="Value of products (acid or RCA) (USD/year)",
        )
        self.add_input(
            "mass_acid_disposed",
            val=0.0,
            units="t/year",
            desc="Mass of acid disposed per year (tonnes)",
        )
        self.add_input(
            "cost_acid_disposal",
            val=0.0,
            units="USD/year",
            desc="Cost of acid disposal (USD/year)",
        )
        self.add_input(
            "based_added_seawater_max_power",
            val=0.0,
            units="mol/year",
            desc="Maximum power for base added seawater per year (mol/year)",
        )
        self.add_input(
            "mass_rca",
            val=0.0,
            units="g",
            desc="Mass of RCA tumbler slurry produced (grams)",
        )

        self.add_output(
            "NPV",
            val=0.0,
            units="USD",
            desc="Net Present Value of the OAE system (USD)",
        )
        self.add_output(
            "carbon_credit_value",
            val=0.0,
            units="USD/t",
            desc="Carbon credit value required to achieve NPV of zero (USD/tCO2)",
        )

    def compute(self, inputs, outputs, discrete_inputs, discrete_outputs):
        annual_energy_cost_usd_yr = inputs["LCOE"] * (
            inputs["annual_energy"] - (sum(inputs["unused_energy"]) / 1000)  # Convert W to kW
        )  # remove unused power from the annual energy cost only used power considered
        costs = echem_oae.OAECosts(
            mass_product=inputs["mass_sellable_product"],
            value_product=inputs["value_products"],
            waste_mass=inputs["mass_acid_disposed"],
            waste_disposal_cost=inputs["cost_acid_disposal"],
            estimated_cdr=inputs["co2_capture_mtpy"],
            base_added_seawater_max_power=inputs["based_added_seawater_max_power"],
            mass_rca=inputs["mass_rca"],
            annual_energy_cost=annual_energy_cost_usd_yr,
        )

        results = costs.run()

        # Calculate CapEx
        outputs["CapEx"] = results["Capital Cost (CAPEX) ($)"]
        outputs["OpEx"] = results["Annual Operating Cost ($/yr)"]
        outputs["NPV"] = results["Net Present Value (NPV) ($)"]
        outputs["carbon_credit_value"] = results["Carbon Credit Value ($/tCO2)"]
