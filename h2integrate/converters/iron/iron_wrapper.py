import copy
from pathlib import Path

from attrs import field, define
from hopp.utilities import load_yaml

import h2integrate.tools.profast_reverse_tools as rev_pf_tools
from h2integrate.core.utilities import CostModelBaseConfig, merge_shared_inputs
from h2integrate.core.validators import contains, range_val
from h2integrate.converters.iron.iron import run_iron_full_model
from h2integrate.core.model_baseclasses import CostModelBaseClass
from h2integrate.converters.iron.martin_transport.iron_transport import calc_iron_ship_cost


@define(kw_only=True)
class IronConfig(CostModelBaseConfig):
    """Configuration class for IronComponent.

    Attributes:
        LCOE (float): cost of electricity in USD/MW/h
        LCOH (float): cost of hydrogen in USD/kg
        ROM_iron_site_name (str): mine for Iron Ore.
            Options are "Hibbing", "Northshore", "United", "Minorca" or "Tilden".
        iron_ore_product_selection (str): iron ore pellet type.
            Options are "drg_taconite_pellets" or "std_taconite_pellets".
        reduced_iron_product_selection (str): material for iron electrwinning process.
            Options are "h2_dri" or "ng_dri"
        structural_iron_product_selection (str): iron processing method.
            Options are "eaf_steel" or "none".
        iron_capacity_denom (str): Capacity denominator to use in iron modeling.
            Options are "iron" or "steel".
        eaf_capacity (float, optional): Capacity of electric arc furnace in
            metric tonnes of iron per year. Defaults to 1000000.
        dri_capacity (float, optional): Capacity of direct reduced iron plant in
            metric tonnes of iron per year. Defaults to 1418095.
        iron_ore_cf_estimate (float, optional): Estimated capacity factor of iron ore mine.
            Defaults to 0.9. Must be between 0 and 1.

    """

    # Comments below denote which step each config variable applies to in run_iron_full_model

    LCOE: float = field()  # $/MWh
    LCOH: float = field()  # $/kg
    ROM_iron_site_name: str = field(
        validator=contains(["Hibbing", "Northshore", "United", "Minorca", "Tilden"])
    )  # ore
    iron_ore_product_selection: str = field(
        converter=(str.lower, str.strip),
        validator=contains(["drg_taconite_pellets", "std_taconite_pellets"]),
    )  # ore
    reduced_iron_site_latitude: float = field()
    reduced_iron_site_longitude: float = field()
    reduced_iron_product_selection: str = field(
        converter=(str.lower, str.strip), validator=contains(["h2_dri", "ng_dri"])
    )  # win
    structural_iron_product_selection: str = field(
        converter=(str.lower, str.strip), validator=contains(["eaf_steel", "none"])
    )  # post
    iron_capacity_denom: str = field(
        default="iron", converter=(str.lower, str.strip), validator=contains(["iron", "steel"])
    )  # win
    eaf_capacity: float | int = field(default=1000000)  # post
    dri_capacity: float | int = field(default=1418095)  # win
    iron_ore_cf_estimate: float = field(default=0.9, validator=range_val(0, 1))  # ore
    transport_cost_included: bool = field(default=True)
    ng_mod: bool = field(default=False)
    ng_price: float = field(default=4.00)  # $/MMBTU
    capex_mod: bool = field(default=False)
    capex_mod_pct: float = field(default=0.0)  # Fraction of orignal capex value to modify by


class IronComponent(CostModelBaseClass):
    """
    A simple OpenMDAO component that represents an Iron model from old GreenHEART code.

    This component uses caching to store and retrieve results of the iron model
    based on the configuration.
    """

    def setup(self):
        n_timesteps = self.options["plant_config"]["plant"]["simulation"]["n_timesteps"]
        self.config = IronConfig.from_dict(
            merge_shared_inputs(self.options["tech_config"]["model_inputs"], "cost"),
            strict=False,
        )
        super().setup()

        CD = Path(__file__).parent
        old_input_path = CD / "old_input"
        h2i_config_old_fn = "h2integrate_config_modular.yaml"
        self.h2i_config_old = load_yaml(old_input_path / h2i_config_old_fn)

        self.add_output("iron_out", val=0.0, shape=n_timesteps, units="kg/h")

        self.add_input("LCOE", val=self.config.LCOE, units="USD/MW/h")
        self.add_input("LCOH", val=self.config.LCOH, units="USD/kg")

        self.add_output("total_iron_produced", val=0.0, units="kg/year")
        self.add_output("LCOI", val=0.0, units="USD/kg")

    def compute(self, inputs, outputs, discrete_inputs, discrete_outputs):
        # Parse in values from config
        mine_site = self.config.ROM_iron_site_name
        ore_type = self.config.iron_ore_product_selection
        red_site_lat = self.config.reduced_iron_site_latitude
        red_site_lon = self.config.reduced_iron_site_longitude
        red_iron_type = self.config.reduced_iron_product_selection
        struct_iron_type = self.config.structural_iron_product_selection
        denom = self.config.iron_capacity_denom
        eaf_cap = self.config.eaf_capacity
        dri_cap = self.config.dri_capacity
        ore_cf = self.config.iron_ore_cf_estimate
        trans_incl = self.config.transport_cost_included
        ng_mod = self.config.ng_mod
        ng_price = self.config.ng_price
        capex_mod = self.config.capex_mod
        capex_pct = self.config.capex_mod_pct

        # BELOW: Copy-pasted from ye olde h2integrate_simulation.py (the 1000+ line monster)

        iron_config = copy.deepcopy(self.h2i_config_old)

        # This is not the most graceful way to do this... but it avoids copied imports
        # and copying iron.py
        iron_ore_config = copy.deepcopy(iron_config)
        iron_win_config = copy.deepcopy(iron_config)
        iron_post_config = copy.deepcopy(iron_config)

        iron_ore_config["iron"] = iron_config["iron_ore"]
        iron_win_config["iron"] = iron_config["iron_win"]
        iron_post_config["iron"] = iron_config["iron_post"]
        for sub_iron_config in [
            iron_ore_config,
            iron_win_config,
            iron_post_config,
        ]:  # ,iron_post_config]: # iron_pre_config, iron_post_config
            sub_iron_config["iron"]["costs"]["lcoe"] = inputs["LCOE"][0] / 1e3
            sub_iron_config["iron"]["finances"]["lcoe"] = inputs["LCOE"][0] / 1e3
            sub_iron_config["iron"]["costs"]["lcoh"] = inputs["LCOH"][0]
            sub_iron_config["iron"]["finances"]["lcoh"] = inputs["LCOH"][0]

        # Update ore config
        iron_ore_config["iron"]["site"]["name"] = mine_site
        iron_ore_config["iron"]["performance"]["input_capacity_factor_estimate"] = ore_cf
        iron_ore_config["iron"]["product_selection"] = ore_type

        # Update win config
        iron_win_config["iron"]["product_selection"] = red_iron_type
        iron_win_config["iron"]["performance"]["plant_capacity_mtpy"] = dri_cap
        iron_win_config["iron"]["site"]["lat"] = red_site_lat
        iron_win_config["iron"]["site"]["lon"] = red_site_lon

        # Update post config
        if struct_iron_type == "none":
            iron_post_config["iron"]["product_selection"] = "none"
        elif struct_iron_type == "eaf_steel":
            if red_iron_type == "ng_dri":
                iron_post_config["iron"]["product_selection"] = "ng_eaf"
            elif red_iron_type == "h2_dri":
                iron_post_config["iron"]["product_selection"] = "h2_eaf"
            else:
                msg = f"The EAF steel model cannot (yet) use {red_iron_type} as input"
                raise NotImplementedError(msg)
            iron_post_config["iron"]["performance"]["capacity_denominator"] = denom
            iron_post_config["iron"]["performance"]["plant_capacity_mtpy"] = eaf_cap

        # Run iron model for iron ore
        iron_ore_config["iron"]["finances"]["ng_mod"] = ng_mod
        iron_ore_config["iron"]["finances"]["ng_price"] = ng_price
        iron_ore_config["iron"]["costs"]["capex_mod"] = capex_mod
        iron_ore_config["iron"]["costs"]["capex_pct"] = capex_pct
        iron_ore_performance, iron_ore_costs, iron_ore_finance = run_iron_full_model(
            iron_ore_config
        )

        # Run iron transport model
        # Determine whether to ship from "Duluth", "Chicago", "Cleveland" or "Buffalo"
        # To electrowinning site
        if trans_incl:
            iron_transport_cost_tonne, ore_profit_pct = calc_iron_ship_cost(iron_win_config)
        else:
            iron_transport_cost_tonne = 0
            ore_profit_pct = 6

        ### DRI ----------------------------------------------------------------------------
        ### Electrowinning

        iron_win_config["iron"]["finances"]["ng_mod"] = ng_mod
        iron_win_config["iron"]["finances"]["ng_price"] = ng_price
        iron_win_config["iron"]["costs"]["capex_mod"] = capex_mod
        iron_win_config["iron"]["costs"]["capex_pct"] = capex_pct
        iron_win_config["iron"]["finances"]["ore_profit_pct"] = ore_profit_pct
        iron_win_config["iron"]["costs"]["iron_transport_tonne"] = iron_transport_cost_tonne
        iron_win_config["iron"]["costs"]["lco_iron_ore_tonne"] = iron_ore_finance.sol["lco"]
        iron_win_performance, iron_win_costs, iron_win_finance = run_iron_full_model(
            iron_win_config
        )

        ### EAF ----------------------------------------------------------------------------
        if iron_post_config["iron"]["product_selection"] == "none":
            iron_performance = iron_win_performance
            iron_costs = iron_win_costs
            iron_finance = iron_win_finance

        else:
            if iron_post_config["iron"]["product_selection"] not in ["ng_eaf", "h2_eaf"]:
                raise ValueError(
                    "The product selection for the iron post module must be either \
                    'ng_eaf' or 'h2_eaf'"
                )
            pf_config = rev_pf_tools.make_pf_config_from_profast(
                iron_win_finance.pf
            )  # dictionary of profast objects
            pf_dict = rev_pf_tools.convert_pf_res_to_pf_config(
                copy.deepcopy(pf_config)
            )  # profast dictionary of values
            iron_post_config["iron"]["finances"]["pf"] = pf_dict
            iron_post_config["iron"]["costs"]["lco_iron_ore_tonne"] = iron_ore_finance.sol["lco"]
            iron_post_config["iron"]["finances"]["ng_mod"] = ng_mod
            iron_post_config["iron"]["finances"]["ng_price"] = ng_price
            iron_post_config["iron"]["costs"]["capex_mod"] = capex_mod
            iron_post_config["iron"]["costs"]["capex_pct"] = capex_pct

            iron_post_performance, iron_post_costs, iron_post_finance = run_iron_full_model(
                iron_post_config
            )

            iron_performance = iron_post_performance
            iron_costs = iron_post_costs
            iron_finance = iron_post_finance

        perf_df = iron_performance.performances_df
        iron_mtpy = perf_df.loc[perf_df["Name"] == "Pig Iron Production", "Model"].values[0]

        # ABOVE: Copy-pasted from ye olde h2integrate_simulation.py (the 1000+ line monster)

        outputs["iron_out"] = iron_mtpy * 1000 / 8760
        outputs["total_iron_produced"] = iron_mtpy * 1000

        cost_df = iron_costs.costs_df
        capex = 0
        opex = 0
        capex_list = [
            "EAF & Casting",
            "Shaft Furnace",
            "Reformer",
            "Recycle Compressor",
            "Oxygen Supply",
            "H2 Pre-heating",
            "Cooling Tower",
            "Piping",
            "Electrical & Instrumentation",
            "Buildings, Storage, Water Service",
            "Other Miscellaneous Cost",
        ]
        opex_list = [
            "labor_cost_annual_operation",
            "labor_cost_maintenance",
            "labor_cost_admin_support",
            "property_tax_insurance",
            "maintenance_materials",
        ]

        location = cost_df.columns.values[-1]
        for capex_item in capex_list:
            capex += cost_df.loc[cost_df["Name"] == capex_item, location].values[0]
        for opex_item in opex_list:
            opex += cost_df.loc[cost_df["Name"] == opex_item, location].values[0]

        outputs["CapEx"] = capex
        outputs["OpEx"] = opex

        lcoi = iron_finance.sol["lco"]
        outputs["LCOI"] = lcoi / 1000
