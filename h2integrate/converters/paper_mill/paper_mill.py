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
    An OpenMDAO component for modeling the performance of an steel plant.
    Computes annual steel production based on plant capacity and capacity factor.
    """

    def setup(self):
        super().setup()
        self.config = PaperMillPerformanceModelConfig.from_dict(
            merge_shared_inputs(self.options["tech_config"]["model_inputs"], "performance"),
            additional_cls_name=self.__class__.__name__,
        )

    def compute(self, inputs, outputs):
        paper_mill_production_mtpy = self.config.plant_capacity_mtpy * self.config.capacity_factor
        outputs["paper_mill_out"] = paper_mill_production_mtpy / len(inputs["electricity_in"])
        outputs["rated_paper_mill_production"] = self.config.plant_capacity_mtpy / 8760
        outputs["capacity_factor"] = self.config.capacity_factor
        outputs["total_paper_mill_produced"] = outputs["paper_out"].sum()
        outputs["annual_paper_mill_produced"] = outputs["total_paper_mill_produced"] * (
            1 / self.fraction_of_year_simulated
        )


@define(kw_only=True)
class PaperMillCostAndFinancialModelConfig(BaseConfig): 
    installation_time: int = field()
    inflation_rate: float = field()
    operational_year: int = field()
    plant_capacity_mtpy: float = field()
    capacity_factor: float = field()
    water_prices: dict = field()

    # Financial parameters - flattened from the nested structure
    grid_prices: dict = field()
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


class PaperMillCostAndFinancialModel(PaperMillCostBaseClass):
    """
    An OpenMDAO component for calculating the costs associated with paper mill production.  
    Includes CapEx, OpEx, and byproduct credits.
    """
# TOASK: In that case, do we need this function?
    def setup(self):
        self.config = PaperMillCostAndFinancialModelConfig.from_dict(
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

# TOASK: Can we have auxiliary from steel to paper mill?
        capex_cooling_tower = (
            model_year_CEPCI
            / equation_year_CEPCI
            * 2513.08314
            * self.config.plant_capacity_mtpy**0.63325
        )

        capex_piping = (
            model_year_CEPCI
            / equation_year_CEPCI
            * 11815.72718
            * self.config.plant_capacity_mtpy**0.59983
        )
        capex_elec_instr = (
            model_year_CEPCI
            / equation_year_CEPCI
            * 7877.15146
            * self.config.plant_capacity_mtpy**0.59983
        )
        capex_buildings_storage_water = (
            model_year_CEPCI
            / equation_year_CEPCI
            * 1097.81876
            * self.config.plant_capacity_mtpy**0.8
        )
        capex_misc = (
            model_year_CEPCI
            / equation_year_CEPCI
            * 7877.1546
            * self.config.plant_capacity_mtpy**0.59983
        )

        total_plant_cost = (
            capex_Kraft_process
            + capex_cooling_tower
            + capex_piping
            + capex_elec_instr
            + capex_buildings_storage_water
            + capex_misc
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

        # Owner's (Installation) Costs
        labor_cost_fivemonth = (
            5
            / 12
            * (labor_cost_annual_operation + labor_cost_maintenance + labor_cost_admin_support)
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
            * self.config.water_production
            / 12
        )

        (
            self.config.plant_capacity_mtpy
            * (
                 self.config.electricity_consumption * self.config.electricity_cost
            )
            / 12
        )
        two_percent_tpc = 0.02 * total_plant_cost

        fuel_consumables_60day_supply_cost = (
            self.config.plant_capacity_mtpy
            * (
                self.config.raw_water_consumption * self.config.raw_water_unitcost
                + self.config.wood_consumption
                * (self.config.wood_unitcost + self.config.wood_transport_cost)
                + self.config.chemicals_consumption
                * (self.config.chemicals_unitcost + self.config.chemicals_transport_cost)
            )
            / 365
            * 60
        )
# TOASK: Can we use those values as placeholders?
        spare_parts_cost = 0.005 * total_plant_cost
        land_cost = 0.775 * self.config.plant_capacity_mtpy
        misc_owners_costs = 0.15 * total_plant_cost

        installation_cost = (
            labor_cost_fivemonth
            + two_percent_tpc
            + fuel_consumables_60day_supply_cost
            + spare_parts_cost
            + misc_owners_costs
        )

        outputs["CapEx"] = total_plant_cost
        outputs["OpEx"] = total_fixed_operating_cost

        # Run finance model directly using ProFAST
        pf = ProFAST.ProFAST("blank")

        # Apply all params passed through from config
        for param, val in self.config.financial_assumptions.items():
            pf.set_params(param, val)

        analysis_start = int([*self.config.grid_prices][0]) - int(
            self.config.installation_time / 12
        )
        plant_life = self.options["plant_config"]["plant"]["plant_life"]

        # Fill these in - can have most of them as 0 also
        pf.set_params(
            "commodity",
            {
                "name": "paper",
                "unit": "metric tons",
                "initial price": 460,
                "escalation": self.config.inflation_rate,
            },
        )
        pf.set_params("capacity", self.config.plant_capacity_mtpy / 365)  # units/day
        pf.set_params("maintenance", {"value": 0, "escalation": self.config.inflation_rate})
        pf.set_params("analysis start year", analysis_start)
        pf.set_params("operating life", plant_life)
        pf.set_params("installation months", self.config.installation_time)
        pf.set_params(
            "installation cost",
            {
                "value": installation_cost,
                "depr type": "Straight line",
                "depr period": 4,
                "depreciable": False,
            },
        )
        pf.set_params("non depr assets", land_cost)
        pf.set_params(
            "end of proj sale non depr assets",
            land_cost * (1 + self.config.inflation_rate) ** plant_life,
        )
        pf.set_params("demand rampup", 0)
        pf.set_params("long term utilization", self.config.capacity_factor)
        pf.set_params("credit card fees", 0)
        pf.set_params("sales tax", 0)
        pf.set_params("license and permit", {"value": 00, "escalation": self.config.inflation_rate})
        pf.set_params("rent", {"value": 0, "escalation": self.config.inflation_rate})
        pf.set_params("property tax and insurance", 0)
        pf.set_params("admin expense", 0)
        pf.set_params("sell undepreciated cap", True)
        pf.set_params("tax losses monetized", True)
        pf.set_params("general inflation rate", self.config.inflation_rate)
        pf.set_params("debt type", "Revolving debt")
        pf.set_params("cash onhand", 1)

        # Add capital items to ProFAST
        pf.add_capital_item(
            name="Kraft process",
            cost=capex_Kraft_process,
            depr_type="MACRS",
            depr_period=7,
            refurb=[0],
        )
        pf.add_capital_item(
            name="Cooling Tower",
            cost=capex_cooling_tower,
            depr_type="MACRS",
            depr_period=7,
            refurb=[0],
        )
        pf.add_capital_item(
            name="Piping",
            cost=capex_piping,
            depr_type="MACRS",
            depr_period=7,
            refurb=[0],
        )
        pf.add_capital_item(
            name="Electrical & Instrumentation",
            cost=capex_elec_instr,
            depr_type="MACRS",
            depr_period=7,
            refurb=[0],
        )
        pf.add_capital_item(
            name="Buildings, Storage, Water Service",
            cost=capex_buildings_storage_water,
            depr_type="MACRS",
            depr_period=7,
            refurb=[0],
        )
        pf.add_capital_item(
            name="Other Miscellaneous Costs",
            cost=capex_misc,
            depr_type="MACRS",
            depr_period=7,
            refurb=[0],
        )

        # Add fixed costs
        pf.add_fixed_cost(
            name="Annual Operating Labor Cost",
            usage=1,
            unit="$/year",
            cost=labor_cost_annual_operation,
            escalation=self.config.inflation_rate,
        )
        pf.add_fixed_cost(
            name="Maintenance Labor Cost",
            usage=1,
            unit="$/year",
            cost=labor_cost_maintenance,
            escalation=self.config.inflation_rate,
        )
        pf.add_fixed_cost(
            name="Administrative & Support Labor Cost",
            usage=1,
            unit="$/year",
            cost=labor_cost_admin_support,
            escalation=self.config.inflation_rate,
        )
        pf.add_fixed_cost(
            name="Property tax and insurance",
            usage=1,
            unit="$/year",
            cost=property_tax_insurance,
            escalation=0.0,
        )

        # Add feedstocks
        pf.add_feedstock(
            name="Maintenance Materials",
            usage=1.0,
            unit="Units per metric ton of steel",
            cost=self.config.maintenance_materials_unitcost,
            escalation=self.config.inflation_rate,
        )
        pf.add_feedstock(
            name="Raw Water Withdrawal",
            usage=self.config.raw_water_consumption,
            unit="gallons of water per metric ton of paper",
            cost=self.config.raw_water_unitcost,
            escalation=self.config.inflation_rate,
        )
        pf.add_feedstock(
            name="Wood",
            usage=self.config.lime_consumption,
            unit="metric tons of wood per metric ton of paper",
            cost=(self.config.wood_unitcost + self.config.wood_transport_cost),
            escalation=self.config.inflation_rate,
        )
        pf.add_feedstock(
            name="Chemicals",
            usage=self.config.carbon_consumption,
            unit="metric tons of chemical per metric ton of paper",
            cost=(self.config.chemicals_unitcost + self.config.chemicals_transport_cost),
            escalation=self.config.inflation_rate,
        )
        pf.add_feedstock(
            name="Electricity",
            usage=self.config.electricity_consumption,
            unit="MWh per metric ton of paper",
            cost=self.config.grid_prices,
            escalation=self.config.inflation_rate,
        )
        pf.add_feedstock(
            name="Water Disposal",
            usage=self.config.slag_production,
            unit="gallon of water per metric ton of paper",
            cost=self.config.water_disposal_unitcost,
            escalation=self.config.inflation_rate,
        )

        # Solve
        sol = pf.solve_price()

        outputs["LCOP"] = sol.get("price")
