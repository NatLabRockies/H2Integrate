import numpy as np
import openmdao.api as om
from attrs import field, define

from h2integrate.core.utilities import BaseConfig, merge_shared_inputs
from h2integrate.core.validators import gt_zero, gte_zero
from h2integrate.core.model_baseclasses import CostModelBaseClass, CostModelBaseConfig


@define(kw_only=True)
class NaturalGasPerformanceConfig(BaseConfig):
    """
    Configuration class for natural gas plant performance model.

    This configuration class handles the parameters for both natural gas
    combustion turbines (NGCT) and natural gas combined cycle (NGCC) plants.

    Attributes:
        system_capacity (float): rated capacity of the natural gas plant in MW
        heat_rate_mmbtu_per_mwh (float): Heat rate of the natural gas plant in MMBtu/MWh.
            This represents the amount of fuel energy required to produce
            one MWh of electricity. Lower values indicate higher efficiency.
            Typical values:
            - NGCT: 10-14 MMBtu/MWh
            - NGCC: 6-8 MMBtu/MWh
    """

    system_capacity_mw: float = field(validator=gte_zero)
    heat_rate_mmbtu_per_mwh: float = field(validator=gt_zero)


class NaturalGasPerformanceModel(om.ExplicitComponent):
    """
    Performance model for natural gas power plants.

    This model calculates electricity output from natural gas input based on
    the plant's heat rate. It can be used for both natural gas combustion
    turbines (NGCT) and natural gas combined cycle (NGCC) plants by providing
    appropriate heat rate values.

    The model implements the relationship:
        electricity_out = natural_gas_in / heat_rate

    Inputs:
        system_capacity (float): Natural gas plant rated capacity in MW
        natural_gas_in (array): Natural gas input energy in MMBtu for each timestep
        heat_rate_mmbtu_per_mwh (float): Plant heat rate in MMBtu/MWh
        electricity_demand (array): Electricity demand in MW for each timestep

    Outputs:
        electricity_out (array): Electricity output in MW for each timestep
        natural_gas_consumed (array): Natural gas consumed in MMBtu for each timestep

    """

    def initialize(self):
        self.options.declare("driver_config", types=dict)
        self.options.declare("plant_config", types=dict)
        self.options.declare("tech_config", types=dict)

    def setup(self):
        self.config = NaturalGasPerformanceConfig.from_dict(
            merge_shared_inputs(self.options["tech_config"]["model_inputs"], "performance")
        )
        n_timesteps = self.options["plant_config"]["plant"]["simulation"]["n_timesteps"]

        # Add natural gas consumed output
        self.add_output(
            "natural_gas_consumed",
            val=0.0,
            shape=n_timesteps,
            units="MMBtu",
            desc="Natural gas consumed by the plant",
        )

        # Add electricity output
        self.add_output(
            "electricity_out",
            val=0.0,
            shape=n_timesteps,
            units="MW",
            desc="Electricity output from natural gas plant",
        )

        # Add heat_rate as an OpenMDAO input with config value as default
        self.add_input(
            "heat_rate_mmbtu_per_mwh",
            val=self.config.heat_rate_mmbtu_per_mwh,
            units="MMBtu/MW/h",
            desc="Plant heat rate in MMBtu/MWh",
        )

        # Add rated capacity as an input with config value as default
        self.add_input(
            "system_capacity",
            val=self.config.system_capacity_mw,
            units="MW",
            desc="Natural gas plant rated capacity in MW",
        )

        # Default the electricity demand input as the rated capacity
        self.add_input(
            "electricity_demand",
            val=self.config.system_capacity_mw,
            shape=n_timesteps,
            units="MW",
            desc="Electricity demand for natural gas plant",
        )

        # Add natural gas input, default to 0 --> set using feedstock component
        self.add_input(
            "natural_gas_in",
            val=0.0,
            shape=n_timesteps,
            units="MMBtu",
            desc="Natural gas input energy",
        )

    def compute(self, inputs, outputs):
        """
        Compute electricity output from natural gas input.

        The computation uses the heat rate to convert natural gas energy input
        to electrical energy output. The heat rate represents the fuel energy
        required per unit of electrical energy produced.

        Args:
            inputs: OpenMDAO inputs object containing natural_gas_in, heat_rate_mmbtu_per_mwh,
                system_capacity, and electricity_demand.
            outputs: OpenMDAO outputs object for electricity_out and natural_gas_consumed
        """

        # calculate max input and output
        system_capacity = inputs["system_capacity"]  # plant capacity in MW
        heat_rate_mmbtu_per_mwh = inputs["heat_rate_mmbtu_per_mwh"]
        max_natural_gas_consumption = system_capacity * heat_rate_mmbtu_per_mwh

        # electrical demand, saturated at maximum rated system capacity
        electricity_demand = np.where(
            inputs["electricity_demand"] > system_capacity,
            system_capacity,
            inputs["electricity_demand"],
        )
        natural_gas_demand = electricity_demand * heat_rate_mmbtu_per_mwh

        # available feedstock, saturated at maximum system feedstock consumption
        natural_gas_available = np.where(
            inputs["natural_gas_in"] > max_natural_gas_consumption,
            max_natural_gas_consumption,
            inputs["natural_gas_in"],
        )

        # natural gas consumed is minimum between available feedstock and output demand
        natural_gas_consumed = np.minimum.reduce([natural_gas_demand, natural_gas_available])

        # Convert natural gas consumption to electricity output using heat rate
        electricity_out = natural_gas_consumed / heat_rate_mmbtu_per_mwh

        outputs["electricity_out"] = electricity_out
        outputs["natural_gas_consumed"] = natural_gas_consumed


@define(kw_only=True)
class NaturalGasCostModelConfig(CostModelBaseConfig):
    """
    Configuration class for natural gas plant cost model.

    This configuration handles cost parameters for both natural gas combustion
    turbines (NGCT) and natural gas combined cycle (NGCC) plants.

    Attributes:
        system_capacity (float | int): Plant capacity in MW.

        capex_per_kw (float|int): Capital cost per unit capacity in $/kW. This includes
            all equipment, installation, and construction costs.
            Typical values:
            - NGCT: 600-2400 $/kW
            - NGCC: 800-2400 $/kW

        fixed_opex_per_kw_per_year (float|int): Fixed operating expenses per unit capacity
            in $/kW/year. This includes fixed O&M costs that don't vary with generation.
            Typical values: 5-15 $/kW/year

        variable_opex_per_mwh (float|int): Variable operating expenses per unit generation in $/MWh.
            This includes variable O&M costs that scale with electricity generation.
            Typical values: 1-5 $/MWh

        heat_rate_mmbtu_per_mwh (float): Heat rate in MMBtu/MWh, used for fuel cost calculations.
            This should match the heat rate used in the performance model.

        cost_year (int): Dollar year corresponding to input costs.
    """

    system_capacity_mw: float | int = field(validator=gt_zero)
    capex_per_kw: float | int = field(validator=gte_zero)
    fixed_opex_per_kw_per_year: float | int = field(validator=gte_zero)
    variable_opex_per_mwh: float | int = field(validator=gte_zero)
    heat_rate_mmbtu_per_mwh: float = field(validator=gt_zero)


class NaturalGasCostModel(CostModelBaseClass):
    """
    Cost model for natural gas power plants.

    This model calculates capital and operating costs for natural gas plants
    including fuel costs. It can be used for both NGCT and NGCC plants.

    The model calculates:
    - CapEx: Capital expenditure based on plant capacity
    - OpEx: Operating expenditure including fixed O&M, variable O&M, and fuel costs

    Cost components:
    1. Capital costs: capex_per_kw * plant_capacity_kw
    2. Fixed O&M: fixed_opex_per_kw_per_year * plant_capacity_kw
    3. Variable O&M: variable_opex_per_mwh * delivered_electricity_MWh

    Inputs:
        system_capacity (float): Natural gas plant capacity in MW
        electricity_out (array): Hourly electricity output in MW from performance model
        capex_per_kw (float): Capital cost per unit capacity in $/kW
        fixed_opex_per_kw_per_year (float): Fixed operating expenses per unit capacity in $/kW/year
        variable_opex_per_mwh (float): Variable operating expenses per unit generation in $/MWh
        heat_rate_mmbtu_per_mwh (float): Heat rate in MMBtu/MWh

    Outputs:
        CapEx (float): Total capital expenditure in USD
        OpEx (float): Total operating expenditure in USD/year
        cost_year (int): Dollar year for the costs
    """

    def setup(self):
        self.config = NaturalGasCostModelConfig.from_dict(
            merge_shared_inputs(self.options["tech_config"]["model_inputs"], "cost")
        )
        n_timesteps = self.options["plant_config"]["plant"]["simulation"]["n_timesteps"]

        super().setup()

        # Add inputs specific to the cost model with config values as defaults
        self.add_input(
            "system_capacity",
            val=self.config.system_capacity_mw,
            units="MW",
            desc="Natural gas plant capacity",
        )
        self.add_input(
            "electricity_out",
            val=0.0,
            shape=n_timesteps,
            units="MW",
            desc="Hourly electricity output from performance model",
        )
        self.add_input(
            "capex_per_kw",
            val=self.config.capex_per_kw,
            units="USD/kW",
            desc="Capital cost per unit capacity",
        )
        self.add_input(
            "fixed_opex_per_kw_per_year",
            val=self.config.fixed_opex_per_kw_per_year,
            units="USD/(kW*year)",
            desc="Fixed operating expenses per unit capacity per year",
        )
        self.add_input(
            "variable_opex_per_mwh",
            val=self.config.variable_opex_per_mwh,
            units="USD/(MW*h)",
            desc="Variable operating expenses per unit generation",
        )
        self.add_input(
            "heat_rate_mmbtu_per_mwh",
            val=self.config.heat_rate_mmbtu_per_mwh,
            units="MMBtu/(MW*h)",
            desc="Plant heat rate",
        )

    def compute(self, inputs, outputs, discrete_inputs, discrete_outputs):
        """
        Compute capital and operating costs for the natural gas plant.
        """
        plant_capacity_kw = inputs["system_capacity"] * 1000  # Convert MW to kW
        electricity_out = inputs["electricity_out"]  # MW hourly profile
        capex_per_kw = inputs["capex_per_kw"]
        fixed_opex_per_kw_per_year = inputs["fixed_opex_per_kw_per_year"]
        variable_opex_per_mwh = inputs["variable_opex_per_mwh"]

        # Sum hourly electricity output to get annual generation
        # electricity_out is in MW, so sum gives MWh for hourly data
        dt = self.options["plant_config"]["plant"]["simulation"]["dt"]
        delivered_electricity_MWdt = electricity_out.sum()
        delivered_electricity_MWh = delivered_electricity_MWdt * dt / 3600

        # Calculate capital expenditure
        capex = capex_per_kw * plant_capacity_kw

        # Calculate fixed operating expenses over project life
        fixed_om = fixed_opex_per_kw_per_year * plant_capacity_kw

        # Calculate variable operating expenses over project life
        variable_om = variable_opex_per_mwh * delivered_electricity_MWh

        # Total operating expenditure includes all O&M
        opex = fixed_om + variable_om

        outputs["CapEx"] = capex
        outputs["OpEx"] = opex
