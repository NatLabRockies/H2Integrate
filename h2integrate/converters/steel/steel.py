import ProFAST
from attrs import field, define

from h2integrate.core.utilities import BaseConfig, merge_shared_inputs
from h2integrate.core.validators import must_equal
from h2integrate.converters.steel.steel_baseclass import (
    SteelCostBaseClass,
    SteelPerformanceBaseClass,
)


@define(kw_only=True)
class SteelPerformanceModelConfig(BaseConfig):
    plant_capacity_mtpy: float = field()
    capacity_factor: float = field()


class SteelPerformanceModel(SteelPerformanceBaseClass):
    """
    An OpenMDAO component for modeling the performance of an steel plant.
    Computes annual steel production based on plant capacity and capacity factor.
    """

    def setup(self):
        super().setup()
        self.config = SteelPerformanceModelConfig.from_dict(
            merge_shared_inputs(self.options["tech_config"]["model_inputs"], "performance")
        )

    def compute(self, inputs, outputs):
        steel_production_mtpy = self.config.plant_capacity_mtpy * self.config.capacity_factor
        outputs["steel"] = steel_production_mtpy / len(inputs["electricity_in"])


@define(kw_only=True)
class SteelCostAndFinancialModelConfig(BaseConfig):
    installation_time: int = field()
    inflation_rate: float = field()
    operational_year: int = field()
    plant_capacity_mtpy: float = field()
    capacity_factor: float = field()
    o2_heat_integration: bool = field()
    lcoh: float = field()
    natural_gas_prices: dict = field()

    # Financial parameters - flattened from the nested structure
    grid_prices: dict = field()
    financial_assumptions: dict = field()
    cost_year: int = field(default=2022, converter=int, validator=must_equal(2022))

    # Feedstock parameters - flattened from the nested structure
    excess_oxygen: float = field(default=395)
    lime_unitcost: float = field(default=122.1)
    lime_transport_cost: float = field(default=0.0)
    carbon_unitcost: float = field(default=236.97)
    carbon_transport_cost: float = field(default=0.0)
    electricity_cost: float = field(default=48.92)
    iron_ore_pellet_unitcost: float = field(default=207.35)
    iron_ore_pellet_transport_cost: float = field(default=0.0)
    oxygen_market_price: float = field(default=0.03)
    raw_water_unitcost: float = field(default=0.59289)
    iron_ore_consumption: float = field(default=1.62927)
    raw_water_consumption: float = field(default=0.80367)
    lime_consumption: float = field(default=0.01812)
    carbon_consumption: float = field(default=0.0538)
    hydrogen_consumption: float = field(default=0.06596)
    natural_gas_consumption: float = field(default=0.71657)
    electricity_consumption: float = field(default=0.5502)
    slag_disposal_unitcost: float = field(default=37.63)
    slag_production: float = field(default=0.17433)
    maintenance_materials_unitcost: float = field(default=7.72)


class SteelCostAndFinancialModel(SteelCostBaseClass):
    """
    An OpenMDAO component for calculating the costs associated with steel production.
    Includes CapEx, OpEx, and byproduct credits.
    """

    def setup(self):
        self.config = SteelCostAndFinancialModelConfig.from_dict(
            merge_shared_inputs(self.options["tech_config"]["model_inputs"], "cost")
        )
        super().setup()

        self.add_input("steel_production_mtpy", val=0.0, units="t/year")
        self.add_output("LCOS", val=0.0, units="USD/t")

    def compute(self, inputs, outputs, discrete_inputs, discrete_outputs):
        # Update config with runtime inputs
        self.config.lcoh = inputs["LCOH"]
        if inputs["electricity_cost"] > 0:
            self.config.electricity_cost = inputs["electricity_cost"][0]

        # Calculate steel production costs directly
        model_year_CEPCI = 816.0  # 2022
        equation_year_CEPCI = 708.8  # 2021

        capex_eaf_casting = (
            model_year_CEPCI
            / equation_year_CEPCI
            * 352191.5237
            * self.config.plant_capacity_mtpy**0.456
        )
        capex_shaft_furnace = (
            model_year_CEPCI
            / equation_year_CEPCI
            * 489.68061
            * self.config.plant_capacity_mtpy**0.88741
        )
        capex_oxygen_supply = (
            model_year_CEPCI
            / equation_year_CEPCI
            * 1715.21508
            * self.config.plant_capacity_mtpy**0.64574
        )
        if self.config.o2_heat_integration:
            capex_h2_preheating = (
                model_year_CEPCI
                / equation_year_CEPCI
                * (1 - 0.4)
                * (45.69123 * self.config.plant_capacity_mtpy**0.86564)
            )
            capex_cooling_tower = (
                model_year_CEPCI
                / equation_year_CEPCI
                * (1 - 0.3)
                * (2513.08314 * self.config.plant_capacity_mtpy**0.63325)
            )
        else:
            capex_h2_preheating = (
                model_year_CEPCI
                / equation_year_CEPCI
                * 45.69123
                * self.config.plant_capacity_mtpy**0.86564
            )
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
            capex_eaf_casting
            + capex_shaft_furnace
            + capex_oxygen_supply
            + capex_h2_preheating
            + capex_cooling_tower
            + capex_piping
            + capex_elec_instr
            + capex_buildings_storage_water
            + capex_misc
        )

        # Fixed O&M Costs
        labor_cost_annual_operation = (
            69375996.9
            * ((self.config.plant_capacity_mtpy / 365 * 1000) ** 0.25242)
            / ((1162077 / 365 * 1000) ** 0.25242)
        )
        labor_cost_maintenance = 0.00863 * total_plant_cost
        labor_cost_admin_support = 0.25 * (labor_cost_annual_operation + labor_cost_maintenance)

        property_tax_insurance = 0.02 * total_plant_cost

        total_fixed_operating_cost = (
            labor_cost_annual_operation
            + labor_cost_maintenance
            + labor_cost_admin_support
            + property_tax_insurance
        )

        # Owner's (Installation) Costs
        labor_cost_fivemonth = (
            5
            / 12
            * (labor_cost_annual_operation + labor_cost_maintenance + labor_cost_admin_support)
        )

        (self.config.maintenance_materials_unitcost * self.config.plant_capacity_mtpy / 12)
        (
            self.config.plant_capacity_mtpy
            * (
                self.config.raw_water_consumption * self.config.raw_water_unitcost
                + self.config.lime_consumption
                * (self.config.lime_unitcost + self.config.lime_transport_cost)
                + self.config.carbon_consumption
                * (self.config.carbon_unitcost + self.config.carbon_transport_cost)
                + self.config.iron_ore_consumption
                * (
                    self.config.iron_ore_pellet_unitcost
                    + self.config.iron_ore_pellet_transport_cost
                )
            )
            / 12
        )

        (
            self.config.plant_capacity_mtpy
            * self.config.slag_disposal_unitcost
            * self.config.slag_production
            / 12
        )

        (
            self.config.plant_capacity_mtpy
            * (
                self.config.hydrogen_consumption * self.config.lcoh * 1000
                + self.config.natural_gas_consumption
                * self.config.natural_gas_prices[str(self.config.operational_year)]
                + self.config.electricity_consumption * self.config.electricity_cost
            )
            / 12
        )
        two_percent_tpc = 0.02 * total_plant_cost

        fuel_consumables_60day_supply_cost = (
            self.config.plant_capacity_mtpy
            * (
                self.config.raw_water_consumption * self.config.raw_water_unitcost
                + self.config.lime_consumption
                * (self.config.lime_unitcost + self.config.lime_transport_cost)
                + self.config.carbon_consumption
                * (self.config.carbon_unitcost + self.config.carbon_transport_cost)
                + self.config.iron_ore_consumption
                * (
                    self.config.iron_ore_pellet_unitcost
                    + self.config.iron_ore_pellet_transport_cost
                )
            )
            / 365
            * 60
        )

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
                "name": "Steel",
                "unit": "metric tons",
                "initial price": 1000,
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
        pf.set_params("demand rampup", 5.3)
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
            name="EAF & Casting",
            cost=capex_eaf_casting,
            depr_type="MACRS",
            depr_period=7,
            refurb=[0],
        )
        pf.add_capital_item(
            name="Shaft Furnace",
            cost=capex_shaft_furnace,
            depr_type="MACRS",
            depr_period=7,
            refurb=[0],
        )
        pf.add_capital_item(
            name="Oxygen Supply",
            cost=capex_oxygen_supply,
            depr_type="MACRS",
            depr_period=7,
            refurb=[0],
        )
        pf.add_capital_item(
            name="H2 Pre-heating",
            cost=capex_h2_preheating,
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
            unit="metric tons of water per metric ton of steel",
            cost=self.config.raw_water_unitcost,
            escalation=self.config.inflation_rate,
        )
        pf.add_feedstock(
            name="Lime",
            usage=self.config.lime_consumption,
            unit="metric tons of lime per metric ton of steel",
            cost=(self.config.lime_unitcost + self.config.lime_transport_cost),
            escalation=self.config.inflation_rate,
        )
        pf.add_feedstock(
            name="Carbon",
            usage=self.config.carbon_consumption,
            unit="metric tons of carbon per metric ton of steel",
            cost=(self.config.carbon_unitcost + self.config.carbon_transport_cost),
            escalation=self.config.inflation_rate,
        )
        pf.add_feedstock(
            name="Iron Ore",
            usage=self.config.iron_ore_consumption,
            unit="metric tons of iron ore per metric ton of steel",
            cost=(
                self.config.iron_ore_pellet_unitcost + self.config.iron_ore_pellet_transport_cost
            ),
            escalation=self.config.inflation_rate,
        )
        pf.add_feedstock(
            name="Hydrogen",
            usage=self.config.hydrogen_consumption,
            unit="metric tons of hydrogen per metric ton of steel",
            cost=self.config.lcoh * 1000,
            escalation=self.config.inflation_rate,
        )
        pf.add_feedstock(
            name="Natural Gas",
            usage=self.config.natural_gas_consumption,
            unit="GJ-LHV per metric ton of steel",
            cost=self.config.natural_gas_prices,
            escalation=self.config.inflation_rate,
        )
        pf.add_feedstock(
            name="Electricity",
            usage=self.config.electricity_consumption,
            unit="MWh per metric ton of steel",
            cost=self.config.grid_prices,
            escalation=self.config.inflation_rate,
        )
        pf.add_feedstock(
            name="Slag Disposal",
            usage=self.config.slag_production,
            unit="metric tons of slag per metric ton of steel",
            cost=self.config.slag_disposal_unitcost,
            escalation=self.config.inflation_rate,
        )

        pf.add_coproduct(
            name="Oxygen sales",
            usage=self.config.excess_oxygen,
            unit="kg O2 per metric ton of steel",
            cost=self.config.oxygen_market_price,
            escalation=self.config.inflation_rate,
        )

        # Solve
        sol = pf.solve_price()

        outputs["LCOS"] = sol.get("price")
