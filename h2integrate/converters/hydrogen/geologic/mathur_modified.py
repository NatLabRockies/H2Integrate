import copy

from attrs import field, define

from h2integrate.core.utilities import merge_shared_inputs
from h2integrate.core.validators import range_val
from h2integrate.tools.inflation.inflate import inflate_cpi, inflate_cepci
from h2integrate.converters.hydrogen.geologic.h2_well_subsurface_baseclass import (
    GeoH2SubsurfaceCostConfig,
    GeoH2SubsurfaceCostBaseClass,
)


@define(kw_only=True)
class GeoH2SubsurfaceCostConfig(GeoH2SubsurfaceCostConfig):
    """Configuration for subsurface well cost parameters in geologic hydrogen models.

    This configuration defines cost parameters specific to subsurface well
    components used in geologic hydrogen systems. It supports either the use of
    a built-in drilling cost curve or a manually specified constant drilling cost.

    Attributes:
        test_drill_cost (float):
            Capital cost (CAPEX) of conducting a test drill for a potential GeoH2 well,
            in USD.

        permit_fees (float):
            Capital cost (CAPEX) associated with obtaining drilling permits, in USD.

        acreage (float):
            Land area required for drilling operations, in acres.

        rights_cost (float):
            Capital cost (CAPEX) to acquire drilling rights, in USD per acre.

        success_chance (float):
            Probability of success at a given test drilling site, expressed as a fraction.

        fixed_opex (float):
            Fixed annual operating expense (OPEX) that does not scale with hydrogen
            production, in USD/year.

        variable_opex (float):
            Variable operating expense (OPEX) that scales with hydrogen production,
            in USD/kg.

        contracting_pct (float):
            Contracting costs as a percentage of bare capital cost.

        contingency_pct (float):
            Contingency allowance as a percentage of bare capital cost.

        preprod_time (float):
            Duration of the preproduction period during which fixed OPEX is charged,
            in months.

        as_spent_ratio (float):
            Ratio of as-spent costs to overnight (instantaneous) costs, dimensionless.

        cost_year (int): Mathur model uses 2022 as the base year for the cost model.
            The cost year is updated based on `target_dollar_year` in the plant
            config to adjust costs based on CPI/CEPCI within the Mathur model. This value
            cannot be user added under `cost_parameters`.

        use_cost_curve (bool): Flag indicating whether to use the built-in drilling
            cost curve. If `True`, the drilling cost is computed from the cost curve.
            If `False`, a constant drilling cost must be provided.

        constant_drill_cost (float | None): Fixed drilling cost to use when
            `use_cost_curve` is `False` [USD]. Defaults to `None`.

    Raises:
        ValueError: If `use_cost_curve` is `False` and `constant_drill_cost` is not provided.
    """

    test_drill_cost: float = field()
    permit_fees: float = field()
    acreage: float = field()
    rights_cost: float = field()
    success_chance: float = field()
    fixed_opex: float = field()
    variable_opex: float = field()
    contracting_pct: float = field()
    contingency_pct: float = field()
    preprod_time: float = field()
    as_spent_ratio: float = field()
    cost_year: int = field(converter=int, validator=range_val(2010, 2024))
    use_cost_curve: bool = field()
    constant_drill_cost: float | None = field(default=None)

    def __attrs_post_init__(self):
        # if use_cost_curve is False, constant_drill_cost must be provided
        if not self.use_cost_curve and self.constant_drill_cost is None:
            raise ValueError(
                "If 'use_cost_curve' is False, 'constant_drill_cost' must be provided."
            )
        # check if cost curve is true and constant_drill_cost is provided
        if self.use_cost_curve and self.constant_drill_cost is not None:
            raise ValueError(
                "If 'use_cost_curve' is True, 'constant_drill_cost' should not be provided."
            )


class GeoH2SubsurfaceCostModel(GeoH2SubsurfaceCostBaseClass):
    """An OpenMDAO component for modeling subsurface well costs in geologic
        hydrogen plants.

    This component estimates the capital and operating costs for subsurface well
    systems in geologic hydrogen production. Cost correlations are based on:

        - Mathur et al. (Stanford): https://doi.org/10.31223/X5599G
        - NETL Quality Guidelines: https://doi.org/10.2172/1567736

    Attributes:
        config (GeoH2SubsurfaceCostConfig): Configuration object containing cost parameters.

    Inputs:
        target_dollar_year (int): The dollar year in which costs are modeled.
        borehole_depth (float): Depth of the wellbore [m].
        test_drill_cost (float): Capital cost of a test drill [USD].
        permit_fees (float): Cost of drilling permits [USD].
        acreage (float): Land area required for drilling [acre].
        rights_cost (float): Cost of obtaining drilling rights [USD/acre].
        success_chance (float): Probability of success for a test drill [%].
        fixed_opex (float): Fixed annual operating cost [USD/year].
        variable_opex (float): Variable operating cost per kg of H₂ produced [USD/kg].
        contracting_pct (float): Contracting costs as a percentage of bare capital cost [%].
        contingency_pct (float): Contingency costs as a percentage of bare capital cost [%].
        preprod_time (float): Duration of preproduction phase [months].
        as_spent_ratio (float): Ratio of as-spent costs to overnight costs.
        wellhead_gas_out (ndarray): Wellhead gas production rate over time [kg/h].

    Outputs:
        bare_capital_cost (float): Unadjusted capital cost before multipliers [USD].
        CapEx (float): Total as-spent capital expenditure [USD].
        OpEx (float): Total annual operating expenditure [USD/year].
        Fixed_OpEx (float): Annual fixed operating expenditure [USD/year].
        Variable_OpEx (float): Variable operating expenditure per kg of H₂ [USD/kg].

    Raises:
        ValueError: If cost curve settings in the configuration are inconsistent.
    """

    def setup(self):
        # merge inputs from performance parameters and cost parameters
        config_dict = merge_shared_inputs(
            copy.deepcopy(self.options["tech_config"]["model_inputs"]), "cost"
        )

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
            # adjust costs from 2021 to target dollar year using CPI/CEPCI adjustment
            self.target_dollar_year = target_dollar_year

        elif target_dollar_year < 2010:
            # adjust costs from 2021 to 2010 using CP/CEPCI adjustment
            self.target_dollar_year = 2010

        elif target_dollar_year > 2024:
            # adjust costs from 2021 to 2024 using CPI/CEPCI adjustment
            self.target_dollar_year = 2024

        config_dict.update({"cost_year": self.target_dollar_year})
        self.config = GeoH2SubsurfaceCostConfig.from_dict(config_dict, strict=True)

        super().setup()

        self.add_input("test_drill_cost", units="USD", val=self.config.test_drill_cost)
        self.add_input("permit_fees", units="USD", val=self.config.permit_fees)
        self.add_input("acreage", units="acre", val=self.config.acreage)
        self.add_input("rights_cost", units="USD/acre", val=self.config.rights_cost)
        self.add_input("success_chance", units="percent", val=self.config.success_chance)
        self.add_input("fixed_opex", units="USD/year", val=self.config.fixed_opex)
        self.add_input("variable_opex", units="USD/kg", val=self.config.variable_opex)
        self.add_input("contracting_pct", units="percent", val=self.config.contracting_pct)
        self.add_input("contingency_pct", units="percent", val=self.config.contingency_pct)
        self.add_input("preprod_time", units="month", val=self.config.preprod_time)
        self.add_input("as_spent_ratio", units=None, val=self.config.as_spent_ratio)

    def compute(self, inputs, outputs, discrete_inputs, discrete_outputs):
        # Get cost years
        cost_year = self.config.cost_year

        # Calculate total capital cost per well (successful or unsuccessful)
        drill = inflate_cepci(inputs["test_drill_cost"], 2022, cost_year)
        permit = inflate_cpi(inputs["permit_fees"], 2022, cost_year)
        acreage = inputs["acreage"]
        rights_acre = inflate_cpi(inputs["rights_cost"], 2022, cost_year)
        cap_well = drill + permit + acreage * rights_acre

        # Calculate total capital cost per SUCCESSFUL well
        if self.config.use_cost_curve:
            completion = self.calc_drill_cost(inputs["borehole_depth"])
        else:
            completion = self.config.constant_drill_cost
            completion = inflate_cepci(
                completion, 2010, cost_year
            )  # Is this the correct base year?
        success = inputs["success_chance"]
        bare_capex = cap_well / success * 100 + completion
        outputs["bare_capital_cost"] = bare_capex

        # Parse in opex
        fopex = inflate_cpi(inputs["fixed_opex"], 2022, cost_year)
        vopex = inflate_cpi(inputs["variable_opex"], 2022, cost_year)
        outputs["OpEx"] = fopex
        outputs["VarOpEx"] = vopex * inputs["total_wellhead_gas_produced"]

        # Apply cost multipliers to bare erected cost via NETL-PUB-22580
        contracting = inputs["contracting_pct"]
        contingency = inputs["contingency_pct"]
        preproduction = inputs["preprod_time"]
        as_spent_ratio = inputs["as_spent_ratio"]
        contracting_costs = bare_capex * contracting / 100
        epc_cost = bare_capex + contracting_costs
        contingency_costs = epc_cost * contingency / 100
        total_plant_cost = epc_cost + contingency_costs
        preprod_cost = fopex * preproduction / 12
        total_overnight_cost = total_plant_cost + preprod_cost
        tasc_toc_multiplier = as_spent_ratio  # simplifying for now - TODO model on well_lifetime
        total_as_spent_cost = total_overnight_cost * tasc_toc_multiplier
        outputs["CapEx"] = total_as_spent_cost
