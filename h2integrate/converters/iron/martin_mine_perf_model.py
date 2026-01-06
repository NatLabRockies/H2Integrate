import numpy as np
import pandas as pd
import openmdao.api as om
from attrs import field, define
from openmdao.utils import units

from h2integrate import ROOT_DIR
from h2integrate.core.utilities import BaseConfig, merge_shared_inputs
from h2integrate.core.validators import contains


@define(kw_only=True)
class MartinIronMinePerformanceConfig(BaseConfig):
    """Configuration class for MartinIronMinePerformanceComponent.

    Attributes:
        taconite_pellet_type (str): type of taconite pellets, options are "std" or "drg".
        mine (str): name of ore mine. Must be "Hibbing", "Northshore", "United",
            "Minorca" or "Tilden"
        max_ore_production_rate_tonnes_per_hr (float): capacity of the pellet plant
            in units of metric tonnes of pellets produced per hour.
    """

    max_ore_production_rate_tonnes_per_hr: float = field()

    taconite_pellet_type: str = field(
        converter=(str.lower, str.strip), validator=contains(["std", "drg"])
    )

    mine: str = field(validator=contains(["Hibbing", "Northshore", "United", "Minorca", "Tilden"]))


class MartinIronMinePerformanceComponent(om.ExplicitComponent):
    def initialize(self):
        self.options.declare("driver_config", types=dict)
        self.options.declare("plant_config", types=dict)
        self.options.declare("tech_config", types=dict)

    def setup(self):
        n_timesteps = self.options["plant_config"]["plant"]["simulation"]["n_timesteps"]
        self.config = MartinIronMinePerformanceConfig.from_dict(
            merge_shared_inputs(self.options["tech_config"]["model_inputs"], "performance"),
            strict=True,
        )

        self.add_input(
            "system_capacity",
            val=self.config.max_ore_production_rate_tonnes_per_hr,
            units="t/h",
            desc="Annual ore production capacity",
        )

        # Add electricity input, default to 0 --> set using feedstock component
        self.add_input(
            "electricity_in",
            val=0.0,
            shape=n_timesteps,
            units="kW",
            desc="Electricity available for iron ore processing",
        )

        # Add crude ore input, default to 0 --> set using feedstock component
        self.add_input(
            "crude_ore_in",
            val=0.0,
            shape=n_timesteps,
            units="t/h",
            desc="Crude ore input",
        )

        # Default the ore demand input as the rated capacity
        self.add_input(
            "iron_ore_demand",
            val=self.config.max_ore_production_rate_tonnes_per_hr,
            shape=n_timesteps,
            units="t/h",
            desc="Iron ore demand for iron mine",
        )

        self.add_output(
            "crude_ore_consumed",
            val=0.0,
            shape=n_timesteps,
            units="t/h",
            desc="Crude ore consumed",
        )

        self.add_output(
            "electricity_consumed",
            val=0.0,
            shape=n_timesteps,
            units="kW",
            desc="Electricity consumed",
        )

        self.add_output(
            "iron_ore_out",
            val=0.0,
            shape=n_timesteps,
            units="t/h",
            desc="Iron ore pellets produced",
        )

        self.add_output(
            "total_iron_ore_produced",
            val=1.0,
            units="t/year",
            desc="Total iron ore pellets produced anually",
        )

        coeff_fpath = ROOT_DIR / "converters" / "iron" / "martin_ore" / "perf_coeffs.csv"
        # martin ore performance model
        coeff_df = pd.read_csv(coeff_fpath, index_col=0)
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
        # only include data for the given product
        coeff_df = coeff_df[
            coeff_df["Product"] == f"{self.config.taconite_pellet_type}_taconite_pellets"
        ]
        data_cols = ["Name", "Type", "Coeff", "Unit", mine]
        coeff_df = coeff_df[data_cols]
        coeff_df = coeff_df.rename(columns={mine: "Value"})

        # convert wet to dry
        moisture_percent = 2.0
        dry_fraction = (100 - moisture_percent) / 100

        # convert wet long tons per year to dry long tons per year
        i_wlt = coeff_df[coeff_df["Unit"] == "wltpy"].index.to_list()
        coeff_df.loc[i_wlt, "Value"] = coeff_df.loc[i_wlt, "Value"] * dry_fraction
        coeff_df.loc[i_wlt, "Unit"] = "lt/yr"

        # convert kWh/wet long ton to kWh/dry long ton
        i_per_wlt = coeff_df[coeff_df["Unit"] == "kWh/LT pellet"].index.to_list()
        coeff_df.loc[i_per_wlt, "Value"] = coeff_df.loc[i_per_wlt, "Value"] / dry_fraction
        coeff_df.loc[i_per_wlt, "Unit"] = "kWh/lt"
        coeff_df.loc[i_per_wlt, "Type"] = "energy use/pellet"

        # convert units to standardized units
        unit_rename_mapper = {}
        old_units = list(set(coeff_df["Unit"].to_list()))
        for ii, old_unit in enumerate(old_units):
            if "kWh" in old_unit:
                old_unit = old_unit.replace("kWh", "(kW*h)")
            if "mlt" in old_unit:  # millon long tons
                old_unit = old_unit.replace("mlt", "(2240*Mlb)")
            if "lt" in old_unit:  # dry long tons
                old_unit = old_unit.replace("lt", "(2240*lb)")
            if "mt" in old_unit:  # metric tonne
                old_unit = old_unit.replace("mt", "t")
            if "wt %" in old_unit:
                old_unit = old_unit.replace("wt %", "unitless")
            if "deg N" in old_unit or "deg E" in old_unit:
                old_unit = "deg"
            unit_rename_mapper.update({old_units[ii]: old_unit})
        coeff_df["Unit"] = coeff_df["Unit"].replace(to_replace=unit_rename_mapper)

        convert_units_dict = {
            "(kW*h)/(2240*lb)": "(kW*h)/t",
            "(2240*Mlb)": "t",
            "(2240*lb)/yr": "t/yr",
        }
        for i in coeff_df.index.to_list():
            if coeff_df.loc[i, "Unit"] in convert_units_dict:
                current_units = coeff_df.loc[i, "Unit"]
                desired_units = convert_units_dict[current_units]
                coeff_df.loc[i, "Value"] = units.convert_units(
                    coeff_df.loc[i, "Value"], current_units, desired_units
                )
                coeff_df.loc[i, "Unit"] = desired_units

        return coeff_df

    def compute(self, inputs, outputs):
        # calculate crude ore required per amount of ore processed
        ref_Orefeedstock = self.coeff_df[self.coeff_df["Name"] == "Crude ore processed"][
            "Value"
        ].values
        ref_Oreproduced = self.coeff_df[self.coeff_df["Name"] == "Ore pellets produced"][
            "Value"
        ].values
        crude_ore_usage_per_processed_ore = ref_Orefeedstock / ref_Oreproduced

        # energy consumption based on ore production
        energy_usage_per_processed_ore = self.coeff_df[
            self.coeff_df["Type"] == "energy use/pellet"
        ]["Value"].sum()
        # check that units work out
        energy_usage_unit = self.coeff_df[self.coeff_df["Type"] == "energy use/pellet"][
            "Unit"
        ].values[0]
        energy_usage_per_processed_ore = units.convert_units(
            energy_usage_per_processed_ore, f"(t/h)*({energy_usage_unit})", "(kW*h)/h"
        )

        # calculate max inputs/outputs based on rated capacity
        max_crude_ore_consumption = inputs["system_capacity"] * crude_ore_usage_per_processed_ore
        max_energy_consumption = inputs["system_capacity"] * energy_usage_per_processed_ore

        # iron ore demand, saturated at maximum rated system capacity
        processed_ore_demand = np.where(
            inputs["iron_ore_demand"] > inputs["system_capacity"],
            inputs["system_capacity"],
            inputs["iron_ore_demand"],
        )

        # available feedstocks, saturated at maximum system feedstock consumption
        crude_ore_available = np.where(
            inputs["crude_ore_in"] > max_crude_ore_consumption,
            max_crude_ore_consumption,
            inputs["crude_ore_in"],
        )

        energy_available = np.where(
            inputs["electricity_in"] > max_energy_consumption,
            max_energy_consumption,
            inputs["electricity_in"],
        )

        # how much output can be produced from each of the feedstocks
        processed_ore_from_electricity = energy_available / energy_usage_per_processed_ore
        processed_ore_from_crude_ore = crude_ore_available / crude_ore_usage_per_processed_ore

        # output is minimum between available feedstocks and output demand
        processed_ore_production = np.minimum.reduce(
            [processed_ore_from_crude_ore, processed_ore_from_electricity, processed_ore_demand]
        )

        # energy consumption
        energy_consumed = processed_ore_production * energy_usage_per_processed_ore

        # crude ore consumption
        crude_ore_consumption = processed_ore_production * crude_ore_usage_per_processed_ore

        outputs["iron_ore_out"] = processed_ore_production
        outputs["total_iron_ore_produced"] = np.sum(processed_ore_production)
        outputs["electricity_consumed"] = energy_consumed
        outputs["crude_ore_consumed"] = crude_ore_consumption
