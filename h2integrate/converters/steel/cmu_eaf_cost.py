from attrs import field, define

from h2integrate.core.utilities import merge_shared_inputs
from h2integrate.core.validators import must_equal
from h2integrate.core.model_baseclasses import CostModelBaseClass, CostModelBaseConfig


@define(kw_only=True)
class CMUElectricArcFurnaceCostConfig(CostModelBaseConfig):
    """Configuration class for the CMUElectricArcFurnaceCostModel.

    Args:
        steel_production_capacity_tonnes_per_year (float): Rated electric arc furnace capacity
            in tonnes of steel produced per year. Default is 2200000 tonnes/year based on the CMU
            decarbSTEEL v5 model which assumes a 2.2 million tonne per year capacity for the EAF.
        capex_usd_per_tonne_capacity (float): Capital expenditure in USD per tonne of steel.
            Default value is 217.15 based on Vogl et al. (2018) study which is reported as
            184 Euros/tonne, converted to USD.
        maintenance_cost_rate (float): Fraction of capital expenditure allocated to annual
            maintenance and operations costs.
            Default value is 0.045, which corresponds to 4.5% of CapEx allocated to annual
            maintenance and operations costs according to the CMU decarbSTEEL v5 model.
        mean_annual_wage (float): Mean annual wage for steel workers, used to calculate labor costs.
            Default value is 66173, which corresponds to the mean annual wage for steel workers in
            the US in 2022 according to the Bureau of Labor Statistics.
        mean_hourly_wage (float): Mean hourly wage for steel workers, used to calculate labor costs.
            Default value is 31.82, which corresponds to the mean hourly wage for steel workers
            in the US in 2022 according to the Bureau of Labor Statistics.
        eaf_labor_required_per_tLS (float): Person hours required per ton of liquid steel produced
            in an electric arc furnace, used to calculate labor costs. Default value is 4/20.
        cost_year (int): Year for which the cost data is reported, used for inflation adjustments.
            Default value is 2022, which corresponds to the year of the cost data used in the CMU
                decarbSTEEL v5 model.

    """

    steel_production_capacity_tonnes_per_year: float = field(default=2200000)
    capex_usd_per_tonne_capacity: float = field(default=217.15)
    # fraction of capex for O&M (x100 = %), 'Model Inputs & Outputs!B3'
    maintenance_cost_rate: float = field(default=0.045)
    # $ mean annual wage steel worker, 'Model Inputs & Outputs!B4'
    mean_annual_wage: float = field(default=66173)
    # $ mean hourly wage steel worker, 'Model Inputs & Outputs!B5'
    mean_hourly_wage: float = field(default=31.82)
    # person hours per ton steel, '6. Production Cost!B43' > '6. Production Cost!J73'
    eaf_labor_required_per_tLS: float = field(default=4 / 20)
    cost_year: int = field(default=2022, converter=int, validator=must_equal(2022))


class CMUElectricArcFurnaceCostModel(CostModelBaseClass):
    """
    OpenMDAO component for calculating electric arc furnace capital and operating
    expenditures based on the CMU decarbSTEEL v5 model.


    Inputs:
        rated_steel_production (float):
            Rated capacity of the electric arc furnace.

    Outputs:
        CapEx (float):
            Total capital expenditure of the EAF.
        OpEx (float):
            Annual operating expenditure of the EAF.
    """

    _time_step_bounds = (
        3600,
        3600,
    )  # (min, max) time step lengths (in seconds) compatible with this model

    def setup(self):
        self.config = CMUElectricArcFurnaceCostConfig.from_dict(
            merge_shared_inputs(self.options["tech_config"]["model_inputs"], "cost"),
            additional_cls_name=self.__class__.__name__,
        )
        super().setup()

        self.add_input(
            "rated_steel_capacity",
            val=self.config.steel_production_capacity_tonnes_per_year,
            units="t/year",
            desc="Electric arc furnace rated capacity",
        )

        self.add_input(
            "rated_steel_production",
            val=0.0,
            units="t/year",
            desc="Rated steel production",
        )

    def compute(self, inputs, outputs, discrete_inputs, discrete_outputs):
        if inputs["rated_steel_production"] > inputs["rated_steel_capacity"]:
            raise ValueError(
                f"Rated steel production ({inputs['rated_steel_production']} t/year) cannot exceed "
                f"rated steel capacity ({inputs['rated_steel_capacity']} t/year)."
            )
        # 6. Production Cost
        # > CAPEX Production Assumptions
        # tons steel/year, '6. Production Cost!C26'
        annual_capacity = inputs["rated_steel_capacity"]
        CEPCI_index_2022 = 816  # CE Index (2022), '6. Production Cost!D26'

        # > Financial Conversion
        # CE Index (original year 2018), '6. Production Cost!F114' > '6. Production Cost!E151'
        CEPCI_index_2018 = 603.1
        # USD conversion for 2018, '6. Production Cost!D151'
        USD_financial_conversion_2018 = 1.180185

        # > CAPEX by Technology Lookup Table
        # $/ton steel capacity annually, EAF (mid) '6. Production Cost!C114'
        reported_levelized_capex = (
            self.config.capex_usd_per_tonne_capacity * USD_financial_conversion_2018
        )
        # $/ton steel capacity annually, EAF (mid) '6. Production Cost!G114' (capex_tpa)
        inflation_adjusted_levelized_capex = (
            reported_levelized_capex * CEPCI_index_2022 / CEPCI_index_2018
        )
        # > CAPEX by pathway node
        # $, '6. Production Cost!F73'
        outputs["CapEx"] = inflation_adjusted_levelized_capex * annual_capacity

        # > Labor by pathway node
        # $/ton liquid steel, '6. Production Cost!K73'
        labor_cost_per_tLS = self.config.eaf_labor_required_per_tLS * self.config.mean_hourly_wage

        # Not in CMU model
        labor_cost = labor_cost_per_tLS * annual_capacity  # $
        maintenance_cost = self.config.maintenance_cost_rate * outputs["CapEx"]  # $
        outputs["OpEx"] = labor_cost + maintenance_cost  # $
