import numpy as np
import pandas as pd
import openmdao.api as om
from attrs import field, define

from h2integrate.core.utilities import BaseConfig, merge_shared_inputs
from h2integrate.core.validators import contains, range_val
from h2integrate.converters.iron.iron import (
    IronCostModelConfig,
    IronPerformanceModelConfig,
    IronPerformanceModelOutputs,
    run_iron_cost_model,
    run_size_iron_plant_performance,
)
from h2integrate.core.model_baseclasses import CostModelBaseClass
from h2integrate.tools.inflation.inflate import inflate_cpi
from h2integrate.converters.iron.martin_ore.variable_om_cost import martin_ore_variable_om_cost
from h2integrate.converters.iron.rosner_ore.variable_om_cost import rosner_ore_variable_om_cost


@define(kw_only=True)
class IronMineBaseConfig(BaseConfig):
    mine: str = field(validator=contains(["Hibbing", "Northshore", "United", "Minorca", "Tilden"]))

    # product_selection
    taconite_pellet_type: str = field(
        converter=(str.lower, str.strip), validator=contains(["std", "drg"])
    )

    model_name: str = field(default="martine_ore")  # only option at the moment
    model_fp: str = field(default="")
    inputs_fp: str = field(default="")
    coeffs_fp: str = field(default="")
    refit_coeffs: bool = field(default=False)

    def make_model_dict(self):
        keys = ["model_fp", "inputs_fp", "coeffs_fp", "refit_coeffs"]
        d = self.as_dict()
        model_dict = {k: v for k, v in d.items() if k in keys}
        model_dict.update({"name": self.model_name})
        return model_dict

    def make_site_dict(self):
        return {"name": self.mine}


@define(kw_only=True)
class IronMinePerformanceConfig(IronMineBaseConfig):
    ore_cf_estimate: float = field(default=0.9, validator=range_val(0, 1))  # ore

    def make_model_dict(self):
        keys = ["model_fp", "inputs_fp", "coeffs_fp", "refit_coeffs"]
        d = self.as_dict()
        model_dict = {k: v for k, v in d.items() if k in keys}
        model_dict.update({"name": self.model_name})
        return model_dict


class IronMinePerformanceComponent(om.ExplicitComponent):
    def initialize(self):
        self.options.declare("driver_config", types=dict)
        self.options.declare("plant_config", types=dict)
        self.options.declare("tech_config", types=dict)

    def setup(self):
        n_timesteps = self.options["plant_config"]["plant"]["simulation"]["n_timesteps"]
        self.config = IronMinePerformanceConfig.from_dict(
            merge_shared_inputs(self.options["tech_config"]["model_inputs"], "performance"),
            strict=False,
        )
        self.add_discrete_output(
            "iron_mine_performance", val=pd.DataFrame, desc="iron mine performance results"
        )
        self.add_output("iron_ore_out", val=0.0, shape=n_timesteps, units="kg/h")
        self.add_output("total_iron_ore_produced", val=0.0, units="t/year")

    def compute(self, inputs, outputs, discrete_inputs, discrete_outputs):
        n_timesteps = self.options["plant_config"]["plant"]["simulation"]["n_timesteps"]
        ore_performance_inputs = {"input_capacity_factor_estimate": self.config.ore_cf_estimate}
        ore_model_inputs = self.config.make_model_dict()
        iron_mine_site = self.config.make_site_dict()
        performance_config = IronPerformanceModelConfig(
            product_selection=f"{self.config.taconite_pellet_type}_taconite_pellets",
            site=iron_mine_site,
            model=ore_model_inputs,
            params=ore_performance_inputs,
        )
        iron_mine_performance = run_size_iron_plant_performance(performance_config)
        # wltpy = wet long tons per year
        ore_produced_wltpy = iron_mine_performance.performances_df.set_index("Name").loc[
            "Ore pellets produced"
        ][self.config.mine]
        ore_produced_wmtpy = ore_produced_wltpy * 1.016047  # wmtpy = wet metric tonnes per year
        ore_produced_mtpy = ore_produced_wmtpy * 0.98  # mtpy = dry metric tonnes per year
        discrete_outputs["iron_mine_performance"] = iron_mine_performance.performances_df
        outputs["iron_ore_out"] = ore_produced_mtpy * 1000 / n_timesteps
        outputs["total_iron_ore_produced"] = ore_produced_mtpy


@define(kw_only=True)
class IronMineCostConfig(IronMineBaseConfig):
    LCOE: float = field(kw_only=True)  # $/MWh
    LCOH: float = field(kw_only=True)  # $/kg
    varom_model_name: str = field(
        default="martin_ore", validator=contains(["martin_ore", "rosner_ore"])
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


class IronMineCostComponent(CostModelBaseClass):
    def setup(self):
        self.target_dollar_year = self.options["plant_config"]["finance_parameters"][
            "cost_adjustment_parameters"
        ]["target_dollar_year"]
        self.plant_life = self.options["plant_config"]["plant"]["plant_life"]

        config_dict = merge_shared_inputs(self.options["tech_config"]["model_inputs"], "cost")
        config_dict.update({"cost_year": self.target_dollar_year})
        config_dict.update({"plant_life": self.plant_life})

        self.config = IronMineCostConfig.from_dict(config_dict, strict=False)

        super().setup()
        self.add_input("LCOE", val=self.config.LCOE, units="USD/MW/h")
        self.add_input("LCOH", val=self.config.LCOH, units="USD/kg")
        self.add_input("total_iron_ore_produced", val=1.0, units="t/year")
        self.add_discrete_input(
            "iron_mine_performance", val=pd.DataFrame, desc="iron mine performance results"
        )
        self.add_discrete_output("iron_mine_cost", val=pd.DataFrame, desc="iron mine cost results")

    def compute(self, inputs, outputs, discrete_inputs, discrete_outputs):
        ore_performance = IronPerformanceModelOutputs(
            performances_df=discrete_inputs["iron_mine_performance"]
        )

        ore_cost_inputs = {
            "lcoe": inputs["LCOE"][0] / 1e3,
            "lcoh": inputs["LCOH"][0],
        }
        cost_dict = self.config.make_cost_dict()
        ore_cost_inputs.update(cost_dict)

        ore_model_inputs = self.config.make_model_dict()
        iron_mine_site = self.config.make_site_dict()
        cost_config = IronCostModelConfig(
            product_selection=f"{self.config.taconite_pellet_type}_taconite_pellets",
            site=iron_mine_site,
            model=ore_model_inputs,
            params=ore_cost_inputs,
            performance=ore_performance,
        )
        iron_ore_cost = run_iron_cost_model(cost_config)

        discrete_outputs["iron_mine_cost"] = iron_ore_cost.costs_df

        # Now taking some stuff from finance
        cost_df = iron_ore_cost.costs_df.set_index("Name")
        cost_ds = cost_df.loc[:, self.config.mine]
        cost_names = cost_df.index.values
        cost_types = cost_df.loc[:, "Type"].values
        cost_units = cost_df.loc[:, "Unit"].values

        capex = 0
        fixed_om = 0
        variable_om = 0
        capital_idxs = np.where(cost_types == "capital")[0]
        for idx in capital_idxs:
            cost_names[idx]
            unit = cost_units[idx]  # Units for capital costs should be "<YYYY> $""
            source_year = int(unit[:4])
            source_year_cost = cost_ds.iloc[idx]
            cost = inflate_cpi(source_year_cost, source_year, self.config.cost_year)
            capex += cost

        # Add fixed opex costs
        fixed_idxs = np.where(cost_types == "fixed opex")[0]
        for idx in fixed_idxs:
            cost_names[idx]
            unit = cost_units[idx]  # Units for fixed opex costs should be "<YYYY> $ per year"
            source_year = int(unit[:4])
            source_year_cost = cost_ds.iloc[idx]
            fixed_cost = inflate_cpi(source_year_cost, source_year, self.config.cost_year)
            fixed_om += fixed_cost
        # NOTE: why are we double counting this cost?
        fixed_om * 6 / 12  # TODO: output installation cost?

        var_idxs = np.where(cost_types == "variable opex")[0]
        for idx in var_idxs:
            unit = cost_units[idx]  # Should be "<YYYY> $ per <unit plant output>"
            source_year = int(unit[:4])
            source_year_cost = cost_ds.iloc[idx]
            cost = inflate_cpi(source_year_cost, source_year, self.config.cost_year)
            variable_om += cost

        analysis_start = self.config.operational_year - self.config.installation_years
        var_om_td = 0
        # below is for rosner finance model
        if "rosner" in self.config.varom_model_name:
            var_om_td = rosner_ore_variable_om_cost(
                self.config.mine, cost_df, analysis_start, self.config.cost_year, self.plant_life
            )
        else:
            var_om_td = martin_ore_variable_om_cost(
                self.config.mine, cost_df, analysis_start, self.config.cost_year, self.plant_life
            )

        variable_om += var_om_td

        total_production = inputs["total_iron_ore_produced"]
        variable_om = np.multiply(total_production, variable_om)

        outputs["CapEx"] = capex
        outputs["OpEx"] = fixed_om
        outputs["VarOpEx"] = variable_om
