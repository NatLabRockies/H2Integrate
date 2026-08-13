import warnings

import numpy as np
import pandas as pd
from attrs import field, define
from openmdao.utils import units

from h2integrate import ROOT_DIR
from h2integrate.core.utilities import BaseConfig, merge_shared_inputs
from h2integrate.core.validators import contains
from h2integrate.core.model_baseclasses import PerformanceModelBaseClass


@define(kw_only=True)
class IronMinePerformanceConfig(BaseConfig):
    """Configuration class for IronMinePerformanceComponent.

    Attributes:
        mine (str): name of ore mine. Must be "Hibbing", "Northshore", "United",
            "Minorca" or "Tilden"
        max_ore_production_rate_tonnes_per_hr (float): capacity of the pellet plant
            in units of metric tonnes of pellets produced per hour.
    """

    max_ore_production_rate_tonnes_per_hr: float = field()
    mine: str = field(validator=contains(["Hibbing", "Northshore", "United", "Minorca", "Tilden"]))


class IronMinePerformanceComponent(PerformanceModelBaseClass):
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
        super().setup()
        self.config = IronMinePerformanceConfig.from_dict(
            merge_shared_inputs(self.options["tech_config"]["model_inputs"], "performance"),
            strict=True,
            additional_cls_name=self.__class__.__name__,
        )

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

        # Add fuel input, default to 0 --> set using feedstock component
        self.add_input(
            "fuel_in",
            val=0.0,
            shape=self.n_timesteps,
            units="MMBtu/h",
            desc="Fuel feedstock into iron mine",
        )

        # Default the ore command value input as the rated capacity
        # TODO: getting weird error when this is uncommented, but it should be here. Need to investigate.
        # self.add_input(
        #     "iron_ore_command_value",
        #     val=self.config.max_ore_production_rate_tonnes_per_hr,
        #     shape=self.n_timesteps,
        #     units="t/h",
        #     desc="Iron ore command value for iron mine",
        # )

        self.add_output(
            "electricity_consumed",
            val=0.0,
            shape=self.n_timesteps,
            units="kW",
            desc="Electricity consumed",
        )

        self.add_output(
            "fuel_consumed", val=0.0, shape=self.n_timesteps, units="MMBtu/h", desc="Fuel consumed"
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
            "mining_fuel": {"units": "MMBtu/h", "desc": "Fuel consumed in mining process"},
            "concentration_fuel": {
                "units": "MMBtu/h",
                "desc": "Fuel consumed in beneficiation process",
            },
            "pelletization_fuel": {
                "units": "MMBtu/h",
                "desc": "Fuel consumed in pelletization process",
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

        # convert kWh/wet long ton to kWh/dry long ton
        i = coeff_df[coeff_df["units"] == "MMBtu/LTP"].index.to_list()
        coeff_df.loc[i, "value"] = coeff_df.loc[i, "value"]
        coeff_df.loc[i, "units"] = "MMBtu/lt"
        coeff_df.loc[i, "Type"] = "fuel use/pellet"

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
        fuel_per_process = {}

        system_capacity = inputs["system_capacity"][0]  # t/h pellets

        ref_pellets = self.coeff_df[self.coeff_df["process"] == "Iron Ore Pellets"]["value"].values
        # User warning if system capacity * 8760 is above ref pellets
        if system_capacity * 8760 > ref_pellets:
            msg = (
                f"System capacity of {system_capacity} t/h exceeds the reference pellet"
                f" production of {ref_pellets} t/h."
                f" This may lead to unrealistic results."
            )
            warnings.warn(msg, UserWarning)

        #### Mining
        ref_raw_ore = self.coeff_df[self.coeff_df["process"] == "ROM Ore"]["value"].values
        energy_per_process["mining"] = self.coeff_df[
            (self.coeff_df["process"] == "Mining") & (self.coeff_df["units"] == "(kW*h)/t")
        ]["value"].values
        fuel_per_process["mining"] = self.coeff_df[
            (self.coeff_df["process"] == "Mining") & (self.coeff_df["units"] == "MMBtu/t")
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
        fuel_per_process["concentration"] = self.coeff_df[
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
        fuel_per_process["pelletization"] = self.coeff_df[
            (self.coeff_df["process"] == "Pelletization") & (self.coeff_df["units"] == "MMBtu/t")
        ]["value"].values

        # max feedstock consumption
        max_elec_consumed = sum(energy_per_process.values()) * system_capacity  # kW
        max_fuel_consumed = sum(fuel_per_process.values()) * system_capacity  # MMBtu

        # iron ore command value, saturated at maximum rated system capacity
        processed_ore_command_value = np.where(
            inputs["iron_ore_command_value"] > system_capacity,
            system_capacity,
            inputs["iron_ore_command_value"],
        )

        # available feedstocks, saturated at maximum system feedstock consumption
        electricity_available = np.where(
            inputs["electricity_in"] > max_elec_consumed,
            max_elec_consumed,
            inputs["electricity_in"],
        )
        fuel_available = np.where(
            inputs["fuel_in"] > max_fuel_consumed,
            max_fuel_consumed,
            inputs["fuel_in"],
        )

        # how much output can be produced from each of the feedstocks
        processed_ore_from_electricity = (
            electricity_available / max_elec_consumed
        ) * system_capacity  # t/h pellets
        processed_ore_from_fuel = (
            fuel_available / max_fuel_consumed
        ) * system_capacity  # t/h pellets

        # output is minimum between available feedstocks and output command value
        processed_ore_production = np.minimum.reduce(
            [
                processed_ore_from_fuel,
                processed_ore_from_electricity,
                processed_ore_command_value,
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

        outputs["mining_fuel"] = fuel_per_process["mining"] * processed_ore_production
        outputs["concentration_fuel"] = fuel_per_process["concentration"] * processed_ore_production
        outputs["pelletization_fuel"] = fuel_per_process["pelletization"] * processed_ore_production

        # feedstock consumption
        outputs["electricity_consumed"] = (
            sum(energy_per_process.values()) * processed_ore_production
        )
        outputs["fuel_consumed"] = sum(fuel_per_process.values()) * processed_ore_production
