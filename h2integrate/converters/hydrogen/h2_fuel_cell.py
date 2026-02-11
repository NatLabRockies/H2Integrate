import numpy as np
from attrs import field, define

from h2integrate.core.utilities import BaseConfig, merge_shared_inputs
from h2integrate.core.validators import gte_zero, range_val
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
        fuel_cell_efficiency (float): The efficiency of the fuel cell (0 <= efficiency <= 1).
    """

    system_capacity_kw: float = field(validator=gte_zero)
    fuel_cell_efficiency: float = field(validator=range_val(0, 1))


class H2FuelCellPerformanceModel(PerformanceModelBaseClass):
    """
    Performance model for a hydrogen fuel cell.

    The model implements the relationship:
    electricity_out = hydrogen_in * fuel_cell_efficiency * LHV_hydrogen

    where:
    - hydrogen_in is the mass flow rate of hydrogen in kg/hr
    - fuel_cell_efficiency is the efficiency of the fuel cell (0 <= efficiency <= 1)
    - LHV_hydrogen is the lower heating value of hydrogen (approximately 120 MJ/kg)
    """

    def initialize(self):
        super().initialize()
        self.commodity = "hydrogen"
        self.commodity_rate_units = "kg/h"
        self.commodity_amount_units = "kg"

    def setup(self):
        super().setup()

        self.config = H2FuelCellPerformanceConfig.from_dict(
            merge_shared_inputs(self.options["tech_config"]["model_inputs"], "performance"),
            additional_cls_name=self.__class__.__name__,
        )

        n_timesteps = self.options["plant_config"]["plant"]["simulation"]["n_timesteps"]

        self.add_input(
            f"{self.commodity}_in",
            val=0.0,
            shape=n_timesteps,
            units=self.commodity_rate_units,
        )

        self.add_input(
            "fuel_cell_efficiency",
            val=self.config.fuel_cell_efficiency,
            units=None,
            desc="Efficiency of the fuel cell (0 <= efficiency <= 1)",
        )

        self.add_input(
            "system_capacity",
            val=self.config.system_capacity_kw,
            units="kW",
            desc="Capacity of the h2 fuel cell system",
        )

        self.add_output(
            "electricity_out",
            val=0.0,
            shape=n_timesteps,
            units="kW",
            desc="Electricity output from the fuel cell",
        )

    def compute(self, inputs, outputs):
        """
        Compute electricity output from the fuel cell based on hydrogen input
            and fuel cell efficiency.

        Args:
            inputs: OpenMDAO inputs object containing hydrogen_in, fuel cell efficiency,
                and system_capacity.
            outputs: OpenMDAO outputs object for electricity_out.
        """

        hydrogen_in = inputs["hydrogen_in"]  # kg/h
        fuel_cell_efficiency = inputs["fuel_cell_efficiency"]
        system_capacity_kw = inputs["system_capacity"]

        LHV_hydrogen = 120.0  # MJ/kg

        # make any negative hydrogen input zero
        hydrogen_in = np.maximum(hydrogen_in, 0.0)

        # calculate electricity output in kW
        electricity_out_kw = hydrogen_in * fuel_cell_efficiency * LHV_hydrogen / (3600.0 * 0.001)
        # kW = kg/h * - * MJ/kg * (1 h / 3600 s) * (1 kW / 0.001 MJ/s)

        # clip the electricity output to the system capacity
        outputs["electricity_out"] = np.minimum(electricity_out_kw, system_capacity_kw)


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

    def compute(self, inputs, outputs, discrete_inputs, discrete_outputs):
        """
        Compute capital and fixed operating costs for the fuel cell system.

        Args:
            inputs: OpenMDAO inputs object containing system_capacity.
            outputs: OpenMDAO outputs object for capital_cost and fixed_operating_cost_per_year.
        """

        system_capacity_kw = inputs["system_capacity"]

        # Calculate capital cost
        outputs["CapEx"] = system_capacity_kw * inputs["capex_per_kw"]

        # Calculate fixed operating cost per year
        outputs["OpEx"] = system_capacity_kw * inputs["fixed_opex_per_kw_per_year"]
