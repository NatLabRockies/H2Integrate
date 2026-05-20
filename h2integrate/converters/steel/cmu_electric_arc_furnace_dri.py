"""Electric Arc Furnace performance model based on CMU decarbSTEEL EAF Model"""

import numpy as np
from attrs import field, define
from openmdao.utils import units

from h2integrate.core.utilities import BaseConfig, merge_shared_inputs
from h2integrate.core.validators import contains
from h2integrate.tools.constants import (
    C_MW,
    CO_MW,
    FE_MW,
    O2_MW,
    R_GAS,
    CAO_MW,
    CH4_MW,
    FEO_MW,
    MGO_MW,
    SIO2_MW,
    T_STD_K,
    AL2O3_MW,
    P_STD_KPA,
    LHV_CH4_MJ_PER_KG,
)
from h2integrate.core.model_baseclasses import PerformanceModelBaseClass


@define
class CMUElectricArcFurnaceDRIPerformanceConfig(BaseConfig):
    """Configuration baseclass for CMUElectricArcFurnaceDRIPerformanceComponent.

    Attributes:
        steel_production_capacity_tonnes_per_year (float): Rated electric arc furnace capacity
            in tonnes of steel produced per year. Default is 2200000 tonnes/year based on the CMU
            decarbSTEEL v5 model which assumes a 2.2 million tonne per year capacity for the EAF.
        steel_production_rate_tonnes_per_year (float): Expected steel production from the steel
            plant in units of metric tonnes of steel produced per year.
        steel_percent_carbon (float): mass fraction of carbon in steel output, used to determine
            mass of iron in steel output and thus mass of scrap needed, as well as feedstock
            requirements and slag composition. Default value of 0.1% mass carbon in steel.
        scrap_composition (dict): dictionary with mass fraction of Fe and SiO2 in scrap. Default
            values of 94% mass Fe and 1% mass SiO2 in scrap.

    """

    steel_production_capacity_tonnes_per_year: float = field(default=2200000.0)
    steel_production_rate_tonnes_per_year: float = field(default=2000000.0)  # metric tons/year
    steel_percent_carbon: float = field(
        default=0.1 / 100
    )  # mass fraction C in steel out, 'Model Inputs & Outputs!B26'
    scrap_composition: dict = field(
        default={
            "Fe": 94.0 / 100,  # mass fraction Fe, 'Model Inputs & Outputs!B27'
            "SiO2": 1.0 / 100,  # mass fraction SiO2, 'Model Inputs & Outputs!B28'
        }
    )
    pellet_grade: str = field(default="DR", validator=contains(["DR", "BF", "custom"]))
    pct_DRI: float = field(default=60.0 / 100)  # mass fraction, 'Model Inputs & Outputs!B61'
    DRI_feed_temp: str = field(
        default="hot", validator=contains(["hot", "cold"])
    )  # hot = 873 K or cold = 298 K, 'Model Inputs & Outputs!B63'
    DRI_composition: dict[str, float] | None = None
    SiO2_ratio: float | None = None
    energy_mass_balance_dict: dict = field(
        default={
            # MMBtu/ton steel, '5. Electric Arc Furnace!C32'
            "natural_gas": 0.44,
            # kg/ton steel, '5. Electric Arc Furnace!C8'
            "electrodes": 2.00,
            # basicity, kg CaO / (kg SiO2 + kg Al2O3),
            # '12. EAF Mass & Energy Balance!D169'
            "slag_basicity": 1.50,
            # kg Al2O3 in slag per ton scrap,
            # '12. EAF Mass & Energy Balance!D53'
            "mass_Al2O3_slag_per_tscrap": 0.0,
            # total kg Al2O3 in slag per ton LS,
            # '12. EAF Mass & Energy Balance!D75'
            "mass_Al2O3_slag_per_tLS": 0.0,
            # mass fraction MgO in slag, assumed input,
            # '12. EAF Mass & Energy Balance!D56'
            "pct_MgO_slag": 12.0 / 100,
            # mass fraction FeO in slag, assumed input,
            # '12. EAF Mass & Energy Balance!D57'
            "pct_FeO_slag": 30.0 / 100,
            # mass fraction carbon input to EAF as % of steel tap mass,
            # '12. EAF Mass & Energy Balance!D89'
            "pct_carbon_steel_tap": 3 / 100,
            # (kg/kg), '12. EAF Mass & Energy Balance!D113'
            "CaO_MgO_ratio": 56.00 / 40.00,
            # (kWh/tonne) assumption input on '5. Electric Arc Furnace'!C6
            "electricity_kWh_per_tonne_steel": 470.0,
            # (kWh/tHM) EAF scrap absolute heat loss adjustment,
            # '12. EAF Mass & Energy Balance!G148'
            # default value based on CMUElectricArcFurnaceScrapOnlyPerformanceComponent model
            "EAF_scrap_heat_loss_adjustment_abs": 170.05902581681391,
        }
    )

    def __attrs_post_init__(self):
        if self.pellet_grade == "DR":
            if self.DRI_composition is None:
                self.DRI_composition = {
                    "Fe": 0.8431916497235140,
                    "FeO": 0.06925321488234770,
                    "gangue": 0.06755513539413880,
                    "C": 0.020,
                }

            if self.SiO2_ratio is None:
                self.SiO2_ratio = 1.25

        elif self.pellet_grade == "BF":
            if self.DRI_composition is None:
                self.DRI_composition = {
                    "Fe": 0.8019049064951670,
                    "FeO": 0.06586224237743430,
                    "gangue": 0.112232851127399000,
                    "C": 0.020,
                }

            if self.SiO2_ratio is None:
                self.SiO2_ratio = 3.0

        elif self.pellet_grade == "custom":
            if self.DRI_composition is None:
                raise ValueError("DRI_composition must be provided when pellet_grade='custom'.")

            required_keys = ["Fe", "FeO", "gangue", "C"]
            for key in required_keys:
                if key not in self.DRI_composition:
                    raise KeyError(f"Missing key '{key}' in DRI_composition.")

            total_dri_composition = sum(self.DRI_composition.values())
            if total_dri_composition > 1.0:
                raise ValueError("The sum of the DRI_composition values cannot exceed 1.0.")

            if self.SiO2_ratio is None:
                raise ValueError("SiO2_ratio must be provided when pellet_grade='custom'.")


class CMUElectricArcFurnaceDRIPerformanceComponent(PerformanceModelBaseClass):
    _time_step_bounds = (
        3600,
        3600,
    )  # (min, max) time step lengths (in seconds) compatible with this model

    def initialize(self):
        super().initialize()
        self.commodity = "steel"
        self.commodity_rate_units = "t/h"
        self.commodity_amount_units = "t"

    def setup(self):
        super().setup()

        n_timesteps = self.options["plant_config"]["plant"]["simulation"]["n_timesteps"]

        self.config = CMUElectricArcFurnaceDRIPerformanceConfig.from_dict(
            merge_shared_inputs(self.options["tech_config"]["model_inputs"], "performance"),
            strict=True,
            additional_cls_name=self.__class__.__name__,
        )

        # annual_capacity = 2.2 million Tons/year
        self.add_input(
            "rated_steel_capacity",
            val=self.config.steel_production_capacity_tonnes_per_year,
            units="t/year",
            desc="Electric arc furnace rated capacity",
        )

        # annual_production = 2.0 million Tons/year, 'Model Inputs & Outputs!B12'
        self.add_input(
            "annual_production",
            val=self.config.steel_production_rate_tonnes_per_year,
            units="t/year",
            desc="Actual steel production",
        )

        # Default the steel demand input as the production rate
        self.add_input(
            "steel_demand",
            val=units.convert_units(
                self.config.steel_production_rate_tonnes_per_year, "t/year", "t/h"
            ),
            shape=n_timesteps,
            units=self.commodity_rate_units,
            desc="Steel demand for steel plant",
        )

        self.add_input(
            "percent_DRI",
            val=self.config.pct_DRI,
            units="percent",
            desc="percentage of DRI vs scrap input into EAF",
        )

        # dri composition
        self.add_input(
            "dri_composition_Fe",
            val=self.config.DRI_composition["Fe"],
            units="unitless",
            desc="Mass fraction of metallic Fe in DRI feedstock",
        )

        self.add_input(
            "dri_composition_FeO",
            val=self.config.DRI_composition["FeO"],
            units="unitless",
            desc="Mass fraction of FeO in DRI feedstock",
        )

        self.add_input(
            "dri_composition_gangue",
            val=self.config.DRI_composition["gangue"],
            units="unitless",
            desc="Mass fraction of gangue in DRI feedstock",
        )

        self.add_input(
            "dri_composition_C",
            val=self.config.DRI_composition["C"],
            units="unitless",
            desc="Mass fraction of elemental C in DRI feedstock",
        )

        feedstocks_to_units = {
            "oxygen": "m**3/h",
            "electricity": "kW",
            "natural_gas": "MMBtu/h",
            "electrodes": "kg/h",
            "sponge_iron": "t/h",
            "scrap": "t/h",
            "coal": "t/h",
            "doloma": "t/h",
            "lime": "t/h",
        }

        for feedstock, feedstock_units in feedstocks_to_units.items():
            self.add_input(
                f"{feedstock}_in",
                val=0.0,
                shape=n_timesteps,
                units=feedstock_units,
                desc=f"{feedstock} available for steel production",
            )
            self.add_output(
                f"{feedstock}_consumed",
                val=0.0,
                shape=n_timesteps,
                units=feedstock_units,
                desc=f"{feedstock} consumed for steel production",
            )

        # Add outputs
        self.add_output(
            "slag_out",
            val=0.0,
            shape=n_timesteps,
            units="kg",
            desc="Total unit of slag",
        )

        self.add_output(
            "mass_MgO_slag",
            val=0.0,
            shape=n_timesteps,
            units="kg",
            desc="Total unit of MgO in slag",
        )

        self.add_output(
            "mass_FeO_slag",
            val=0.0,
            shape=n_timesteps,
            units="kg",
            desc="Total unit of FeO in slag",
        )

        self.add_output(
            "mass_Fe_to_FeO",
            val=0.0,
            shape=n_timesteps,
            units="kg",
            desc="Total unit of Fe consumed to produce FeO",
        )

        self.add_output(
            "mass_steel_per_unit_dri",
            val=0.0,
            shape=n_timesteps,
            units="kg/t",
            desc="Total unit of steel formed from EAF fed with dri + scrap per unit of dri",
        )

    def compute(self, inputs, outputs):
        """
        Computes the steel production from an electric arc furnace fed with DRI and scrap based on
        the feedstock availability and the energy and mass balance of the system.
        """
        if inputs["annual_production"] > inputs["rated_steel_capacity"]:
            raise ValueError(
                f"Rated steel production ({inputs['annual_production']} t/year) cannot exceed "
                f"rated steel capacity ({inputs['rated_steel_capacity']} t/year)."
            )

        # calculate energy mass balance on a per ton liquid steel basis
        energy_mass_per_tonne = self.energy_mass_balance_per_unit(inputs)

        annual_steel_production = inputs["annual_production"]  # t/year
        # t/h, convert annual production to hourly production for
        # feedstock usage calculations based on per ton steel feedstock usage rates
        system_production = units.convert_units(annual_steel_production, "t/year", "t/h")

        # Feedstock usage for based on "annual_production" and feedstock
        # usage rates per unit of steel production
        feedstocks_usage_per_tonne_steel = {
            "oxygen": energy_mass_per_tonne["oxygen_per_tLS"],  # Nm^3/t
            "electricity": energy_mass_per_tonne["electricity_per_tLS"],  # kWh/t
            "natural_gas": energy_mass_per_tonne["natural_gas_per_tLS"],  # MMBtu/t
            "electrodes": energy_mass_per_tonne["electrodes_per_tLS"],  # kg/t
            "sponge_iron": energy_mass_per_tonne["mass_DRI_per_tLS"],  # t/t
            "scrap": energy_mass_per_tonne["mass_scrap_per_tLS"],  # t/t
            "coal": energy_mass_per_tonne["coal_per_tLS"],  # t/t
            "doloma": energy_mass_per_tonne["burnt_doloma_per_tLS"],  # t/t
            "lime": energy_mass_per_tonne["burnt_lime_per_tLS"],  # t/t
        }

        # steel demand, saturated at maximum rated system capacity
        steel_demand = np.where(
            inputs["steel_demand"] > system_production,
            system_production,
            inputs["steel_demand"],
        )

        # initialize an array of how much steel could be produced
        # from the available feedstocks and the demand
        steel_from_feedstocks = np.zeros(
            (len(feedstocks_usage_per_tonne_steel) + 1, len(inputs["steel_demand"]))
        )
        # first entry is the steel demand
        steel_from_feedstocks[0] = steel_demand
        ii = 1

        for feedstock_type, consumption_rate in feedstocks_usage_per_tonne_steel.items():
            # calculate max inputs/outputs based on rated capacity
            max_feedstock_consumption = system_production * consumption_rate
            # available feedstocks, saturated at maximum system feedstock consumption
            feedstock_available = np.where(
                inputs[f"{feedstock_type}_in"] > max_feedstock_consumption,
                max_feedstock_consumption,
                inputs[f"{feedstock_type}_in"],
            )
            # how much output can be produced from each of the feedstocks
            steel_from_feedstocks[ii] = feedstock_available / consumption_rate
            ii += 1

        # output is minimum between available feedstocks and output demand
        steel_production = np.minimum.reduce(steel_from_feedstocks)

        outputs["steel_out"] = steel_production
        outputs["rated_steel_production"] = system_production
        outputs["total_steel_produced"] = outputs["steel_out"].sum()
        outputs["annual_steel_produced"] = outputs["total_steel_produced"] * (
            1 / self.fraction_of_year_simulated
        )
        outputs["capacity_factor"] = outputs["total_steel_produced"] / (
            outputs["rated_steel_production"] * len(outputs["steel_out"])
        )

        # feedstock consumption based on actual steel produced
        for feedstock_type, consumption_rate in feedstocks_usage_per_tonne_steel.items():
            outputs[f"{feedstock_type}_consumed"] = steel_production * consumption_rate

        # Total kg slag
        outputs["slag_out"] = energy_mass_per_tonne["mass_slag_per_tLS"] * steel_production
        # Total kg MgO in slag
        outputs["mass_MgO_slag"] = energy_mass_per_tonne["mass_MgO_slag_per_tLS"] * steel_production
        # Total kg FeO in slag
        outputs["mass_FeO_slag"] = energy_mass_per_tonne["mass_FeO_slag_per_tLS"] * steel_production
        # Total kg Fe consumed to produce FeO
        outputs["mass_Fe_to_FeO"] = energy_mass_per_tonne["mass_Fe_to_FeO_tLS"] * steel_production
        # Total kg Fe from scrap
        outputs["mass_steel_per_unit_dri"] = energy_mass_per_tonne["mass_steel_per_tDRI"]

    def energy_mass_balance_per_unit(self, inputs):
        """Computes the energy and mass balance for the EAF fed with dri and scrap on a
            per ton of dri or liquid steel basis.
        Returns:
            output_dict (dict): Dictionary with the amount of feedstocks and energy used per
                ton of steel.
                - mass_slag_per_tDRI (kg/t): Total mass of slag produced per ton of DRI.
                - mass_MgO_slag_per_tDRI (kg/t): Mass of MgO in slag per ton of DRI.
                - mass_FeO_slag_per_tDRI (kg/t): Mass of FeO in slag per ton of DRI.
                - mass_Fe_to_FeO_per_tDRI (kg/t): Mass of Fe consumed to produce FeO per ton DRI.
                - mass_Fe_scrap_per_tDRI (kg/t): Mass of Fe from scrap per ton of DRI.
                - mass_Fe_DRI_per_tDRI (kg/t): Mass of Fe from DRI per ton of DRI.
                - mass_steel_per_tDRI (kg/t): Mass of steel formed from scrap per ton of DRI.
                - natural_gas_per_tLS (MMBtu/t): Natural gas usage per ton of liquid steel.
                - electrodes_per_tLS (kg/t): Electrode usage per ton of liquid steel.
                - mass_DRI_per_tLS (t/t): Mass of DRI per ton of liquid steel.
                - mass_scrap_per_tLS (t/t): Mass of scrap per ton of liquid steel.
                - mass_gangue_per_tLS (kg/t): Mass of gangue per ton of liquid steel.
                - mass_slag_per_tLS (kg/t): Mass of slag per ton of liquid steel.
                - mass_MgO_slag_per_tLS (kg/t): Mass of MgO in slag per ton of liquid steel.
                - mass_FeO_slag_per_tLS (kg/t): Mass of FeO in slag per ton of liquid steel.
                - mass_Fe_to_FeO_per_tLS (kg/t): Mass of Fe consumed to produce FeO per ton
                    of liquid steel.
                - mass_CO_injected_per_tLS (kg/t): Mass of CO injected per ton of liquid steel.
                - coal_per_tLS (t/t): Mass of coal per ton of liquid steel.
                - oxygen_per_tLS (Nm^3/t): Normal cubic meters of oxygen per ton of liquid steel.
                - burnt_doloma_per_tLS (t/t): Mass of burnt doloma per ton of liquid steel.
                - burnt_lime_per_tLS (t/t): Mass of burnt lime per ton of liquid steel.
                - mass_flux_per_tLS (kg/t): Mass of flux (lime and doloma) per ton of liquid steel.
                - off_gas_CO_kg (kg/t): Mass of CO in off-gas per ton of liquid steel.
                - EAF_DRI_heat_loss_pct (%): Percentage of heat loss in EAF.
                - electricity_per_tLS (kWh/t): Total electricity consumption per ton of liquid
                    steel for EAF with scrap-only case, including heat loss adjustment.

        """
        output_dict = {}
        # Including DRI in feed (assumed constants in feedstocks)
        output_dict["natural_gas_per_tLS"] = self.config.energy_mass_balance_dict[
            "natural_gas"
        ]  # '5. Electric Arc Furnace!C7'
        self.config.energy_mass_balance_dict["electrodes"]
        output_dict["electrodes_per_tLS"] = self.config.energy_mass_balance_dict[
            "electrodes"
        ]  # kg/ton steel, '5. Electric Arc Furnace!C33'

        # 12. EAF Mass & Energy Balance
        # Essential Mass Summary
        ####### reverse mass calculation on a per tonne of scrap basis #################
        # kg liquid steel, '12. EAF Mass & Energy Balance!D4'
        mass_steel_stream = 1000
        # % mass C, 'Model Inputs & Outputs!B26' > '12. EAF Mass & Energy Balance!D5'
        pct_carbon_steel = self.config.steel_percent_carbon
        # kg Fe/ton liquid steel, '12. EAF Mass & Energy Balance!D7'
        mass_iron_per_tLS = mass_steel_stream * (1 - pct_carbon_steel)
        # kg C/ton liquid steel, '12. EAF Mass & Energy Balance!D8'
        mass_carbon_per_tLS = mass_steel_stream * pct_carbon_steel

        # % mass Fe and % mass SiO2,
        # 'Model Inputs & Outputs!B27' & 'Model Inputs & Outputs!B28'
        scrap_composition = self.config.scrap_composition

        # Essential Mass Summary > Burden of Composition DRI-EAF
        # NOTE: calculated relative to 1 ton DRI (tDRI)
        # mass %, 'Model Inputs & Outputs!B61' > '12. EAF Mass & Energy Balance!D29'
        share_of_DRI_in_charge = inputs["percent_DRI"]
        # Electric Arc Furnace Fed with DRI Directly (No ESF) -
        # Mass Balance (Fe, C, O, MgO, SiO2, Al2O3, CaO)
        # NOTE: calculated per ton DRI (tDRI)
        # kg, '12. EAF Mass & Energy Balance!D158'
        mass_basis_DRI = 1000
        # kg, '12. EAF Mass & Energy Balance!D159'
        mass_scrap_from_basis = (
            mass_basis_DRI - share_of_DRI_in_charge * mass_basis_DRI
        ) / share_of_DRI_in_charge

        # kg gangue/tDRI, '12. EAF Mass & Energy Balance!D161'
        mass_gangue_per_tDRI = mass_basis_DRI * inputs["dri_composition_gangue"]
        # kg/kg SiO2 to Alumina Ratio in DRI, '12. EAF Mass & Energy Balance!D162'
        SiO2_ratio = self.config.SiO2_ratio

        # kg SiO2/tDRI, '12. EAF Mass & Energy Balance!D163'
        mass_SiO2_DRI_per_tDRI = (mass_gangue_per_tDRI * SiO2_ratio) / (SiO2_ratio + 1)
        # kg Al2O3/tDRI, '12. EAF Mass & Energy Balance!D164'
        mass_Al2O3_DRI_per_tDRI = mass_gangue_per_tDRI / (SiO2_ratio + 1)

        # % mass SiO2, 'Model Inputs & Outputs!B28' > '12. EAF Mass & Energy Balance!D166'
        mass_pct_SiO2_scrap = scrap_composition["SiO2"]
        # kg SiO2/tDRI '12. EAF Mass & Energy Balance!D167'
        mass_SiO2_scrap_per_tDRI = mass_pct_SiO2_scrap * mass_scrap_from_basis

        # basicity, kg CaO / (kg SiO2 + kg Al2O3)
        # # kg SiO2/tDRI, '12. EAF Mass & Energy Balance!D169'
        slag_B3 = self.config.energy_mass_balance_dict["slag_basicity"]

        # kg CaO mass added to EAF per tDRI, '12. EAF Mass & Energy Balance!D170'
        mass_CaO_per_tDRI = slag_B3 * (
            mass_SiO2_scrap_per_tDRI + mass_Al2O3_DRI_per_tDRI + mass_SiO2_DRI_per_tDRI
        )
        # kg SiO2/tDRI, '12. EAF Mass & Energy Balance!D172'
        mass_SiO2_slag_per_tDRI = mass_SiO2_DRI_per_tDRI + mass_SiO2_scrap_per_tDRI
        # kg AlO3/tDRI, '12. EAF Mass & Energy Balance!D173'
        mass_Al2O3_slag_per_tDRI = mass_Al2O3_DRI_per_tDRI
        # kg CaO/tDRI, '12. EAF Mass & Energy Balance!D174'
        mass_CaO_slag_per_tDRI = mass_CaO_per_tDRI

        # mass fraction MgO of slag, assumed input, '12. EAF Mass & Energy Balance!D176'
        pct_MgO_slag = self.config.energy_mass_balance_dict["pct_MgO_slag"]
        # mass fraction FeO of slag, assumed input, '12. EAF Mass & Energy Balance!D177'
        pct_FeO_slag = self.config.energy_mass_balance_dict["pct_FeO_slag"]

        # kg slag/tDRI, '12. EAF Mass & Energy Balance!D178'
        output_dict["mass_slag_per_tDRI"] = (
            mass_SiO2_slag_per_tDRI + mass_Al2O3_slag_per_tDRI + mass_CaO_slag_per_tDRI
        ) / (1 - pct_FeO_slag - pct_MgO_slag)
        # kg MgO in slag/tDRI, '12. EAF Mass & Energy Balance!D179'
        output_dict["mass_MgO_slag_per_tDRI"] = pct_MgO_slag * output_dict["mass_slag_per_tDRI"]
        # kg FeO in slag/tDRI, '12. EAF Mass & Energy Balance!D180'
        output_dict["mass_FeO_slag_per_tDRI"] = pct_FeO_slag * output_dict["mass_slag_per_tDRI"]
        # kg FeO/tDRI, '12. EAF Mass & Energy Balance!D182'
        mass_FeO_DRI_per_tDRI = mass_basis_DRI * inputs["dri_composition_FeO"]

        # kmol FeO/tDRI, 71.80 = '10. DRI Mass & Energy Balance!D22',
        # '12. EAF Mass & Energy Balance!D183'
        mass_FeO_DRI_per_tDRI * FEO_MW
        # kg additional mass FeO required for slag per tDRI,
        # '12. EAF Mass & Energy Balance!D184'
        add_mass_FeO_needed = output_dict["mass_FeO_slag_per_tDRI"] - mass_FeO_DRI_per_tDRI
        # kmol additional mass FeO required for slag per tDRI,
        # '12. EAF Mass & Energy Balance!D185'
        add_moles_FeO_needed = add_mass_FeO_needed / FEO_MW
        # mole Fe consumed to produce FeO per tDRI,
        # '12. EAF Mass & Energy Balance!D186'
        moles_Fe_to_FeO = add_moles_FeO_needed
        # kg Fe consumed to produce FeO per tDRI, '12. EAF Mass & Energy Balance!D187'
        output_dict["mass_Fe_to_FeO_per_tDRI"] = moles_Fe_to_FeO * FE_MW

        # kg Fe from DRI per tDRI, '12. EAF Mass & Energy Balance!D189'
        output_dict["mass_Fe_DRI_per_tDRI"] = (
            mass_basis_DRI * inputs["dri_composition_Fe"] - output_dict["mass_Fe_to_FeO_per_tDRI"]
        )
        # kg Fe from scrap per tDRI, '12. EAF Mass & Energy Balance!D190'
        output_dict["mass_Fe_scrap_per_tDRI"] = mass_scrap_from_basis * scrap_composition["Fe"]
        # kg Fe from DRI + scrap per tDRI, '12. EAF Mass & Energy Balance!D191'
        mass_Fe_per_tDRI = (
            output_dict["mass_Fe_DRI_per_tDRI"] + output_dict["mass_Fe_scrap_per_tDRI"]
        )
        # kg Steel formed from DRI + scrap per tDRI, '12. EAF Mass & Energy Balance!D192'
        output_dict["mass_steel_per_tDRI"] = mass_Fe_per_tDRI / (1 - pct_carbon_steel)

        ###### forward mass calculation on a per tonne of liquid steel basis #################
        # NOTE: calculated per ton liquid steel (tLS)
        # kg DRI per tLS, '12. EAF Mass & Energy Balance!D195'
        mass_DRI_per_tLS = (mass_basis_DRI / output_dict["mass_steel_per_tDRI"]) * 1000
        # kg scrap per ton LS, '12. EAF Mass & Energy Balance!D69'
        output_dict["mass_DRI_per_tLS"] = units.convert_units(mass_DRI_per_tLS, "kg", "t")

        # kg scrap per tLS, '12. EAF Mass & Energy Balance!D196'
        mass_scrap_per_tLS = (mass_scrap_from_basis / output_dict["mass_steel_per_tDRI"]) * 1000
        output_dict["mass_scrap_per_tLS"] = units.convert_units(mass_scrap_per_tLS, "kg", "t")
        # kg gangue per tLS from DRI, '12. EAF Mass & Energy Balance!D198'
        output_dict["mass_gangue_per_tLS"] = mass_DRI_per_tLS * inputs["dri_composition_gangue"]
        # kg/kg SiO2 to Alumina Ratio in DRI,
        # '12. EAF Mass & Energy Balance!D199' > '12. EAF Mass & Energy Balance!D162'
        SiO2_ratio = SiO2_ratio
        # kg SiO2 per tLS from DRI, '12. EAF Mass & Energy Balance!D200'
        mass_SiO2_DRI_per_tLS = (output_dict["mass_gangue_per_tLS"] * SiO2_ratio) / (SiO2_ratio + 1)
        # kg SiO2 per tLS from scrap, '12. EAF Mass & Energy Balance!D201'
        mass_SiO2_scrap_per_tLS = mass_scrap_per_tLS * mass_pct_SiO2_scrap
        # kg Al2O3 per tLS from DRI, '12. EAF Mass & Energy Balance!D202'
        mass_Al2O3_per_tLS = output_dict["mass_gangue_per_tLS"] / (SiO2_ratio + 1)

        # kg SiO2 in slag per tLS, '12. EAF Mass & Energy Balance!D205'
        mass_SiO2_slag_per_tLS = mass_SiO2_DRI_per_tLS + mass_SiO2_scrap_per_tLS
        # kg Al2O3 in slag per tLS,
        # '12. EAF Mass & Energy Balance!D206' > '12. EAF Mass & Energy Balance!D202'
        mass_Al2O3_slag_per_tLS = mass_Al2O3_per_tLS
        # kg CaO in slag per tLS, '12. EAF Mass & Energy Balance!D207'
        mass_CaO_slag_per_tLS = slag_B3 * (mass_SiO2_slag_per_tLS + mass_Al2O3_slag_per_tLS)

        # kg slag per tLS, '12. EAF Mass & Energy Balance!D211'
        output_dict["mass_slag_per_tLS"] = (
            mass_SiO2_slag_per_tLS + mass_Al2O3_slag_per_tLS + mass_CaO_slag_per_tLS
        ) / (1 - pct_MgO_slag - pct_FeO_slag)
        # kg MgO in slag per tLS, '12. EAF Mass & Energy Balance!D212'
        output_dict["mass_MgO_slag_per_tLS"] = pct_MgO_slag * output_dict["mass_slag_per_tLS"]
        # kg FeO in slag per tLS, '12. EAF Mass & Energy Balance!D213'
        output_dict["mass_FeO_slag_per_tLS"] = pct_FeO_slag * output_dict["mass_slag_per_tLS"]

        # kg FeO from DRI per tLS, '12. EAF Mass & Energy Balance!D215'
        mass_FeO_DRI_per_tLS = mass_DRI_per_tLS * inputs["dri_composition_FeO"]

        # kmol FeO from DRI per tLS, '12. EAF Mass & Energy Balance!D216'
        mole_FeO_DRI_per_tLS = mass_FeO_DRI_per_tLS / FEO_MW
        # kg additional FeO required from slag per tLS, '12. EAF Mass & Energy Balance!D217'
        add_mass_FeO_needed_tLS = output_dict["mass_FeO_slag_per_tLS"] - mass_FeO_DRI_per_tLS
        # kmol additional FeO required from slag per tLS, '12. EAF Mass & Energy Balance!D218'
        add_moles_FeO_needed_tLS = add_mass_FeO_needed_tLS / FEO_MW
        # kmol Fe consumed to produce FeO per tLS, '12. EAF Mass & Energy Balance!D219'
        moles_Fe_to_FeO_tLS = add_moles_FeO_needed_tLS
        # kg Fe consumed to produce FeO per tLS, '12. EAF Mass & Energy Balance!D220'
        output_dict["mass_Fe_to_FeO_tLS"] = moles_Fe_to_FeO_tLS * FE_MW

        # kmol O2 consumed to produce FeO per tLS, '12. EAF Mass & Energy Balance!D221'
        # 0.5 comes from the notes in '12. EAF Mass & Energy Balance!H221',
        # 1 mole Fe reacts with 0.5 mole O2 to form 1 mole FeO
        moles_O2_to_FeO_tLS = moles_Fe_to_FeO_tLS * 0.5

        # kg Carbon in Steel per tLS, '12. EAF Mass & Energy Balance!D223'
        mass_C_steel_per_tLS = mass_steel_stream * pct_carbon_steel
        # kg Carbon in DRI per tLS, '12. EAF Mass & Energy Balance!D224'
        mass_C_DRI_per_tLS = mass_DRI_per_tLS * inputs["dri_composition_C"]
        natural_gas_MJ = units.convert_units(output_dict["natural_gas_per_tLS"], "MMBtu", "MJ")
        # kg Carbon in natural gas per tLS, '12. EAF Mass & Energy Balance!D225'
        mass_C_ng_per_tLS = natural_gas_MJ / LHV_CH4_MJ_PER_KG * C_MW / CH4_MW

        # mass fraction carbon input to EAF as % of steel tap mass,
        # '12. EAF Mass & Energy Balance!D226'
        pct_carbon_steel_tap = self.config.energy_mass_balance_dict["pct_carbon_steel_tap"]
        # kg total Carbon in put per tLS, '12. EAF Mass & Energy Balance!D227'
        total_C_kg_per_tLS = units.convert_units(pct_carbon_steel_tap, "t", "kg")
        # kg additional Carbon required per tLS, '12. EAF Mass & Energy Balance!D228'
        if (total_C_kg_per_tLS - mass_C_DRI_per_tLS) > 0:
            mass_injected_carbon_per_tLS = total_C_kg_per_tLS - mass_C_DRI_per_tLS
        else:
            mass_injected_carbon_per_tLS = 0
        # ton, assume 0.806 tonC/tonCoal,
        # '5. Electric Arc Furnace!C35' > '12. EAF Mass & Energy Balance!D228/0.806/1000'
        # 0.806 is the ratio of ton Carbon per ton Coal
        output_dict["coal_per_tLS"] = units.convert_units(
            mass_injected_carbon_per_tLS / 0.806, "kg", "t"
        )
        # kmol Carbon in NG blown out per tLS, '12. EAF Mass & Energy Balance!D229'
        moles_C_ng_per_tLS = mass_C_ng_per_tLS / C_MW
        # kmol Oxygen needed to blow out NG per tLS,
        # '12. EAF Mass & Energy Balance!D230', carbon in NG oxidizes to CO2 immediately
        # From '12. EAF Mass & Energy Balance!H231', 1 mole of Carbon reacts with
        # 1 mole O2 to form 1 mole of CO2
        moles_O2_ng_per_tLS = moles_C_ng_per_tLS * 1
        # kmol CO2 formed from NG, '12. EAF Mass & Energy Balance!D231'
        moles_CO2_ng_per_tLS = moles_C_ng_per_tLS * 1

        # kg CO2 formed from NG, '12. EAF Mass & Energy Balance!D232'
        output_dict["mass_CO_injected_per_tLS"] = moles_CO2_ng_per_tLS * CO_MW
        # kmol Carbon in DRI blown out per tLS,
        # '12. EAF Mass & Energy Balance!D233', assume remaining C originated in DRI
        moles_C_DRI_per_tLS = (mass_C_DRI_per_tLS - mass_C_steel_per_tLS) / C_MW
        # kmol Oxygen needed to blow out C in DRI per tLS, '12. EAF Mass & Energy Balance!D234'
        # per the notes in '12. EAF Mass & Energy Balance!H235', 1 mole of C reacts with
        # 0.5 mole O2 to form 1 mole of CO
        moles_O2_DRI_per_tLS = moles_C_DRI_per_tLS * 0.5
        # kmol CO formed from C in DRI per tLS, '12. EAF Mass & Energy Balance!D235'
        moles_CO_DRI_per_tLS = moles_C_DRI_per_tLS
        # kg CO formed from C in DRI per tLS, '12. EAF Mass & Energy Balance!D236'
        mass_CO_DRI_per_tLS = moles_CO_DRI_per_tLS * CO_MW
        # kmol C injected carbon blown out per tLS, '12. EAF Mass & Energy Balance!D237',
        # assume remaining C in steel originated in DRI or injected carbon
        moles_C_injected_per_tLS = mass_injected_carbon_per_tLS / C_MW
        # kmol O2 needed to blow out C in injected carbon, '12. EAF Mass & Energy Balance!D238'
        # per the notes in '12. EAF Mass & Energy Balance!H235', 1 mole of C reacts with
        # 0.5 mole O2 to form 1 mole of CO
        moles_O2_injected_per_tLS = moles_C_injected_per_tLS * 0.5

        # kmol CO formed from C in injected carbon, '12. EAF Mass & Energy Balance!D239'
        moles_CO_injected_per_tLS = moles_C_injected_per_tLS * 1
        # kg CO formed from C in injected carbon, '12. EAF Mass & Energy Balance!D240'
        mass_CO_injected_per_tLS = moles_CO_injected_per_tLS * CO_MW

        # kmol O2 required per tLS, '12. EAF Mass & Energy Balance!D241'
        moles_O2_per_tLS = (
            moles_O2_ng_per_tLS
            + moles_O2_injected_per_tLS
            + moles_O2_to_FeO_tLS
            + moles_O2_DRI_per_tLS
        )
        # Nm^3 O2 required per tLS, '12. EAF Mass & Energy Balance!D242' (ideal gas law)
        output_dict["oxygen_per_tLS"] = (moles_O2_per_tLS * R_GAS * T_STD_K) / P_STD_KPA

        # Electric Arc Furnace (EAF) Fed with DRI Directly (No ESF) - Flux Addition
        # (kg/kg), '12. EAF Mass & Energy Balance!D254'
        CaO_MgO_ratio = self.config.energy_mass_balance_dict["CaO_MgO_ratio"]
        # (kg/tLS), '12. EAF Mass & Energy Balance!D255'
        mass_MgO_doloma = output_dict["mass_MgO_slag_per_tLS"]
        # (kg/tLS), '12. EAF Mass & Energy Balance!D256'
        mass_CaO_doloma = mass_MgO_doloma * CaO_MgO_ratio
        # (kg/tLS), '12. EAF Mass & Energy Balance!D257'
        mass_doloma = mass_MgO_doloma + mass_CaO_doloma
        # ton, '5. Electric Arc Furnace!C36' > '12. EAF Mass & Energy Balance!D257/1000'
        output_dict["burnt_doloma_per_tLS"] = units.convert_units(mass_doloma, "kg", "t")
        # (kg/tLS), '12. EAF Mass & Energy Balance!D258'
        mass_lime = mass_CaO_slag_per_tLS - mass_CaO_doloma
        # ton, '5. Electric Arc Furnace!C37' > '12. EAF Mass & Energy Balance!D258/1000'
        output_dict["burnt_lime_per_tLS"] = units.convert_units(mass_lime, "kg", "t")
        # (kg/tLS), '12. EAF Mass & Energy Balance!D259'
        output_dict["mass_flux_per_tLS"] = mass_doloma + mass_lime

        # Electric Arc Furnace (EAF) Fed with DRI Directly (No ESF) - Energy Balance
        # Inputs into EAF (feedstocks)
        # DRI, Scrap, Flux, Oxygen, Carbon
        # NOTE: Possibly replace these mole values with
        # actual enthalpy calculations from excel sheet?
        if (
            self.config.DRI_feed_temp == "hot"
        ):  # 873 K; this temp assumption is baked into the enthalpy values below
            # H (J/mol) Fe,
            # '12. EAF Mass & Energy Balance!D264' > '14. Enthalpy Calculations!C235'
            DRI_Fe_J_mol = 1.8432477097027300e04
            # H (J/mol) FeO,
            # '12. EAF Mass & Energy Balance!D265' > '14. Enthalpy Calculations!C272'
            DRI_FeO_J_mol = -2.346170978905830e05
            # H (J/mol) C,
            # '12. EAF Mass & Energy Balance!D266' > '14. Enthalpy Calculations!C286'
            DRI_C_J_mol = 9.144557831628680e03
            # H (J/mol) SiO2,
            # '12. EAF Mass & Energy Balance!D267' > '14. Enthalpy Calculations!C281'
            DRI_SiO2_J_mol = -8.724350519581140e05
            # H (J/mol) Al2O3,
            #  '12. EAF Mass & Energy Balance!D268' > '14. Enthalpy Calculations!C232'

            DRI_Al2O3_J_mol = -1.613427222924770e06

        if (
            self.config.DRI_feed_temp == "cold"
        ):  # 298 K; this temp assumption is baked into the enthalpy values below
            # H (J/mol) Fe,
            # '12. EAF Mass & Energy Balance!D264' > '14. Enthalpy Calculations!C113'
            DRI_Fe_J_mol = 0.0
            # H (J/mol) FeO,
            # '12. EAF Mass & Energy Balance!D265' > '14. Enthalpy Calculations!C150'
            DRI_FeO_J_mol = -2.65832239120e05
            # H (J/mol) C,
            # '12. EAF Mass & Energy Balance!D266' > '14. Enthalpy Calculations!C69'
            DRI_C_J_mol = 0.0
            # H (J/mol) SiO2,
            #  '12. EAF Mass & Energy Balance!D267' > '14. Enthalpy Calculations!C207'
            DRI_SiO2_J_mol = -9.0830e05
            # H (J/mol) Al2O3,
            # '12. EAF Mass & Energy Balance!D268' > '14. Enthalpy Calculations!C56'
            DRI_Al2O3_J_mol = -1.675711853668660e06

        # kg Fe BF pellets, '12. EAF Mass & Energy Balance!F264'
        DRI_Fe_kg = mass_DRI_per_tLS * inputs["dri_composition_Fe"]
        # kmol Fe BF pellets, '12. EAF Mass & Energy Balance!E264'
        DRI_Fe_n_kmol = DRI_Fe_kg / FE_MW
        # kJ Fe BF pellets, '12. EAF Mass & Energy Balance!G264'
        DRI_Fe_kJ = DRI_Fe_J_mol * DRI_Fe_n_kmol

        # kmol FeO BF pellets, '12. EAF Mass & Energy Balance!E265'
        DRI_FeO_n_kmol = mole_FeO_DRI_per_tLS
        # kJ FeO BF pellets, '12. EAF Mass & Energy Balance!G265'
        DRI_FeO_kJ = DRI_FeO_J_mol * DRI_FeO_n_kmol

        # kg C BF pellets,
        # '12. EAF Mass & Energy Balance!F266' > '12. EAF Mass & Energy Balance!D224'
        DRI_C_kg = mass_C_DRI_per_tLS
        # kmol C BF pellets, '12. EAF Mass & Energy Balance!E266'
        DRI_C_n_kmol = DRI_C_kg / C_MW
        # kJ C BF pellets, '12. EAF Mass & Energy Balance!G266'
        DRI_C_kJ = DRI_C_J_mol * DRI_C_n_kmol

        # kg SiO2 BF pellets,
        # '12. EAF Mass & Energy Balance!F267' > '12. EAF Mass & Energy Balance!D200'
        DRI_SiO2_kg = mass_SiO2_DRI_per_tLS
        # kmol SiO2 BF pellets, '12. EAF Mass & Energy Balance!E267'
        DRI_SiO2_n_kmol = DRI_SiO2_kg / SIO2_MW
        # kJ SiO2 BF pellets, '12. EAF Mass & Energy Balance!G267'
        DRI_SiO2_kJ = DRI_SiO2_J_mol * DRI_SiO2_n_kmol

        # kg Al2O3 BF pellets,
        # '12. EAF Mass & Energy Balance!F268' > '12. EAF Mass & Energy Balance!D202'
        DRI_Al2O3_kg = mass_Al2O3_per_tLS
        # kmol Al2O3 BF pellets, '12. EAF Mass & Energy Balance!E268'
        DRI_Al2O3_n_kmol = DRI_Al2O3_kg / AL2O3_MW
        # kJ Al2O3 BF pellets, '12. EAF Mass & Energy Balance!G268'
        DRI_Al2O3_kJ = DRI_Al2O3_J_mol * DRI_Al2O3_n_kmol

        # H (J/mol) Fe, '12. EAF Mass & Energy Balance!D269' > '14. Enthalpy Calculations!C113'
        scrap_Fe_J_mol = 0.0
        # kg Fe, '12. EAF Mass & Energy Balance!F269'
        scrap_Fe_kg = mass_scrap_per_tLS * scrap_composition["Fe"]
        # kmol Fe, '12. EAF Mass & Energy Balance!E269'
        scrap_Fe_n_kmol = scrap_Fe_kg / FE_MW
        # kJ Fe, '12. EAF Mass & Energy Balance!G269'
        scrap_Fe_kJ = scrap_Fe_J_mol * scrap_Fe_n_kmol

        # H (J/mol) SiO2, '12. EAF Mass & Energy Balance!D270' > '14. Enthalpy Calculations!C207'
        scrap_SiO2_J_mol = -9.0830e05
        # kg SiO2, '12. EAF Mass & Energy Balance!F270' > '12. EAF Mass & Energy Balance!D201'
        scrap_SiO2_kg = mass_SiO2_scrap_per_tLS
        # kmol SiO2, '12. EAF Mass & Energy Balance!E270'
        scrap_SiO2_n_kmol = scrap_SiO2_kg / SIO2_MW
        # kJ SiO2, '12. EAF Mass & Energy Balance!G270'
        scrap_SiO2_kJ = scrap_SiO2_J_mol * scrap_SiO2_n_kmol

        # H (J/mol) CaO, '12. EAF Mass & Energy Balance!D271' > '14. Enthalpy Calculations!C93'
        flux_CaO_J_mol = -6.3490e05
        # kg CaO, '12. EAF Mass & Energy Balance!F271' > '12. EAF Mass & Energy Balance!D207'
        flux_CaO_kg = mass_CaO_slag_per_tLS
        # kmol CaO, '12. EAF Mass & Energy Balance!E271'
        flux_CaO_n_kmol = flux_CaO_kg / CAO_MW
        # kJ CaO, '12. EAF Mass & Energy Balance!G271'
        flux_CaO_kJ = flux_CaO_J_mol * flux_CaO_n_kmol

        # H (J/mol) MgO, '12. EAF Mass & Energy Balance!D272' > '14. Enthalpy Calculations!C181'
        flux_MgO_J_mol = -6.0160e05
        # kg MgO, '12. EAF Mass & Energy Balance!F272' > '12. EAF Mass & Energy Balance!D212'
        flux_MgO_kg = output_dict["mass_MgO_slag_per_tLS"]
        # kmol MgO, '12. EAF Mass & Energy Balance!E272'
        flux_MgO_n_kmol = flux_MgO_kg / MGO_MW
        # kJ MgO, '12. EAF Mass & Energy Balance!G272'
        flux_MgO_kJ = flux_MgO_J_mol * flux_MgO_n_kmol

        # H (J/mol) O2, '12. EAF Mass & Energy Balance!D273' > '14. Enthalpy Calculations!C220'
        O2_J_mol = 0.0
        # kmol O2, '12. EAF Mass & Energy Balance!E273' > '12. EAF Mass & Energy Balance!D241'
        O2_n_kmol = moles_O2_per_tLS
        # kg O2, '12. EAF Mass & Energy Balance!F273'
        output_dict["mass_O2"] = O2_n_kmol * O2_MW
        # kJ O2, '12. EAF Mass & Energy Balance!G273'
        O2_kJ = O2_J_mol * O2_n_kmol

        # H (J/mol) C from NG and injected Carbon,
        # '12. EAF Mass & Energy Balance!D274' > '14. Enthalpy Calculations!C69'
        C_J_mol = 0.0
        # kg C from NG and injected Carbon, '12. EAF Mass & Energy Balance!F274'
        C_kg = mass_C_ng_per_tLS + mass_injected_carbon_per_tLS
        # kmol C from NG and injected Carbon,
        # '12. EAF Mass & Energy Balance!E274' > '12. EAF Mass & Energy Balance!D241'
        C_n_kmol = C_kg / C_MW
        # kJ C from NG and injected Carbon, '12. EAF Mass & Energy Balance!G274'
        C_kJ = C_J_mol * C_n_kmol

        total_EAF_DRI_inputs_kJ = (
            DRI_Fe_kJ
            + DRI_FeO_kJ
            + DRI_C_kJ
            + DRI_SiO2_kJ
            + DRI_Al2O3_kJ
            + scrap_Fe_kJ
            + scrap_SiO2_kJ
            + flux_CaO_kJ
            + flux_MgO_kJ
            + O2_kJ
            + C_kJ
        )

        # EAF Products
        # NOTE: Possibly replace these mole values with
        # actual enthalpy calculations from excel sheet?
        # Steel, Slag, Off-gas
        # H (J/mol) Fe in Steel product,
        # '12. EAF Mass & Energy Balance!D279' > '14. Enthalpy Calculations!C364'
        steel_Fe_J_mol = 7.583849597377010e04
        # kg Fe in Steel product,
        # '12. EAF Mass & Energy Balance!F279' > '12. EAF Mass & Energy Balance!D7'
        steel_Fe_kg = mass_iron_per_tLS
        # kmol Fe in Steel product, '12. EAF Mass & Energy Balance!E279'
        steel_Fe_kmol = steel_Fe_kg / FE_MW
        # kJ Fe in Steel product, '12. EAF Mass & Energy Balance!G279'
        steel_Fe_kJ = steel_Fe_J_mol * steel_Fe_kmol

        # H (J/mol) C in Steel product,
        # '12. EAF Mass & Energy Balance!D280' > '14. Enthalpy Calculations!C371'
        steel_C_J_mol = 3.2201451507069200e04
        # kg C in Steel product,
        # '12. EAF Mass & Energy Balance!F280' > '12. EAF Mass & Energy Balance!D8'
        steel_C_kg = mass_carbon_per_tLS
        # kmol C in Steel product, '12. EAF Mass & Energy Balance!E280'
        steel_C_kmol = steel_C_kg / C_MW
        # kJ C in Steel product, '12. EAF Mass & Energy Balance!G280'
        steel_C_kJ = steel_C_J_mol * steel_C_kmol

        # kg FeO in slag product,
        # '12. EAF Mass & Energy Balance!F281' > '12. EAF Mass & Energy Balance!D213'
        slag_FeO_kg = output_dict["mass_FeO_slag_per_tLS"]
        # kg SiO2 in slag product,
        # '12. EAF Mass & Energy Balance!F282' > '12. EAF Mass & Energy Balance!D205'
        slag_SiO2_kg = mass_SiO2_slag_per_tLS
        # kg Al2O3 in slag product,
        # '12. EAF Mass & Energy Balance!F283' > '12. EAF Mass & Energy Balance!D206'
        slag_Al2O3_kg = mass_Al2O3_slag_per_tLS
        # kg CaO in slag product,
        # '12. EAF Mass & Energy Balance!F284' > '12. EAF Mass & Energy Balance!D207'
        slag_CaO_kg = mass_CaO_slag_per_tLS
        # kg MgO in slag product,
        # '12. EAF Mass & Energy Balance!F285' > '12. EAF Mass & Energy Balance!D212'
        slag_MgO_kg = output_dict["mass_MgO_slag_per_tLS"]

        if self.config.pellet_grade == "BF":
            # H (MJ/kg) BF grade pellets estimated enthalpy of liquid slag (Bjorkvall approach),
            # '14. Enthalpy Calculations!J14'
            pellets_MJ_kg = -8.377283654515320e00
        if self.config.pellet_grade == "DR":
            # H (MJ/kg) BF grade pellets estimated enthalpy of liquid slag (Bjorkvall approach),
            # '14. Enthalpy Calculations!J14'
            pellets_MJ_kg = -8.382019633585080e00

        slag_total_kJ = units.convert_units(
            pellets_MJ_kg
            * (slag_FeO_kg + slag_SiO2_kg + slag_Al2O3_kg + slag_CaO_kg + slag_MgO_kg),
            "MJ",
            "kJ",
        )

        # H (J/mol) CO in off-gas product,
        # '12. EAF Mass & Energy Balance!D286' > '14. Enthalpy Calculations!C322'
        off_gas_CO_J_mol = -5.887443663594190e04
        # kmol CO in off-gas product,
        # '12. EAF Mass & Energy Balance!E286' > '12. EAF Mass & Energy Balance!D239'
        off_gas_CO_kmol = moles_CO_injected_per_tLS
        # kg CO in off-gas product, '12. EAF Mass & Energy Balance!F286'
        output_dict["off_gas_CO_kg"] = mass_CO_injected_per_tLS + mass_CO_DRI_per_tLS
        # kJ CO in off-gas product, '12. EAF Mass & Energy Balance!G286'
        off_gas_CO_kJ = off_gas_CO_J_mol * off_gas_CO_kmol

        # H (J/mol) CO2 in off-gas product,
        # '12. EAF Mass & Energy Balance!D287' > '14. Enthalpy Calculations!C327'
        off_gas_CO2_J_mol = -3.10933969795530e05
        # kmol CO2 in off-gas product,
        # '12. EAF Mass & Energy Balance!E287' > '12. EAF Mass & Energy Balance!D231'
        off_gas_CO2_kmol = moles_CO2_ng_per_tLS
        # kJ CO2 in off-gas product, '12. EAF Mass & Energy Balance!G287'
        off_gas_CO2_kJ = off_gas_CO2_J_mol * off_gas_CO2_kmol

        total_EAF_DRI_products_kJ = (
            steel_Fe_kJ + steel_C_kJ + slag_total_kJ + off_gas_CO_kJ + off_gas_CO2_kJ
        )

        # (kJ/tHM) Energy Consumption of EAF, '12. EAF Mass & Energy Balance!G290'
        EAF_DRI_energy_consumption_kJ_tHM = total_EAF_DRI_products_kJ - total_EAF_DRI_inputs_kJ
        # (kWh/tHM) Energy Consumption of EAF, '12. EAF Mass & Energy Balance!G291'
        EAF_DRI_energy_consumption_kWh_tHM = units.convert_units(
            EAF_DRI_energy_consumption_kJ_tHM, "kJ", "kW*h"
        )

        # NOTE EAF_scarp_heat_loss_adjustment_abs comes from EAF scrap only performance model
        # NOTE: Need to update below to possibly call EAF scrap only model here and calculate,
        # or pre-calculate in other workflows
        # (kWh/tHM) EAF DRI absolute heat loss adjustment,
        # '12. EAF Mass & Energy Balance!293' > '12. EAF Mass & Energy Balance!G148'
        EAF_DRI_heat_loss_adjustment_abs = self.config.energy_mass_balance_dict[
            "EAF_scrap_heat_loss_adjustment_abs"
        ]

        electricity_usage_per_tonne_steel = self.config.energy_mass_balance_dict[
            "electricity_kWh_per_tonne_steel"
        ]
        # % EAF DRI heat loss adjustment, '12. EAF Mass & Energy Balance!G294'
        output_dict["EAF_DRI_heat_loss_pct"] = (
            EAF_DRI_heat_loss_adjustment_abs / electricity_usage_per_tonne_steel
        )
        # (kWh/tHM) Total EAF with scrap energy consumption with heat loss adjustment,
        # '12. EAF Mass & Energy Balance!G295'
        output_dict["electricity_per_tLS"] = (
            EAF_DRI_energy_consumption_kWh_tHM + EAF_DRI_heat_loss_adjustment_abs
        )

        return output_dict
