import numpy as np
from attrs import field, define
from openmdao.utils import units

from h2integrate.core.utilities import BaseConfig, merge_shared_inputs
from h2integrate.tools.constants import (
    C_MW,
    CO_MW,
    FE_MW,
    R_GAS,
    CAO_MW,
    CH4_MW,
    CO2_MW,
    FEO_MW,
    MGO_MW,
    SIO2_MW,
    T_STD_K,
    P_STD_KPA,
    LHV_CH4_MJ_PER_KG,
)
from h2integrate.core.model_baseclasses import PerformanceModelBaseClass


@define
class CMUElectricArcFurnaceScrapOnlyPerformanceConfig(BaseConfig):
    """Configuration baseclass for CMUElectricArcFurnaceScrapOnlyPerformanceComponent.

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
        energy_mass_balance_dict (dict): dictionary with inputs for energy and mass
            balance calculations. Defaults are based on values from CMU decarbSTEEL EAF model.
            - natural_gas (float): Natural gas used per ton of steel. Default 0.44 MMBtu/ton.
            - electrodes (float): Electrodes used per ton of steel. Default 2.00 kg/ton.
            - slag_basicity (float): basicity, kg CaO / (kg SiO2 + kg Al2O3). Default 1.50.
            - mass_Al2O3_slag_per_tscrap (float): kg Al2O3 in slag per ton scrap.
                Default 0.0.
            - mass_Al2O3_slag_per_tLS (float): total kg Al2O3 in slag per ton liquid steel.
                Default 0.0.
            - pct_MgO_slag (float): percent mass fraction of MgO in slag. Default is 0.12.
            - pct_FeO_slag (float): percent mass fraction of FeO in slag. Default is 0.30.
            - pct_carbon_steel_tap (float): percent mass fraction carbon input to EAF as
                % of steel tap mass. Default 0.03.
            - CaO_MgO_ratio (float): kg of CaO to kg MgO. Default is 56/40.
            - electricity_kWh_per_tonne_steel (float): electricity usage per ton of steel.
                Default is 470 kWh/ton.

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
    energy_mass_balance_dict: dict = field(
        default={
            # MMBtu/ton steel, '5. Electric Arc Furnace!C32'
            "natural_gas": 0.44,
            # kg/ton steel, '5. Electric Arc Furnace!C8'
            "electrodes": 2.00,
            # basicity, kg CaO / (kg SiO2 + kg Al2O3),
            # '12. EAF Mass & Energy Balance!D51'
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
        }
    )


class CMUElectricArcFurnaceScrapOnlyPerformanceComponent(PerformanceModelBaseClass):
    """Electric Arc Furnace performance model based on CMU decarbSTEEL EAF Model v5"""

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

        self.config = CMUElectricArcFurnaceScrapOnlyPerformanceConfig.from_dict(
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

        feedstocks_to_units = {
            "oxygen": "m**3/h",
            "electricity": "kW",
            "natural_gas": "MMBtu/h",
            "electrodes": "kg/h",
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
            "mass_Fe_from_scrap",
            val=0.0,
            shape=n_timesteps,
            units="kg",
            desc="Total unit of Fe from scrap",
        )

        self.add_output(
            "mass_steel_per_unit_scrap",
            val=0.0,
            shape=n_timesteps,
            units="kg/t",
            desc="Total unit of steel formed from EAF fed with scrap only per unit of scrap",
        )

    def compute(self, inputs, outputs):
        """calculates energy and mass balance for EAF fed with scrap only case on a per unit basis,
        then calculates feedstock usage based on steel demand and available feedstocks,
        and finally calculates outputs.
        """
        if inputs["annual_production"] > inputs["rated_steel_capacity"]:
            raise ValueError(
                f"Rated steel production ({inputs['annual_production']} t/year) cannot exceed "
                f"rated steel capacity ({inputs['rated_steel_capacity']} t/year)."
            )

        # calculate energy mass balance on a per ton liquid steel basis
        energy_mass_per_tonne = self.energy_mass_balance_per_unit()

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
        outputs["mass_Fe_from_scrap"] = (
            energy_mass_per_tonne["mass_Fe_scrap_per_tLS"] * steel_production
        )
        # Total kg Steel formed from scrap per ton scrap
        outputs["mass_steel_per_unit_scrap"] = energy_mass_per_tonne["mass_steel_per_tscrap"]

    def energy_mass_balance_per_unit(self):
        """Computes the energy and mass balance for the EAF fed with scrap only case on a
            per ton of scrap basis (tscrap) and per ton of liquid steel basis (tLS).
        Returns:
            output_dict (dict): Dictionary with the amount of feedstocks and energy used per
                ton of steel.
                - mass_slag_per_tscrap (kg/t): Total mass of slag produced per ton of scrap.
                - mass_MgO_slag_per_tscrap (kg/t): Mass of MgO in slag per ton of scrap.
                - mass_FeO_slag_per_tscrap (kg/t): Mass of FeO in slag per ton of scrap.
                - mass_Fe_to_FeO_tscrap (kg/t): Mass of Fe consumed to produce FeO per ton scrap.
                - mass_Fe_scrap_per_tscrap (kg/t): Mass of Fe from scrap per ton of scrap.
                - mass_steel_per_tscrap (kg/t): Mass of steel formed from scrap per ton of scrap.
                - natural_gas_per_tLS (MMBtu/t): Natural gas usage per ton of liquid steel.
                - electrodes_per_tLS (kg/t): Electrode usage per ton of liquid steel.
                - mass_scrap_per_tLS (t/t): Mass of scrap per ton of liquid steel.
                - mass_slag_per_tLS (kg/t): Mass of slag per ton of liquid steel.
                - mass_MgO_slag_per_tLS (kg/t): Mass of MgO in slag per ton of liquid steel.
                - mass_FeO_slag_per_tLS (kg/t): Mass of FeO in slag per ton of liquid steel.
                - mass_Fe_to_FeO_tLS (kg/t): Mass of Fe consumed to produce FeO per ton of
                    liquid steel.
                - mass_Fe_scrap_per_tLS (kg/t): Mass of Fe from scrap per ton of liquid steel.
                - coal_per_tLS (t/t): Mass of coal per ton of liquid steel.
                - oxygen_per_tLS (Nm^3/t): Normal cubic meters of oxygen per ton of liquid steel.
                - burnt_doloma_per_tLS (t/t): Mass of burnt doloma per ton of liquid steel.
                - burnt_lime_per_tLS (t/t): Mass of burnt lime per ton of liquid steel.
                - mass_flux_per_tLS (kg/t): Mass of flux (lime and doloma) per ton of liquid steel.
                - EAF_scrap_heat_loss_pct (%): Percentage of heat loss in EAF with scrap-only case.
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
        # NOTE: Hardcoding mass_steel_stream and mass_basis_scrap for per
        # ton liquid steel and per ton scrap basis calculations

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

        # Electric Arc Furnace Fed with Scrap Only - Mass Balance (Fe, C, O, MgO, SiO2, Al2O3, CaO)
        # NOTE: calculated per ton scrap (tsrap)

        # kg, '12. EAF Mass & Energy Balance!D47'
        mass_basis_scrap = 1000
        # % mass SiO2, 'Model Inputs & Outputs!B28' > '12. EAF Mass & Energy Balance!D48'
        mass_pct_SiO2_scrap = scrap_composition["SiO2"]
        # kg SiO2 per ton scrap, '12. EAF Mass & Energy Balance!D49'
        mass_SiO2_scrap_per_tscrap = mass_basis_scrap * mass_pct_SiO2_scrap

        # basicity, kg CaO / (kg SiO2 + kg Al2O3), '12. EAF Mass & Energy Balance!D51'
        slag_B3 = self.config.energy_mass_balance_dict["slag_basicity"]
        # kg total SiO2 in slag per ton scrap, '12. EAF Mass & Energy Balance!D52'
        mass_SiO2_slag_per_tscrap = mass_SiO2_scrap_per_tscrap
        # kg Al2O3 in slag per ton scrap, '12. EAF Mass & Energy Balance!D53'
        mass_Al2O3_slag_per_tscrap = self.config.energy_mass_balance_dict[
            "mass_Al2O3_slag_per_tscrap"
        ]
        # kg CaO in slag per ton scrap,  '12. EAF Mass & Energy Balance!D54'
        mass_CaO_slag_per_tscrap = slag_B3 * (
            mass_SiO2_slag_per_tscrap + mass_Al2O3_slag_per_tscrap
        )

        # mass fraction MgO in slag, assumed input, '12. EAF Mass & Energy Balance!D56'
        pct_MgO_slag = self.config.energy_mass_balance_dict["pct_MgO_slag"]
        # mass fraction FeO in slag, assumed input, '12. EAF Mass & Energy Balance!D57'
        pct_FeO_slag = self.config.energy_mass_balance_dict["pct_FeO_slag"]

        # kg slag per ton scrap, '12. EAF Mass & Energy Balance!D58'
        output_dict["mass_slag_per_tscrap"] = (
            mass_SiO2_slag_per_tscrap + mass_Al2O3_slag_per_tscrap + mass_CaO_slag_per_tscrap
        ) / (1 - pct_MgO_slag - pct_FeO_slag)
        # kg MgO in slag per ton scrap, '12. EAF Mass & Energy Balance!D59'
        output_dict["mass_MgO_slag_per_tscrap"] = pct_MgO_slag * output_dict["mass_slag_per_tscrap"]

        # kg FeO in slag per ton scrap, '12. EAF Mass & Energy Balance!D60'
        output_dict["mass_FeO_slag_per_tscrap"] = pct_FeO_slag * output_dict["mass_slag_per_tscrap"]
        # kmol FeO in slag per ton scrap, '12. EAF Mass & Energy Balance!D61'
        moles_FeO_slag_per_tscrap = output_dict["mass_FeO_slag_per_tscrap"] / FEO_MW

        # kmol Fe consumed to produce FeO per ton scrap, '12. EAF Mass & Energy Balance!D62'
        moles_Fe_to_FeO_tscrap = moles_FeO_slag_per_tscrap
        # kg Fe consumed to produce FeO per ton scrap, '12. EAF Mass & Energy Balance!D63'
        output_dict["mass_Fe_to_FeO_tscrap"] = moles_Fe_to_FeO_tscrap * FE_MW

        # kg Fe mass from scrap per ton scrap, '12. EAF Mass & Energy Balance!D65'
        output_dict["mass_Fe_scrap_per_tscrap"] = (
            mass_basis_scrap * scrap_composition["Fe"]
        ) - output_dict["mass_Fe_to_FeO_tscrap"]
        # kg steel formed from DRI + scrap per ton srap, '12. EAF Mass & Energy Balance!D66'
        output_dict["mass_steel_per_tscrap"] = output_dict["mass_Fe_scrap_per_tscrap"] / (
            1 - pct_carbon_steel
        )

        ###### forward mass calculation on a per tonne of liquid steel basis #################

        # NOTE calculated per ton liquid steel (tLS)
        mass_scrap_per_tLS = (mass_basis_scrap / output_dict["mass_steel_per_tscrap"]) * 1000

        # kg scrap per ton LS, '12. EAF Mass & Energy Balance!D69'
        output_dict["mass_scrap_per_tLS"] = units.convert_units(mass_scrap_per_tLS, "kg", "t")
        # mass fraction SiO2, '12. EAF Mass & Energy Balance!D70' > 'Model Inputs & Outputs!B28'
        mass_pct_SiO2_scrap = scrap_composition["SiO2"]
        # kg SiO2 from scrap per ton LS, '12. EAF Mass & Energy Balance!D71
        mass_SiO2_scrap_per_tLS = mass_scrap_per_tLS * mass_pct_SiO2_scrap
        # total kg SiO2 in slag per ton LS, '12. EAF Mass & Energy Balance!D74'
        mass_SiO2_slag_per_tLS = mass_SiO2_scrap_per_tLS
        # total kg Al2O3 in slag per ton LS, '12. EAF Mass & Energy Balance!D75'
        mass_Al2O3_slag_per_tLS = self.config.energy_mass_balance_dict["mass_Al2O3_slag_per_tLS"]

        # total kg CaO in slag per ton LS, '12. EAF Mass & Energy Balance!D76'
        mass_CaO_slag_per_tLS = slag_B3 * (mass_SiO2_slag_per_tLS + mass_Al2O3_slag_per_tLS)

        # kg slag per ton LS, '12. EAF Mass & Energy Balance!D80'
        output_dict["mass_slag_per_tLS"] = (
            mass_SiO2_slag_per_tLS + mass_Al2O3_slag_per_tLS + mass_CaO_slag_per_tLS
        ) / (1 - pct_MgO_slag - pct_FeO_slag)
        # total mass MgO in slag per ton LS, '12. EAF Mass & Energy Balance!D81'
        output_dict["mass_MgO_slag_per_tLS"] = pct_MgO_slag * output_dict["mass_slag_per_tLS"]

        # total mass FeO in slag per ton LS, '12. EAF Mass & Energy Balance!D82'
        output_dict["mass_FeO_slag_per_tLS"] = pct_FeO_slag * output_dict["mass_slag_per_tLS"]
        # moles FeO in slag per ton LS, '12. EAF Mass & Energy Balance!D83'
        moles_FeO_slag_per_tLS = output_dict["mass_FeO_slag_per_tLS"] / FEO_MW
        # moles Fe consumed to produce FeO in slag per ton LS,
        # '12. EAF Mass & Energy Balance!D84'
        moles_Fe_to_FeO_tLS = moles_FeO_slag_per_tLS
        # kg Fe consumed to produce FeO in slag per ton LS, '12. EAF Mass & Energy Balance!D85'
        output_dict["mass_Fe_to_FeO_tLS"] = moles_Fe_to_FeO_tLS * FE_MW
        # moles O2 consumed to produce FeO in slag per ton LS,
        # '12. EAF Mass & Energy Balance!D86'
        moles_O2_to_FeO_tLS = moles_Fe_to_FeO_tLS * 0.5

        output_dict["mass_Fe_scrap_per_tLS"] = (
            output_dict["mass_Fe_scrap_per_tscrap"] * (output_dict["mass_scrap_per_tLS"])
        )

        # method causes small differences rather than using MMbtu_to_MJ = 1055.0
        natural_gas_MJ = units.convert_units(output_dict["natural_gas_per_tLS"], "MMBtu", "MJ")
        # kg Carbon in NG per ton LS, '12. EAF Mass & Energy Balance!D88'
        mass_C_ng_per_tLS = ((natural_gas_MJ) / LHV_CH4_MJ_PER_KG) * (C_MW / CH4_MW)
        # mass fraction carbon input to EAF as % of steel tap mass,
        # '12. EAF Mass & Energy Balance!D89'
        pct_carbon_steel_tap = self.config.energy_mass_balance_dict["pct_carbon_steel_tap"]
        # kg total carbon input per tLS, '12. EAF Mass & Energy Balance!D90'
        total_C_kg_per_tLS = units.convert_units(pct_carbon_steel_tap, "t", "kg")
        # additional carbon required / injected per tLS, '12. EAF Mass & Energy Balance!D91'
        mass_injected_carbon_per_tLS = total_C_kg_per_tLS

        # ton, assume 0.806 tonC/tonCoal,
        # '5. Electric Arc Furnace!C10' > '12. EAF Mass & Energy Balance!D91/0.806/1000'
        # 0.806 is the ratio of ton Carbon per ton Coal
        output_dict["coal_per_tLS"] = units.convert_units(
            mass_injected_carbon_per_tLS / 0.806, "kg", "t"
        )

        # kmol Carbon in NG blown out per ton LS, '12. EAF Mass & Energy Balance!D92'
        moles_C_ng_per_tLS = mass_C_ng_per_tLS / C_MW
        # kmol O2 needed to blow out NG per tLS,
        # '12. EAF Mass & Energy Balance!D93'
        moles_O2_ng_per_tLS = moles_C_ng_per_tLS * 1.0
        # kmol CO2 formed per tLS,
        # '12. EAF Mass & Energy Balance!D94'
        moles_CO2_ng_per_tLS = moles_C_ng_per_tLS * 1.0
        # kg CO2 formed per tLS, '12. EAF Mass & Energy Balance!D95'
        moles_CO2_ng_per_tLS * CO2_MW
        # kmol C per tLS, '12. EAF Mass & Energy Balance!D96'
        moles_C_injected_per_tLS = (mass_injected_carbon_per_tLS - mass_carbon_per_tLS) / C_MW
        # kmol O2 needed to blow out C in injected Carbon,
        # '12. EAF Mass & Energy Balance!D97'
        # 1 mole of C reacts with 0.5 mole O2 to form 1 mole of CO
        moles_O2_injected_per_tLS = moles_C_injected_per_tLS * 0.5

        # kmol CO formed per tLS, '12. EAF Mass & Energy Balance!D98'
        moles_CO_injected_per_tLS = moles_C_injected_per_tLS
        # kg CO formed per tLS, '12. EAF Mass & Energy Balance!D99'
        moles_CO_injected_per_tLS * CO_MW
        # kmol O2 required per tLS, '12. EAF Mass & Energy Balance!D100'
        moles_O2_per_tLS = moles_O2_ng_per_tLS + moles_O2_injected_per_tLS + moles_O2_to_FeO_tLS
        # Nm^3 O2 required per tLS,
        # '12. EAF Mass & Energy Balance!D101' > '5. Electric Arc Furnace!C5'
        output_dict["oxygen_per_tLS"] = (moles_O2_per_tLS * R_GAS * T_STD_K) / P_STD_KPA

        # Electric Arc Furnace (EAF) Fed with Scrap - Flux Addition
        # (kg/kg), '12. EAF Mass & Energy Balance!D113'
        CaO_MgO_ratio = self.config.energy_mass_balance_dict["CaO_MgO_ratio"]
        # (kg/tLS), '12. EAF Mass & Energy Balance!D114'
        mass_MgO_doloma = output_dict["mass_MgO_slag_per_tLS"]
        # (kg/tLS), '12. EAF Mass & Energy Balance!D115'
        mass_CaO_doloma = mass_MgO_doloma * CaO_MgO_ratio
        # (kg/tLS), '12. EAF Mass & Energy Balance!D116'
        mass_doloma = mass_MgO_doloma + mass_CaO_doloma
        # ton, '5. Electric Arc Furnace!C11' > '12. EAF Mass & Energy Balance!D116/1000'
        output_dict["burnt_doloma_per_tLS"] = units.convert_units(mass_doloma, "kg", "t")
        # (kg/tLS), '12. EAF Mass & Energy Balance!D117'
        mass_lime = mass_CaO_slag_per_tLS - mass_CaO_doloma
        # ton, '5. Electric Arc Furnace!C12' > '12. EAF Mass & Energy Balance!D117/1000'
        output_dict["burnt_lime_per_tLS"] = units.convert_units(mass_lime, "kg", "t")
        # (kg/tLS), '12. EAF Mass & Energy Balance!D118'
        output_dict["mass_flux_per_tLS"] = mass_doloma + mass_lime

        # Electric Arc Furnace (EAF) Fed with Scrap Only - Energy Balance
        ###### energy balance #################
        # Inputs into EAF (feedstocks)
        # Scrap, Flux, Oxygen, Carbon
        # NOTE: Possibly replace these mole values w/ actual enthalpy calculations from excel?
        # CMU decarbSTEEL v5 uses a look up table based on temperature to
        # determine enthalpy in tab '14. Enthalpy Calculations'
        # Potentially update enthalpy calculation to use package CoolProp
        # Method example using CoolProp
        # from CoolProp.CoolProp import PropsSI

        # # Parameters for Iron (Fe)
        # temperature = 500  # in Kelvin (K)
        # pressure = 101325   # in Pascal (Pa)

        # # Calculate Enthalpy (h) in J/kg
        # enthalpy = PropsSI('H', 'T', temperature, 'P', pressure, 'Iron')

        # H (J/mol) Fe, '12. EAF Mass & Energy Balance!D124' > '14. Enthalpy Calculations!C113'
        scrap_Fe_J_mol = 0.0
        # kg Fe, '12. EAF Mass & Energy Balance!F124'
        scrap_Fe_kg = output_dict["mass_scrap_per_tLS"] * scrap_composition["Fe"]
        # kmol Fe, '12. EAF Mass & Energy Balance!E124'
        scrap_Fe_n_kmol = scrap_Fe_kg / FEO_MW
        # kJ Fe, '12. EAF Mass & Energy Balance!G124'
        scrap_Fe_kJ = scrap_Fe_J_mol * scrap_Fe_n_kmol

        # H (J/mol) SiO2, '12. EAF Mass & Energy Balance!D125' > '14. Enthalpy Calculations!C207'
        scrap_SiO2_J_mol = -9.0830e05
        # kg SiO2, '12. EAF Mass & Energy Balance!F125' > '12. EAF Mass & Energy Balance!D71'
        scrap_SiO2_kg = mass_SiO2_scrap_per_tLS
        # kmol SiO2, '12. EAF Mass & Energy Balance!E125'
        scrap_SiO2_n_kmol = scrap_SiO2_kg / SIO2_MW
        # kJ SiO2, '12. EAF Mass & Energy Balance!G125'
        scrap_SiO2_kJ = scrap_SiO2_J_mol * scrap_SiO2_n_kmol

        # H (J/mol) CaO, '12. EAF Mass & Energy Balance!D126' > '14. Enthalpy Calculations!C93'
        flux_CaO_J_mol = -6.3490e05
        # kg CaO, '12. EAF Mass & Energy Balance!F126' > '12. EAF Mass & Energy Balance!D76'
        flux_CaO_kg = mass_CaO_slag_per_tLS
        # kmol CaO, '12. EAF Mass & Energy Balance!E126'
        flux_CaO_n_kmol = flux_CaO_kg / CAO_MW
        # kJ CaO, '12. EAF Mass & Energy Balance!G126'
        flux_CaO_kJ = flux_CaO_J_mol * flux_CaO_n_kmol

        # H (J/mol) MgO,
        # '12. EAF Mass & Energy Balance!D127' > '14. Enthalpy Calculations!C181'
        flux_MgO_J_mol = -6.0160e05

        # kg MgO,
        # '12. EAF Mass & Energy Balance!F127' > '12. EAF Mass & Energy Balance!D81'
        flux_MgO_kg = output_dict["mass_MgO_slag_per_tLS"]

        # kmol MgO, '12. EAF Mass & Energy Balance!E127'
        flux_MgO_n_kmol = flux_MgO_kg / MGO_MW

        # kJ MgO, '12. EAF Mass & Energy Balance!G127'
        flux_MgO_kJ = flux_MgO_J_mol * flux_MgO_n_kmol

        # H (J/mol) O2,
        # '12. EAF Mass & Energy Balance!D128' > '14. Enthalpy Calculations!C220'
        O2_J_mol = 0.0
        # kmol O2,
        # '12. EAF Mass & Energy Balance!E128' > '12. EAF Mass & Energy Balance!D100'
        O2_n_kmol = moles_O2_per_tLS
        # kJ O2, '12. EAF Mass & Energy Balance!G128'
        O2_kJ = O2_J_mol * O2_n_kmol

        # H (J/mol) C from NG and injected Carbon,
        # '12. EAF Mass & Energy Balance!D129' > '14. Enthalpy Calculations!C69'
        C_J_mol = 0.0

        # kg C from NG and injected Carbon, '12. EAF Mass & Energy Balance!F129'
        C_kg = mass_C_ng_per_tLS + mass_injected_carbon_per_tLS

        # kmol C from NG and injected Carbon,
        # '12. EAF Mass & Energy Balance!E129' > '12. EAF Mass & Energy Balance!D241'
        C_n_kmol = C_kg / C_MW

        # kJ C from NG and injected Carbon, '12. EAF Mass & Energy Balance!G129'
        C_kJ = C_J_mol * C_n_kmol

        # total kJ EAF inputs, '12. EAF Mass & Energy Balance!G130'
        total_EAF_scrap_inputs_kJ = (
            scrap_Fe_kJ + scrap_SiO2_kJ + flux_CaO_kJ + flux_MgO_kJ + O2_kJ + C_kJ
        )

        # EAF Products
        # Steel, Slag, Off-gas
        # NOTE: Possibly replace these mole values w/ actual enthalpy calculations from excel?
        # H (J/mol) Fe in Steel product,
        # '12. EAF Mass & Energy Balance!D134' > '14. Enthalpy Calculations!C364'
        steel_Fe_J_mol = 7.583849597377010e04

        # kg Fe in Steel product,
        # '12. EAF Mass & Energy Balance!F134' > '12. EAF Mass & Energy Balance!D7'
        steel_Fe_kg = mass_iron_per_tLS

        # kmol Fe in Steel product, '12. EAF Mass & Energy Balance!E134'
        steel_Fe_kmol = steel_Fe_kg / FE_MW

        # kJ Fe in Steel product, '12. EAF Mass & Energy Balance!G134'
        steel_Fe_kJ = steel_Fe_J_mol * steel_Fe_kmol

        # H (J/mol) C in Steel product,
        # '12. EAF Mass & Energy Balance!D135' > '14. Enthalpy Calculations!C371'
        steel_C_J_mol = 3.220145150706920e04
        # kg C in Steel product,
        # '12. EAF Mass & Energy Balance!F135' > '12. EAF Mass & Energy Balance!D8'
        steel_C_kg = mass_carbon_per_tLS
        steel_C_kmol = (
            steel_C_kg / C_MW
        )  # kmol C in Steel product, '12. EAF Mass & Energy Balance!E135'

        # kJ C in Steel product, '12. EAF Mass & Energy Balance!G135'
        steel_C_kJ = steel_C_J_mol * steel_C_kmol

        # kg FeO in slag product,
        # '12. EAF Mass & Energy Balance!F136' > '12. EAF Mass & Energy Balance!D82'
        slag_FeO_kg = output_dict["mass_FeO_slag_per_tLS"]
        # kg SiO2 in slag product,
        # '12. EAF Mass & Energy Balance!F137' > '12. EAF Mass & Energy Balance!D74'
        slag_SiO2_kg = mass_SiO2_slag_per_tLS
        # kg Al2O3 in slag product,
        # '12. EAF Mass & Energy Balance!F138' > '12. EAF Mass & Energy Balance!D75'
        slag_Al2O3_kg = mass_Al2O3_slag_per_tLS
        # kg CaO in slag product,
        # '12. EAF Mass & Energy Balance!F139' > '12. EAF Mass & Energy Balance!D76'
        slag_CaO_kg = mass_CaO_slag_per_tLS

        # kg MgO in slag product,
        # '12. EAF Mass & Energy Balance!F140' > '12. EAF Mass & Energy Balance!D81'
        slag_MgO_kg = output_dict["mass_MgO_slag_per_tLS"]

        # slag_total_kJ == '12. EAF Mass & Energy Balance!G140'
        slag_total_kJ = (
            -8.35401374434514
            * (slag_FeO_kg + slag_SiO2_kg + slag_Al2O3_kg + slag_CaO_kg + slag_MgO_kg)
        ) * 1000

        # H (J/mol) CO in off-gas product,
        # '12. EAF Mass & Energy Balance!D141' > '14. Enthalpy Calculations!C322'
        off_gas_CO_J_mol = -5.887443663594190e04

        # kmol CO in off-gas product,
        # '12. EAF Mass & Energy Balance!E141' > '12. EAF Mass & Energy Balance!D98'
        off_gas_CO_kmol = moles_CO_injected_per_tLS

        # kJ CO in off-gas product, '12. EAF Mass & Energy Balance!G141'
        off_gas_CO_kJ = off_gas_CO_J_mol * off_gas_CO_kmol

        # H (J/mol) CO2 in off-gas product,
        # '12. EAF Mass & Energy Balance!D142' > '14. Enthalpy Calculations!C327'
        off_gas_CO2_J_mol = -3.10933969795530e05

        # kmol CO2 in off-gas product,
        # '12. EAF Mass & Energy Balance!E142' > '12. EAF Mass & Energy Balance!D94'
        off_gas_CO2_kmol = moles_CO2_ng_per_tLS

        # kJ CO2 in off-gas product, '12. EAF Mass & Energy Balance!G142'
        off_gas_CO2_kJ = off_gas_CO2_J_mol * off_gas_CO2_kmol

        # total kJ EAF products, '12. EAF Mass & Energy Balance!G143'
        total_EAF_scrap_products_kJ = (
            steel_Fe_kJ + steel_C_kJ + slag_total_kJ + off_gas_CO_kJ + off_gas_CO2_kJ
        )

        # (kJ/tHM) EAF scrap energy consumption, '12. EAF Mass & Energy Balance!G145'
        EAF_scrap_energy_consumption_kJ_tHM = (
            total_EAF_scrap_products_kJ - total_EAF_scrap_inputs_kJ
        )

        # (kWh/tHM) EAF scrap energy consumption, '12. EAF Mass & Energy Balance!G146'
        EAF_scrap_energy_consumption_kWh_tHM = units.convert_units(
            EAF_scrap_energy_consumption_kJ_tHM, "kJ", "kW*h"
        )

        # NOTE: 470.00 is a hardcoded value / assumption input on '5. Electric Arc Furnace'!C6
        electricity_usage_per_tonne_steel = self.config.energy_mass_balance_dict[
            "electricity_kWh_per_tonne_steel"
        ]

        # (kWh/tHM) EAF scrap absolute heat loss adjustment,
        # '12. EAF Mass & Energy Balance!G148'
        EAF_scrap_heat_loss_adjustment_abs = (
            electricity_usage_per_tonne_steel - EAF_scrap_energy_consumption_kWh_tHM
        )
        # % EAF scrap heat loss adjustment, '12. EAF Mass & Energy Balance!G149'
        output_dict["EAF_scrap_heat_loss_pct"] = (
            EAF_scrap_heat_loss_adjustment_abs / electricity_usage_per_tonne_steel
        )

        # (kWh/tHM) Total EAF with scrap energy consumption with heat loss adjustment,
        # '12. EAF Mass & Energy Balance!G151'`
        EAF_scrap_energy_consumption_w_heat_loss_kWh_tHM = (
            EAF_scrap_energy_consumption_kWh_tHM + EAF_scrap_heat_loss_adjustment_abs
        )

        # kWh/ton Hot Metal / Liquid Steel?,
        # '12. EAF Mass & Energy Balance!G151' >'5. Electric Arc Furnace!C6'
        output_dict["electricity_per_tLS"] = EAF_scrap_energy_consumption_w_heat_loss_kWh_tHM

        return output_dict
