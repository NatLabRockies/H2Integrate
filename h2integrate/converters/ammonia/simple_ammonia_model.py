import openmdao.api as om
from attrs import field, define

from h2integrate.core.utilities import BaseConfig, CostModelBaseConfig, merge_shared_inputs
from h2integrate.core.validators import must_equal
from h2integrate.core.model_baseclasses import CostModelBaseClass


@define(kw_only=True)
class AmmoniaPerformanceModelConfig(BaseConfig):
    """Configuration inputs for the ammonia performance model, including plant capacity and
    capacity factor.

    Attributes:
        plant_capacity_kgpy (float): Annual production capacity of the plant in kg.
        plant_capacity_factor (float): The ratio of actual production to maximum
            possible production over a year.
    """

    plant_capacity_kgpy: float = field()
    plant_capacity_factor: float = field()


class SimpleAmmoniaPerformanceModel(om.ExplicitComponent):
    """
    An OpenMDAO component for modeling the performance of an ammonia plant.
    Computes annual ammonia production based on plant capacity and capacity factor.
    """

    def initialize(self):
        self.options.declare("plant_config", types=dict)
        self.options.declare("tech_config", types=dict)
        self.options.declare("driver_config", types=dict)

    def setup(self):
        n_timesteps = self.options["plant_config"]["plant"]["simulation"]["n_timesteps"]
        self.config = AmmoniaPerformanceModelConfig.from_dict(
            merge_shared_inputs(self.options["tech_config"]["model_inputs"], "performance")
        )
        self.add_input("hydrogen_in", val=0.0, shape=n_timesteps, units="kg/h")
        self.add_output("ammonia_out", val=0.0, shape=n_timesteps, units="kg/h")
        self.add_output("total_ammonia_produced", val=0.0, units="kg/year")

    def compute(self, inputs, outputs):
        ammonia_production_kgpy = (
            self.config.plant_capacity_kgpy * self.config.plant_capacity_factor
        )
        outputs["ammonia_out"] = ammonia_production_kgpy / len(inputs["hydrogen_in"])
        outputs["total_ammonia_produced"] = ammonia_production_kgpy


@define(kw_only=True)
class AmmoniaCostModelConfig(CostModelBaseConfig):
    """
    Configuration inputs for the ammonia cost model, including plant capacity and
    feedstock details.

    Attributes:
        plant_capacity_kgpy (float): Annual production capacity of the plant in kg.
        plant_capacity_factor (float): The ratio of actual production to maximum
            possible production over a year.
        electricity_cost (float): Cost per MWh of electricity.
        cooling_water_cost (float): Cost per gallon of cooling water.
        iron_based_catalyst_cost (float): Cost per kg of iron-based catalyst.
        oxygen_cost (float): Cost per kg of oxygen.
        electricity_consumption (float): Electricity consumption in MWh per kg of
            ammonia production.
        hydrogen_consumption (float): Hydrogen consumption in kg per kg of ammonia
            production.
        cooling_water_consumption (float): Cooling water consumption in gallons per
            kg of ammonia production.
        iron_based_catalyst_consumption (float): Iron-based catalyst consumption in kg
            per kg of ammonia production.
        oxygen_byproduct (float): Oxygen byproduct in kg per kg of ammonia production.
        capex_scaling_exponent (float): Power applied to ratio of capacities when calculating CAPEX
            from a baseline value at a different capacity.
        cost_year (int): dollar year for costs.
    """

    plant_capacity_kgpy: float = field()
    plant_capacity_factor: float = field()
    electricity_cost: float = field()
    cooling_water_cost: float = field()
    iron_based_catalyst_cost: float = field()
    oxygen_cost: float = field()
    electricity_consumption: float = field()
    hydrogen_consumption: float = field()
    cooling_water_consumption: float = field()
    iron_based_catalyst_consumption: float = field()
    oxygen_byproduct: float = field()
    capex_scaling_exponent: float = field()
    cost_year: int = field(default=2022, converter=int, validator=must_equal(2022))


class SimpleAmmoniaCostModel(CostModelBaseClass):
    """
    An OpenMDAO component for calculating the costs associated with ammonia production.
    Includes CapEx, OpEx, and byproduct credits, and exposes all detailed cost outputs.
    """

    def setup(self):
        self.config = AmmoniaCostModelConfig.from_dict(
            merge_shared_inputs(self.options["tech_config"]["model_inputs"], "cost")
        )
        super().setup()
        # Inputs for cost model configuration
        self.add_input(
            "plant_capacity_kgpy", val=0.0, units="kg/year", desc="Annual plant capacity"
        )
        self.add_input("plant_capacity_factor", val=0.0, units=None, desc="Capacity factor")
        self.add_input("LCOH", val=0.0, units="USD/kg", desc="Cost per kg of hydrogen")
        self.add_input(
            "capex_scaling_exponent", val=0.6, units=None, desc="Exponent of CAPEX corr."
        )

        # Outputs for all cost model outputs
        self.add_output(
            "capex_air_separation_cryogenic",
            val=0.0,
            units="USD",
            desc="Capital cost for air separation",
        )
        self.add_output(
            "capex_haber_bosch", val=0.0, units="USD", desc="Capital cost for Haber-Bosch process"
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

        self.add_output(
            "H2_cost_in_startup_year",
            val=0.0,
            units="USD",
            desc="Hydrogen cost in the startup year",
        )
        self.add_output(
            "energy_cost_in_startup_year",
            val=0.0,
            units="USD",
            desc="Energy cost in the startup year",
        )
        self.add_output(
            "non_energy_cost_in_startup_year",
            val=0.0,
            units="USD",
            desc="Non-energy cost in the startup year",
        )
        self.add_output(
            "variable_cost_in_startup_year",
            val=0.0,
            units="USD",
            desc="Variable cost in the startup year",
        )
        self.add_output("credits_byproduct", val=0.0, units="USD", desc="Credits from byproducts")

    def compute(self, inputs, outputs, discrete_inputs, discrete_outputs):
        # Prepare config object
        config = self.config

        # Inline the run_ammonia_cost_model logic
        model_year_CEPCI = 816.0  # 2022
        equation_year_CEPCI = 541.7  # 2016

        # scale with respect to a baseline plant (What is this?)
        scaling_ratio = config.plant_capacity_kgpy / (365.0 * 1266638.4)

        # -------------------------------CapEx Costs------------------------------
        scaling_factor_equipment = inputs["capex_scaling_exponent"]
        capex_scale_factor = scaling_ratio**scaling_factor_equipment

        capex_air_separation_cryogenic = (
            model_year_CEPCI / equation_year_CEPCI * 22506100 * capex_scale_factor
        )
        capex_haber_bosch = model_year_CEPCI / equation_year_CEPCI * 18642800 * capex_scale_factor
        capex_boiler = model_year_CEPCI / equation_year_CEPCI * 7069100 * capex_scale_factor
        capex_cooling_tower = model_year_CEPCI / equation_year_CEPCI * 4799200 * capex_scale_factor
        capex_direct = (
            capex_air_separation_cryogenic + capex_haber_bosch + capex_boiler + capex_cooling_tower
        )
        capex_depreciable_nonequipment = capex_direct * 0.42 + 4112701.84103543 * scaling_ratio
        capex_total = capex_direct + capex_depreciable_nonequipment
        land_cost = 2500000 * capex_scale_factor

        # -------------------------------Fixed O&M Costs------------------------------
        scaling_factor_labor = 0.25
        labor_cost = 57 * 50 * 2080 * scaling_ratio**scaling_factor_labor
        general_administration_cost = labor_cost * 0.2
        property_tax_insurance = capex_total * 0.02
        maintenance_cost = capex_direct * 0.005 * scaling_ratio**scaling_factor_equipment
        land_cost = 2500000 * capex_scale_factor
        total_fixed_operating_cost = (
            land_cost
            + labor_cost
            + general_administration_cost
            + property_tax_insurance
            + maintenance_cost
        )

        # -------------------------------Feedstock Costs------------------------------
        H2_cost_in_startup_year = (
            inputs["LCOH"]
            * config.hydrogen_consumption
            * config.plant_capacity_kgpy
            * config.plant_capacity_factor
        )
        energy_cost_in_startup_year = (
            config.electricity_cost
            * config.electricity_consumption
            * config.plant_capacity_kgpy
            * config.plant_capacity_factor
        )
        non_energy_cost_in_startup_year = (
            (
                (config.cooling_water_cost * config.cooling_water_consumption)
                + (config.iron_based_catalyst_cost * config.iron_based_catalyst_consumption)
            )
            * config.plant_capacity_kgpy
            * config.plant_capacity_factor
        )
        variable_cost_in_startup_year = (
            energy_cost_in_startup_year + non_energy_cost_in_startup_year
        )
        # -------------------------------Byproduct Costs------------------------------
        credits_byproduct = (
            config.oxygen_cost
            * config.oxygen_byproduct
            * config.plant_capacity_kgpy
            * config.plant_capacity_factor
        )

        # Set outputs
        outputs["capex_air_separation_cryogenic"] = capex_air_separation_cryogenic
        outputs["capex_haber_bosch"] = capex_haber_bosch
        outputs["capex_boiler"] = capex_boiler
        outputs["capex_cooling_tower"] = capex_cooling_tower
        outputs["capex_direct"] = capex_direct
        outputs["capex_depreciable_nonequipment"] = capex_depreciable_nonequipment
        outputs["land_cost"] = land_cost

        outputs["labor_cost"] = labor_cost
        outputs["general_administration_cost"] = general_administration_cost
        outputs["property_tax_insurance"] = property_tax_insurance
        outputs["maintenance_cost"] = maintenance_cost

        outputs["H2_cost_in_startup_year"] = H2_cost_in_startup_year
        outputs["energy_cost_in_startup_year"] = energy_cost_in_startup_year
        outputs["non_energy_cost_in_startup_year"] = non_energy_cost_in_startup_year
        outputs["variable_cost_in_startup_year"] = variable_cost_in_startup_year
        outputs["credits_byproduct"] = credits_byproduct

        outputs["CapEx"] = capex_total
        outputs["OpEx"] = total_fixed_operating_cost
