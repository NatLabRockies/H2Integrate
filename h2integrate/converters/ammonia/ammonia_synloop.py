import numpy as np
from attrs import field, define

from h2integrate.core.utilities import (
    CostModelBaseConfig,
    ResizeablePerformanceModelBaseConfig,
    merge_shared_inputs,
)
from h2integrate.core.validators import gt_zero, range_val
from h2integrate.tools.constants import H_MW, N_MW
from h2integrate.core.model_baseclasses import (
    CostModelBaseClass,
    ResizeablePerformanceModelBaseClass,
)
from h2integrate.tools.inflation.inflate import inflate_cpi, inflate_cepci


@define(kw_only=True)
class AmmoniaSynLoopPerformanceConfig(ResizeablePerformanceModelBaseConfig):
    """
    Configuration inputs for the ammonia synthesis loop performance model.
    *Starred inputs are from tech_config/ammonia/model_inputs/shared_parameters
    The other inputs are from tech_config/ammonia/model_inputs/performance_parameters

    Attributes:
        size_mode (str): The mode in which the component is sized. Options:
            - "normal": The component size is taken from the tech_config.
            - "resize_by_max_feedstock": Resize based on maximum feedstock availability.
            - "resize_by_max_commodity": Resize based on maximum commodity demand.
        flow_used_for_sizing (str | None): The feedstock/commodity flow used for sizing.
            Required when size_mode is not "normal".
        max_feedstock_ratio (float): Ratio for sizing in "resize_by_max_feedstock" mode.
            Defaults to 1.0.
        max_commodity_ratio (float): Ratio for sizing in "resize_by_max_commodity" mode.
            Defaults to 1.0.
        *production_capacity (float): The total production capacity of the ammonia synthesis loop
            (in kg ammonia per hour)
        *catalyst_consumption_rate (float): The mass ratio of catalyst consumed by the reactor over
            its lifetime to ammonia produced (in kg catalyst / kg ammonia)
        *catalyst_replacement_interval (float): The interval in years when the catalyst is replaced
        capacity_factor (float): The ratio of ammonia produced over a year to maximum production
            capacity (as a decimal)
        energy_demand (float): The total energy demand of the ammonia synthesis loop
            (in kWh electricity per kg ammonia).
        heat_output (float): The total heat output of the ammonia synthesis loop
            (in kWh thermal per kg ammonia)
        feed_gas_t (float): The synloop makeup feed gas temperature (in Kelvin)
        feed_gas_p (float): The synloop makeup feed gas pressure (in bar)
        feed_gas_x_n2 (float): The synloop makeup feed gas molar fraction of nitrogen (as a decimal)
        feed_gas_x_h2 (float): The synloop makeup feed gas molar fraction of hydrogen (as a decimal)
        feed_gas_mass_ratio (float): The synloop makeup feed gas mass ratio to ammonia produced (as
            a decimal)
        purge_gas_t (float): The synloop purge gas temperature (in Kelvin)
        purge_gas_p (float): The synloop purge gas pressure (in bar)
        purge_gas_x_n2 (float): The synloop purge gas molar fraction of nitrogen (as a decimal)
        purge_gas_x_h2 (float): The synloop purge gas molar fraction of hydrogen (as a decimal)
        purge_gas_x_ar (float): The synloop purge gas molar fraction of argon (as a decimal)
        purge_gas_x_nh3 (float): The synloop purge gas molar fraction of hydrogen (as a decimal)
        purge_gas_mass_ratio (float): The synloop purge gas mass ratio to ammonia produced (as a
            decimal)
    """

    production_capacity: float = field(validator=gt_zero)
    catalyst_consumption_rate: float = field(validator=gt_zero)
    catalyst_replacement_interval: float = field(validator=gt_zero)
    capacity_factor: float = field(validator=range_val(0, 1))
    energy_demand: float = field(validator=gt_zero)
    heat_output: float = field(validator=gt_zero)
    feed_gas_t: float = field(validator=gt_zero)
    feed_gas_p: float = field(validator=gt_zero)
    feed_gas_x_n2: float = field(validator=range_val(0, 1))
    feed_gas_x_h2: float = field(validator=range_val(0, 1))
    feed_gas_mass_ratio: float = field(validator=gt_zero)
    purge_gas_t: float = field(validator=gt_zero)
    purge_gas_p: float = field(validator=gt_zero)
    purge_gas_x_n2: float = field(validator=range_val(0, 1))
    purge_gas_x_h2: float = field(validator=range_val(0, 1))
    purge_gas_x_ar: float = field(validator=range_val(0, 1))
    purge_gas_x_nh3: float = field(validator=range_val(0, 1))
    purge_gas_mass_ratio: float = field(validator=gt_zero)


class AmmoniaSynLoopPerformanceModel(ResizeablePerformanceModelBaseClass):
    """
    OpenMDAO component modeling the performance of an ammonia synthesis loop.

    This component calculates the hourly ammonia production based on the available
    hydrogen, nitrogen, and electricity inputs, considering the stoichiometric and
    energetic requirements of the synthesis process. It also computes the unused
    hydrogen, nitrogen, and electricity (as heat), as well as the total ammonia
    produced over the modeled period.

    Attributes
    ----------
    config : AmmoniaSynLoopPerformanceConfig
        Configuration object containing model parameters such as energy demand,
        nitrogen conversion rate, and hydrogen conversion rate.

    Inputs
    ------
    hydrogen_in : array [kg/h]
        Hourly hydrogen feed to the synthesis loop.
    nitrogen_in : array [kg/h]
        Hourly nitrogen feed to the synthesis loop.
    electricity_in : array [MW]
        Hourly electricity supplied to the synthesis loop.

    Outputs
    -------
    ammonia_out : array [kg/h]
        Hourly ammonia produced by the synthesis loop.
    nitrogen_out : array [kg/h]
        Hourly unused nitrogen after synthesis loop.
    hydrogen_out : array [kg/h]
        Hourly unused hydrogen after synthesis loop.
    electricity_out : array [MW]
        Hourly unused electricity after synthesis loop.
    heat_out : array [MW]
        Hourly heat generated by synthesis loop.
    catalyst_mass: float [kg]
        Total catalyst mass needed in synthesis loop.
    total_ammonia_produced : float [kg/year]
        Total ammonia produced over the modeled period.
    total_hydrogen_consumed : float [kg/year]
        Total hydrogen consumed over the modeled period.
    total_nitrogen_consumed : float [kg/year]
        Total nitrogen consumed over the modeled period.
    total_electricity_consumed : float [kWh/year]
        Total electricity consumed over the modeled period.
    limiting_output: array of ints [-]
        0: nitrogen-limited, 1: hydrogen-limited, 2: electricity-limited 3: capacity-limited
    max_hydrogen_capacity : float [kg/h]
        The maximum rate of hydrogen consumption.
    ammonia_capacity_factor : float [-]
        The ratio of ammonia produced to the maximum production capacity.

    Notes
    -----
    The ammonia production is limited by the most constraining input (hydrogen,
    nitrogen, or electricity) at each timestep. The component assumes perfect
    conversion efficiency up to the limiting reagent or energy input.
    """

    def setup(self):
        n_timesteps = self.options["plant_config"]["plant"]["simulation"]["n_timesteps"]
        self.config = AmmoniaSynLoopPerformanceConfig.from_dict(
            merge_shared_inputs(self.options["tech_config"]["model_inputs"], "performance")
        )
        super().setup()

        self.add_input("hydrogen_in", val=0.0, shape=n_timesteps, units="kg/h")
        self.add_input("nitrogen_in", val=0.0, shape=n_timesteps, units="kg/h")
        self.add_input("electricity_in", val=0.0, shape=n_timesteps, units="MW")

        self.add_output("ammonia_out", val=0.0, shape=n_timesteps, units="kg/h")
        self.add_output("nitrogen_out", val=0.0, shape=n_timesteps, units="kg/h")
        self.add_output("hydrogen_out", val=0.0, shape=n_timesteps, units="kg/h")
        self.add_output("electricity_out", val=0.0, shape=n_timesteps, units="MW")
        self.add_output("heat_out", val=0.0, shape=n_timesteps, units="kW*h/kg")
        self.add_output("catalyst_mass", val=0.0, units="kg")
        self.add_output("total_ammonia_produced", val=0.0, units="kg/year")
        self.add_output("total_hydrogen_consumed", val=0.0, units="kg/year")
        self.add_output("total_nitrogen_consumed", val=0.0, units="kg/year")
        self.add_output("total_electricity_consumed", val=0.0, units="kW*h/year")
        self.add_output(
            "limiting_input", val=0, shape_by_conn=True, copy_shape="hydrogen_in", units=None
        )
        self.add_output("max_hydrogen_capacity", val=1000.0, units="kg/h")
        self.add_output("ammonia_capacity_factor", val=0.0, units="unitless")

    def compute(self, inputs, outputs, discrete_inputs, discrete_outputs):
        # Get config values
        nh3_cap = self.config.production_capacity  # kg NH3 per hour
        cat_consume = self.config.catalyst_consumption_rate  # kg Cat per kg NH3
        cat_replace = self.config.catalyst_replacement_interval  # years
        energy_demand = self.config.energy_demand  # kWh electric per kg NH3
        heat_output = self.config.heat_output  # kWh thermal per kg NH3
        x_h2_feed = self.config.feed_gas_x_h2  # mol frac
        x_n2_feed = self.config.feed_gas_x_n2  # mol frac
        ratio_feed = self.config.feed_gas_mass_ratio  # kg/kg NH3
        x_h2_purge = self.config.purge_gas_x_h2  # mol frac
        x_n2_purge = self.config.purge_gas_x_n2  # mol frac
        ratio_purge = self.config.purge_gas_mass_ratio  # kg/kg NH3

        # Resize if needed
        size_mode = discrete_inputs["size_mode"]
        if size_mode == "normal":
            pass
        elif size_mode == "resize_by_max_feedstock":
            if discrete_inputs["flow_used_for_sizing"] == "hydrogen":
                max_cap_ratio = inputs["max_feedstock_ratio"]
                feed_mw = x_h2_feed * H_MW * 2 + x_n2_feed * N_MW * 2  # g / mol
                w_h2_feed = x_h2_feed * H_MW * 2 / feed_mw  # kg H2 / kg feed gas
                nh3_cap = np.max(inputs["hydrogen_in"]) / (ratio_feed * w_h2_feed) * max_cap_ratio
            else:
                flow = discrete_inputs["flow_used_for_sizing"]
                NotImplementedError(
                    f"The sizing mode '{size_mode}' is not implemented for the '{flow}' flow"
                )
        else:
            NotImplementedError(
                f"The sizing mode '{size_mode}' is not implemented for this converter"
            )

        # Inputs (arrays of length n_timesteps)
        h2_in = inputs["hydrogen_in"]
        n2_in = inputs["nitrogen_in"]
        if np.max(n2_in) == 0:  # Temporary until ASU is added
            n2_in = h2_in / H_MW * 3 * N_MW  # TODO: Replace with connected input
        elec_in = inputs["electricity_in"]  # Temporary until HOPP is connected
        if np.max(elec_in) == 0:
            elec_in = (
                np.ones(
                    len(h2_in),
                )
                * nh3_cap
                * energy_demand
            )  # TODO: replace with connected input

        # Calculate max NH3 production for each input
        feed_mw = x_h2_feed * H_MW * 2 + x_n2_feed * N_MW * 2  # g / mol

        w_h2_feed = x_h2_feed * H_MW * 2 / feed_mw  # kg H2 / kg feed gas
        h2_rate = w_h2_feed * ratio_feed  # kg H2 / kg NH3
        nh3_from_h2 = h2_in / h2_rate  # kg nh3 / hr

        w_n2_feed = x_n2_feed * N_MW * 2 / feed_mw  # kg N2 / kg feed gas
        n2_rate = w_n2_feed * ratio_feed  # kg N2 / kg NH3
        nh3_from_n2 = n2_in / n2_rate  # kg nh3 / hr

        nh3_from_elec = elec_in / energy_demand * 1000  # kg nh3 / hr, converting MW elec_in to kW

        # Limiting NH3 production per hour by each input
        nh3_prod = np.minimum.reduce([nh3_from_n2, nh3_from_h2, nh3_from_elec])
        limiters = np.argmin([nh3_from_n2, nh3_from_h2, nh3_from_elec], axis=0)

        # Limiting NH3 production per hour by capacity
        nh3_prod = np.minimum.reduce([nh3_prod, np.full(len(nh3_prod), nh3_cap)])
        cap_lim = 1 - np.argmax([nh3_prod, list(np.full(len(nh3_prod), nh3_cap))], axis=0)

        # Determine what the limiting factor is for each hour
        limiters = np.maximum.reduce([cap_lim * 3, limiters])
        outputs["limiting_input"] = limiters

        # Calculate unused inputs
        used_h2 = nh3_prod * h2_rate
        used_n2 = nh3_prod * n2_rate
        used_elec = nh3_prod * energy_demand

        # Calculate output in purge gas
        purge_mw = x_h2_purge * H_MW * 2 + x_n2_purge * N_MW * 2  # g / mol

        w_h2_purge = x_h2_purge * H_MW * 2 / purge_mw  # kg H2 / kg purge gas
        h2_purge = w_h2_purge * ratio_purge * nh3_prod  # kg H2 / hr

        w_n2_purge = x_n2_purge * H_MW * 2 / purge_mw  # kg N2 / kg purge gas
        n2_purge = w_n2_purge * ratio_purge * nh3_prod  # kg N2 / hr

        # Calculate catalyst mass
        cat_rate = cat_consume * nh3_prod  # kg Cat / hr
        cat_mass = np.sum(cat_rate) * cat_replace  # kg

        outputs["ammonia_out"] = nh3_prod
        outputs["hydrogen_out"] = h2_in - used_h2 + h2_purge
        outputs["nitrogen_out"] = n2_in - used_n2 + n2_purge
        outputs["electricity_out"] = elec_in - used_elec
        outputs["heat_out"] = nh3_prod * heat_output
        outputs["catalyst_mass"] = cat_mass
        outputs["total_ammonia_produced"] = max(nh3_prod.sum(), 1e-6)
        outputs["total_hydrogen_consumed"] = h2_in.sum()
        outputs["total_nitrogen_consumed"] = n2_in.sum()
        outputs["total_electricity_consumed"] = elec_in.sum()

        h2_cap = nh3_cap * h2_rate  # kg H2 per hour
        outputs["max_hydrogen_capacity"] = h2_cap

        # Calculate capacity factor
        outputs["ammonia_capacity_factor"] = np.mean(nh3_prod) / nh3_cap


@define(kw_only=True)
class AmmoniaSynLoopCostConfig(CostModelBaseConfig):
    """
    Configuration inputs for the ammonia synthesis loop cost model.
    *Starred inputs are from tech_config/ammonia/model_inputs/shared_parameters
    The other inputs are from tech_config/ammonia/model_inputs/cost_parameters

    Attributes:
        ---Scaling---
        *production_capacity (float): The total production capacity of the ammonia synthesis loop
            (in kg ammonia per hour)
        baseline_capacity (float): The capacity of the baseline ammonia plant for cost simulations
            (in kg ammonia per hour)
        base_cost_year (int): Year in which base USD costs are derived - to be adjusted using
            CEPCI for capex and CPI for opex.
        capex_scaling_exponent (float): Power applied to ratio of capacities when calculating capex
            from a baseline value at a different capacity.
        labor_scaling_exponent (float): Power applied to ratio of capacities when calculating labor
            cost from a baseline value at a different capacity.

        ---CAPEX---
        asu_capex_base (float): Baseline capital expenditure for the air separation unit [$].
        synloop_capex_base (float): Baseline capital expenditure for the synthesis loop [$].
        heat_capex_base (float) : Baseline capital expenditure for the boiler and steam turbine [$].
        cool_capex_base (float) : Baseline capital expenditure for the cooling tower [$].
        other_eqpt_capex_base (float): Other baseline direct capital expenditures [$].
        land_capex_base (float): Baseline capital expenditure for land to construct the plant [$].
        deprec_noneq_capex_rate (float): Fract of equipment capex for depreciable nonequipment [$].

        ---OPEX---
        labor_rate_base (float) : Baseline all-in labor rate [$/hr].
        num_workers_base (float) : Baseline number of workers for the entire ammonia plant [-].
        hours_yr (float) : Work hours per year per worker [hr/year].
        gen_admin (float) : General and administrative expenses as a fraction of labor [-].
        prop_tax_ins (float) : Property tax and insurance as a fraction of total capex [-].
        maint_rep (float) : Maintenance and repair cost as a fraction of equipment capex [-].
        oxygen_byproduct_rate (float): Rate at which oxygen byproduct is generated [kg O2/kg NH3]
        water_consumption_rate (float): Ratio of cooling water consumed by the reactor [gal/kg NH3]
        *catalyst_consumption_rate (float): The mass ratio of catalyst consumed by the reactor over
            its lifetime to ammonia produced
        *catalyst_replacement_interval (float): The interval in years when the catalyst is replaced
        rebuild_cost_base (float): Cost to rebuild baseline reactor for catalyst replacement [USD].

        ---Feedstock Costs---
        cooling_water_cost_base (float): Cost of cooling water [$/gal H2O]
        catalyst_cost_base (float): Cost of iron-based catalyst [$/kg cat]
        oxygen_price_base (float): Sales price of oxygen co-product [$/kg O2]
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

    def setup(self):
        target_cost_year = self.options["plant_config"]["finance_parameters"][
            "cost_adjustment_parameters"
        ]["target_dollar_year"]
        self.options["tech_config"]["model_inputs"]["cost_parameters"].update(
            {"cost_year": target_cost_year}
        )

        self.config = AmmoniaSynLoopCostConfig.from_dict(
            merge_shared_inputs(self.options["tech_config"]["model_inputs"], "cost")
        )
        super().setup()

        self.add_input("total_ammonia_produced", val=0.0, units="kg/year")
        self.add_input("total_hydrogen_consumed", val=0.0, units="kg/year")
        self.add_input("total_nitrogen_consumed", val=0.0, units="kg/year")
        self.add_input("total_electricity_consumed", val=0.0, units="kW*h/year")

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
        capacity = self.config.production_capacity  # kg NH3 / hr
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
        nh3_prod = inputs["total_ammonia_produced"]  # kg NH3 /year

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
