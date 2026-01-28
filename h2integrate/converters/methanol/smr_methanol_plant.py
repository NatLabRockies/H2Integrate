import numpy as np
from attrs import field, define
from openmdao.utils.units import convert_units

from h2integrate.core.utilities import merge_shared_inputs
from h2integrate.converters.methanol.methanol_baseclass import (
    MethanolCostConfig,
    MethanolCostBaseClass,
    MethanolFinanceConfig,
    MethanolFinanceBaseClass,
    MethanolPerformanceConfig,
    MethanolPerformanceBaseClass,
)


@define(kw_only=True)
class SMRPerformanceConfig(MethanolPerformanceConfig):
    meoh_syn_cat_consume_ratio: float = field()
    meoh_atr_cat_consume_ratio: float = field()
    ng_consume_ratio: float = field()
    elec_produce_ratio: float = field()


class SMRMethanolPlantPerformanceModel(MethanolPerformanceBaseClass):
    """
    An OpenMDAO component for modeling the performance of a steam methane reforming (SMR) methanol
    plant. Computes annual methanol and co-product production, feedstock consumption, and emissions
    based on plant capacity and capacity factor.

    Inputs:
        - meoh_syn_cat_consume_ratio: ratio of ft^3 methanol synthesis catalyst consumed to
            kg methanol produced
        - meoh_atr_cat_consume_ratio: ratio of ft^3 methanol autothermal reforming (ATR) catalyst
            consumed to kg methanol produced
        - ng_consume_ratio: ratio of kg natural gas (NG) consumed to kg methanol produced
        - elec_produce_ratio: ratio of electricity produced to kg methanol produced
    Outputs:
        - meoh_syn_cat_consume: annual consumption of methanol synthesis catalyst (ft**3/yr)
        - meoh_atr_cat_consume: annual consumption of methanol ATR catalyst (ft**3/yr)
        - ng_consume: hourly consumption of NG (kg/h)
        - methanol_out: hourly methanol production (kg/h)
        - electricity_out: hourly electricity production (kW*h/h)
    """

    def setup(self):
        n_timesteps = self.options["plant_config"]["plant"]["simulation"]["n_timesteps"]
        self.config = SMRPerformanceConfig.from_dict(
            merge_shared_inputs(self.options["tech_config"]["model_inputs"], "performance")
        )
        super().setup()

        # Add in tech-specific feedstock consumption ratios
        syn_ratio = self.config.meoh_syn_cat_consume_ratio
        atr_ratio = self.config.meoh_atr_cat_consume_ratio
        ng_ratio = self.config.ng_consume_ratio
        elec_ratio = self.config.elec_produce_ratio
        self.add_input("meoh_syn_cat_consume_ratio", units="ft**3/kg", val=syn_ratio)
        self.add_input("meoh_atr_cat_consume_ratio", units="ft**3/kg", val=atr_ratio)
        self.add_input("ng_consume_ratio", units="kg/kg", val=ng_ratio)
        self.add_input("elec_produce_ratio", units="kW*h/kg", val=elec_ratio)

        # Set up feedstock supply inputs - can be replaced by connections
        meoh_cap = self.config.plant_capacity_kgpy
        meoh_max_out = np.ones(n_timesteps) * meoh_cap / n_timesteps
        self.add_input("meoh_syn_cat_in", units="ft**3/yr", val=syn_ratio * np.sum(meoh_max_out))
        self.add_input("meoh_atr_cat_in", units="ft**3/yr", val=atr_ratio * np.sum(meoh_max_out))
        self.add_input(
            "ng_in", shape=n_timesteps, units="kg/h", val=ng_ratio * np.sum(meoh_max_out)
        )

        # Set up feedstock consumption outputs
        self.add_output("meoh_syn_cat_consume", units="ft**3/yr")
        self.add_output("meoh_atr_cat_consume", units="ft**3/yr")
        self.add_output("ng_consume", shape=n_timesteps, units="kg/h")

        # Set up electricity production output
        self.add_output("electricity_out", shape=n_timesteps, units="kW*h/h")

    def compute(self, inputs, outputs):
        n_timesteps = len(inputs["ng_in"])
        # Calculate max methanol production from each input
        syn_in = inputs["meoh_syn_cat_in"]
        atr_in = inputs["meoh_atr_cat_in"]
        ng_in = inputs["ng_in"]
        syn_ratio = inputs["meoh_syn_cat_consume_ratio"]
        atr_ratio = inputs["meoh_atr_cat_consume_ratio"]
        ng_ratio = inputs["ng_consume_ratio"]
        meoh_from_syn = np.ones(n_timesteps) * syn_in / syn_ratio / n_timesteps
        meoh_from_atr = np.ones(n_timesteps) * atr_in / atr_ratio / n_timesteps
        meoh_from_ng = ng_in / ng_ratio

        # Limiting methanol production per hour
        meoh_prod = np.minimum.reduce([meoh_from_syn, meoh_from_atr, meoh_from_ng])
        meoh_cap = np.ones(n_timesteps) * inputs["plant_capacity_kgpy"] / n_timesteps
        meoh_prod = np.minimum.reduce([meoh_prod, meoh_cap])

        # Get co-product ratio0
        elec_ratio = inputs["elec_produce_ratio"]

        # Parse outputs
        outputs["meoh_syn_cat_consume"] = np.sum(meoh_prod) * syn_ratio
        outputs["meoh_atr_cat_consume"] = np.sum(meoh_prod) * atr_ratio
        outputs["ng_consume"] = meoh_prod * ng_ratio
        outputs["methanol_out"] = meoh_prod
        outputs["total_methanol_produced"] = np.sum(meoh_prod)
        outputs["electricity_out"] = meoh_prod * elec_ratio


@define(kw_only=True)
class SMRCostConfig(MethanolCostConfig):
    ng_lhv: float = field()
    meoh_syn_cat_price: float = field()
    meoh_atr_cat_price: float = field()
    ng_price: float = field()
    cost_year: int = field(converter=int)


class SMRMethanolPlantCostModel(MethanolCostBaseClass):
    """
    An OpenMDAO component for modeling the cost of a steam methane (SMR) reforming methanol plant.

    Inputs:
        ng_lhv: natural gas lower heating value in MJ/kg
        meoh_syn_cat_consume: annual consumption of methanol synthesis catalyst (ft**3/yr)
        meoh_atr_cat_consume: annual consumption of methanol ATR catalyst (ft**3/yr)
        ng_consume: hourly consumption of NG (kg/h)
        electricity_out: hourly electricity production (kW*h/h)
        meoh_syn_cat_price: price of methanol synthesis catalyst (USD/ft**3)
        meoh_atr_cat_price: price of methanol ATR catalyst (USD/ft**3)
        ng_price: price of NG (USD/MBtu)
    Outputs:
        meoh_syn_cat_cost: annual cost of methanol synthesis catalyst (USD/year)
        meoh_atr_cat_cost: annual cost of methanol ATR catalyst (USD/year)
        ng_cost: annual cost of NG (USD/year)
        elec_revenue: annual revenue from electricity sales (USD/year)
        cost_year: dollar year for output costs
    """

    def setup(self):
        self.config = SMRCostConfig.from_dict(
            merge_shared_inputs(self.options["tech_config"]["model_inputs"], "cost")
        )
        super().setup()
        n_timesteps = self.options["plant_config"]["plant"]["simulation"]["n_timesteps"]

        self.add_input("ng_lhv", units="MJ/kg", val=self.config.ng_lhv)
        self.add_input("meoh_syn_cat_consume", units="ft**3/yr")
        self.add_input("meoh_atr_cat_consume", units="ft**3/yr")
        self.add_input("ng_consume", shape=n_timesteps, units="kg/h")
        self.add_input("electricity_out", shape=n_timesteps, units="kW*h/h")
        self.add_input("meoh_syn_cat_price", units="USD/ft**3", val=self.config.meoh_syn_cat_price)
        self.add_input("meoh_atr_cat_price", units="USD/ft**3", val=self.config.meoh_atr_cat_price)
        self.add_input(
            "ng_price", units="USD/MBtu", val=self.config.ng_price
        )  # TODO: get OpenMDAO to recognize 'MMBtu'

        self.add_output("meoh_syn_cat_cost", units="USD/year")
        self.add_output("meoh_atr_cat_cost", units="USD/year")
        self.add_output("ng_cost", units="USD/year")
        self.add_output("elec_revenue", units="USD/year")

    def compute(self, inputs, outputs, discrete_inputs, discrete_outputs):
        toc_usd = inputs["plant_capacity_kgpy"] * inputs["toc_kg_y"]
        foc_usd_y = inputs["plant_capacity_kgpy"] * inputs["foc_kg_y2"]
        voc_usd_y = np.sum(inputs["methanol_out"]) * inputs["voc_kg"]

        ppa_price = self.options["plant_config"]["plant"]["ppa_price"]

        lhv_mj = inputs["ng_lhv"]
        lhv_mmbtu = convert_units(lhv_mj, "MJ", "MBtu")

        outputs["Fixed_OpEx"] = foc_usd_y
        outputs["Variable_OpEx"] = voc_usd_y
        meoh_cat = inputs["meoh_syn_cat_consume"] * inputs["meoh_syn_cat_price"]
        outputs["meoh_syn_cat_cost"] = meoh_cat
        atr_cat = inputs["meoh_atr_cat_consume"] * inputs["meoh_atr_cat_price"]
        outputs["meoh_atr_cat_cost"] = atr_cat
        ng_cost = np.sum(inputs["ng_consume"]) * lhv_mmbtu * inputs["ng_price"]
        outputs["ng_cost"] = ng_cost
        elec_rev = np.sum(inputs["electricity_out"]) * ppa_price
        outputs["elec_revenue"] = elec_rev

        outputs["CapEx"] = toc_usd
        outputs["OpEx"] = foc_usd_y + voc_usd_y + meoh_cat + atr_cat + ng_cost - elec_rev


class SMRMethanolPlantFinanceModel(MethanolFinanceBaseClass):
    """
    An OpenMDAO component for modeling the financing of a steam methane reforming (SMR) methanol
    plant.

    Inputs:
        meoh_syn_cat_cost: annual cost of synthesis catalyst in USD/year
        meoh_atr_cat_cost: annual cost of ATR catalyst in USD/year
        ng_cost: annual cost of natural gas in USD/year
        elec_revenue: annual revenue from electricity sales in USD/year
    Outputs:
        LCOM_meoh_atr_cat: levelized cost of methanol from ATR catalyst in USD/kg
        LCOM_meoh_syn_cat: levelized cost of methanol from synthesis catalyst in USD/kg
        LCOM_ng: levelized cost of methanol from natural gas in USD/kg
        LCOM_elec: levelized cost of methanol from electricity revenue in USD/kg
    """

    def setup(self):
        self.config = MethanolFinanceConfig.from_dict(
            merge_shared_inputs(self.options["tech_config"]["model_inputs"], "finance")
        )
        super().setup()

        self.add_input(
            "meoh_syn_cat_cost",
            units="USD/year",
            desc="Annual cost of synthesis catalyst in USD/year",
        )
        self.add_input(
            "meoh_atr_cat_cost",
            units="USD/year",
            desc="Annual cost of ATR catalyst in USD/year",
        )
        self.add_input(
            "ng_cost",
            units="USD/year",
            desc="Annual cost of natural gas in USD/year",
        )
        self.add_input(
            "elec_revenue",
            units="USD/year",
            desc="Annual revenue from electricity sales in USD/year",
        )
        self.add_output(
            "LCOM_meoh_atr_cat",
            units="USD/kg",
            desc="Levelized cost of methanol from ATR catalyst in USD/kg",
        )
        self.add_output(
            "LCOM_meoh_syn_cat",
            units="USD/kg",
            desc="Levelized cost of methanol from synthesis catalyst in USD/kg",
        )
        self.add_output(
            "LCOM_ng",
            units="USD/kg",
            desc="Levelized cost of methanol from natural gas in USD/kg",
        )
        self.add_output(
            "LCOM_elec",
            units="USD/kg",
            desc="Levelized cost of methanol from electricity revenue in USD/kg",
        )

    def compute(self, inputs, outputs):
        kgph = inputs["methanol_out"]

        lcom_capex = (
            inputs["CapEx"]
            * inputs["fixed_charge_rate"]
            * inputs["tasc_toc_multiplier"]
            / np.sum(kgph)
        )
        lcom_fopex = inputs["Fixed_OpEx"] / np.sum(kgph)
        lcom_vopex = inputs["Variable_OpEx"] / np.sum(kgph)
        outputs["LCOM_meoh_capex"] = lcom_capex
        outputs["LCOM_meoh_fopex"] = lcom_fopex

        meoh_syn_cat_cost = inputs["meoh_syn_cat_cost"]
        meoh_atr_cat_cost = inputs["meoh_atr_cat_cost"]
        lcom_meoh_syn_cat = meoh_syn_cat_cost / np.sum(kgph)
        lcom_meoh_atr_cat = meoh_atr_cat_cost / np.sum(kgph)
        outputs["LCOM_meoh_syn_cat"] = lcom_meoh_syn_cat
        outputs["LCOM_meoh_atr_cat"] = lcom_meoh_atr_cat

        # Correct LCOM_meoh_vopex which initially included catalyst
        lcom_vopex -= lcom_meoh_syn_cat + lcom_meoh_atr_cat
        outputs["LCOM_meoh_vopex"] = lcom_vopex

        ng_cost = inputs["ng_cost"]
        lcom_ng = ng_cost / np.sum(kgph)
        outputs["LCOM_ng"] = lcom_ng

        elec_rev = inputs["elec_revenue"]
        lcom_elec = -elec_rev / np.sum(kgph)
        outputs["LCOM_elec"] = lcom_elec

        lcom_meoh = lcom_capex + lcom_fopex + lcom_vopex + lcom_meoh_syn_cat + lcom_meoh_atr_cat
        outputs["LCOM_meoh"] = lcom_meoh

        lcom = lcom_meoh + lcom_ng + lcom_elec
        outputs["LCOM"] = lcom
