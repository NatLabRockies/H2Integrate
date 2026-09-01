import copy
import warnings

import numpy as np
import pandas as pd
from attrs import field, define, validators
from openmdao.utils import units

from h2integrate import ROOT_DIR
from h2integrate.core.utilities import BaseConfig, merge_shared_inputs
from h2integrate.core.model_baseclasses import CostModelBaseClass, PerformanceModelBaseClass
from h2integrate.tools.inflation.inflate import inflate_cpi


@define(kw_only=True)
class NRRIIronMinePerformanceConfig(BaseConfig):
    """Configuration class for NRRIIronMinePerformanceComponent.

    Attributes:
        mine (str): name of ore mine. Must be "Hibbing", "Northshore", "United",
            "Minorca" or "Tilden"
        max_ore_production_rate_tonnes_per_hr (float): capacity of the pellet plant
            in units of metric tonnes of pellets produced per hour.

    """

    max_ore_production_rate_tonnes_per_hr: float = field()
    mine: str = field(
        validator=validators.in_(["Hibbing", "Northshore", "United", "Minorca", "Tilden"])
    )


class NRRIIronMinePerformanceComponent(PerformanceModelBaseClass):
    _time_step_bounds = (
        3600,
        3600,
    )  # (min, max) time step lengths (in seconds) compatible with this model
    _control_classifier = "flexible"

    def initialize(self):
        super().initialize()
        self.commodity = "iron_ore"
        self.commodity_rate_units = "t/h"
        self.commodity_amount_units = "t"

    def setup(self):
        self.config = NRRIIronMinePerformanceConfig.from_dict(
            merge_shared_inputs(self.options["tech_config"]["model_inputs"], "performance"),
            strict=True,
            additional_cls_name=self.__class__.__name__,
        )
        super().setup()

        self.add_input(
            "system_capacity",
            val=self.config.max_ore_production_rate_tonnes_per_hr,
            units="t/h",
            desc="Ore production capacity",
        )

        # Add electricity input, default to 0 --> set using feedstock component
        self.add_input(
            "electricity_in",
            val=0.0,
            shape=self.n_timesteps,
            units="kW",
            desc="Electricity available for iron ore processing",
        )

        # Add natural_gas input, default to 0 --> set using feedstock component
        self.add_input(
            "natural_gas_in",
            val=0.0,
            shape=self.n_timesteps,
            units="MMBtu/h",
            desc="Natural_gas feedstock into iron mine",
        )

        # Add diesel input, default to 0 --> set using feedstock component
        self.add_input(
            "diesel_in",
            val=0.0,
            shape=self.n_timesteps,
            units="galUS/h",
            desc="Diesel feedstock into iron mine",
        )

        self.add_output(
            "electricity_consumed",
            val=0.0,
            shape=self.n_timesteps,
            units="kW",
            desc="Electricity consumed",
        )

        self.add_output(
            "natural_gas_consumed",
            val=0.0,
            shape=self.n_timesteps,
            units="MMBtu/h",
            desc="Natural gas consumed",
        )

        self.add_output(
            "diesel_consumed",
            val=0.0,
            shape=self.n_timesteps,
            units="galUS/h",
            desc="Diesel consumed",
        )

        self.add_output(
            "tailings_out", val=0.0, shape=self.n_timesteps, units="t/h", desc="Tailings produced"
        )

        output_dict = {
            "raw_ore": {"units": "t/h", "desc": "Raw ore mass flow"},
            "crushed_ore": {"units": "t/h", "desc": "Crushed ore mass flow"},
            "concentrated_ore": {"units": "t/h", "desc": "Concentrated ore mass flow"},
            "mining_electricity": {"units": "kW", "desc": "Electricity consumed in mining process"},
            "crushing_electricity": {
                "units": "kW",
                "desc": "Electricity consumed in crushing process",
            },
            "concentration_electricity": {
                "units": "kW",
                "desc": "Electricity consumed in beneficiation process",
            },
            "pelletization_electricity": {
                "units": "kW",
                "desc": "Electricity consumed in pelletization process",
            },
            "mining_diesel": {"units": "galUS/h", "desc": "Diesel consumed in mining process"},
            "concentration_natural_gas": {
                "units": "MMBtu/h",
                "desc": "Natural gas consumed in beneficiation process",
            },
            "pelletization_natural_gas": {
                "units": "MMBtu/h",
                "desc": "Natrual gas consumed in pelletization process",
            },
        }
        for key, val in output_dict.items():
            self.add_output(
                f"{key}",
                val=0.0,
                shape=self.n_timesteps,
                units=val["units"],
                desc=val["desc"],
            )

        coeff_fpath = ROOT_DIR / "converters" / "iron" / "nrri_ore" / "perf_coeffs.csv"
        # nrri ore performance model
        coeff_df = pd.read_csv(coeff_fpath)
        self.coeff_df = self.format_coeff_df(coeff_df, self.config.mine)

    def format_coeff_df(self, coeff_df, mine):
        """Update the coefficient dataframe such that values are adjusted to standard units
            and units are compatible with OpenMDAO units. Also filter the dataframe to include
            only the data necessary for a given mine and pellet type.

        Args:
            coeff_df (pd.DataFrame): cost coefficient dataframe.
            mine (str): name of mine that ore is extracted from.

        Returns:
            pd.DataFrame: cost coefficient dataframe
        """
        data_cols = ["units", "process", mine]
        coeff_df = coeff_df[data_cols]
        coeff_df = coeff_df.rename(columns={mine: "value"})

        # convert wet to dry
        moisture_percent = 2.0
        dry_fraction = (100 - moisture_percent) / 100

        # convert wet long tons per year to dry long tons per year
        i_wlt = coeff_df[coeff_df["units"] == "WLT/Yr"].index.to_list()
        coeff_df.loc[i_wlt, "value"] = coeff_df.loc[i_wlt, "value"] * dry_fraction
        coeff_df.loc[i_wlt, "units"] = "lt/yr"

        # convert kWh/wet long ton to kWh/dry long ton
        i_per_wlt = coeff_df[coeff_df["units"] == "kWh/LTP"].index.to_list()
        coeff_df.loc[i_per_wlt, "value"] = coeff_df.loc[i_per_wlt, "value"]
        coeff_df.loc[i_per_wlt, "units"] = "kWh/lt"
        coeff_df.loc[i_per_wlt, "Type"] = "energy use/pellet"

        # convert MMBtu/wet long ton to MMBtu/dry long ton
        i = coeff_df[coeff_df["units"] == "MMBtu/LTP"].index.to_list()
        coeff_df.loc[i, "value"] = coeff_df.loc[i, "value"]
        coeff_df.loc[i, "units"] = "MMBtu/lt"
        coeff_df.loc[i, "Type"] = "natural gas use/pellet"

        # convert gal/wet long ton to gal/dry long ton
        i = coeff_df[coeff_df["units"] == "gal/LTP"].index.to_list()
        coeff_df.loc[i, "value"] = coeff_df.loc[i, "value"]
        coeff_df.loc[i, "units"] = "galUS/lt"
        coeff_df.loc[i, "Type"] = "diesel use/pellet"

        # convert units to standardized units
        unit_rename_mapper = {}
        old_units = list(set(coeff_df["units"].to_list()))
        for ii, old_unit in enumerate(old_units):
            if "kWh" in old_unit:
                old_unit = old_unit.replace("kWh", "(kW*h)")
            if "lt" in old_unit:  # dry long tons
                old_unit = old_unit.replace("lt", "(2240*lb)")
            unit_rename_mapper.update({old_units[ii]: old_unit})
        coeff_df["units"] = coeff_df["units"].replace(to_replace=unit_rename_mapper)

        convert_units_dict = {
            "(kW*h)/(2240*lb)": "(kW*h)/t",
            "MMBtu/(2240*lb)": "MMBtu/t",
            "galUS/(2240*lb)": "galUS/t",
            "(2240*lb)": "t",
            "(2240*lb)/yr": "t/yr",
        }
        for i in coeff_df.index.to_list():
            if coeff_df.loc[i, "units"] in convert_units_dict:
                current_units = coeff_df.loc[i, "units"]
                desired_units = convert_units_dict[current_units]
                coeff_df.loc[i, "value"] = units.convert_units(
                    coeff_df.loc[i, "value"], current_units, desired_units
                )
                coeff_df.loc[i, "units"] = desired_units

        return coeff_df

    def compute(self, inputs, outputs):
        energy_per_process = {}
        natural_gas_per_process = {}
        diesel_per_process = {}

        system_capacity = inputs["system_capacity"][0]  # t/h pellets

        ref_pellets = self.coeff_df[self.coeff_df["process"] == "Iron Ore Pellets"]["value"].values
        # User warning if system capacity * 8760 is above ref pellets
        if system_capacity * 8760 > ref_pellets:
            msg = (
                f"System capacity of {system_capacity} t/yr exceeds the reference pellet"
                f" production of {ref_pellets} t/yr."
                f" This may lead to unrealistic results."
            )
            warnings.warn(msg, UserWarning)

        #### Mining
        ref_raw_ore = self.coeff_df[self.coeff_df["process"] == "ROM Ore"]["value"].values
        energy_per_process["mining"] = self.coeff_df[
            (self.coeff_df["process"] == "Mining") & (self.coeff_df["units"] == "(kW*h)/t")
        ]["value"].values
        diesel_per_process["mining"] = self.coeff_df[
            (self.coeff_df["process"] == "Mining") & (self.coeff_df["units"] == "galUS/t")
        ]["value"].values

        #### Crushing (Comminution)
        ref_crushed_ore = self.coeff_df[self.coeff_df["process"] == "Crushed Ore"]["value"].values
        energy_per_process["crushing"] = self.coeff_df[
            (self.coeff_df["process"] == "Comminution (Crushing)")
            & (self.coeff_df["units"] == "(kW*h)/t")
        ]["value"].values

        #### Beneficiation (Concentration)
        ref_conc_ore = self.coeff_df[self.coeff_df["process"] == "Concentrated Ore"]["value"].values
        energy_per_process["concentration"] = self.coeff_df[
            (self.coeff_df["process"] == "Beneficiation (Concentration)")
            & (self.coeff_df["units"] == "(kW*h)/t")
        ]["value"].values
        natural_gas_per_process["concentration"] = self.coeff_df[
            (self.coeff_df["process"] == "Beneficiation (Concentration)")
            & (self.coeff_df["units"] == "MMBtu/t")
        ]["value"].values

        # Byproduct of beneficiation
        ref_tailings = self.coeff_df[self.coeff_df["process"] == "Tailings"]["value"].values

        #### Pelletization
        ref_pellets = self.coeff_df[self.coeff_df["process"] == "Iron Ore Pellets"]["value"].values
        energy_per_process["pelletization"] = self.coeff_df[
            (self.coeff_df["process"] == "Pelletization") & (self.coeff_df["units"] == "(kW*h)/t")
        ]["value"].values
        natural_gas_per_process["pelletization"] = self.coeff_df[
            (self.coeff_df["process"] == "Pelletization") & (self.coeff_df["units"] == "MMBtu/t")
        ]["value"].values

        # max feedstock consumption
        max_elec_consumed = sum(energy_per_process.values()) * system_capacity  # kW
        max_natural_gas_consumed = sum(natural_gas_per_process.values()) * system_capacity  # MMBtu
        max_diesel_consumed = sum(diesel_per_process.values()) * system_capacity  # gal

        # available feedstocks, saturated at maximum system feedstock consumption
        electricity_available = np.where(
            inputs["electricity_in"] > max_elec_consumed,
            max_elec_consumed,
            inputs["electricity_in"],
        )
        natural_gas_available = np.where(
            inputs["natural_gas_in"] > max_natural_gas_consumed,
            max_natural_gas_consumed,
            inputs["natural_gas_in"],
        )
        diesel_available = np.where(
            inputs["diesel_in"] > max_diesel_consumed,
            max_diesel_consumed,
            inputs["diesel_in"],
        )

        # how much output can be produced from each of the feedstocks
        processed_ore_from_electricity = (
            electricity_available / max_elec_consumed
        ) * system_capacity  # t/h pellets
        processed_ore_from_natural_gas = (
            natural_gas_available / max_natural_gas_consumed
        ) * system_capacity  # t/h pellets
        processed_ore_from_diesel = (
            diesel_available / max_diesel_consumed
        ) * system_capacity  # t/h pellets

        # output is minimum between available feedstocks and output command value
        processed_ore_production = np.minimum.reduce(
            [
                processed_ore_from_diesel,
                processed_ore_from_natural_gas,
                processed_ore_from_electricity,
            ]
        )
        outputs["iron_ore_out"] = processed_ore_production
        outputs["total_iron_ore_produced"] = np.sum(processed_ore_production)
        outputs["annual_iron_ore_produced"] = outputs["total_iron_ore_produced"] * (
            1 / self.fraction_of_year_simulated
        )
        outputs["rated_iron_ore_production"] = inputs["system_capacity"]
        outputs["capacity_factor"] = outputs["total_iron_ore_produced"] / (
            outputs["rated_iron_ore_production"] * self.n_timesteps
        )

        # mass flow through mining process
        outputs["raw_ore"] = processed_ore_production * ref_raw_ore / ref_pellets
        outputs["crushed_ore"] = processed_ore_production * ref_crushed_ore / ref_pellets
        outputs["concentrated_ore"] = processed_ore_production * ref_conc_ore / ref_pellets
        outputs["tailings_out"] = processed_ore_production * ref_tailings / ref_pellets

        # energy and fuel consumption per process
        outputs["mining_electricity"] = energy_per_process["mining"] * processed_ore_production
        outputs["crushing_electricity"] = energy_per_process["crushing"] * processed_ore_production
        outputs["concentration_electricity"] = (
            energy_per_process["concentration"] * processed_ore_production
        )
        outputs["pelletization_electricity"] = (
            energy_per_process["pelletization"] * processed_ore_production
        )

        outputs["mining_diesel"] = diesel_per_process["mining"] * processed_ore_production
        outputs["concentration_natural_gas"] = (
            natural_gas_per_process["concentration"] * processed_ore_production
        )
        outputs["pelletization_natural_gas"] = (
            natural_gas_per_process["pelletization"] * processed_ore_production
        )

        # feedstock consumption
        outputs["electricity_consumed"] = (
            sum(energy_per_process.values()) * processed_ore_production
        )
        outputs["natural_gas_consumed"] = (
            sum(natural_gas_per_process.values()) * processed_ore_production
        )
        outputs["diesel_consumed"] = sum(diesel_per_process.values()) * processed_ore_production

        # Apply curtailment based on set_point
        self.apply_curtailment(outputs)


@define(kw_only=True)
class NRRIIronMineCostConfig(BaseConfig):
    """Configuration class for NRRIIronMineCostComponent.

    Attributes:
        mine (str): name of ore mine. Must be "Hibbing", "Northshore", "United",
            "Minorca" or "Tilden"
        taconite_pellet_type (str): type of taconite pellets, options are "std" or "drg".
        cost_year (int): target dollar year to convert costs to.
    """

    mine: str = field(
        validator=validators.in_(["Hibbing", "Northshore", "United", "Minorca", "Tilden"])
    )
    taconite_pellet_type: str = field(
        converter=(str.lower, str.strip), validator=validators.in_(["std", "drg"])
    )
    # the cost model is based on costs from 2021 and can be adjusted to another cost year
    # using CPI adjustment.
    cost_year: int = field(converter=int, validator=(validators.ge(2010), validators.le(2024)))


class NRRIIronMineCostComponent(CostModelBaseClass):
    _time_step_bounds = (
        3600,
        3600,
    )  # (min, max) time step lengths (in seconds) compatible with this model

    def setup(self):
        # merge inputs from performance parameters and cost parameters
        config_dict = merge_shared_inputs(
            copy.deepcopy(self.options["tech_config"]["model_inputs"]), "cost"
        )

        if "cost_year" in config_dict:
            if config_dict.get("cost_year", 2021) != 2021:
                msg = (
                    "This cost model is based on 2021 costs and adjusts costs using CPI. "
                    "The cost year cannot be modified for this cost model. "
                )
                raise ValueError(msg)

        target_dollar_year = self.options["plant_config"]["finance_parameters"][
            "cost_adjustment_parameters"
        ]["target_dollar_year"]

        if target_dollar_year <= 2024 and target_dollar_year >= 2010:
            # adjust costs from 2021 to target dollar year using CPI adjustment
            self.target_dollar_year = target_dollar_year

        elif target_dollar_year < 2010:
            # adjust costs from 2021 to 2010 using CPI adjustment
            self.target_dollar_year = 2010

        elif target_dollar_year > 2024:
            # adjust costs from 2021 to 2024 using CPI adjustment
            self.target_dollar_year = 2024

        config_dict.update({"cost_year": self.target_dollar_year})

        self.config = NRRIIronMineCostConfig.from_dict(
            config_dict,
            strict=True,
            additional_cls_name=self.__class__.__name__,
        )

        super().setup()

        self.add_input(
            "annual_iron_ore_produced",
            val=0.0,
            shape=self.plant_life,
            units="t/yr",
            desc="Annual iron ore production",
        )

        coeff_fpath = ROOT_DIR / "converters" / "iron" / "nrri_ore" / "cost_coeffs.csv"
        # nrri ore cost model
        coeff_df = pd.read_csv(coeff_fpath)
        self.coeff_df = self.format_coeff_df(coeff_df, self.config.mine)

    def format_coeff_df(self, coeff_df, mine):
        """Update the coefficient dataframe such that values are adjusted to standard units
            and units are compatible with OpenMDAO units. Also filter the dataframe to include
            only the data necessary for a given mine and pellet type.

        Args:
            coeff_df (pd.DataFrame): cost coefficient dataframe.
            mine (str): name of mine that ore is extracted from.

        Returns:
            pd.DataFrame: cost coefficient dataframe
        """
        data_cols = ["units", "process", mine]
        coeff_df = coeff_df[data_cols]
        coeff_df = coeff_df.rename(columns={mine: "value"})

        # convert wet to dry
        moisture_percent = 2.0
        dry_fraction = (100 - moisture_percent) / 100

        # convert wet long tons per year to dry long tons per year
        i_wlt = coeff_df[coeff_df["units"] == "WLT/Yr"].index.to_list()
        coeff_df.loc[i_wlt, "value"] = coeff_df.loc[i_wlt, "value"] * dry_fraction
        coeff_df.loc[i_wlt, "units"] = "lt/yr"

        i_per_wlt = coeff_df[coeff_df["units"] == "USD/LTP"].index.to_list()
        coeff_df.loc[i_per_wlt, "value"] = coeff_df.loc[i_per_wlt, "value"]
        coeff_df.loc[i_per_wlt, "units"] = "USD/lt"

        i_per_wlt = coeff_df[coeff_df["units"] == "USD/LT"].index.to_list()
        coeff_df.loc[i_per_wlt, "value"] = coeff_df.loc[i_per_wlt, "value"]
        coeff_df.loc[i_per_wlt, "units"] = "USD/lt"

        # convert units to standardized units
        unit_rename_mapper = {}
        old_units = list(set(coeff_df["units"].to_list()))
        for ii, old_unit in enumerate(old_units):
            if "lt" in old_unit:  # dry long tons
                old_unit = old_unit.replace("lt", "(2240*lb)")
            unit_rename_mapper.update({old_units[ii]: old_unit})
        coeff_df["units"] = coeff_df["units"].replace(to_replace=unit_rename_mapper)

        convert_units_dict = {
            "USD/(2240*lb)": "USD/t",
            "(2240*lb)": "t",
            "(2240*lb)/yr": "t/yr",
        }
        for i in coeff_df.index.to_list():
            if coeff_df.loc[i, "units"] in convert_units_dict:
                current_units = coeff_df.loc[i, "units"]
                desired_units = convert_units_dict[current_units]
                coeff_df.loc[i, "value"] = units.convert_units(
                    coeff_df.loc[i, "value"], current_units, desired_units
                )
                coeff_df.loc[i, "units"] = desired_units

        return coeff_df

    def compute(self, inputs, outputs, discrete_inputs, discrete_outputs):
        pellet_type = self.config.taconite_pellet_type

        # Get the capital cost for the reference design and scale to the modeled mine
        ref_Oreproduced = self.coeff_df[self.coeff_df["process"] == "capacity"]["value"].values
        capex_index = "capex_" + pellet_type
        ref_tot_capex = self.coeff_df[self.coeff_df["process"] == capex_index]["value"].values
        ref_capex_per_processed_ore = ref_tot_capex / ref_Oreproduced  # USD/t/yr
        tot_capex_2021USD = (
            inputs["annual_iron_ore_produced"][0] * ref_capex_per_processed_ore
        )  # USD

        # OpEx is calculated from the total opex minus energy costs calculated from SEC reports
        # Variable energy cost is then considered from electricity, NG, and diesel feedstocks
        opex_index = "opex_" + pellet_type
        om_2021USD = (
            inputs["annual_iron_ore_produced"][0]
            * self.coeff_df.loc[self.coeff_df["process"] == opex_index, "value"].values
        )

        # adjust costs to cost year
        outputs["CapEx"] = inflate_cpi(tot_capex_2021USD, 2021, self.config.cost_year)
        outputs["OpEx"] = inflate_cpi(om_2021USD, 2021, self.config.cost_year)
