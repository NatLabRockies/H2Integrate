from attrs import field, define

from h2integrate.core.utilities import BaseConfig, merge_shared_inputs
from h2integrate.core.validators import must_equal
from h2integrate.core.model_baseclasses import CostModelBaseClass, PerformanceModelBaseClass


@define(kw_only=True)
class SAFPerformanceModelConfig(BaseConfig):
    plant_capacity_mtpy: float = field()
    capacity_factor: float = field()


class SAFPerformanceModel(PerformanceModelBaseClass):
    """
    An OpenMDAO component for modeling the performance of a saf plant.
    Computes annual saf production based on plant capacity and capacity factor.
    """

    _time_step_bounds = (
        3600,
        3600,
    )  # (min, max) time step lengths (in seconds) compatible with this model

    def initialize(self):
        super().initialize()
        self.commodity = "saf"
        self.commodity_amount_units = "t"
        self.commodity_rate_units = "t/h"

    def setup(self):
        super().setup()
        self.config = SAFPerformanceModelConfig.from_dict(
            merge_shared_inputs(self.options["tech_config"]["model_inputs"], "performance"),
            additional_cls_name=self.__class__.__name__,
        )
        n_timesteps = self.options["plant_config"]["plant"]["simulation"]["n_timesteps"]
        self.add_input("electricity_in", val=0, shape=n_timesteps, units="kW")
        self.add_input("lignin_in", val=0, shape=n_timesteps, units="kg/h")
        self.add_input("water_in", val=0, shape=n_timesteps, units="kg/h")
        self.add_input("hydrogen_in", val=0, shape=n_timesteps, units="kg/h")
        self.add_input("salt_mix_in", val=0, shape=n_timesteps, units="kg/h")
        self.add_input("hydrogen_chloride_in", val=0, shape=n_timesteps, units="kg/h")

    def compute(self, inputs, outputs):
        saf_production_mtpy = self.config.plant_capacity_mtpy * self.config.capacity_factor
        outputs["saf_out"] = saf_production_mtpy / 8760
        outputs["rated_saf_production"] = self.config.plant_capacity_mtpy / 8760
        outputs["capacity_factor"] = self.config.capacity_factor
        outputs["total_saf_produced"] = outputs["saf_out"].sum()
        outputs["annual_saf_produced"] = outputs["total_saf_produced"] * (
            1 / self.fraction_of_year_simulated
        )


@define(kw_only=True)
class SAFCostModelConfig(BaseConfig):
    installation_time: int = field()
    inflation_rate: float = field()
    operational_year: int = field()
    plant_capacity_mtpy: float = field()
    capacity_factor: float = field()
    cost_year: int = field(default=2023, converter=int, validator=must_equal(2023))

    # Feedstock parameters - flattened from the nested structure
    lignin_unitcost: float = field(default=0.78)  # $/kg of final product
    lignin_transport_cost: float = field(default=0.0)
    salt_mix_unitcost: float = field(default=0.86)  # $/kg consumable
    salt_mix_transport_cost: float = field(default=0.0)
    hydrogen_chloride_unitcost: float = field(default=0.26)  # $/kg consumable
    hydrogen_chloride_transport_cost: float = field(default=0.0)
    hydrogen_unitcost: float = field(default=7.37)  # $/kg consumable
    hydrogen_transport_cost: float = field(default=0.0)
    electricity_cost: float = field(default=0.054)  # $/kWh
    raw_water_unitcost: float = field(default=0.001519)  # $/kg water
    lignin_consumption: float = field(default=1650)  # kg/MT product
    raw_water_consumption: float = field(default=2839)  # kg/tonne product
    hydrogen_consumption: float = field(default=580)  # kg/tonne product
    salt_mix_consumption: float = field(default=41.3)  # kg/MT product
    hydrogen_chloride_consumption: float = field(default=1.5)  # kg/MT product
    electricity_consumption: float = field(default=19750)  # kWh/tonne product
    water_disposal_unitcost: float = field(default=0.002013)  # $/kg
    water_disposal_rate: float = field(default=0)  # TODO: Change assumption


class SAFCostModel(CostModelBaseClass):
    """
    An OpenMDAO component for calculating the costs associated with saf production.
    Includes CapEx, OpEx, and byproduct credits.
    """

    _time_step_bounds = (
        3600,
        3600,
    )  # (min, max) time step lengths (in seconds) compatible with this model

    # TOASK: In that case, do we need this function?
    def setup(self):
        self.config = SAFCostModelConfig.from_dict(
            merge_shared_inputs(self.options["tech_config"]["model_inputs"], "cost"),
            additional_cls_name=self.__class__.__name__,
        )
        super().setup()

        self.add_input("plant_capacity_mtpy", val=0, units="t/year", desc="Annual plant capacity")
        self.add_input("plant_capacity_factor", val=0, units=None, desc="Capacity factor")
        self.add_input("lignin_cost", val=0, units="USD/kg", desc="Levelized cost of lignin")
        self.add_input(
            "electricity_cost", val=0, units="USD/(kW*h)", desc="Levelized cost of electricity"
        )
        self.add_input("water_cost", val=0, units="USD/kg", desc="Levelized cost of water")
        self.add_input("hydrogen_cost", val=0, units="USD/kg", desc="Levelized cost of hydrogen")
        self.add_input("salt_mix_cost", val=0, units="USD/kg", desc="Levelized cost of chemicals")
        self.add_input(
            "hydrogen_chloride_cost", val=0, units="USD/kg", desc="Levelized cost of chemicals"
        )

        self.add_input("saf_production_mtpy", val=0.0, units="t/year")

    def compute(self, inputs, outputs, discrete_inputs, discrete_outputs):
        # Calculate saf production costs directly
        total_plant_capex = 5570 * self.config.plant_capacity_mtpy

        # Fixed O&M Costs
        # TODO: Need to update labor cost
        labor_cost_annual_operation = (
            69375996.9
            * ((self.config.plant_capacity_mtpy / 365 * 1000) ** 0.25242)
            / ((1162077 / 365 * 1000) ** 0.25242)
        )
        labor_cost_maintenance = 0.00863 * total_plant_capex
        0.25 * (labor_cost_annual_operation + labor_cost_maintenance)

        fixed_operating_cost = 390 * self.config.plant_capacity_mtpy

        property_tax_insurance = 0.02 * total_plant_capex

        total_fixed_operating_cost = fixed_operating_cost + property_tax_insurance

        c = self.config
        variable_consumables_cost = c.plant_capacity_mtpy * (
            c.raw_water_consumption * c.raw_water_unitcost
            + c.lignin_consumption * (c.lignin_unitcost + c.lignin_transport_cost)
            + c.salt_mix_consumption * (c.salt_mix_unitcost + c.salt_mix_transport_cost)
            + c.hydrogen_chloride_consumption
            * (c.hydrogen_chloride_unitcost + c.hydrogen_chloride_transport_cost)
            + c.hydrogen_consumption * (c.hydrogen_unitcost + c.hydrogen_transport_cost)
        )

        water_disposal_cost = (
            c.plant_capacity_mtpy * c.water_disposal_unitcost * c.water_disposal_rate
        )

        electricity_cost = c.plant_capacity_mtpy * (c.electricity_consumption * c.electricity_cost)

        total_variable_operating_cost = (
            variable_consumables_cost + water_disposal_cost + electricity_cost
        )

        outputs["CapEx"] = total_plant_capex
        outputs["OpEx"] = total_fixed_operating_cost
        outputs["VarOpEx"] = total_variable_operating_cost
