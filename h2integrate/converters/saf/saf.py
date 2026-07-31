import ProFAST
from attrs import field, define

from h2integrate.core.utilities import BaseConfig, merge_shared_inputs
from h2integrate.core.validators import must_equal
from h2integrate.converters.saf.saf_baseclass import (
    SAFCostBaseClass,
    SAFPerformanceBaseClass,
)


@define(kw_only=True)
class SAFPerformanceModelConfig(BaseConfig):
    
    plant_capacity_mtpy: float = field()
    capacity_factor: float = field()


class SAFPerformanceModel(SAFPerformanceBaseClass):
    """
    An OpenMDAO component for modeling the performance of a saf plant.
    Computes annual saf production based on plant capacity and capacity factor.
    """

    def setup(self):
        super().setup()
        self.config = SAFPerformanceModelConfig.from_dict(
            merge_shared_inputs(self.options["tech_config"]["model_inputs"], "performance"),
            additional_cls_name=self.__class__.__name__,
        )

    def compute(self, inputs, outputs):
        saf_production_mtpy = self.config.plant_capacity_mtpy * self.config.capacity_factor
        outputs["saf_out"] = saf_production_mtpy / 8760
        outputs["rated_saf_production"] = self.config.plant_capacity_mtpy / 8760
        outputs["capacity_factor"] = self.config.capacity_factor
        outputs["total_saf_produced"] = outputs["saf_out"].sum()
        outputs["annual_saf_produced"] = outputs["total_saf_produced"] * (1 / self.fraction_of_year_simulated)

@define(kw_only=True)
class SAFCostModelConfig(BaseConfig): 
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
    lignin_unitcost: float = field(default=0.78) #$/kg of final product
    lignin_transport_cost: float = field(default=0.0)    
    salt_mix_unitcost: float = field(default=0.86) #$/kg consumable
    salt_mix_transport_cost: float = field(default=0.0)
    hydrogen_chloride_unitcost: float = field(default=0.26) #$/kg consumable
    hydrogen_chloride_transport_cost: float = field(default=0.0)    
    hydrogen_unitcost: float = field(default=7.37) #$/kg consumable
    hydrogen_transport_cost: float = field(default=0.0)
    electricity_cost: float = field(default=0.054) #$/kWh
    raw_water_unitcost: float = field(default=0.001519) #$/kg water
    lignin_consumption: float = field(default=1650) #kg/MT product
    raw_water_consumption: float = field(default=2839) #kg/tonne product
    hydrogen_consumption: float = field(default=580) #kg/tonne product
    salt_mix_consumption: float = field(default=41.3) #kg/MT product
    hydrogen_chloride_consumption: float = field(default=1.5) #kg/MT product    
    electricity_consumption: float = field(default=19750) #kWh/tonne product
    water_disposal_unitcost: float = field(default=0.002013) #$/kg
    water_disposal_rate: float = field(default=0) #TODO: Change assumption


class SAFCostModel(SAFCostBaseClass):
    """
    An OpenMDAO component for calculating the costs associated with saf production.  
    Includes CapEx, OpEx, and byproduct credits.
    """
# TOASK: In that case, do we need this function?
    def setup(self):
        self.config = SAFCostModelConfig.from_dict(
            merge_shared_inputs(self.options["tech_config"]["model_inputs"], "cost"),
            additional_cls_name=self.__class__.__name__,
        )
        super().setup()

        self.add_input(
            "saf_production_mtpy", val=0.0, units="t/year"
        )  
        self.add_output("LCOP", val=0.0, units="USD/t")

    def compute(self, inputs, outputs, discrete_inputs, discrete_outputs):

        # Calculate saf production costs directly
        model_year_CEPCI = 816.0  # 2022
        equation_year_CEPCI = 797.9  # 2023

        capex_saf_process = (
            model_year_CEPCI
            / equation_year_CEPCI
            * 5570
            * self.config.plant_capacity_mtpy**1
        )

        total_plant_cost = (
            capex_saf_process
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
        
        fixed_operating_cost = 390 * self.config.plant_capacity_mtpy

        property_tax_insurance = 0.02 * total_plant_cost

        total_fixed_operating_cost = (
            fixed_operating_cost
            + property_tax_insurance
        )
        
        variable_consumables_cost = (
            self.config.plant_capacity_mtpy
            * (
                self.config.raw_water_consumption * self.config.raw_water_unitcost
                + self.config.lignin_consumption
                * (self.config.lignin_unitcost + self.config.lignin_transport_cost)
 
                + self.config.salt_mix_consumption
                * (self.config.salt_mix_unitcost + self.config.salt_mix_transport_cost)
                + self.config.hydrogen_chloride_consumption
                * (self.config.hydrogen_chloride_unitcost + self.config.hydrogen_chloride_transport_cost)
                
                + self.config.hydrogen_consumption
                * (self.config.hydrogen_unitcost + self.config.hydrogen_transport_cost)
            )
            
        )

        water_disposal_cost = (
            self.config.plant_capacity_mtpy
            * self.config.water_disposal_unitcost
            * self.config.water_disposal_rate
           
        )

        electricity_cost = (
            self.config.plant_capacity_mtpy
            * (
                 self.config.electricity_consumption * self.config.electricity_cost
            )
           
        )

        total_variable_operating_cost = (
            variable_consumables_cost
            + water_disposal_cost
            + electricity_cost
        )

        outputs["CapEx"] = total_plant_cost
        outputs["OpEx"] = total_fixed_operating_cost
        outputs["VarOpEx"] = total_variable_operating_cost


