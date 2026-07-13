from attrs import field, define

from h2integrate.core.utilities import merge_shared_inputs
from h2integrate.core.model_baseclasses import CostModelBaseClass, CostModelBaseConfig
from h2integrate.tools.inflation.inflate import inflate_cpi, inflate_cepci


@define(kw_only=True)
class AmmoniaSynLoopCostConfig(CostModelBaseConfig):
    """
    Configuration inputs for the ammonia synthesis loop cost model.

    Attributes marked with a leading asterisk (``*``) are read from
    ``tech_config/ammonia/model_inputs/shared_parameters``; the other inputs come from
    ``tech_config/ammonia/model_inputs/cost_parameters``.

    Attributes:
        production_capacity (float): (\\*) The total production capacity of the ammonia synthesis
            loop (in kg ammonia per hour). *[Scaling]*
        baseline_capacity (float): The capacity of the baseline ammonia plant for cost simulations
            (in kg ammonia per hour). *[Scaling]*
        base_cost_year (int): Year in which base USD costs are derived - to be adjusted using
            CEPCI for capex and CPI for opex. *[Scaling]*
        capex_scaling_exponent (float): Power applied to ratio of capacities when calculating capex
            from a baseline value at a different capacity. *[Scaling]*
        labor_scaling_exponent (float): Power applied to ratio of capacities when calculating labor
            cost from a baseline value at a different capacity. *[Scaling]*
        asu_capex_base (float): Baseline capital expenditure for the air separation unit [$].
            *[CAPEX]*
        synloop_capex_base (float): Baseline capital expenditure for the synthesis loop [$].
            *[CAPEX]*
        heat_capex_base (float) : Baseline capital expenditure for the boiler and steam
            turbine [$]. *[CAPEX]*
        cool_capex_base (float) : Baseline capital expenditure for the cooling tower [$].
            *[CAPEX]*
        other_eqpt_capex_base (float): Other baseline direct capital expenditures [$]. *[CAPEX]*
        land_capex_base (float): Baseline capital expenditure for land to construct the plant [$].
            *[CAPEX]*
        deprec_noneq_capex_rate (float): Fract of equipment capex for depreciable nonequipment [$].
            *[CAPEX]*
        labor_rate_base (float) : Baseline all-in labor rate [$/hr]. *[OPEX]*
        num_workers_base (float) : Baseline number of workers for the entire ammonia plant [-].
            *[OPEX]*
        hours_yr (float) : Work hours per year per worker [hr/year]. *[OPEX]*
        gen_admin (float) : General and administrative expenses as a fraction of labor [-].
            *[OPEX]*
        prop_tax_ins (float) : Property tax and insurance as a fraction of total capex [-].
            *[OPEX]*
        maint_rep (float) : Maintenance and repair cost as a fraction of equipment capex [-].
            *[OPEX]*
        oxygen_byproduct_rate (float): Rate at which oxygen byproduct is generated
            [kg O2/kg NH3]. *[OPEX]*
        water_consumption_rate (float): Ratio of cooling water consumed by the reactor
            [gal/kg NH3]. *[OPEX]*
        catalyst_consumption_rate (float): (\\*) The mass ratio of catalyst consumed by the reactor
            over its lifetime to ammonia produced. *[OPEX]*
        catalyst_replacement_interval (float): (\\*) The interval in years when the catalyst is
            replaced. *[OPEX]*
        rebuild_cost_base (float): Cost to rebuild baseline reactor for catalyst
            replacement [USD]. *[OPEX]*
        cooling_water_cost_base (float): Cost of cooling water [$/gal H2O]. *[Feedstock Costs]*
        catalyst_cost_base (float): Cost of iron-based catalyst [$/kg cat]. *[Feedstock Costs]*
        oxygen_price_base (float): Sales price of oxygen co-product [$/kg O2]. *[Feedstock Costs]*
    """

    production_capacity: float = field()
    baseline_capacity: float = field()
    base_cost_year: int = field(converter=int)
    capex_scaling_exponent: float = field()
    labor_scaling_exponent: float = field()
    asu_capex_base: float = field()
    synloop_capex_base: float = field()
    heat_capex_base: float = field()
    cool_capex_base: float = field()
    other_eqpt_capex_base: float = field()
    land_capex_base: float = field()
    deprec_noneq_capex_rate: float = field()
    labor_rate_base: float = field()
    num_workers_base: float = field()
    hours_yr: float = field()
    gen_admin: float = field()
    prop_tax_ins: float = field()
    maint_rep: float = field()
    oxygen_byproduct_rate: float = field()
    water_consumption_rate: float = field()
    catalyst_consumption_rate: float = field()
    catalyst_replacement_interval: float = field()
    rebuild_cost_base: float = field()
    cooling_water_cost_base: float = field()
    catalyst_cost_base: float = field()
    oxygen_price_base: float = field()


class AmmoniaSynLoopCostModel(CostModelBaseClass):
    """
    OpenMDAO component modeling the cost of an ammonia synthesis loop.

    This component outputs the capital expenditure (CapEx) and annual operating
    expenditure (OpEx) associated with the synthesis loop, based on provided
    configuration values.

    Attributes
    ----------
    config : AmmoniaSynLoopCostConfig
        Configuration object containing CapEx and annual rebuild cost.

    Inputs
    -------
    total_ammonia_produced : float [kg/year]
        Total ammonia produced over the modeled period.
    total_hydrogen_consumed : float [kg/year]
        Total hydrogen consumed over the modeled period.
    total_nitrogen_consumed : float [kg/year]
        Total nitrogen consumed over the modeled period.
    total_electricity_consumed : float [kg/year]
        Total electricity consumed over the modeled period.

    Outputs
    -------
    CapEx : float [$]
        Capital expenditure for the synthesis loop.
    OpEx : float [$ per year]
        Annual operating expenditure (catalyst replacement/rebuild).
    capex_asu : float [$]
        Capital cost for air separation unit
    capex_synloop : float [$]
        Capital cost for NH3 synthesis loop
    capex_boiler : float [$]
        Capital cost for boilers
    capex_cooling_tower : float [$]
        Capital cost for cooling towers
    capex_direct : float [$]
        Direct capital costs
    capex_depreciable_nonequipment : float [$]
        Depreciable non-equipment capital costs",
    land_cost : float [$]
        Cost of land
    labor_cost : float [$]
        Annual labor cost")
    general_administration_cost : float [$]
        Annual general and administrative cost
    property_tax_insurance : float [$]
        Annual property tax and insurance cost",
    maintenance_cost : float [$]
        Annual maintenance cost
    """

    _time_step_bounds = (
        3600,
        3600,
    )  # (min, max) time step lengths (in seconds) compatible with this model

    def setup(self):
        target_cost_year = self.options["plant_config"]["finance_parameters"][
            "cost_adjustment_parameters"
        ]["target_dollar_year"]
        self.options["tech_config"]["model_inputs"]["cost_parameters"].update(
            {"cost_year": target_cost_year}
        )

        self.config = AmmoniaSynLoopCostConfig.from_dict(
            merge_shared_inputs(self.options["tech_config"]["model_inputs"], "cost"),
            additional_cls_name=self.__class__.__name__,
        )
        super().setup()

        self.add_input("annual_ammonia_produced", val=0.0, shape=self.plant_life, units="kg/year")
        self.add_input(
            "rated_ammonia_production", val=self.config.production_capacity, units="kg/h"
        )

        self.add_output(
            "capex_asu", val=0.0, units="USD", desc="Capital cost for air separation unit"
        )
        self.add_output(
            "capex_synloop", val=0.0, units="USD", desc="Capital cost for NH3 synthesis loop"
        )
        self.add_output("capex_boiler", val=0.0, units="USD", desc="Capital cost for boilers")
        self.add_output(
            "capex_cooling_tower", val=0.0, units="USD", desc="Capital cost for cooling towers"
        )
        self.add_output("capex_direct", val=0.0, units="USD", desc="Direct capital costs")
        self.add_output(
            "capex_depreciable_nonequipment",
            val=0.0,
            units="USD",
            desc="Depreciable non-equipment capital costs",
        )
        self.add_output("land_cost", val=0.0, units="USD", desc="Cost of land")

        self.add_output("labor_cost", val=0.0, units="USD/year", desc="Annual labor cost")
        self.add_output(
            "general_administration_cost",
            val=0.0,
            units="USD/year",
            desc="Annual general and administrative cost",
        )
        self.add_output(
            "property_tax_insurance",
            val=0.0,
            units="USD/year",
            desc="Annual property tax and insurance cost",
        )
        self.add_output(
            "maintenance_cost", val=0.0, units="USD/year", desc="Annual maintenance cost"
        )

    def compute(self, inputs, outputs, discrete_inputs, discrete_outputs):
        ##---Scaling Ratios---

        # Get config values
        capacity = inputs["rated_ammonia_production"]  # kg NH3 / hr
        base_cap = self.config.baseline_capacity  # kg NH3 / hr
        year = self.options["plant_config"]["finance_parameters"]["cost_adjustment_parameters"][
            "target_dollar_year"
        ]  # dollar year
        base_year = self.config.base_cost_year  # dollar year
        capex_exp = self.config.capex_scaling_exponent  # unitless
        labor_exp = self.config.labor_scaling_exponent  # unitless

        # Get ratios
        cap_ratio = capacity / base_cap
        cepci_ratio = inflate_cepci(1, base_year, year)
        cpi_ratio = inflate_cpi(1, base_year, year)
        capex_ratio = cap_ratio**capex_exp
        labor_ratio = cap_ratio**labor_exp

        ##---CAPEX---

        # Get config values
        asu_capex_base = self.config.asu_capex_base  # USD (base year)
        synloop_capex_base = self.config.synloop_capex_base  # USD (base year)
        heat_capex_base = self.config.heat_capex_base  # USD (base year)
        cool_capex_base = self.config.cool_capex_base  # USD (base year)
        other_eqpt_capex_base = self.config.other_eqpt_capex_base  # USD (base year)
        land_capex_base = self.config.land_capex_base  # USD (base year)
        deprec_noneq_capex_rate = self.config.deprec_noneq_capex_rate  # unitless

        # Apply scaling
        asu_capex = asu_capex_base * capex_ratio * cepci_ratio
        synloop_capex = synloop_capex_base * capex_ratio * cepci_ratio
        heat_capex = heat_capex_base * capex_ratio * cepci_ratio
        cool_capex = cool_capex_base * capex_ratio * cepci_ratio
        other_eqpt_capex = other_eqpt_capex_base * capex_ratio * cepci_ratio
        land_capex = land_capex_base * cap_ratio * cpi_ratio  # Using CPI not CEPCI for land

        # Calculate capex - all in USD
        eqpt_capex = asu_capex + synloop_capex + heat_capex + cool_capex + other_eqpt_capex
        deprec_noneq_capex = land_capex + eqpt_capex * deprec_noneq_capex_rate
        total_capex = eqpt_capex + deprec_noneq_capex

        ##---Fixed OPEX---

        # Get config values
        labor_rate_base = self.config.labor_rate_base  # USD / hr (base year)
        num_workers_base = self.config.num_workers_base  # Workers / plant (base capacity)
        hours_yr = self.config.hours_yr  # hours / year
        gen_admin = self.config.gen_admin  # fraction of labor
        prop_tax_ins = self.config.prop_tax_ins  # fraction of total capex
        maint_rep = self.config.maint_rep  # fraction of equipment capex

        # Apply scaling
        labor_rate = labor_rate_base * cpi_ratio
        num_workers = num_workers_base * labor_ratio

        # Calculate fixed opex - all in USD/year
        labor_opex = labor_rate * num_workers * hours_yr
        gen_admin_opex = labor_opex * gen_admin
        prop_tax_ins_opex = prop_tax_ins * total_capex
        maint_rep_opex = maint_rep * eqpt_capex
        fixed_opex = labor_opex = gen_admin_opex + prop_tax_ins_opex + maint_rep_opex

        ##---Variable OPEX---

        # Get config values
        o2_rate = self.config.oxygen_byproduct_rate  # kg O2 / kg NH3
        h2o_rate = self.config.water_consumption_rate  # kg O2 / kg NH3
        cat_rate = self.config.catalyst_consumption_rate  # kg O2 / kg NH3
        cat_int = self.config.catalyst_replacement_interval  # kg O2 / kg NH3
        rebuild_cost_base = self.config.rebuild_cost_base  # USD
        h2o_cost_base = self.config.cooling_water_cost_base  # USD / kg H2O
        cat_cost_base = self.config.catalyst_cost_base  # USD / kg cat
        o2_price_base = self.config.oxygen_price_base  # USD / kg O2

        # Get total production/consumption
        nh3_prod = inputs["annual_ammonia_produced"].mean()  # kg NH3 /year

        # Apply scaling
        rebuild_cost = rebuild_cost_base * capex_ratio * cepci_ratio
        h2o_cost = h2o_cost_base * cpi_ratio
        cat_cost = cat_cost_base * cpi_ratio
        o2_price = o2_price_base * cpi_ratio

        # Calculate variable opex - all in USD/year
        rebuild_opex = rebuild_cost * cat_int
        cat_opex = cat_cost * cat_rate * nh3_prod
        h2o_opex = h2o_cost * h2o_rate * nh3_prod
        o2_sales = o2_price * o2_rate * nh3_prod
        variable_opex = rebuild_opex + cat_opex + h2o_opex - o2_sales

        ##---Final Outputs---
        outputs["CapEx"] = total_capex
        outputs["OpEx"] = fixed_opex + variable_opex

        outputs["capex_asu"] = asu_capex
        outputs["capex_synloop"] = synloop_capex
        outputs["capex_boiler"] = heat_capex
        outputs["capex_cooling_tower"] = cool_capex
        outputs["capex_direct"] = eqpt_capex
        outputs["capex_depreciable_nonequipment"] = total_capex - eqpt_capex
        outputs["land_cost"] = land_capex

        outputs["labor_cost"] = labor_opex
        outputs["general_administration_cost"] = gen_admin_opex
        outputs["property_tax_insurance"] = prop_tax_ins_opex
        outputs["maintenance_cost"] = maint_rep_opex
