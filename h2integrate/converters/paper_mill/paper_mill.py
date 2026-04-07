import ProFAST
from attrs import field, define

from h2integrate.core.utilities import BaseConfig, merge_shared_inputs
from h2integrate.core.validators import must_equal
from h2integrate.converters.paper_mill.paper_mill_baseclass import (
    PaperMillCostBaseClass,
    PaperMillPerformanceBaseClass,
)


@define(kw_only=True)
class PaperMillPerformanceModelConfig(BaseConfig):
    
    #TOASK: It can be as simple as adding the values here
    plant_capacity_mtpy: float = field()
    capacity_factor: float = field()


class PaperMillPerformanceModel(PaperMillPerformanceBaseClass):
    """
    An OpenMDAO component for modeling the performance of an paper mill plant.
    Computes annual paper production based on plant capacity and capacity factor.
    """

    def setup(self):
        super().setup()
        self.config = PaperMillPerformanceModelConfig.from_dict(
            merge_shared_inputs(self.options["tech_config"]["model_inputs"], "performance"),
            additional_cls_name=self.__class__.__name__,
        )

    def compute(self, inputs, outputs):
        paper_mill_production_mtpy = self.config.plant_capacity_mtpy * self.config.capacity_factor
        outputs["paper_out"] = paper_mill_production_mtpy / len(inputs["electricity_in"])
        outputs["rated_paper_production"] = self.config.plant_capacity_mtpy / 8760
        outputs["capacity_factor"] = self.config.capacity_factor
        outputs["total_paper_produced"] = outputs["paper_out"].sum()
        outputs["annual_paper_produced"] = outputs["total_paper_produced"] * (
            1 / self.fraction_of_year_simulated
        )

@define(kw_only=True)
class PaperMillCostModelConfig(BaseConfig): 
    installation_time: int = field()
    inflation_rate: float = field()
    operational_year: int = field()
    plant_capacity_mtpy: float = field()
    capacity_factor: float = field()
#    water_prices: dict = field()

    # Financial parameters - flattened from the nested structure
#    grid_prices: dict = field()
    financial_assumptions: dict = field()
    cost_year: int = field(default=2022, converter=int, validator=must_equal(2022))  #TOASK: Do we keep cost year as 2022?

    # Feedstock parameters - flattened from the nested structure
    wood_unitcost: float = field(default=11.04) #$/MT of final product
    wood_transport_cost: float = field(default=0.0)
    chemicals_unitcost: float = field(default=15150) #$/ton consumable
    chemicals_transport_cost: float = field(default=0.0)
    electricity_cost: float = field(default=54) #$/MWh
    raw_water_unitcost: float = field(default=0.00575) #$/gal water
    wood_consumption: float = field(default=2.5) #MT/MT product
    raw_water_consumption: float = field(default=10750) #gal/tonne product
    chemicals_consumption: float = field(default=164) #MT/MT product
    electricity_consumption: float = field(default=0.65) #MWh/tonne product
    water_disposal_unitcost: float = field(default=0.00755) #$/gal
    water_disposal_rate: float = field(default=0) #TODO: Change assumption


class PaperMillCostModel(PaperMillCostBaseClass):
    """
    An OpenMDAO component for calculating the costs associated with paper mill production.  
    Includes CapEx, OpEx, and byproduct credits.
    """
# TOASK: In that case, do we need this function?
    def setup(self):
        self.config = PaperMillCostModelConfig.from_dict(
            merge_shared_inputs(self.options["tech_config"]["model_inputs"], "cost"),
            additional_cls_name=self.__class__.__name__,
        )
        super().setup()

        self.add_input(
            "paper_mill_production_mtpy", val=0.0, units="t/year"
        )  
        self.add_output("LCOP", val=0.0, units="USD/t")

    def compute(self, inputs, outputs, discrete_inputs, discrete_outputs):

        # Calculate paper mill production costs directly
        model_year_CEPCI = 816.0  # 2022
        equation_year_CEPCI = 797.9  # 2023

        capex_Kraft_process = (
            model_year_CEPCI
            / equation_year_CEPCI
            * 2500
            * self.config.plant_capacity_mtpy**1
        )

        total_plant_cost = (
            capex_Kraft_process
        )

        # Fixed O&M Costs
# TODO: Need to update labor cost
        labor_cost_annual_operation = (
            69375996.9
            * ((self.config.plant_capacity_mtpy / 365 * 1000) ** 0.25242)
            / ((1162077 / 365 * 1000) ** 0.25242)
        )
        labor_cost_maintenance = 0.00863 * total_plant_cost
        labor_cost_admin_support = 0.25 * (labor_cost_annual_operation + labor_cost_maintenance)
        
        fixed_operating_cost = 421 * self.config.plant_capacity_mtpy

        property_tax_insurance = 0.02 * total_plant_cost

        total_fixed_operating_cost = (
            fixed_operating_cost
            + property_tax_insurance
        )
        
        (
            self.config.plant_capacity_mtpy
            * (
                self.config.raw_water_consumption * self.config.raw_water_unitcost
                + self.config.wood_consumption
                * (self.config.wood_unitcost + self.config.wood_transport_cost)
                + self.config.chemicals_consumption
                * (self.config.chemicals_unitcost + self.config.chemicals_transport_cost)
            )
            / 12
        )

        (
            self.config.plant_capacity_mtpy
            * self.config.water_disposal_unitcost
            * self.config.water_disposal_rate
            / 12
        )

        (
            self.config.plant_capacity_mtpy
            * (
                 self.config.electricity_consumption * self.config.electricity_cost
            )
            / 12
        )


        outputs["CapEx"] = total_plant_cost
        outputs["OpEx"] = total_fixed_operating_cost


