from attrs import field, define

from h2integrate.core.utilities import BaseConfig, merge_shared_inputs
from h2integrate.core.validators import must_equal
from h2integrate.core.model_baseclasses import CostModelBaseClass, PerformanceModelBaseClass


@define(kw_only=True)
class PaperMillPerformanceModelConfig(BaseConfig):
    plant_capacity_mtpy: float = field()
    capacity_factor: float = field()


class PaperMillPerformanceModel(PerformanceModelBaseClass):
    """
    An OpenMDAO component for modeling the performance of an paper mill plant.
    Computes annual paper production based on plant capacity and capacity factor.
    """

    _time_step_bounds = (
        3600,
        3600,
    )  # (min, max) time step lengths (in seconds) compatible with this model

    def initialize(self):
        super().initialize()
        self.commodity = "paper"
        self.commodity_amount_units = "t"
        self.commodity_rate_units = "t/h"

    def setup(self):
        super().setup()

        self.config = PaperMillPerformanceModelConfig.from_dict(
            merge_shared_inputs(self.options["tech_config"]["model_inputs"], "performance"),
            additional_cls_name=self.__class__.__name__,
        )

        self.add_input("plant_capacity_mtpy", val=self.config.plant_capacity_mtpy, units="t/year")

        n_timesteps = self.options["plant_config"]["plant"]["simulation"]["n_timesteps"]
        self.add_output("lignin_out", val=0.0, shape=n_timesteps, units="kg/h")
        self.add_output("rated_lignin_production", shape=n_timesteps, val=0.0, units="kg/h")
        self.add_output("total_lignin_produced", val=0.0, units="kg")
        self.add_output("annual_lignin_produced", val=0.0, units="kg/year")

        self.add_output("pulp_out", val=0.0, shape=n_timesteps, units="t/h")
        self.add_output("rated_pulp_out_production", val=0.0, units="t/h")
        self.add_output("total_pulp_out_produced", val=0.0, units="t")
        self.add_output("annual_pulp_out_produced", val=0.0, units="t/year")

    def compute(self, inputs, outputs):
        plant_capacity_mtpy = inputs["plant_capacity_mtpy"]
        capacity_factor = self.config.capacity_factor
        paper_mill_production_mtpy = plant_capacity_mtpy * capacity_factor
        outputs["paper_out"] = paper_mill_production_mtpy / 8760  # tons per hour
        outputs["rated_paper_production"] = plant_capacity_mtpy / 8760  # tons per hour
        outputs["capacity_factor"] = capacity_factor
        outputs["total_paper_produced"] = outputs["paper_out"].sum()
        outputs["annual_paper_produced"] = outputs["total_paper_produced"] * (
            1 / self.fraction_of_year_simulated
        )

        outputs["lignin_out"] = 0.06 * 1000 * paper_mill_production_mtpy / 8760  # tons per hour
        outputs["rated_lignin_production"] = 0.06 * 1000 * plant_capacity_mtpy / 8760
        outputs["total_lignin_produced"] = outputs["lignin_out"].sum()
        outputs["annual_lignin_produced"] = outputs["total_lignin_produced"] * (
            1 / self.fraction_of_year_simulated
        )

        outputs["pulp_out"] = 1.1 * paper_mill_production_mtpy / 8760
        outputs["rated_pulp_out_production"] = 1.1 * plant_capacity_mtpy / 8760
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
    cost_year: int = field(default=2023, converter=int, validator=must_equal(2023))
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


class PaperMillCostModel(CostModelBaseClass):
    """
    An OpenMDAO component for calculating the costs associated with paper mill production.
    Includes CapEx, OpEx, and byproduct credits.
    """

    _time_step_bounds = (
        3600,
        3600,
    )  # (min, max) time step lengths (in seconds) compatible with this model

    def setup(self):
        self.config = PaperMillCostModelConfig.from_dict(
            merge_shared_inputs(self.options["tech_config"]["model_inputs"], "cost"),
            additional_cls_name=self.__class__.__name__,
        )
        super().setup()

        self.add_input("plant_capacity_mtpy", val=self.config.plant_capacity_mtpy, units="t/year")

    def compute(self, inputs, outputs, discrete_inputs, discrete_outputs):
        plant_capacity_mtpy = inputs["plant_capacity_mtpy"][0]

        # Calculate plant CapEx for Kraft process
        total_plant_capex = 2500 * plant_capacity_mtpy

        # Fixed O&M Costs
        # TODO: Need to update labor cost
        labor_cost_annual_operation = (
            69375996.9
            * ((plant_capacity_mtpy / 365 * 1000) ** 0.25242)
            / ((1162077 / 365 * 1000) ** 0.25242)
        )
        labor_cost_maintenance = 0.00863 * total_plant_capex
        0.25 * (labor_cost_annual_operation + labor_cost_maintenance)

        fixed_operating_cost = 370 * plant_capacity_mtpy

        property_tax_insurance = 0.02 * total_plant_capex

        total_fixed_operating_cost = fixed_operating_cost + property_tax_insurance

        # Sum total consumables costs and consumption
        c = self.config
        consumable_costs_per_mt = {
            "raw_water": c.raw_water_consumption * c.raw_water_unitcost,
            "wood": c.wood_consumption * (c.wood_unitcost + c.wood_transport_cost),
            "calcium_carbonate": c.calcium_carbonate_consumption
            * (c.calcium_carbonate_unitcost + c.calcium_carbonate_transport_cost),
            "sodium_sulfide": c.sodium_sulfide_consumption
            * (c.sodium_sulfide_unitcost + c.sodium_sulfide_transport_cost),
            "sodium_hydroxide": c.sodium_hydroxide_consumption
            * (c.sodium_hydroxide_unitcost + c.sodium_hydroxide_transport_cost),
            "chlorine_dioxide": c.chlorine_dioxide_consumption
            * (c.chlorine_dioxide_unitcost + c.chlorine_dioxide_transport_cost),
            "hydrogen_peroxide": c.hydrogen_peroxide_consumption
            * (c.hydrogen_peroxide_unitcost + c.hydrogen_peroxide_transport_cost),
            "magnesium_sulfate": c.magnesium_sulfate_consumption
            * (c.magnesium_sulfate_unitcost + c.magnesium_sulfate_transport_cost),
            "oxygen": c.oxygen_consumption * (c.oxygen_unitcost + c.oxygen_transport_cost),
        }
        variable_consumables_cost = plant_capacity_mtpy * sum(consumable_costs_per_mt.values())

        water_disposal_cost = (
            plant_capacity_mtpy
            * self.config.water_disposal_unitcost
            * self.config.water_disposal_rate
        )

        electricity_cost = plant_capacity_mtpy * (
            self.config.electricity_consumption * self.config.electricity_cost
        )

        total_variable_operating_cost = (
            variable_consumables_cost + water_disposal_cost + electricity_cost
        )

        outputs["CapEx"] = total_plant_capex
        outputs["OpEx"] = total_fixed_operating_cost
        outputs["VarOpEx"] = total_variable_operating_cost
