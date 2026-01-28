import copy

import pandas as pd
from attrs import field, define
from openmdao.utils import units

from h2integrate import ROOT_DIR
from h2integrate.core.utilities import BaseConfig, merge_shared_inputs
from h2integrate.core.validators import contains, range_val
from h2integrate.core.model_baseclasses import CostModelBaseClass
from h2integrate.tools.inflation.inflate import inflate_cpi


@define(kw_only=True)
class MartinIronMineCostConfig(BaseConfig):
    """Configuration class for MartinIronMineCostComponent.

    Attributes:
        taconite_pellet_type (str): type of taconite pellets, options are "std" or "drg".
        mine (str): name of ore mine. Must be "Hibbing", "Northshore", "United",
            "Minorca" or "Tilden"
        max_ore_production_rate_tonnes_per_hr (float): capacity of the pellet plant
            in units of metric tonnes of pellets produced per hour.
        cost_year (int): target dollar year to convert costs to.
            Cannot be input under `cost_parameters`.
    """

    max_ore_production_rate_tonnes_per_hr: float = field()

    taconite_pellet_type: str = field(
        converter=(str.lower, str.strip), validator=contains(["std", "drg"])
    )

    mine: str = field(validator=contains(["Hibbing", "Northshore", "United", "Minorca", "Tilden"]))

    # the cost model is based on costs from 2021 and can be adjusted to another cost year
    # using CPI adjustment.
    cost_year: int = field(converter=int, validator=range_val(2010, 2024))


class MartinIronMineCostComponent(CostModelBaseClass):
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
        self.config = MartinIronMineCostConfig.from_dict(config_dict, strict=True)

        super().setup()

        n_timesteps = self.options["plant_config"]["plant"]["simulation"]["n_timesteps"]

        self.add_input(
            "system_capacity",
            val=self.config.max_ore_production_rate_tonnes_per_hr,
            # shape=n_timesteps,
            units="t/h",
            desc="Annual ore production capacity",
        )
        self.add_input(
            "iron_ore_out",
            val=0.0,
            shape=n_timesteps,
            units="t/h",
            desc="Iron ore pellets produced",
        )

        coeff_fpath = ROOT_DIR / "converters" / "iron" / "martin_ore" / "cost_coeffs.csv"
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
        i_per_wlt = coeff_df[coeff_df["Unit"] == "2021 $ per wlt pellet"].index.to_list()
        coeff_df.loc[i_per_wlt, "Value"] = coeff_df.loc[i_per_wlt, "Value"] / dry_fraction
        coeff_df.loc[i_per_wlt, "Unit"] = "USD/lt"
        coeff_df.loc[i_per_wlt, "Type"] = "variable opex/pellet"

        # convert units to standardized units
        unit_rename_mapper = {}
        old_units = list(set(coeff_df["Unit"].to_list()))
        for ii, old_unit in enumerate(old_units):
            if "2021 $" in old_unit:
                old_unit = old_unit.replace("2021 $", "USD")
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
            "USD/(2240*lb)": "USD/t",
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

    def compute(self, inputs, outputs, discrete_inputs, discrete_outputs):
        ref_Oreproduced = self.coeff_df[self.coeff_df["Name"] == "Ore pellets produced"][
            "Value"
        ].values

        # get the capital cost for the reference design
        ref_tot_capex = self.coeff_df[self.coeff_df["Type"] == "capital"]["Value"].sum()
        ref_capex_per_anual_processed_ore = ref_tot_capex / ref_Oreproduced  # USD/t/yr
        ref_capex_per_processed_ore = ref_capex_per_anual_processed_ore * 8760  # USD/t/hr
        tot_capex_2021USD = inputs["system_capacity"] * ref_capex_per_processed_ore  # USD

        # get the variable om cost based on the total pellet production
        total_pellets_produced = sum(inputs["iron_ore_out"])
        var_om_2021USD = (
            self.coeff_df[self.coeff_df["Type"] == "variable opex/pellet"]["Value"]
            * total_pellets_produced
        ).sum()

        # adjust costs to cost year
        outputs["CapEx"] = inflate_cpi(tot_capex_2021USD, 2021, self.config.cost_year)
        outputs["VarOpEx"] = inflate_cpi(var_om_2021USD, 2021, self.config.cost_year)
