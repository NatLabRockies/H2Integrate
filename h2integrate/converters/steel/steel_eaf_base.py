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
class ElectricArcFurnacePerformanceBaseConfig(BaseConfig):
    """Configuration baseclass for ElectricArcFurnacePlantBasePerformanceComponent.

    Attributes:
        steel_production_rate_tonnes_per_hr (float): capacity of the steel processing plant
            in units of metric tonnes of steel produced per hour.
        water_density (float): water density in kg/m3 to use to calculate water volume
            from mass. Defaults to 1000.0
    """

    steel_production_rate_tonnes_per_hr: float = field()
    water_density: float = field(default=1000)  # kg/m3


class ElectricArcFurnacePlantBasePerformanceComponent(om.ExplicitComponent):
    def initialize(self):
        self.options.declare("driver_config", types=dict)
        self.options.declare("plant_config", types=dict)
        self.options.declare("tech_config", types=dict)

    def setup(self):
        n_timesteps = self.options["plant_config"]["plant"]["simulation"]["n_timesteps"]

        self.config = ElectricArcFurnacePerformanceBaseConfig.from_dict(
            merge_shared_inputs(self.options["tech_config"]["model_inputs"], "performance"),
            strict=True,
        )

        self.add_input(
            "system_capacity",
            val=self.config.steel_production_rate_tonnes_per_hr,
            units="t/h",
            desc="Rated steel production capacity",
        )

        # Add feedstock inputs and outputs, default to 0 --> set using feedstock component
        for feedstock, feedstock_units in self.feedstocks_to_units.items():
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

        # Default the steel demand input as the rated capacity
        self.add_input(
            "steel_demand",
            val=self.config.steel_production_rate_tonnes_per_hr,
            shape=n_timesteps,
            units="t/h",
            desc="Steel demand for steel plant",
        )

        self.add_output(
            "steel_out",
            val=0.0,
            shape=n_timesteps,
            units="t/h",
            desc="Steel produced",
        )

        coeff_fpath = ROOT_DIR / "converters" / "iron" / "rosner" / "perf_coeffs.csv"
        # rosner dri performance model
        coeff_df = pd.read_csv(coeff_fpath, index_col=0)
        self.coeff_df = self.format_coeff_df(coeff_df)

    def format_coeff_df(self, coeff_df):
        """Update the coefficient dataframe such that feedstock values are converted to standard
        units and that units are compatible with OpenMDAO Units. Filter the dataframe to include
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

        # H2 EAF needs natural gas, electricity, carbon, lime, water
        # NG EAF needs natural gas and electricity.
        # add pig iron feedstock to dataframe
        steel_plant_capacity = coeff_df[coeff_df["Name"] == "Steel Production"]["Value"].values[0]
        iron_plant_capacity = coeff_df[coeff_df["Name"] == "Pig Iron Production"]["Value"].values[0]
        iron_to_steel_ratio = iron_plant_capacity / steel_plant_capacity  # both in metric tons/year
        # add to dataframe
        pig_iron_row = pd.DataFrame(
            {
                "Name": ["Pig Iron"],
                "Type": ["feed"],
                "Coeff": ["lin"],
                "Unit": ["mt pig iron/mt steel"],
                "Value": [iron_to_steel_ratio],
            }
        )
        coeff_df = pd.concat([coeff_df, pig_iron_row], ignore_index=True)

        # capacity units units are mtpy
        unit_rename_mapper = {"mtpy": "t/yr", "%": "unitless"}

        # efficiency units are %
        # feedstock units are GJ-LHV NG/mt steel,
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
                .replace("MWh", "(MW*h)")
                .replace("mt C", "t")
                .replace("mt lime", "t")
                .replace("%", "percent")
                .replace("mtpy", "(t/yr)")
                .replace("mt", "t")
                .replace("kW/", "(kW*h)/")
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
        feedstocks = self.coeff_df[self.coeff_df["Type"] == "feed"].copy()

        # get the feedstock usage rates in units/t steel
        feedstocks_usage_rates = {
            "natural_gas": feedstocks[feedstocks["Name"] == "Natural Gas"][
                "Value"
            ].sum(),  # MMBtu/t
            "water": feedstocks[feedstocks["Name"] == "Raw Water Withdrawal"][
                "Value"
            ].sum(),  # galUS/t
            "pig_iron": feedstocks[feedstocks["Name"] == "Pig Iron"]["Value"].sum(),  # t/t
            "electricity": feedstocks[feedstocks["Unit"] == "(kW*h)/t"][
                "Value"
            ].sum(),  # electricity
        }

        if "carbon" in self.feedstocks_to_units:
            # t/t
            feedstocks_usage_rates["carbon"] = feedstocks[feedstocks["Name"] == "Carbon (Coke)"][
                "Value"
            ].sum()  # t/t

        if "lime" in self.feedstocks_to_units:
            # m**3/t
            feedstocks_usage_rates["lime"] = feedstocks[feedstocks["Name"] == "Lime"][
                "Value"
            ].sum()  # t/t

        # steel demand, saturated at maximum rated system capacity
        steel_demand = np.where(
            inputs["steel_demand"] > inputs["system_capacity"],
            inputs["system_capacity"],
            inputs["steel_demand"],
        )

        # initialize an array of how much steel could be produced
        # from the available feedstocks and the demand
        steel_from_feedstocks = np.zeros(
            (len(feedstocks_usage_rates) + 1, len(inputs["steel_demand"]))
        )
        # first entry is the steel demand
        steel_from_feedstocks[0] = steel_demand
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
            steel_from_feedstocks[ii] = feedstock_available / consumption_rate
            ii += 1

        # output is minimum between available feedstocks and output demand
        steel_production = np.minimum.reduce(steel_from_feedstocks)
        outputs["steel_out"] = steel_production

        # feedstock consumption based on actual steel produced
        for feedstock_type, consumption_rate in feedstocks_usage_rates.items():
            outputs[f"{feedstock_type}_consumed"] = steel_production * consumption_rate


@define
class ElectricArcFurnaceCostBaseConfig(CostModelBaseConfig):
    """Configuration baseclass for ElectricArcFurnacePlantBaseCostComponent.

    Attributes:
        steel_production_rate_tonnes_per_hr (float): capacity of the steel processing plant
            in units of metric tonnes of steel produced per hour.
        cost_year (int): This model uses 2022 as the base year for the cost model.
            The cost year is updated based on `target_dollar_year` in the plant
            config to adjust costs based on CPI/CEPCI within this model. This value
            cannot be user added under `cost_parameters`.
        skilled_labor_cost (float): Skilled labor cost in 2022 USD/hr
        unskilled_labor_cost (float): Unskilled labor cost in 2022 USD/hr
    """

    steel_production_rate_tonnes_per_hr: float = field()
    cost_year: int = field(converter=int)
    skilled_labor_cost: float = field(validator=gte_zero)
    unskilled_labor_cost: float = field(validator=gte_zero)


class ElectricArcFurnacePlantBaseCostComponent(CostModelBaseClass):
    """Cost component for electric arc furnace (EAF) plant
    using the Rosner cost model.

    Attributes:
        config (ElectricArcFurnaceCostBaseConfig): configuration class
        coeff_df (pd.DataFrame): cost coefficient dataframe
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

        self.config = ElectricArcFurnaceCostBaseConfig.from_dict(config_dict, strict=False)

        super().setup()

        self.add_input(
            "system_capacity",
            val=self.config.steel_production_rate_tonnes_per_hr,
            units="t/h",
            desc="Steel production capacity",
        )
        self.add_input(
            "steel_out",
            val=0.0,
            shape=n_timesteps,
            units="t/h",
            desc="Steel produced",
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

        # perf_coeff_fpath = ROOT_DIR / "converters" / "iron" / "rosner" / "perf_coeffs.csv"

        # perf_df = pd.read_csv(perf_coeff_fpath, index_col=0)
        # perf_df = perf_df[perf_df["Product"] == self.product]

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

        ref_steel_plant_capacity_tpy = units.convert_units(inputs["system_capacity"], "t/h", "t/yr")

        total_capex_usd = 0.0
        for item in capital_items:
            if (
                np.abs(capital_items_df.loc[item, "exp"]["Value"]) > 0
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
            inputs["system_capacity"], "t/h", "kg/d"
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
        tot_varopex = varom * inputs["steel_out"].sum()

        # Adjust costs to target dollar year
        tot_capex_adjusted = inflate_cepci(total_capex_usd, dollar_year, self.config.cost_year)
        tot_fixed_om_adjusted = inflate_cpi(tot_fixed_om, dollar_year, self.config.cost_year)
        tot_varopex_adjusted = inflate_cpi(tot_varopex, dollar_year, self.config.cost_year)

        outputs["CapEx"] = tot_capex_adjusted
        outputs["VarOpEx"] = tot_varopex_adjusted
        outputs["OpEx"] = tot_fixed_om_adjusted
