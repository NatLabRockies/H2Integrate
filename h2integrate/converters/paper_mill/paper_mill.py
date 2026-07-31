from attrs import field, define

from h2integrate.core.utilities import BaseConfig, merge_shared_inputs
from h2integrate.core.validators import must_equal
from h2integrate.converters.paper_mill.paper_mill_baseclass import (
    PaperMillCostBaseClass,
    PaperMillPerformanceBaseClass,
)


@define(kw_only=True)
class PaperMillPerformanceModelConfig(BaseConfig):
    plant_capacity_mtpy: float = field()
    capacity_factor: float = field()


class PaperMillPerformanceModel(PaperMillPerformanceBaseClass):
    """
    An OpenMDAO component for modeling the performance of an paper mill plant.
    Computes annual paper production based on plant capacity and capacity factor.
    """

    def setup(self):
        n_timesteps = self.options["plant_config"]["plant"]["simulation"]["n_timesteps"]
        super().setup()

        self.config = PaperMillPerformanceModelConfig.from_dict(
            merge_shared_inputs(self.options["tech_config"]["model_inputs"], "performance"),
            additional_cls_name=self.__class__.__name__,
        )

        self.add_output("pulp_out", val=0.0, shape=n_timesteps, units="t/h")
        self.add_output("rated_pulp_out_production", val=0.0, units="t/h")
        self.add_output("total_pulp_out_produced", val=0.0, units="t")
        self.add_output("annual_pulp_out_produced", val=0.0, units="t/year")

    def compute(self, inputs, outputs):
        paper_mill_production_mtpy = self.config.plant_capacity_mtpy * self.config.capacity_factor
        outputs["paper_out"] = paper_mill_production_mtpy / 8760  # tons per hour
        outputs["rated_paper_production"] = self.config.plant_capacity_mtpy / 8760  # tons per hour
        outputs["capacity_factor"] = self.config.capacity_factor
        outputs["total_paper_produced"] = outputs["paper_out"].sum()
        outputs["annual_paper_produced"] = outputs["total_paper_produced"] * (
            1 / self.fraction_of_year_simulated
        )

        outputs["lignin_out"] = 0.06 * 1000 * paper_mill_production_mtpy / 8760  # tons per hour
        outputs["rated_lignin_production"] = 0.06 * 1000 * self.config.plant_capacity_mtpy / 8760
        outputs["total_lignin_produced"] = outputs["lignin_out"].sum()
        outputs["annual_lignin_produced"] = outputs["total_lignin_produced"] * (
            1 / self.fraction_of_year_simulated
        )

        outputs["pulp_out"] = 1.1 * paper_mill_production_mtpy / 8760
        outputs["rated_pulp_out_production"] = 1.1 * self.config.plant_capacity_mtpy / 8760
        outputs["total_pulp_out_produced"] = outputs["pulp_out"].sum()
        outputs["annual_pulp_out_produced"] = outputs["total_pulp_out_produced"] * (
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
    cost_year: int = field(default=2022, converter=int, validator=must_equal(2022))
    wood_unitcost: float = field(default=99.3)  # $/MT of wood
    wood_transport_cost: float = field(default=0.0)

    calcium_carbonate_unitcost: float = field(default=0.33)  # $/kg consumable
    calcium_carbonate_transport_cost: float = field(default=0.0)
    sodium_sulfide_unitcost: float = field(default=0.22)  # $/kg consumable
    sodium_sulfide_transport_cost: float = field(default=0.0)
    sodium_hydroxide_unitcost: float = field(default=0.33)  # $/kg consumable
    sodium_hydroxide_transport_cost: float = field(default=0.0)
    chlorine_dioxide_unitcost: float = field(default=1.79)  # $/kg consumable
    chlorine_dioxide_transport_cost: float = field(default=0.0)
    hydrogen_peroxide_unitcost: float = field(default=0.33)  # $/kg consumable
    hydrogen_peroxide_transport_cost: float = field(default=0.0)
    magnesium_sulfate_unitcost: float = field(default=0.36)  # $/kg consumable
    magnesium_sulfate_transport_cost: float = field(default=0.0)
    oxygen_unitcost: float = field(default=0)  # $/ton consumable
    oxygen_transport_cost: float = field(default=0.0)

    electricity_cost: float = field(default=0.054)  # $/kWh
    raw_water_unitcost: float = field(default=0.001519)  # $/kg water
    wood_consumption: float = field(default=0.225)  # MT/MT product
    raw_water_consumption: float = field(default=40693)  # kg/tonne product

    calcium_carbonate_consumption: float = field(default=240)  # kg/MT product
    sodium_sulfide_consumption: float = field(default=16.5)  # kg/MT product
    sodium_hydroxide_consumption: float = field(default=3.5)  # kg/MT product
    chlorine_dioxide_consumption: float = field(default=2)  # kg/MT product
    hydrogen_peroxide_consumption: float = field(default=0.5)  # kg/MT product
    magnesium_sulfate_consumption: float = field(default=0.2)  # kg/MT product
    oxygen_consumption: float = field(default=2.25)  # kg/MT product

    electricity_consumption: float = field(default=68.7)  # kWh/tonne product
    water_disposal_unitcost: float = field(default=0.002013)  # $/kg
    water_disposal_rate: float = field(default=18927)  # kg/MT product


class PaperMillCostModel(PaperMillCostBaseClass):
    """
    An OpenMDAO component for calculating the costs associated with paper mill production.
    Includes CapEx, OpEx, and byproduct credits.
    """

    _time_step_bounds = (
        3600,
        3600,
    )  # (min, max) time step lengths (in seconds) compatible with this model

    # TOASK: In that case, do we need this function?
    def setup(self):
        self.config = PaperMillCostModelConfig.from_dict(
            merge_shared_inputs(self.options["tech_config"]["model_inputs"], "cost"),
            additional_cls_name=self.__class__.__name__,
        )
        super().setup()

        self.add_input("paper_mill_production_mtpy", val=0.0, units="t/year")

    def compute(self, inputs, outputs, discrete_inputs, discrete_outputs):
        # Calculate paper mill production costs directly
        model_year_CEPCI = 816.0  # 2022
        equation_year_CEPCI = 797.9  # 2023

        capex_Kraft_process = (
            model_year_CEPCI / equation_year_CEPCI * 2500 * self.config.plant_capacity_mtpy**1
        )

        total_plant_cost = capex_Kraft_process

        # Fixed O&M Costs
        # TODO: Need to update labor cost
        labor_cost_annual_operation = (
            69375996.9
            * ((self.config.plant_capacity_mtpy / 365 * 1000) ** 0.25242)
            / ((1162077 / 365 * 1000) ** 0.25242)
        )
        labor_cost_maintenance = 0.00863 * total_plant_cost
        0.25 * (labor_cost_annual_operation + labor_cost_maintenance)

        fixed_operating_cost = 370 * self.config.plant_capacity_mtpy

        property_tax_insurance = 0.02 * total_plant_cost

        total_fixed_operating_cost = fixed_operating_cost + property_tax_insurance

        variable_consumables_cost = self.config.plant_capacity_mtpy * (
            self.config.raw_water_consumption * self.config.raw_water_unitcost
            + self.config.wood_consumption
            * (self.config.wood_unitcost + self.config.wood_transport_cost)
            + self.config.calcium_carbonate_consumption
            * (
                self.config.calcium_carbonate_unitcost
                + self.config.calcium_carbonate_transport_cost
            )
            + self.config.sodium_sulfide_consumption
            * (self.config.sodium_sulfide_unitcost + self.config.sodium_sulfide_transport_cost)
            + self.config.sodium_hydroxide_consumption
            * (self.config.sodium_hydroxide_unitcost + self.config.sodium_hydroxide_transport_cost)
            + self.config.chlorine_dioxide_consumption
            * (self.config.chlorine_dioxide_unitcost + self.config.chlorine_dioxide_transport_cost)
            + self.config.hydrogen_peroxide_consumption
            * (
                self.config.hydrogen_peroxide_unitcost
                + self.config.hydrogen_peroxide_transport_cost
            )
            + self.config.magnesium_sulfate_consumption
            * (
                self.config.magnesium_sulfate_unitcost
                + self.config.magnesium_sulfate_transport_cost
            )
            + self.config.oxygen_consumption
            * (self.config.oxygen_unitcost + self.config.oxygen_transport_cost)
        )

        water_disposal_cost = (
            self.config.plant_capacity_mtpy
            * self.config.water_disposal_unitcost
            * self.config.water_disposal_rate
        )

        electricity_cost = self.config.plant_capacity_mtpy * (
            self.config.electricity_consumption * self.config.electricity_cost
        )

        total_variable_operating_cost = (
            variable_consumables_cost + water_disposal_cost + electricity_cost
        )

        outputs["CapEx"] = total_plant_cost
        outputs["OpEx"] = total_fixed_operating_cost
        outputs["VarOpEx"] = total_variable_operating_cost
