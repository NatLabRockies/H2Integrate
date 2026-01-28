import openmdao.api as om
from attrs import field, define

from h2integrate.core.utilities import BaseConfig
from h2integrate.core.validators import contains
from h2integrate.core.model_baseclasses import CostModelBaseClass


@define(kw_only=True)
class MethanolPerformanceConfig(BaseConfig):
    plant_capacity_kgpy: float = field()
    plant_capacity_flow: str = field(validator=contains(["hydrogen", "methanol"]))
    capacity_factor: float = field()
    co2e_emit_ratio: float = field()
    h2o_consume_ratio: float = field()


class MethanolPerformanceBaseClass(om.ExplicitComponent):
    """
    An OpenMDAO component for modeling the performance of a methanol plant.
    Computes annual methanol and co-product production, feedstock consumption, and emissions
    based on plant capacity and capacity factor.

    Inputs:
        - plant_capacity_kgpy: (float) plant capacity in kg/year
        - plant_capacity_flow: (str) flow that determines capacity, options: "hydrogen", "methanol"
        - capacity_factor: (float) fractional factor of full production capacity that is realized
        - co2e_emit_ratio: (float) ratio of kg co2e emitted to kg methanol produced
        - h2o_consume_ratio: (float) ratio of kg h2o consumed to kg methanol produced
    Outputs:
        - methanol_out: methanol production in kg/h
        - total_methanol_produced: annual methanol production in kg/year
        - co2e_emissions: co2e emissions in kg/h
        - h2o_consumption: h2o consumption in kg/h
    """

    def initialize(self):
        self.options.declare("driver_config", types=dict)
        self.options.declare("plant_config", types=dict)
        self.options.declare("tech_config", types=dict)

    def setup(self):
        n_timesteps = self.options["plant_config"]["plant"]["simulation"]["n_timesteps"]
        self.add_input("plant_capacity_kgpy", units="kg/year", val=self.config.plant_capacity_kgpy)
        self.add_input("capacity_factor", units="unitless", val=self.config.capacity_factor)
        self.add_input("co2e_emit_ratio", units="kg/kg", val=self.config.co2e_emit_ratio)
        self.add_input("h2o_consume_ratio", units="kg/kg", val=self.config.h2o_consume_ratio)

        self.add_output("methanol_out", units="kg/h", shape=n_timesteps)
        self.add_output("total_methanol_produced", units="kg/year")
        self.add_output("co2e_emissions", units="kg/h", shape=n_timesteps)
        self.add_output("h2o_consumption", units="kg/h", shape=n_timesteps)


@define(kw_only=True)
class MethanolCostConfig(BaseConfig):
    plant_capacity_kgpy: float = field()
    plant_capacity_flow: str = field(validator=contains(["hydrogen", "methanol"]))
    toc_kg_y: float = field()
    foc_kg_y2: float = field()
    voc_kg: float = field()
    cost_year: int = field(converter=int)


class MethanolCostBaseClass(CostModelBaseClass):
    """
    An OpenMDAO component for modeling the cost of a methanol plant.
    Includes CapEx, OpEx (fixed and variable), feedstock costs, and co-product credits.

    Uses NETL power plant quality guidelines quantity of "total overnight cost" (TOC) for CapEx
    NETL-PUB-22580 doi.org/10.2172/1567736
    Splits OpEx into Fixed and Variable (variable scales with capacity factor, fixed does not)

    Inputs:
        - plant_capacity_kgpy: (float) plant capacity in kg/year
        - plant_capacity_flow: (str) flow that determines capacity, options: "hydrogen", "methanol"
        - toc_kg_y: (float) total overnight cost (TOC) slope - multiply by plant_capacity_kgpy to
            get CapEx
        - foc_kg_y^2: (float) fixed operating cost (FOC) slope - multiply by plant_capacity_kgpy to
            get Fixed_OpEx
        - voc_kg: (float) variable operating cost - multiply by methanol to get Variable_OpEx
        - methanol_out: (array) promoted output from MethanolPerformanceBaseClass
    Outputs:
        - CapEx: all methanol plant capital expenses in the form of total overnight cost (TOC)
        - OpEx: all methanol plant operating expenses (fixed and variable)
        - Fixed_OpEx: all methanol plant fixed operating expenses (do NOT vary with production rate)
        - Variable_OpEx: all methanol plant variable operating expenses (vary with production rate)
    """

    def setup(self):
        n_timesteps = self.options["plant_config"]["plant"]["simulation"]["n_timesteps"]
        super().setup()
        self.add_input("toc_kg_y", units="USD/kg/year", val=self.config.toc_kg_y)
        self.add_input("foc_kg_y2", units="USD/kg/year**2", val=self.config.foc_kg_y2)
        self.add_input("voc_kg", units="USD/kg", val=self.config.voc_kg)
        self.add_input("plant_capacity_kgpy", units="kg/year", val=self.config.plant_capacity_kgpy)
        self.add_input("methanol_out", shape=n_timesteps, units="kg/h")

        self.add_output("Fixed_OpEx", units="USD/year")
        self.add_output("Variable_OpEx", units="USD/year")


@define(kw_only=True)
class MethanolFinanceConfig(BaseConfig):
    tasc_toc_multiplier: float = field()
    fixed_charge_rate: float = field()
    plant_capacity_kgpy: float = field()
    plant_capacity_flow: str = field(validator=contains(["hydrogen", "methanol"]))


class MethanolFinanceBaseClass(om.ExplicitComponent):
    """
    An OpenMDAO component for modeling the financial aspects of a methanol plant.

    Inputs:
        - plant_capacity_kgpy: (float) plant capacity in kg/year
        - plant_capacity_flow: (str) flow that determines capacity, options: "hydrogen", "methanol"
        - CapEx: (float) total capital expenditure in USD
        - OpEx: (float) total operational expenditure in USD/year
        - Fixed_OpEx: (float) fixed operational expenditure in USD/year
        - Variable_OpEx: (float) variable operational expenditure in USD/year
        - tasc_toc_multiplier: (float) multiplier for total as-spent cost to total overnight cost
        - fixed_charge_rate: (float) fixed charge rate for financial calculations
        - methanol_out: (array) methanol production rate in kg/h over n_timesteps hours
    Outputs:
        - LCOM: levelized cost of methanol in USD/kg
        - LCOM_meoh: levelized cost of methanol including all components in USD/kg
        - LCOM_meoh_capex: levelized cost of methanol attributed to CapEx in USD/kg
        - LCOM_meoh_fopex: levelized cost of methanol attributed to fixed OpEx in USD/kg
        - LCOM_meoh_vopex: levelized cost of methanol attributed to variable OpEx in USD/kg
    """

    def initialize(self):
        self.options.declare("driver_config", types=dict)
        self.options.declare("plant_config", types=dict)
        self.options.declare("tech_config", types=dict)

    def setup(self):
        n_timesteps = self.options["plant_config"]["plant"]["simulation"]["n_timesteps"]
        self.add_input("CapEx", units="USD", val=1.0, desc="Total capital expenditure in USD.")
        self.add_input(
            "OpEx", units="USD/year", val=1.0, desc="Total operational expenditure in USD/year."
        )
        self.add_input(
            "Fixed_OpEx",
            units="USD/year",
            val=1.0,
            desc="Fixed operational expenditure in USD/year.",
        )
        self.add_input(
            "Variable_OpEx",
            units="USD/year",
            val=1.0,
            desc="Variable operational expenditure in USD/year.",
        )
        self.add_input(
            "tasc_toc_multiplier",
            units=None,
            val=self.config.tasc_toc_multiplier,
            desc="Multiplier for total as-spent cost to total overnight cost.",
        )
        self.add_input(
            "fixed_charge_rate",
            units=None,
            val=self.config.fixed_charge_rate,
            desc="Fixed charge rate for financial calculations.",
        )
        self.add_input(
            "methanol_out",
            shape=n_timesteps,
            units="kg/h",
            desc="Methanol production rate in kg/h over n_timesteps hours.",
        )

        self.add_output("LCOM", units="USD/kg", desc="Levelized cost of methanol in USD/kg.")
        self.add_output(
            "LCOM_meoh",
            units="USD/kg",
            desc="Levelized cost of methanol including all components in USD/kg.",
        )
        self.add_output(
            "LCOM_meoh_capex",
            units="USD/kg",
            desc="Levelized cost of methanol attributed to CapEx in USD/kg.",
        )
        self.add_output(
            "LCOM_meoh_fopex",
            units="USD/kg",
            desc="Levelized cost of methanol attributed to fixed OpEx in USD/kg.",
        )
        self.add_output(
            "LCOM_meoh_vopex",
            units="USD/kg",
            desc="Levelized cost of methanol attributed to variable OpEx in USD/kg.",
        )
