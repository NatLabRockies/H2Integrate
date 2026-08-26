import numpy as np
from attrs import field, define, validators

from h2integrate.core.utilities import BaseConfig, merge_shared_inputs
from h2integrate.tools.constants import HHV_H2_MJ_PER_KG
from h2integrate.core.model_baseclasses import (
    CostModelBaseClass,
    CostModelBaseConfig,
    PerformanceModelBaseClass,
)


@define(kw_only=True)
class LinearH2FuelCellPerformanceConfig(BaseConfig):
    """Configuration class for the hydrogen fuel cell performance model.

    Attributes:
        system_capacity_kw (float): The capacity of the fuel cell system in kilowatts (kW).
        fuel_cell_efficiency_hhv (float): The higher heating value efficiency of the
            fuel cell (0 <= efficiency <= 1).
        uptime_hours_until_eol (int): Number of "on" hours until the fuel cell reaches
            end-of-life (EOL).
    """

    system_capacity_kw: float = field(validator=validators.ge(0))
    fuel_cell_efficiency_hhv: float = field(validator=(validators.ge(0), validators.le(1)))
    uptime_hours_until_eol: int = field(validator=validators.ge(0))


class LinearH2FuelCellPerformanceModel(PerformanceModelBaseClass):
    """
    Performance model for a hydrogen fuel cell.

    The model implements the relationship:
    electricity_out = hydrogen_in * fuel_cell_efficiency_hhv * HHV_hydrogen

    where:
    - hydrogen_in is the mass flow rate of hydrogen in kg/hr
    - fuel_cell_efficiency is the efficiency of the fuel cell (0 <= efficiency <= 1)
    - HHV_hydrogen is the higher heating value of hydrogen (approximately 142 MJ/kg)
    """

    _time_step_bounds = (
        3600,
        3600,
    )  # (min, max) time step lengths (in seconds) compatible with this model
    _control_classifier = "dispatchable"

    def initialize(self):
        super().initialize()
        self.commodity = "electricity"
        self.commodity_rate_units = "kW"
        self.commodity_amount_units = "kW*h"

    def setup(self):
        super().setup()

        self.config = LinearH2FuelCellPerformanceConfig.from_dict(
            merge_shared_inputs(self.options["tech_config"]["model_inputs"], "performance"),
            additional_cls_name=self.__class__.__name__,
        )

        # Add natural gas input, default to 0 --> set using feedstock component
        # or upstream hydrogen converter component
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

        # Add rated capacity as an input with config value as default
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

        # Default the electricity command value input as the rated capacity
        self.add_input(
            f"{self.commodity}_command_value",
            val=self.config.system_capacity_kw,
            shape=self.n_timesteps,
            units=self.commodity_rate_units,
            desc="Electricity command value for natural gas plant",
        )

    def compute(self, inputs, outputs):
        """
        Compute electricity output from the fuel cell based on hydrogen input
            and fuel cell HHV efficiency.

        Args:
            inputs: OpenMDAO inputs object containing hydrogen_in, fuel cell
                HHV efficiency, electricity_command_value, and system_capacity.
            outputs: OpenMDAO outputs object for electricity_out,
                hydrogen_consumed, and replacement_schedule.
        """

        # calculate max input and output
        system_capacity = inputs["system_capacity"]  # plant capacity in kW
        hydrogen_in = inputs["hydrogen_in"]  # kg/h
        fuel_cell_efficiency = inputs["fuel_cell_efficiency"]

        # conversion factor: kW electricity to kg/h hydrogen, units: (kg/h)/kW
        kw_to_kgh_h2 = (3600.0 * 0.001) / (fuel_cell_efficiency * HHV_H2_MJ_PER_KG)

        max_h2_consumption = system_capacity * kw_to_kgh_h2

        # electrical command value, saturated at maximum rated system capacity
        electricity_command_value = np.where(
            inputs["electricity_command_value"] > system_capacity,
            system_capacity,
            inputs["electricity_command_value"],
        )

        h2_demand = electricity_command_value * kw_to_kgh_h2

        # available feedstock, saturated at maximum system feedstock consumption
        h2_available = np.where(
            inputs["hydrogen_in"] > max_h2_consumption,
            max_h2_consumption,
            inputs["hydrogen_in"],
        )

        # h2 consumed is minimum between available feedstock and output demand
        hydrogen_in = np.minimum(h2_available, h2_demand)

        # make any negative hydrogen input zero
        hydrogen_in = np.maximum(hydrogen_in, 0.0)

        # calculate electricity output in kW
        electricity_out_kw = hydrogen_in / kw_to_kgh_h2

        # calculate replacement schedule based on cumulative "on" hours, where "on" hours
        # are timesteps where electricity output is greater than zero
        n_hours_eol = self.config.uptime_hours_until_eol
        on_off_status = np.where(electricity_out_kw > 0, 1, 0)

        # Calculate cumulative hours and find all crossings of n_hours_eol multiples
        cumsum_hours = np.cumsum(np.tile(on_off_status, self.plant_life))

        # Find all replacement thresholds (n_hours_eol, 2*n_hours_eol, 3*n_hours_eol, ...)
        max_hours = np.max(cumsum_hours)
        n_replacements = int(max_hours / n_hours_eol)

        # For each replacement threshold, find the first index where cumsum >= threshold
        i_replace = []
        for k in range(1, n_replacements + 1):
            threshold = k * n_hours_eol
            # Find first index where cumsum >= threshold
            idx = np.searchsorted(cumsum_hours, threshold, side="left")
            if idx < len(cumsum_hours):
                i_replace.append(idx)

        i_replace = np.array(i_replace) if i_replace else np.array([], dtype=int)

        # Convert indices to years and count replacements per year
        refurb_schedule = np.zeros(self.plant_life)
        for idx in i_replace:
            year = int(np.floor(idx / self.n_timesteps))
            if 0 <= year < self.plant_life:
                refurb_schedule[year] += 1

        # The replacement_schedule is the number of refurbishments that occur in each year (0, 1, or
        # more if several thresholds are crossed within a single year). The portion of capex of the
        # total capacity that is replaced per refurbishment is given by the users in the tech_config
        # as replacement_cost_percent.
        # The replacement_schedule may be used in the finance model if the replacement_cost_percent
        # is specified in the tech_config under
        # ['model_inputs']['finance_parameters']['capital_items']['replacement_cost_percent']
        outputs["replacement_schedule"] = refurb_schedule

        # clip the electricity output to the system capacity
        outputs["electricity_out"] = np.minimum(electricity_out_kw, system_capacity)
        outputs["total_electricity_produced"] = np.sum(outputs["electricity_out"]) * (
            self.dt / 3600
        )
        outputs["rated_electricity_production"] = system_capacity
        outputs["annual_electricity_produced"] = outputs["total_electricity_produced"] * (
            1 / self.fraction_of_year_simulated
        )
        outputs["capacity_factor"] = outputs["total_electricity_produced"] / (
            system_capacity * self.n_timesteps * (self.dt / 3600)
        )
        outputs["hydrogen_consumed"] = outputs["electricity_out"] * kw_to_kgh_h2


@define(kw_only=True)
class H2FuelCellCostConfig(CostModelBaseConfig):
    """Configuration class for the hydrogen fuel cell cost model.

    Attributes:
        system_capacity_kw (float): The capacity of the fuel cell system in kilowatts (kW).
        capex_per_kw (float): Capital cost per unit of capacity in USD/kW.
        fixed_opex_per_kw_per_year (float): Fixed operating expenses per unit of capacity per year
            in USD/(kW*year).
        variable_opex_per_kwh (float): Variable operating expenses per unit of electricity
            produced in USD/(kW*h).
    """

    system_capacity_kw: float = field(validator=validators.ge(0))
    capex_per_kw: float = field(validator=validators.ge(0))
    fixed_opex_per_kw_per_year: float = field(validator=validators.ge(0))
    variable_opex_per_kwh: float = field(validator=validators.ge(0))


class H2FuelCellCostModel(CostModelBaseClass):
    """
    Cost model for a hydrogen fuel cell system.

    The model calculates capital and fixed operating costs based on system capacity and
    specified cost parameters.
    """

    _time_step_bounds = (
        3600,
        3600,
    )  # (min, max) time step lengths (in seconds) compatible with this model

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

        self.add_input(
            "unit_varopex",
            val=self.config.variable_opex_per_kwh,
            units="USD/(kW*h)",
            desc="Variable operating expenses per unit of electricity produced",
        )

        self.add_input(
            "annual_electricity_produced",
            val=0.0,
            shape=self.plant_life,
            units="(kW*h)/year",
        )

    def compute(self, inputs, outputs, discrete_inputs, discrete_outputs):
        """
        Compute capital, fixed operating, and variable operating costs for the fuel cell system.

        Args:
            inputs: OpenMDAO inputs object containing system_capacity, unit_capex,
                fixed_opex_per_year, unit_varopex, and annual_electricity_produced.
            outputs: OpenMDAO outputs object for CapEx, OpEx, and VarOpEx.
        """

        system_capacity_kw = inputs["system_capacity"]

        # Calculate capital cost
        outputs["CapEx"] = system_capacity_kw * inputs["unit_capex"]

        # Calculate fixed operating cost per year
        outputs["OpEx"] = system_capacity_kw * inputs["fixed_opex_per_year"]

        # Calculate variable operating cost per year
        outputs["VarOpEx"] = inputs["annual_electricity_produced"] * inputs["unit_varopex"]
