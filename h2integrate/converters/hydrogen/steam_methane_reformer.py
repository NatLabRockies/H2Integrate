import numpy as np
from attrs import field, define
from openmdao.utils import units

from h2integrate.core.utilities import BaseConfig, merge_shared_inputs
from h2integrate.core.validators import gt_zero, gte_zero
from h2integrate.core.model_baseclasses import (
    CostModelBaseClass,
    CostModelBaseConfig,
    PerformanceModelBaseClass,
)


@define(kw_only=True)
class SteamMethaneReformerPerformanceConfig(BaseConfig):
    """
    Configuration class for steam methane reformer (SMR) performance model.

    This configuration class handles the parameters for natural gas
    steam methane reforming for hydrogen production.

    Attributes:
        system_capacity_tonnes_per_day (float): rated capacity of the SMR plant
            in metric tonnes/day.
        natural_gas_usage_mmbtu_per_kg (float): Natural gas usage for steam
            methane reforming process in MMBtu/kg.
        electricity_usage_kwh_per_kg (float): Electricity usage for steam methane
            reforming process in kWh/kg.
    """

    system_capacity_tonnes_per_day: float = field(validator=gte_zero)
    natural_gas_usage_mmbtu_per_kg: float = field(validator=gt_zero)
    electricity_usage_kwh_per_kg: float = field(validator=gte_zero)


class SteamMethaneReformerPerformanceModel(PerformanceModelBaseClass):
    """
    Performance model for steam methane reforming (SMR) hydrogen production plants.

    Outputs:
        hydrogen_out (array): Hydrogen output in kg/h for each timestep
        natural_gas_consumed (array): Natural gas consumed in MMBtu/h
        electricity_consumed (array): Electricity consumed in kW for each timestep
        unmet_hydrogen_demand (array): Unmet hydrogen demand in kg/h for each timestep
    """

    _time_step_bounds = (3600, 3600)  # (min, max) time step lengths compatible with this model

    def initialize(self):
        super().initialize()
        self.commodity = "hydrogen"
        self.commodity_rate_units = "kg/h"
        self.commodity_amount_units = "kg"

    def setup(self):
        super().setup()

        self.config = SteamMethaneReformerPerformanceConfig.from_dict(
            merge_shared_inputs(self.options["tech_config"]["model_inputs"], "performance"),
            additional_cls_name=self.__class__.__name__,
        )
        n_timesteps = self.options["plant_config"]["plant"]["simulation"]["n_timesteps"]

        # Add natural_gas_usage_mmbtu_per_kg as an OpenMDAO input with config value as default
        self.add_input(
            "natural_gas_usage_rate",
            val=self.config.natural_gas_usage_mmbtu_per_kg,
            units="MMBtu/kg",
            desc="Plant natural gas usage rate in MMBtu/kg",
        )

        # Add electricity_usage_kwh_per_kg as an OpenMDAO input with config value as default
        self.add_input(
            "electricity_usage_rate",
            val=self.config.electricity_usage_kwh_per_kg,
            units="(kW*h)/kg",
            desc="Plant electricity usage rate in kWh/kg",
        )

        # Add rated capacity as an input with config value as default
        self.add_input(
            "system_capacity",
            val=self.config.system_capacity_tonnes_per_day,
            units="t/d",
            desc="SMR plant rated capacity in t/d",
        )

        # Default the hydrogen demand input as the rated capacity
        self.add_input(
            f"{self.commodity}_demand",
            val=self.config.system_capacity_tonnes_per_day * (1000 / 24),  # convert t/d to kg/h
            shape=n_timesteps,
            units=self.commodity_rate_units,
            desc="Hydrogen demand for SMR plant",
        )

        # Add natural gas input, default to 0 --> set using feedstock component
        self.add_input(
            "natural_gas_in",
            val=0.0,
            shape=n_timesteps,
            units="MMBtu/h",
            desc="Natural gas input energy",
        )

        # Add electricity input, default to 0 --> set using feedstock component
        self.add_input(
            "electricity_in",
            val=0.0,
            shape=n_timesteps,
            units="kW",
            desc="Electricity input energy",
        )

        # Add natural gas consumed output
        self.add_output(
            "natural_gas_consumed",
            val=0.0,
            shape=n_timesteps,
            units="MMBtu/h",
            desc="Natural gas consumed by the plant",
        )

        # Add natural gas consumed output
        self.add_output(
            "electricity_consumed",
            val=0.0,
            shape=n_timesteps,
            units="kW",
            desc="Electricity consumed by the plant",
        )

        # Equivalent electrical rating of the plant
        self.add_output(
            "electrical_rated_hydrogen_production",
            val=0.0,
            units="MW",
            desc="Electrical equivalent rated hydrogen production of the plant",
        )

        self.add_output(
            "unmet_hydrogen_demand",
            val=0.0,
            shape=n_timesteps,
            units=self.commodity_rate_units,
            desc="Unmet hydrogen demand for SMR plant",
        )

        self.add_output(
            "total_energy_conversion_ratio",
            val=0.0,
            shape=1,
            units="kW*h/kg",
            desc="Net energy conversion ratio",
        )

    def compute(self, inputs, outputs):
        """
        Compute hydrogen output from natural gas input.

        The computation uses the natural gas usage rate and the electricity
            usage rate to convert natural gas energy input to hydrogen
            energy output.

        Args:
            inputs: OpenMDAO inputs object containing natural_gas_in,
                natural_gas_usage_rate, electricity_usage_rate,
                system_capacity, and hydrogen_demand.
            outputs: OpenMDAO outputs object for hydrogen_out, natural_gas_consumed,
                electricity_consumed, and unmet_hydrogen_demand.
        """

        # calculate max input and output
        system_capacity_kg_per_hour = inputs["system_capacity"] * (
            1000 / 24
        )  # plant capacity in kg/h from tonnes per day
        natural_gas_usage_mmbtu_per_kg = inputs["natural_gas_usage_rate"]
        max_natural_gas_consumption = system_capacity_kg_per_hour * natural_gas_usage_mmbtu_per_kg
        electricity_usage_kWh_per_kg = inputs["electricity_usage_rate"]
        max_electricity_consumption = system_capacity_kg_per_hour * electricity_usage_kWh_per_kg

        # hydrogen demand, saturated at maximum rated system capacity
        hydrogen_demand = np.where(
            inputs["hydrogen_demand"] > system_capacity_kg_per_hour,
            system_capacity_kg_per_hour,
            inputs["hydrogen_demand"],
        )
        natural_gas_demand = hydrogen_demand * natural_gas_usage_mmbtu_per_kg
        electricity_demand = hydrogen_demand * electricity_usage_kWh_per_kg

        # available feedstock, saturated at maximum system feedstock consumption
        natural_gas_available = np.where(
            inputs["natural_gas_in"] > max_natural_gas_consumption,
            max_natural_gas_consumption,
            inputs["natural_gas_in"],
        )
        electricity_available = np.where(
            inputs["electricity_in"] > max_electricity_consumption,
            max_electricity_consumption,
            inputs["electricity_in"],
        )

        # natural gas consumed is minimum between available feedstock and output demand
        natural_gas_consumed = np.minimum.reduce([natural_gas_demand, natural_gas_available])

        # electricity consumed is minimum between available feedstock and output demand
        electricity_consumed = np.minimum.reduce([electricity_demand, electricity_available])

        # Convert electricity consumption to hydrogen output using electricity usage rate
        hydrogen_out_ng = natural_gas_consumed / natural_gas_usage_mmbtu_per_kg
        hydrogen_out_elec = electricity_consumed / electricity_usage_kWh_per_kg
        hydrogen_out = np.minimum.reduce([hydrogen_out_ng, hydrogen_out_elec])

        outputs["hydrogen_out"] = hydrogen_out
        outputs["natural_gas_consumed"] = hydrogen_out * natural_gas_usage_mmbtu_per_kg
        outputs["electricity_consumed"] = hydrogen_out * electricity_usage_kWh_per_kg

        outputs["rated_hydrogen_production"] = system_capacity_kg_per_hour  # kg/h

        # Convert natural gas usage from MMBtu/kg to kW*h/kg
        energy_conversion_ratio_ng = units.convert_units(
            inputs["natural_gas_usage_rate"], "MMBtu/kg", "kW*h/kg"
        )
        total_energy_conversion_ratio = (
            energy_conversion_ratio_ng + inputs["electricity_usage_rate"]
        )

        outputs["electrical_rated_hydrogen_production"] = (
            system_capacity_kg_per_hour * total_energy_conversion_ratio
        ) / 1000  # convert kg/h to MW using energy conversion ratio

        max_production = system_capacity_kg_per_hour * len(hydrogen_out) * (self.dt / 3600)

        # Sum hourly hydrogen output to get annual hydrogen production
        # hydrogen_out is in kg/h, so sum gives kg for hourly data
        outputs["total_hydrogen_produced"] = np.sum(hydrogen_out) * (self.dt / 3600)
        outputs["capacity_factor"] = outputs["total_hydrogen_produced"].sum() / max_production
        outputs["annual_hydrogen_produced"] = outputs["total_hydrogen_produced"] * (
            1 / self.fraction_of_year_simulated
        )
        outputs["unmet_hydrogen_demand"] = inputs["hydrogen_demand"] - hydrogen_out
        outputs["total_energy_conversion_ratio"] = total_energy_conversion_ratio


@define(kw_only=True)
class SteamMethaneReformerCostModelConfig(CostModelBaseConfig):
    """
    Configuration class for hydrogen steam methane reformer plant cost model.

    Attributes:
        capex_per_kw (float|int): Capital cost per unit capacity in $/kW. This includes
            all equipment, installation, and construction costs.
        fixed_opex_per_kw_per_year (float|int): Fixed operating expenses per unit capacity
            in $/kW/year. This includes fixed O&M costs that don't vary with generation.
        variable_opex_per_kwh (float|int): Variable operating expenses per unit generation in $/kWh.
            This includes variable O&M costs that scale with electricity generation.
        cost_year (int): Dollar year corresponding to input costs.
    """

    capex_per_kw: float | int = field(validator=gte_zero)
    fixed_opex_per_kw_per_year: float | int = field(validator=gte_zero)
    variable_opex_per_kwh: float | int = field(validator=gte_zero)


class SteamMethaneReformerCostModel(CostModelBaseClass):
    """
    Cost model for steam methane reforming hydrogen production plants.

    Outputs:
        CapEx (float): Total capital expenditure in USD
        OpEx (float): Total fixed operating expenditure in USD/year
        VarOpEx (float): Total variable operating expenditure in USD/year
        cost_year (int): Dollar year for the costs
    """

    _time_step_bounds = (3600, 3600)  # (min, max) time step lengths compatible with this model

    def setup(self):
        self.config = SteamMethaneReformerCostModelConfig.from_dict(
            merge_shared_inputs(self.options["tech_config"]["model_inputs"], "cost"),
            additional_cls_name=self.__class__.__name__,
        )
        self.options["plant_config"]["plant"]["simulation"]["n_timesteps"]
        plant_life = self.options["plant_config"]["plant"]["plant_life"]

        super().setup()

        self.add_input(
            "annual_hydrogen_produced",
            val=0.0,
            shape=plant_life,
            units="kg/year",
            desc="Annual hydrogen output from performance model",
        )
        self.add_input(
            "total_energy_conversion_ratio",
            val=0.0,
            units="(kW*h)/kg",
            desc="Plant electricity usage rate in kWh/kg",
        )
        self.add_input(
            "electrical_rated_hydrogen_production",
            val=0.0,
            units="kW",
            desc="Electrical equivalent rated hydrogen production from performance model",
        )

        # Add inputs specific to the cost model with config values as defaults
        self.add_input(
            "unit_capex",
            val=self.config.capex_per_kw,
            units="USD/kW",
            desc="Capital cost per unit capacity",
        )
        self.add_input(
            "fixed_opex",
            val=self.config.fixed_opex_per_kw_per_year,
            units="USD/(kW*year)",
            desc="Fixed operating expenses per unit capacity per year",
        )
        self.add_input(
            "variable_opex",
            val=self.config.variable_opex_per_kwh,
            units="USD/(kW*h)",
            desc="Variable operating expenses per unit generation",
        )

    def compute(self, inputs, outputs, discrete_inputs, discrete_outputs):
        """
        Compute capital and operating costs for the hydrogen SMR plant.
        """
        plant_capacity_kw = inputs["electrical_rated_hydrogen_production"]

        capex_per_kw = inputs["unit_capex"]
        fixed_opex_per_kw_per_year = inputs["fixed_opex"]

        # Calculate capital expenditure
        capex = capex_per_kw * plant_capacity_kw

        # Calculate fixed operating expenses over project life
        fixed_om = fixed_opex_per_kw_per_year * plant_capacity_kw

        # Calculate variable O&M over project life
        variable_opex_per_kwh = inputs["variable_opex"]

        hydrogen_out = inputs["annual_hydrogen_produced"]  # kg/year annual profile

        # Convert the variable O&M from USD/kWh to USD/kg using the energy conversion ratio
        # USD/kW*h * kW*h/kg = USD/kg
        variable_opex_per_kg = variable_opex_per_kwh * inputs["total_energy_conversion_ratio"][0]

        # Calculate variable operating expenses over project life
        variable_om = variable_opex_per_kg * hydrogen_out

        outputs["CapEx"] = capex
        outputs["OpEx"] = fixed_om
        outputs["VarOpEx"] = variable_om
