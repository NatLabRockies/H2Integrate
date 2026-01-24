import numpy as np
from attrs import field, define

from h2integrate.core.utilities import BaseConfig, merge_shared_inputs
from h2integrate.core.model_baseclasses import CostModelBaseClass, CostModelBaseConfig
from h2integrate.converters.water_power.hydro_plant_baseclass import HydroPerformanceBaseClass


@define(kw_only=True)
class RunOfRiverHydroPerformanceConfig(BaseConfig):
    """Configuration class for the RunOfRiverHydroPerformanceComponent.
    This class defines the parameters for the run-of-river hydropower plant performance model.

    Args:
        plant_capacity_mw (float): Capacity of the run-of-river hydropower plant in MW.
        water_density (float): Density of water in kg/m^3.
        acceleration_gravity (float): Acceleration due to gravity in m/s^2.
        turbine_efficiency (float): Efficiency of the turbine as a decimal.
        head (float): Head of the water in meters.
        flow_rate (list): Flow rate of water in m^3/s.
    """

    plant_capacity_mw: float = field()
    water_density: float = field()
    acceleration_gravity: float = field()
    turbine_efficiency: float = field()
    head: float = field()


class RunOfRiverHydroPerformanceModel(HydroPerformanceBaseClass):
    """
    An OpenMDAO component for modeling the performance of a run-of-river hydropower plant.
    Computes annual electricity production based on water flow rate and turbine efficiency.
    """

    def initialize(self):
        super().initialize()

    def setup(self):
        super().setup()
        n_timesteps = self.options["plant_config"]["plant"]["simulation"]["n_timesteps"]
        self.config = RunOfRiverHydroPerformanceConfig.from_dict(
            merge_shared_inputs(self.options["tech_config"]["model_inputs"], "performance")
        )

        self.add_input("discharge", val=0.0, shape=n_timesteps, units="m**3/s")

    def compute(self, inputs, outputs):
        # Calculate the power output of the run-of-river hydropower plant
        power_output = (
            self.config.water_density
            * self.config.acceleration_gravity
            * self.config.turbine_efficiency
            * self.config.head
            * inputs["discharge"]  # m^3/s
        ) / 1e3  # Convert to kW

        # power_output can't be greater than plant_capacity_mw
        plant_capacity_kw = self.config.plant_capacity_mw * 1e3
        power_output = np.clip(power_output, 0, plant_capacity_kw)

        # Distribute the power output over the number of time steps
        outputs["electricity_out"] = power_output


@define(kw_only=True)
class RunOfRiverHydroCostConfig(CostModelBaseConfig):
    """Configuration class for the RunOfRiverHydroCostComponent.
    This class defines the parameters for the run-of-river hydropower plant cost model.

    Args:
        plant_capacity_mw (float): Capacity of the run-of-river hydropower plant in MW.
        capital_cost_usd_per_kw (float): Capital cost of the run-of-river plant in USD/kW.
        operational_cost_usd_per_kw_year (float): Operational cost as a percentage of total
            capacity, expressed in USD/kW/year.
        cost_year (int): dollar-year for input costs
    """

    plant_capacity_mw: float = field()
    capital_cost_usd_per_kw: float = field()
    operational_cost_usd_per_kw_year: float = field()


class RunOfRiverHydroCostModel(CostModelBaseClass):
    """
    An OpenMDAO component that calculates the capital expenditure (CapEx) for a run-of-river
        hydropower plant.

    Just a placeholder for now, but can be extended with more detailed cost models.
    """

    def setup(self):
        self.config = RunOfRiverHydroCostConfig.from_dict(
            merge_shared_inputs(self.options["tech_config"]["model_inputs"], "cost")
        )

        super().setup()

    def compute(self, inputs, outputs, discrete_inputs, discrete_outputs):
        capex_kw = self.config.capital_cost_usd_per_kw
        total_capacity_kw = self.config.plant_capacity_mw * 1e3

        outputs["CapEx"] = capex_kw * total_capacity_kw
        outputs["OpEx"] = self.config.operational_cost_usd_per_kw_year * total_capacity_kw
