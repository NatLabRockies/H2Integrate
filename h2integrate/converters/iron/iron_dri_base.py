import numpy as np
import pandas as pd
import openmdao.api as om
from attrs import field, define
from openmdao.utils import units

from h2integrate import ROOT_DIR
from h2integrate.core.utilities import BaseConfig, CostModelBaseConfig, merge_shared_inputs
from h2integrate.core.validators import gte_zero
from h2integrate.core.model_baseclasses import CostModelBaseClass
from h2integrate.tools.inflation.inflate import inflate_cpi, inflate_cepci


@define
class IronReductionPerformanceBaseConfig(BaseConfig):
    """Configuration baseclass for IronReductionPlantBasePerformanceComponent.

    Attributes:
        pig_iron_production_rate_tonnes_per_hr (float): capacity of the iron processing plant
            in units of metric tonnes of pig iron produced per hour.
        water_density (float): water density in kg/m3 to use to calculate water volume
            from mass. Defaults to 1000.0
    """

    pig_iron_production_rate_tonnes_per_hr: float = field()
    water_density: float = field(default=1000)  # kg/m3


class IronReductionPlantBasePerformanceComponent(om.ExplicitComponent):
    def initialize(self):
        self.options.declare("driver_config", types=dict)
        self.options.declare("plant_config", types=dict)
        self.options.declare("tech_config", types=dict)

    def setup(self):
        n_timesteps = self.options["plant_config"]["plant"]["simulation"]["n_timesteps"]

        self.config = IronReductionPerformanceBaseConfig.from_dict(
            merge_shared_inputs(self.options["tech_config"]["model_inputs"], "performance"),
            strict=True,
        )

        self.add_input(
            "system_capacity",
            val=self.config.pig_iron_production_rate_tonnes_per_hr,
            units="t/h",
            desc="Rated pig iron production capacity",
        )

        # Add feedstock inputs and outputs, default to 0 --> set using feedstock component
        for feedstock, feedstock_units in self.feedstocks_to_units.items():
            self.add_input(
                f"{feedstock}_in",
                val=0.0,
                shape=n_timesteps,
                units=feedstock_units,
                desc=f"{feedstock} available for iron reduction",
            )
            self.add_output(
                f"{feedstock}_consumed",
                val=0.0,
                shape=n_timesteps,
                units=feedstock_units,
                desc=f"{feedstock} consumed for iron reduction",
            )

        # Default the pig iron demand input as the rated capacity
        self.add_input(
            "pig_iron_demand",
            val=self.config.pig_iron_production_rate_tonnes_per_hr,
            shape=n_timesteps,
            units="t/h",
            desc="Pig iron demand for iron plant",
        )

        self.add_output(
            "pig_iron_out",
            val=0.0,
            shape=n_timesteps,
            units="t/h",
            desc="Pig iron produced",
        )

        coeff_fpath = ROOT_DIR / "converters" / "iron" / "rosner" / "perf_coeffs.csv"
        # rosner dri performance model
        coeff_df = pd.read_csv(coeff_fpath, index_col=0)
        self.coeff_df = self.format_coeff_df(coeff_df)

    def format_coeff_df(self, coeff_df):
        """Update the coefficient dataframe such that feedstock values are converted to units of
        feedstock unit / unit pig iron, e.g., 'galUS/t'. Also convert values to standard units
        and that units are compatible with OpenMDAO Units. Filter the dataframe to include
        only the data necessary for the specified type of reduction.

        Args:
            coeff_df (pd.DataFrame): performance coefficient dataframe.

        Returns:
            pd.DataFrame: filtered performance coefficient dataframe
        """
        # only include data for the given product
        coeff_df = coeff_df[coeff_df["Product"] == self.product]
        data_cols = ["Name", "Type", "Coeff", "Unit", "Model"]
        coeff_df = coeff_df[data_cols]
        coeff_df = coeff_df.rename(columns={"Model": "Value"})
        coeff_df = coeff_df[coeff_df["Value"] > 0]
        coeff_df = coeff_df[coeff_df["Type"] != "emission"]  # dont include emission data

        # ng DRI needs natural gas, water, electricity, iron ore and reformer catalyst
        # h2_dri needs natural gas, water, hydrogen, iron ore.
        steel_plant_capacity = coeff_df[coeff_df["Name"] == "Steel Production"]["Value"].values[0]
        iron_plant_capacity = coeff_df[coeff_df["Name"] == "Pig Iron Production"]["Value"].values[0]

        # capacity units units are mtpy
        steel_to_iron_ratio = steel_plant_capacity / iron_plant_capacity  # both in metric tons/year
        unit_rename_mapper = {"mtpy": "t/yr", "%": "unitless"}

        # efficiency units are %
        # feedstock units are mt ore/mt steel, mt H2/mt steel, GJ-LHV NG/mt steel,
        # mt H2O/mt steel, kW/mtpy steel

        # convert units to standardized units
        old_units = list(set(coeff_df["Unit"].to_list()))
        for ii, old_unit in enumerate(old_units):
            if old_unit in unit_rename_mapper:
                continue
            if "steel" in old_unit:
                feedstock_unit, capacity_unit = old_unit.split("/")
                capacity_unit = capacity_unit.replace("steel", "").strip()
                feedstock_unit = feedstock_unit.strip()

                i_update = coeff_df[coeff_df["Unit"] == old_unit].index

                # convert from feedstock per unit steel to feedstock per unit pig iron
                coeff_df.loc[i_update, "Value"] = (
                    coeff_df.loc[i_update, "Value"] * steel_to_iron_ratio
                )

                # update the "Type" to specify that units were changed to be per unit pig iron
                coeff_df.loc[i_update, "Type"] = f"{coeff_df.loc[i_update, 'Type'].values[0]}/iron"

                is_capacity_type = all(
                    k == "capacity" for k in coeff_df.loc[i_update]["Type"].to_list()
                )
                if capacity_unit == "mtpy" and not is_capacity_type:
                    # some feedstocks had misleading units,
                    # where 'kW/ mtpy steel' is actually 'kW/mt steel'
                    # NOTE: perhaps these ones need to be modified with the steel efficiency?
                    capacity_unit = "mt"

                old_unit = f"{feedstock_unit}/{capacity_unit}"

            if "H2O" in old_unit:
                # convert metric tonnes to kg (value*1e3)
                # convert mass to volume in cubic meters (value*1e3)/density
                # then convert cubic meters to liters 1e3*(value*1e3)/density
                water_volume_m3 = coeff_df.loc[i_update]["Value"] * 1e3 / self.config.water_density
                water_volume_L = units.convert_units(water_volume_m3.values, "m**3", "L")
                coeff_df.loc[i_update, "Value"] = water_volume_L
                old_unit = f"L/{capacity_unit}"

            old_unit = (
                old_unit.replace("-LHV NG", "")
                .replace("%", "percent")
                .replace("m3 catalyst", "(m**3)")
            )
            old_unit = old_unit.replace("mt H2", "t").replace("MWh", "(MW*h)").replace(" ore", "")
            old_unit = (
                old_unit.replace("mtpy", "(t/yr)").replace("mt", "t").replace("kW/", "(kW*h)/")
            )
            # NOTE: how would 'kW / mtpy steel' be different than 'kW / mt steel'
            # replace % with "unitless"
            unit_rename_mapper.update({old_units[ii]: old_unit})
        coeff_df["Unit"] = coeff_df["Unit"].replace(to_replace=unit_rename_mapper)

        convert_units_dict = {
            "GJ/t": "MMBtu/t",
            "L/t": "galUS/t",
            "(MW*h)/t": "(kW*h)/t",
            "percent": "unitless",
        }
        # convert units to standard units and OpenMDAO compatible units
        for i in coeff_df.index.to_list():
            if coeff_df.loc[i, "Unit"] in convert_units_dict:
                current_units = coeff_df.loc[i, "Unit"]
                desired_units = convert_units_dict[current_units]
                coeff_df.loc[i, "Value"] = units.convert_units(
                    coeff_df.loc[i, "Value"], current_units, desired_units
                )
                coeff_df.loc[i, "Unit"] = desired_units
                # NOTE: not sure if percent is actually being converted to unitless
                # but not big deal since percent is not used in feedstocks
        return coeff_df

    def compute(self, inputs, outputs):
        # get the feedstocks from
        feedstocks = self.coeff_df[self.coeff_df["Type"] == "feed/iron"].copy()

        # get the feedstock usage rates in units/t pig iron
        feedstocks_usage_rates = {
            "natural_gas": feedstocks[feedstocks["Name"] == "Natural Gas"][
                "Value"
            ].sum(),  # MMBtu/t
            "water": feedstocks[feedstocks["Name"] == "Raw Water Withdrawal"][
                "Value"
            ].sum(),  # galUS/t
            "iron_ore": feedstocks[feedstocks["Name"] == "Iron Ore"]["Value"].sum(),  # t/t
            "electricity": feedstocks[feedstocks["Name"] == "Electricity"][
                "Value"
            ].sum(),  # (kW*h)/t
        }
        if "hydrogen" in self.feedstocks_to_units:
            # t/t
            feedstocks_usage_rates["hydrogen"] = feedstocks[feedstocks["Name"] == "Hydrogen"][
                "Value"
            ].sum()

        if "reformer_catalyst" in self.feedstocks_to_units:
            # m**3/t
            feedstocks_usage_rates["reformer_catalyst"] = feedstocks[
                feedstocks["Name"] == "Reformer Catalyst"
            ]["Value"].sum()

        # pig iron demand, saturated at maximum rated system capacity
        pig_iron_demand = np.where(
            inputs["pig_iron_demand"] > inputs["system_capacity"],
            inputs["system_capacity"],
            inputs["pig_iron_demand"],
        )

        # initialize an array of how much pig iron could be produced
        # from the available feedstocks and the demand
        pig_iron_from_feedstocks = np.zeros(
            (len(feedstocks_usage_rates) + 1, len(inputs["pig_iron_demand"]))
        )
        # first entry is the pig iron demand
        pig_iron_from_feedstocks[0] = pig_iron_demand
        ii = 1
        for feedstock_type, consumption_rate in feedstocks_usage_rates.items():
            # calculate max inputs/outputs based on rated capacity
            max_feedstock_consumption = inputs["system_capacity"] * consumption_rate
            # available feedstocks, saturated at maximum system feedstock consumption
            feedstock_available = np.where(
                inputs[f"{feedstock_type}_in"] > max_feedstock_consumption,
                max_feedstock_consumption,
                inputs[f"{feedstock_type}_in"],
            )
            # how much output can be produced from each of the feedstocks
            pig_iron_from_feedstocks[ii] = feedstock_available / consumption_rate
            ii += 1

        # output is minimum between available feedstocks and output demand
        pig_iron_production = np.minimum.reduce(pig_iron_from_feedstocks)
        outputs["pig_iron_out"] = pig_iron_production

        # feedstock consumption based on actual pig iron produced
        for feedstock_type, consumption_rate in feedstocks_usage_rates.items():
            outputs[f"{feedstock_type}_consumed"] = pig_iron_production * consumption_rate


@define
class IronReductionCostBaseConfig(CostModelBaseConfig):
    """Configuration baseclass for IronReductionPlantBaseCostComponent.

    Attributes:
        pig_iron_production_rate_tonnes_per_hr (float): capacity of the iron processing plant
            in units of metric tonnes of pig iron produced per hour.
        cost_year (int): This model uses 2022 as the base year for the cost model.
            The cost year is updated based on `target_dollar_year` in the plant
            config to adjust costs based on CPI/CEPCI within this model. This value
            cannot be user added under `cost_parameters`.
        skilled_labor_cost (float): Skilled labor cost in 2022 USD/hr
        unskilled_labor_cost (float): Unskilled labor cost in 2022 USD/hr
    """

    pig_iron_production_rate_tonnes_per_hr: float = field()
    cost_year: int = field(converter=int)
    skilled_labor_cost: float = field(validator=gte_zero)
    unskilled_labor_cost: float = field(validator=gte_zero)


class IronReductionPlantBaseCostComponent(CostModelBaseClass):
    """Cost component for direct reduced iron (DRI) plant
    using the Rosner cost model.

    Attributes:
        config (IronReductionCostBaseConfig): configuration class
        coeff_df (pd.DataFrame): cost coefficient dataframe
        steel_to_iron_ratio (float): steel/pig iron ratio
    """

    def setup(self):
        n_timesteps = self.options["plant_config"]["plant"]["simulation"]["n_timesteps"]

        config_dict = merge_shared_inputs(self.options["tech_config"]["model_inputs"], "cost")

        if "cost_year" in config_dict:
            msg = (
                "This cost model is based on 2022 costs and adjusts costs using CPI and CEPCI. "
                "The cost year cannot be modified for this cost model. "
            )
            raise ValueError(msg)

        target_dollar_year = self.options["plant_config"]["finance_parameters"][
            "cost_adjustment_parameters"
        ]["target_dollar_year"]

        if target_dollar_year <= 2024 and target_dollar_year >= 2010:
            # adjust costs from 2022 to target dollar year using CPI/CEPCI adjustment
            target_dollar_year = target_dollar_year

        elif target_dollar_year < 2010:
            # adjust costs from 2022 to 2010 using CP/CEPCI adjustment
            target_dollar_year = 2010

        elif target_dollar_year > 2024:
            # adjust costs from 2022 to 2024 using CPI/CEPCI adjustment
            target_dollar_year = 2024

        config_dict.update({"cost_year": target_dollar_year})

        self.config = IronReductionCostBaseConfig.from_dict(config_dict, strict=False)

        super().setup()

        self.add_input(
            "system_capacity",
            val=self.config.pig_iron_production_rate_tonnes_per_hr,
            units="t/h",
            desc="Pig ore production capacity",
        )
        self.add_input(
            "pig_iron_out",
            val=0.0,
            shape=n_timesteps,
            units="t/h",
            desc="Pig iron produced",
        )

        coeff_fpath = ROOT_DIR / "converters" / "iron" / "rosner" / "cost_coeffs.csv"

        # rosner cost model
        coeff_df = pd.read_csv(coeff_fpath, index_col=0)
        self.coeff_df = self.format_coeff_df(coeff_df)

    def format_coeff_df(self, coeff_df):
        """Update the coefficient dataframe such that values are adjusted to standard units
            and units are compatible with OpenMDAO units. Also filter the dataframe to include
            only the data necessary for natural gas DRI type.

        Args:
            coeff_df (pd.DataFrame): cost coefficient dataframe.

        Returns:
            pd.DataFrame: cost coefficient dataframe
        """

        perf_coeff_fpath = ROOT_DIR / "converters" / "iron" / "rosner" / "perf_coeffs.csv"

        perf_df = pd.read_csv(perf_coeff_fpath, index_col=0)
        perf_df = perf_df[perf_df["Product"] == self.product]
        steel_plant_capacity = perf_df[perf_df["Name"] == "Steel Production"]["Model"].values[0]
        iron_plant_capacity = perf_df[perf_df["Name"] == "Pig Iron Production"]["Model"].values[0]
        steel_to_iron_ratio = steel_plant_capacity / iron_plant_capacity  # both in metric tons/year
        self.steel_to_iron_ratio = steel_to_iron_ratio

        # only include data for the given product

        data_cols = ["Type", "Coeff", "Unit", self.product]
        coeff_df = coeff_df[data_cols]

        coeff_df = coeff_df.rename(columns={self.product: "Value"})

        return coeff_df

    def compute(self, inputs, outputs, discrete_inputs, discrete_outputs):
        # Calculate the capital cost for the item
        dollar_year = self.coeff_df.loc["Dollar Year", "Value"].astype(int)

        # Calculate
        capital_items = list(set(self.coeff_df[self.coeff_df["Type"] == "capital"].index.to_list()))
        capital_items_df = self.coeff_df.loc[capital_items].copy()
        capital_items_df = capital_items_df.reset_index(drop=False)
        capital_items_df = capital_items_df.set_index(
            keys=["Name", "Coeff"]
        )  # costs are in USD/steel plant capacity
        capital_items_df = capital_items_df.drop(columns=["Unit", "Type"])

        ref_steel_plant_capacity_tpy = units.convert_units(
            inputs["system_capacity"] * self.steel_to_iron_ratio, "t/h", "t/yr"
        )

        total_capex_usd = 0.0
        for item in capital_items:
            if (
                capital_items_df.loc[item, "exp"]["Value"] > 0
                and capital_items_df.loc[item, "lin"]["Value"] > 0
            ):
                capex = capital_items_df.loc[item, "lin"]["Value"] * (
                    (ref_steel_plant_capacity_tpy) ** capital_items_df.loc[item, "exp"]["Value"]
                )
                total_capex_usd += inflate_cepci(capex, dollar_year, self.config.cost_year)

        # Calculate Owners Costs
        # owner_costs_frac_tpc = self.coeff_df[self.coeff_df["Type"]=="owner"]["Value"].sum()

        # Calculate Fixed OpEx, includes:
        fixed_items = list(
            set(self.coeff_df[self.coeff_df["Type"] == "fixed opex"].index.to_list())
        )
        fixed_items_df = self.coeff_df.loc[fixed_items].copy()
        fixed_items_df = fixed_items_df.reset_index(drop=False)
        fixed_items_df = fixed_items_df.set_index(keys=["Name", "Coeff"])
        fixed_items_df = fixed_items_df.drop(columns=["Type"])

        property_om = (
            total_capex_usd * fixed_items_df.loc["Property Tax & Insurance"]["Value"].sum()
        )

        # Calculate labor costs
        skilled_labor_cost = self.config.skilled_labor_cost * (
            fixed_items_df.loc["% Skilled Labor"]["Value"].values / 100
        )
        unskilled_labor_cost = self.config.unskilled_labor_cost * (
            fixed_items_df.loc["% Unskilled Labor"]["Value"].values / 100
        )
        labor_cost_per_hr = skilled_labor_cost + unskilled_labor_cost  # USD/hr

        ref_steel_plant_capacity_kgpd = units.convert_units(
            inputs["system_capacity"] * self.steel_to_iron_ratio, "t/h", "kg/d"
        )
        scaled_steel_plant_capacity_kgpd = (
            ref_steel_plant_capacity_kgpd
            ** fixed_items_df.loc["Annual Operating Labor Cost", "exp"]["Value"]
        )

        # employee-hours/day/process step = ((employee-hours/day/process step)/(kg/day))*(kg/day)
        work_hrs_per_day_per_step = (
            scaled_steel_plant_capacity_kgpd
            * fixed_items_df.loc["Annual Operating Labor Cost", "lin"]["Value"]
        )

        # employee-hours/day = employee-hours/day/process step * # of process steps
        work_hrs_per_day = (
            work_hrs_per_day_per_step * fixed_items_df.loc["Processing Steps"]["Value"].values
        )
        labor_cost_per_day = labor_cost_per_hr * work_hrs_per_day
        annual_labor_cost = labor_cost_per_day * units.convert_units(1, "yr", "d")
        maintenance_labor_cost = (
            total_capex_usd * fixed_items_df.loc["Maintenance Labor Cost"]["Value"].values
        )
        admin_labor_cost = fixed_items_df.loc["Administrative & Support Labor Cost"][
            "Value"
        ].values * (annual_labor_cost + maintenance_labor_cost)

        total_labor_related_cost = admin_labor_cost + maintenance_labor_cost + annual_labor_cost
        tot_fixed_om = total_labor_related_cost + property_om

        # Calculate Variable O&M
        varom = self.coeff_df[self.coeff_df["Type"] == "variable opex"][
            "Value"
        ].sum()  # units are USD/mtpy steel
        tot_varopex = varom * self.steel_to_iron_ratio * inputs["pig_iron_out"].sum()

        # Adjust costs to target dollar year
        tot_capex_adjusted = inflate_cepci(total_capex_usd, dollar_year, self.config.cost_year)
        tot_fixed_om_adjusted = inflate_cpi(tot_fixed_om, dollar_year, self.config.cost_year)
        tot_varopex_adjusted = inflate_cpi(tot_varopex, dollar_year, self.config.cost_year)

        outputs["CapEx"] = tot_capex_adjusted
        outputs["VarOpEx"] = tot_varopex_adjusted
        outputs["OpEx"] = tot_fixed_om_adjusted
