import numpy as np
import pandas as pd
import openmdao.api as om
from attrs import field, define

from h2integrate.core.utilities import BaseConfig, merge_shared_inputs
from h2integrate.core.validators import contains
from h2integrate.converters.iron.iron import (
    IronCostModelConfig,
    IronPerformanceModelConfig,
    IronPerformanceModelOutputs,
    run_iron_cost_model,
    run_size_iron_plant_performance,
)
from h2integrate.core.model_baseclasses import CostModelBaseClass
from h2integrate.tools.inflation.inflate import inflate_cpi, inflate_cepci
from h2integrate.converters.iron.load_top_down_coeffs import load_top_down_coeffs


@define(kw_only=True)
class IronPlantBaseConfig(BaseConfig):
    winning_type: str = field(
        kw_only=True, converter=(str.lower, str.strip), validator=contains(["h2", "ng"])
    )  # product selection
    iron_win_capacity: float | int = field(default=1418095)  # plant_capacity_mtpy
    win_capacity_demon: str = field(
        default="iron", converter=(str.lower, str.strip), validator=contains(["iron", "steel"])
    )  # capacity_denominator

    model_name: str = field(default="rosner")  # only option at the moment
    model_fp: str = field(default="")
    inputs_fp: str = field(default="")
    coeffs_fp: str = field(default="")
    refit_coeffs: bool = field(default=False)
    site_name: str = field(default="winning_site")

    def make_model_dict(self):
        keys = ["model_fp", "inputs_fp", "coeffs_fp", "refit_coeffs"]
        d = self.as_dict()
        model_dict = {k: v for k, v in d.items() if k in keys}
        model_dict.update({"name": self.model_name})
        return model_dict

    def make_site_dict(self):
        return {"name": self.site_name}


@define(kw_only=True)
class IronPlantPerformanceConfig(IronPlantBaseConfig):
    def make_model_dict(self):
        keys = ["model_fp", "inputs_fp", "coeffs_fp", "refit_coeffs"]
        d = self.as_dict()
        model_dict = {k: v for k, v in d.items() if k in keys}
        model_dict.update({"name": self.model_name})
        return model_dict


class IronPlantPerformanceComponent(om.ExplicitComponent):
    def initialize(self):
        self.options.declare("driver_config", types=dict)
        self.options.declare("plant_config", types=dict)
        self.options.declare("tech_config", types=dict)

    def setup(self):
        n_timesteps = self.options["plant_config"]["plant"]["simulation"]["n_timesteps"]
        self.config = IronPlantPerformanceConfig.from_dict(
            merge_shared_inputs(self.options["tech_config"]["model_inputs"], "performance"),
            strict=False,
        )
        self.add_input("iron_ore_in", val=0.0, shape=n_timesteps, units="t/h")
        self.add_discrete_output(
            "iron_plant_performance", val=pd.DataFrame, desc="iron plant performance results"
        )
        self.add_output("pig_iron_out", val=0.0, shape=n_timesteps, units="kg/h")
        self.add_output("total_pig_iron_produced", val=0.0, units="t/year")
        # self.add_output("total_steel_produced", val=0.0, units="t/year")

    def compute(self, inputs, outputs, discrete_inputs, discrete_outputs):
        n_timesteps = self.options["plant_config"]["plant"]["simulation"]["n_timesteps"]
        iron_plant_performance_inputs = {
            "plant_capacity_mtpy": self.config.iron_win_capacity,
            "capacity_denominator": self.config.win_capacity_demon,
        }
        iron_plant_model_inputs = self.config.make_model_dict()
        iron_plant_site = self.config.make_site_dict()
        performance_config = IronPerformanceModelConfig(
            product_selection=f"{self.config.winning_type}_dri",
            site=iron_plant_site,
            model=iron_plant_model_inputs,
            params=iron_plant_performance_inputs,
        )
        iron_plant_performance = run_size_iron_plant_performance(performance_config)
        # wltpy = wet long tons per year
        pig_iron_produced_mtpy = iron_plant_performance.performances_df.set_index("Name").loc[
            "Pig Iron Production"
        ]["Model"]
        outputs["pig_iron_out"] = pig_iron_produced_mtpy * 1000 / n_timesteps
        outputs["total_pig_iron_produced"] = pig_iron_produced_mtpy
        discrete_outputs["iron_plant_performance"] = iron_plant_performance.performances_df


@define(kw_only=True)
class IronPlantCostConfig(IronPlantBaseConfig):
    LCOE: float = field(kw_only=True)  # $/MWh
    LCOH: float = field(kw_only=True)  # $/kg
    LCOI_ore: float = field(kw_only=True)
    iron_transport_cost: float = field(kw_only=True)
    ore_profit_pct: float = field(kw_only=True)

    # varom_model_name is unused at the moment
    varom_model_name: str = field(
        default="rosner", validator=contains(["rosner", "rosner_override"])
    )
    operational_year: int = field(converter=int, kw_only=True)
    installation_years: int | float = field(kw_only=True)
    plant_life: int = field(converter=int, kw_only=True)
    cost_year: int = field(converter=int, kw_only=True)

    def make_model_dict(self):
        keys = ["model_fp", "inputs_fp", "coeffs_fp", "refit_coeffs"]
        d = self.as_dict()
        model_dict = {k: v for k, v in d.items() if k in keys}
        model_dict.update({"name": self.model_name})
        return model_dict

    def make_cost_dict(self):
        keys = ["operational_year", "installation_years", "plant_life"]
        d = self.as_dict()
        cost_dict = {k: v for k, v in d.items() if k in keys}
        return cost_dict


class IronPlantCostComponent(CostModelBaseClass):
    def setup(self):
        self.target_dollar_year = self.options["plant_config"]["finance_parameters"][
            "cost_adjustment_parameters"
        ]["target_dollar_year"]
        self.plant_life = self.options["plant_config"]["plant"]["plant_life"]

        config_dict = merge_shared_inputs(self.options["tech_config"]["model_inputs"], "cost")
        config_dict.update({"cost_year": self.target_dollar_year})
        config_dict.update({"plant_life": self.plant_life})

        self.config = IronPlantCostConfig.from_dict(config_dict)

        super().setup()
        self.add_input("LCOE", val=self.config.LCOE, units="USD/MW/h")
        self.add_input("LCOH", val=self.config.LCOH, units="USD/kg")
        self.add_input("price_iron_ore", val=self.config.LCOI_ore, units="USD/t")
        self.add_input("iron_transport_cost", val=self.config.iron_transport_cost, units="USD/t")
        self.add_input("ore_profit_pct", val=self.config.ore_profit_pct, units="USD/t")
        self.add_input("total_pig_iron_produced", val=1.0, units="t/year")
        self.add_discrete_input(
            "iron_plant_performance", val=pd.DataFrame, desc="iron plant performance results"
        )
        self.add_discrete_output(
            "iron_plant_cost", val=pd.DataFrame, desc="iron plant cost results"
        )

    def compute(self, inputs, outputs, discrete_inputs, discrete_outputs):
        iron_plant_performance = IronPerformanceModelOutputs(
            performances_df=discrete_inputs["iron_plant_performance"]
        )

        iron_plant_cost_inputs = {
            "lcoe": inputs["LCOE"][0] / 1e3,
            "lcoh": inputs["LCOH"][0],
            "lco_iron_ore_tonne": inputs["price_iron_ore"],
            "iron_transport_tonne": inputs["iron_transport_cost"][0],
            "plant_capacity_mtpy": self.config.iron_win_capacity,
            "capacity_denominator": self.config.win_capacity_demon,
        }
        cost_dict = self.config.make_cost_dict()
        iron_plant_cost_inputs.update(cost_dict)

        iron_plant_model_inputs = self.config.make_model_dict()
        iron_ore_site = self.config.make_site_dict()
        cost_config = IronCostModelConfig(
            product_selection=f"{self.config.winning_type}_dri",
            site=iron_ore_site,
            model=iron_plant_model_inputs,
            params=iron_plant_cost_inputs,
            performance=iron_plant_performance,
        )
        iron_plant_cost = run_iron_cost_model(cost_config)

        discrete_outputs["iron_plant_cost"] = iron_plant_cost.costs_df

        # Now taking some stuff from finance
        cost_df = iron_plant_cost.costs_df.set_index("Name")
        cost_ds = cost_df.loc[:, self.config.site_name]

        cost_names = cost_df.index.values
        cost_types = cost_df.loc[:, "Type"].values
        cost_units = cost_df.loc[:, "Unit"].values

        # add capital items
        capex = 0
        fixed_om = 0
        variable_om = 0
        capital_idxs = np.where(cost_types == "capital")[0]
        for idx in capital_idxs:
            cost_names[idx]
            unit = cost_units[idx]  # Units for capital costs should be "<YYYY> $""
            source_year = int(unit[:4])
            source_year_cost = cost_ds.iloc[idx]
            capex += inflate_cepci(source_year_cost, source_year, self.config.cost_year)

        # add fixed costs
        fixed_idxs = np.where(cost_types == "fixed opex")[0]
        for idx in fixed_idxs:
            cost_names[idx]
            unit = cost_units[idx]  # Units for fixed opex costs should be "<YYYY> $ per year"
            source_year = int(unit[:4])
            source_year_cost = cost_ds.iloc[idx]
            fixed_om += inflate_cpi(source_year_cost, source_year, self.config.cost_year)

        # add feedstock costs
        perf_df = iron_plant_performance.performances_df.set_index("Name")
        perf_ds = perf_df.loc[:, "Model"]

        coeff_dict = load_top_down_coeffs(
            [
                "Raw Water",
                "Lime",
                "Carbon",
                "Slag Disposal",
                "Hydrogen",
                "Natural Gas",
                "Electricity",
                "Inflation Rate",
            ]
        )

        years = list(coeff_dict["years"])
        analysis_start = self.config.operational_year - self.config.installation_years
        start_idx = years.index(analysis_start)
        if len(years) > (start_idx + self.config.plant_life + self.config.installation_years + 1):
            end_idx = years.index(
                analysis_start + self.config.plant_life + self.config.installation_years + 1
            )
            indices = list(np.arange(start_idx, end_idx))
        else:
            end_idx = len(years) - 1
            indices = list(np.arange(start_idx, end_idx))
            repeats = (
                start_idx + self.config.plant_life + self.config.installation_years + 2 - len(years)
            )
            for _i in range(repeats):
                indices.append(end_idx)

        raw_water_unitcost_tonne = coeff_dict["Raw Water"]["values"][indices].astype(float)
        lime_unitcost_tonne = coeff_dict["Lime"]["values"][indices].astype(float)
        carbon_unitcost_tonne = coeff_dict["Carbon"]["values"][indices].astype(float)
        slag_disposal_unitcost_tonne = coeff_dict["Slag Disposal"]["values"][indices].astype(float)

        # TODO: make natural gas costs an input
        natural_gas_prices_MMBTU = coeff_dict["Natural Gas"]["values"][indices].astype(float)
        natural_gas_prices_GJ = natural_gas_prices_MMBTU / 1.05506  # Convert to GJ

        iron_ore_pellet_unitcost_tonne = inputs["price_iron_ore"]
        if inputs["iron_transport_cost"] > 0:
            iron_transport_cost_tonne = inputs["iron_transport_cost"][0]
            ore_profit_pct = inputs["ore_profit_pct"][0]
            iron_ore_pellet_unitcost_tonne = (
                iron_ore_pellet_unitcost_tonne + iron_transport_cost_tonne
            ) * (1 + ore_profit_pct / 100)

        v_start = years.index(self.config.operational_year) - years.index(analysis_start) + 1
        variable_om += perf_ds["Raw Water Withdrawal"] * raw_water_unitcost_tonne
        variable_om += perf_ds["Lime"] * lime_unitcost_tonne
        variable_om += perf_ds["Carbon (Coke)"] * carbon_unitcost_tonne
        variable_om += perf_ds["Iron Ore"] * iron_ore_pellet_unitcost_tonne
        variable_om += perf_ds["Hydrogen"] * inputs["LCOH"][0] * 1000
        variable_om += perf_ds["Natural Gas"] * natural_gas_prices_GJ
        variable_om += perf_ds["Electricity"] * inputs["LCOE"][0]
        variable_om += perf_ds["Slag"] * slag_disposal_unitcost_tonne

        total_production = inputs["total_pig_iron_produced"]
        variable_om = np.multiply(total_production, variable_om)

        outputs["CapEx"] = capex
        outputs["OpEx"] = fixed_om
        outputs["VarOpEx"] = variable_om[v_start:]
