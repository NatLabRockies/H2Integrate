import numpy as np
from attrs import field, define

from h2integrate.core.utilities import BaseConfig, merge_shared_inputs
from h2integrate.core.validators import gte_zero, range_val
from h2integrate.tools.constants import HHV_H2_MJ_PER_KG
from h2integrate.core.model_baseclasses import (
    CostModelBaseClass,
    CostModelBaseConfig,
    PerformanceModelBaseClass,
)


@define(kw_only=True)
class H2FuelCellPerformanceConfig(BaseConfig):
    """Configuration class for the hydrogen fuel cell performance model.

    Attributes:
        system_capacity_kw (float): The capacity of the fuel cell system in kilowatts (kW).
        fuel_cell_efficiency_hhv (float): The higher heating value efficiency of the
            fuel cell (0 <= efficiency <= 1).
    """

    system_capacity_kw: float = field(validator=gte_zero)
    fuel_cell_efficiency_hhv: float = field(validator=range_val(0, 1))


class H2FuelCellPerformanceModel(PerformanceModelBaseClass):
    """
    Performance model for a hydrogen fuel cell.

    The model implements the relationship:
    electricity_out = hydrogen_in * fuel_cell_efficiency_hhv * HHV_hydrogen

    where:
    - hydrogen_in is the mass flow rate of hydrogen in kg/hr
    - fuel_cell_efficiency is the efficiency of the fuel cell (0 <= efficiency <= 1)
    - HHV_hydrogen is the higher heating value of hydrogen (approximately 142 MJ/kg)
    """

    def initialize(self):
        super().initialize()
        self.commodity = "electricity"
        self.commodity_rate_units = "kW"
        self.commodity_amount_units = "kW*h"

    def setup(self):
        super().setup()

        self.config = H2FuelCellPerformanceConfig.from_dict(
            merge_shared_inputs(self.options["tech_config"]["model_inputs"], "performance"),
            additional_cls_name=self.__class__.__name__,
        )

        self.add_input(
            "hydrogen_in",
            val=0.0,
            shape=self.n_timesteps,
            units="kg/h",
        )

        self.add_input(
            "fuel_cell_efficiency",
            val=self.config.fuel_cell_efficiency_hhv,
            units=None,
            desc="HHV efficiency of the fuel cell (0 <= efficiency <= 1)",
        )

        self.add_input(
            "system_capacity",
            val=self.config.system_capacity_kw,
            units="kW",
            desc="Capacity of the h2 fuel cell system",
        )

        self.add_output(
            "hydrogen_consumed",
            val=0.0,
            shape=self.n_timesteps,
            units="kg/h",
            desc="Mass flow rate of hydrogen consumed by the fuel cell",
        )

    def compute(self, inputs, outputs):
        """
        Compute electricity output from the fuel cell based on hydrogen input
            and fuel cell HHV efficiency.

        Args:
            inputs: OpenMDAO inputs object containing hydrogen_in, fuel cell
                HHV efficiency,and system_capacity.
            outputs: OpenMDAO outputs object for electricity_out,
                hydrogen_consumed.
        """

        hydrogen_in = inputs["hydrogen_in"]  # kg/h
        fuel_cell_efficiency = inputs["fuel_cell_efficiency"]
        system_capacity_kW = inputs["system_capacity"]

        # make any negative hydrogen input zero
        hydrogen_in = np.maximum(hydrogen_in, 0.0)

        # calculate electricity output in kW
        electricity_out_kw = (
            hydrogen_in * fuel_cell_efficiency * HHV_H2_MJ_PER_KG / (3600.0 * 0.001)
        )
        # kW = kg/h * - * MJ/kg * (1 h / 3600 s) * (1 kW / 0.001 MJ/s)

        # clip the electricity output to the system capacity
        outputs["electricity_out"] = np.minimum(electricity_out_kw, system_capacity_kW)
        outputs["total_electricity_produced"] = np.sum(outputs["electricity_out"]) * (
            self.dt / 3600
        )
        outputs["rated_electricity_production"] = system_capacity_kW
        outputs["annual_electricity_produced"] = outputs["total_electricity_produced"] * (
            1 / self.fraction_of_year_simulated
        )
        outputs["capacity_factor"] = outputs["total_electricity_produced"] / (
            system_capacity_kW * self.n_timesteps * (self.dt / 3600)
        )
        outputs["hydrogen_consumed"] = outputs["electricity_out"] / (
            fuel_cell_efficiency * HHV_H2_MJ_PER_KG / (3600.0 * 0.001)
        )


@define(kw_only=True)
class H2FuelCellCostConfig(CostModelBaseConfig):
    """Configuration class for the hydrogen fuel cell cost model.

    Attributes:
        system_capacity_kw (float): The capacity of the fuel cell system in kilowatts (kW).

        capex_per_kw (float): Capital expenditure per kilowatt of fuel cell capacity.

        fixed_opex_per_kw_per_year (float|int): Fixed operating expenses per unit capacity
            in $/kW/year. This includes fixed O&M costs that don't vary with generation.

        cost_year (int): Dollar year corresponding to input costs.
    """

    system_capacity_kw: float = field(validator=gte_zero)
    capex_per_kw: float = field(validator=gte_zero)
    fixed_opex_per_kw_per_year: float = field(validator=gte_zero)


class H2FuelCellCostModel(CostModelBaseClass):
    """
    Cost model for a hydrogen fuel cell system.

    The model calculates capital and fixed operating costs based on system capacity and
    specified cost parameters.
    """

    def setup(self):
        self.config = H2FuelCellCostConfig.from_dict(
            merge_shared_inputs(self.options["tech_config"]["model_inputs"], "cost"),
            additional_cls_name=self.__class__.__name__,
        )

        super().setup()

        self.add_input(
            "system_capacity",
            val=self.config.system_capacity_kw,
            units="kW",
            desc="Capacity of the h2 fuel cell system",
        )

        self.add_input(
            "unit_capex",
            val=self.config.capex_per_kw,
            units="USD/kW",
            desc="Capital cost per unit capacity",
        )

        self.add_input(
            "fixed_opex_per_year",
            val=self.config.fixed_opex_per_kw_per_year,
            units="(USD/kW)/year",
            desc="Fixed operating expenses per unit capacity per year",
        )

    def compute(self, inputs, outputs, discrete_inputs, discrete_outputs):
        """
        Compute capital and fixed operating costs for the fuel cell system.

        Args:
            inputs: OpenMDAO inputs object containing system_capacity.
            outputs: OpenMDAO outputs object for capital_cost and fixed_operating_cost_per_year.
        """

        system_capacity_kw = inputs["system_capacity"]

        # Calculate capital cost
        outputs["CapEx"] = system_capacity_kw * inputs["unit_capex"]

        # Calculate fixed operating cost per year
        outputs["OpEx"] = system_capacity_kw * inputs["fixed_opex_per_year"]
