import numpy as np
from attrs import field, define

from h2integrate.core.utilities import BaseConfig, merge_shared_inputs
from h2integrate.core.validators import gte_zero
from h2integrate.tools.constants import H_MW, O2_MW, faraday
from h2integrate.core.model_baseclasses import (
    CostModelBaseClass,
    CostModelBaseConfig,
    PerformanceModelBaseClass,
)


@define(kw_only=True)
class PEMH2FuelCellPerformanceConfig(BaseConfig):
    """Configuration class for the hydrogen fuel cell performance model.

    Attributes:
        system_capacity_kw (float): The capacity of the fuel cell system in kilowatts (kW).
        n_stacks (int): The number of stacks in the fuel cell system.
        stack_temperature_K (float): The operating temperature of the fuel cell stack in Kelvin (K).
    """

    # TODO: how to size the fuel cell? N_cells + N_stacks?
    # How does N_cells translate to electricity rating?

    system_capacity_kw: float = field(validator=gte_zero)
    n_stacks: int
    stack_temperature_K: float
    hhv: float
    # min_system_power_fraction_kw: float
    # fuel_cell_efficiency_hhv: float = field(validator=range_val(0, 1))


def calc_current(system_power_reference, cell_area, n_cells, n_stacks):
    """_summary_

    Args:
        system_power_reference (np.ndarray): power demanded of the entire system in W
        cell_area (float): cell active area in cm^2
        n_cells (int): number of cells per stack
        n_stacks (int): number of stacks in the system

    Returns:
            tuple(np.ndarray, np.poly1d): stack current and
                function to convert from current density to voltage
    """
    # Calculates the current and voltage from IV curve based on power reference
    #   These current, voltage and power values are from the fuel cell data collected here: https://github.com/ECSIM/pem-dataset1
    #   Using the data from the "Activation Test MEA Standard Protocol (Repeat)" case
    J_curve = np.array([0.0356, 0.05413333, 0.0796, 0.11366667, 0.244, 0.454])  # in A/cm^2
    voltage_curve = np.array([0.987, 0.936, 0.884, 0.838, 0.786, 0.736])  # in V
    power_curve = (
        np.array([35.16666667, 50.53333333, 70.33333333, 95.46666667, 191.66666667, 334.33333333])
        / 1e3
    )  # in W/cm^2

    # Function to calculate voltage from current density
    V_coefs = np.polyfit(J_curve, voltage_curve, 5)
    V_J_curve = np.poly1d(V_coefs)

    # Function to calculate current density from power
    stack_P_curve = power_curve * cell_area * n_cells
    J_coefs = np.polyfit(stack_P_curve, J_curve, 5)
    J_P_curve = np.poly1d(J_coefs)

    # Calculate power per stack and power density
    power_per_stack = system_power_reference / n_stacks  # in Watts

    # Create power/current density relationship curve
    stack_current_density = J_P_curve(power_per_stack)
    stack_current = stack_current_density * cell_area * n_cells  # in A
    stack_current = np.clip(stack_current, a_min=0.0, a_max=None)  # clip negative values

    return stack_current, V_J_curve


class PEMH2FuelCellPerformanceModel(PerformanceModelBaseClass):
    """
    Performance model for a PEM hydrogen fuel cell.

    The model simulates electrochemical conversion of hydrogen and oxygen into electricity
    and water. It calculates:
    - hydrogen and oxygen consumption based on electrochemical reactions
    - water production as a byproduct
    - electricity output based on system capacity and operational conditions

    Inputs:
    - hydrogen_in: mass flow rate of hydrogen (kg/h)
    - oxygen_in: mass flow rate of oxygen (kg/h)
    - stack_temperature: operating temperature of the fuel cell stack (K)
    - system_capacity: rated capacity of the fuel cell system (kW)

    Outputs:
    - hydrogen_consumed: hydrogen consumption rate (kg/h)
    - oxygen_consumed: oxygen consumption rate (kg/h)
    - water_out: water production rate (kg/h)
    - electricity_out: electricity output (kW)
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

        self.config = PEMH2FuelCellPerformanceConfig.from_dict(
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
            "oxygen_in",
            val=0.0,
            shape=self.n_timesteps,
            units="kg/h",
        )

        self.add_input(
            "stack_temperature",
            val=self.config.stack_temperature_K,
            units="K",
            desc="Operating temperature of the stack",
        )

        # Add rated capacity as an input with config value as default
        self.add_input(
            "system_capacity",
            val=self.config.system_capacity_kw,
            units="kW",
            desc="Rated electricity production of the PEM fuel cell system",
        )

        self.add_output(
            "hydrogen_consumed",
            val=0.0,
            shape=self.n_timesteps,
            units=f"kg/({self.dt}*s)",
            desc="Mass flow rate of hydrogen consumed by the fuel cell",
        )

        self.add_output(
            "oxygen_consumed",
            val=0.0,
            shape=self.n_timesteps,
            units=f"kg/({self.dt}*s)",
            desc="Mass flow rate of oxygen consumed by the fuel cell",
        )

        self.add_output(
            "water_out",
            val=0.0,
            shape=self.n_timesteps,
            units=f"kg/({self.dt}*s)",
            desc="Mass flow rate of water produced by the fuel cell",
        )

        self.add_output(
            "heat_out",
            val=0.0,
            shape=self.n_timesteps,
            units=self.commodity_rate_units,
            desc="Heat generated by the fuel cell",
        )

        self.add_output(
            "rated_h2_consumed",
            val=0.0,
            units=f"kg/({self.dt}*s)",
            desc="Rated hydrogen consumed by the fuel cell",
        )

        self.add_output(
            "rated_o2_consumed",
            val=0.0,
            units=f"kg/({self.dt}*s)",
            desc="Rated oxygen consumed by the fuel cell",
        )

        self.add_output(
            "rated_water_out",
            val=0.0,
            units=f"kg/({self.dt}*s)",
            desc="Rated water produced by the fuel cell",
        )

        self.add_output(
            "rated_heat_out",
            val=0.0,
            units=self.commodity_rate_units,
            desc="Rated heat generated by the fuel cell",
        )

        # Default the electricity command value input as the rated capacity
        self.add_input(
            f"{self.commodity}_command_value",
            val=self.config.system_capacity_kw,
            shape=self.n_timesteps,
            units=self.commodity_rate_units,
            desc="Electricity command value for PEM fuel cell",
        )

    def compute(self, inputs, outputs):
        """
        Compute electricity output from the fuel cell based on hydrogen and oxygen input.

        Uses I-V curve characteristics to calculate fuel cell current and voltage,
        then computes hydrogen consumed, oxygen consumed, and water generated for
        each timestep based on electrochemical reactions.

        Args:
            inputs: OpenMDAO inputs object containing hydrogen_in, oxygen_in,
                stack_temperature, electricity_command_value, and system_capacity.
            outputs: OpenMDAO outputs object for electricity_out, hydrogen_consumed,
                oxygen_consumed, water_out, and various electricity production quantities.
        """

        # Set calculation constants:
        M_H2 = H_MW * 2 / 1000  # Molar mass of H2 in kg/mol
        M_O2 = O2_MW / 1000  # Molar mass of O2 in kg/mol
        M_H2O = M_H2 + M_O2 / 2  # Molar mass of H2O in kg/mol
        # Electron transfer constants
        n_h2 = 2  # number of electrons transferred per mole of H2
        n_o2 = 4  # number of electrons transferred per mole of O2
        n_h2o = 2  # number of electrons transferred per mole of H2O

        # Sizing the cells
        max_cell_power_density = 0.000334  # in W/cm^2
        stack_size = inputs["system_capacity"][0] / self.config.n_stacks
        cell_active_area = 400  # [cm^2] from Battelle (https://www.energy.gov/sites/prod/files/2018/02/f49/fcto_battelle_mfg_cost_analysis_1%20_to_25kw_pp_chp_fc_systems_jan2017_0.pdf)
        n_cells = round(stack_size / (cell_active_area * max_cell_power_density))
        # Recalculate the rated power production based on final fuel cell sizing
        rated_power_production = (
            max_cell_power_density * n_cells * cell_active_area * self.config.n_stacks
        )

        # Calculate the rated outputs of the system
        rated_I_stack, _ = calc_current(
            rated_power_production * 1e3, cell_active_area, n_cells, self.config.n_stacks
        )  # in A per stack
        rated_I_cell = rated_I_stack / n_cells  # in A per cell
        rated_h2_consumed = ((rated_I_cell * M_H2) / (n_h2 * faraday)) * (
            self.dt * self.config.n_stacks * n_cells
        )  # kg/time step
        rated_o2_consumed = ((rated_I_cell * M_O2) / (n_o2 * faraday)) * (
            self.dt * self.config.n_stacks * n_cells
        )  # kg/time step
        rated_h2o_out = ((rated_I_cell * M_H2O) / (n_h2o * faraday)) * (
            self.dt * self.config.n_stacks * n_cells
        )  # kg/time step
        rated_heat_out = rated_h2_consumed * self.config.hhv - rated_power_production  # in kW

        ################## Model Calculations ##################
        # 1. Receive power setpoint into fuel cell
        power_reference = np.clip(
            inputs[f"{self.commodity}_command_value"], a_min=0.0, a_max=rated_power_production
        )  # in commodity rate units (kW)

        # 2. Find stack current from power reference
        commanded_I_stack, V_J_curve = calc_current(
            power_reference * 1e3, cell_active_area, n_cells, self.config.n_stacks
        )  # in A

        # 3. Find available hydrogen and oxygen for each timestep
        h2_in_kg_per_s = inputs["hydrogen_in"] / 3600  # convert from kg/h to kg/s
        o2_in_kg_per_s = inputs["oxygen_in"] / 3600  # convert from kg/h to kg/s

        # convert from kg/s to A per stack - current that feedstocks in can support
        I_stack_from_h2 = (h2_in_kg_per_s * n_h2 * faraday) / (M_H2 * self.config.n_stacks)
        I_stack_from_o2 = (o2_in_kg_per_s * n_o2 * faraday) / (M_O2 * self.config.n_stacks)

        # 4. Take minimum current from power reference, hydrogen available, and oxygen available
        I_stack = np.minimum(commanded_I_stack, np.minimum(I_stack_from_h2, I_stack_from_o2))
        # in Amps per stack

        # 5. Calculate current density and voltage from I-V curve, all of these are per stack
        J_cell = I_stack / (cell_active_area * n_cells)  # in A/cm^2
        I_cell = J_cell * cell_active_area  # in A
        V_cell = V_J_curve(J_cell)  # in V

        # 6. Calculate power output from current and voltage
        power_out = V_cell * I_cell * n_cells * self.config.n_stacks / 1e3
        # Calculated in Watts, then converted to kW

        # 7. Calculate hydrogen and oxygen consumed and water produced
        #       based on electrochemical reactions
        h2_consumed = ((I_cell * M_H2) / (n_h2 * faraday)) * (
            self.dt * self.config.n_stacks * n_cells
        )  # kg/time step
        o2_consumed = ((I_cell * M_O2) / (n_o2 * faraday)) * (
            self.dt * self.config.n_stacks * n_cells
        )  # kg/time step
        h2o_generated = ((I_cell * M_H2O) / (n_h2o * faraday)) * (
            self.dt * self.config.n_stacks * n_cells
        )  # kg/time step

        # 8. Calculate heat generation from fuel cell
        heat_generated = inputs["hydrogen_in"] * self.config.hhv - power_out  # in kW

        # Set Outputs
        # clip the electricity output to the system capacity
        outputs["rated_electricity_production"] = rated_power_production

        outputs["electricity_out"] = np.minimum(power_out, rated_power_production)
        outputs["total_electricity_produced"] = np.sum(outputs["electricity_out"]) * (
            self.dt / 3600
        )
        outputs["annual_electricity_produced"] = outputs["total_electricity_produced"] * (
            1 / self.fraction_of_year_simulated
        )
        outputs["capacity_factor"] = outputs["total_electricity_produced"] / (
            rated_power_production * self.n_timesteps * (self.dt / 3600)
        )
        outputs["hydrogen_consumed"] = h2_consumed
        outputs["oxygen_consumed"] = o2_consumed
        outputs["water_out"] = h2o_generated
        outputs["heat_out"] = heat_generated

        # Set rated outputs
        outputs["rated_h2_consumed"] = rated_h2_consumed
        outputs["rated_o2_consumed"] = rated_o2_consumed
        outputs["rated_water_out"] = rated_h2o_out
        outputs["rated_heat_out"] = rated_heat_out

        # TODO: implement a hydrogen and oxygen conversion efficiency based on stack
        #   temperature and other factors


@define(kw_only=True)
class PEMH2FuelCellCostConfig(CostModelBaseConfig):
    """Configuration class for the hydrogen fuel cell cost model.

    TODO: update doc string
    Fields include `system_capacity_kw`, `capex_stack_per_kw`, `capex_hydrogen_supply_per_kw`,
    `capex_air_supply_per_kw`, `capex_cooling_per_kw`, `capex_controls_instrumentation_per_kw`,
    `capex_electrical_per_kw`, `capex_assembly_per_kw`, `capex_additional_labor_per_kw`,
    and `fixed_opex_per_kw_per_year`. The `cost_year` field is inherited from `CostModelBaseConfig`.
    """

    # system_capacity_kw: float = field(validator=gte_zero)
    capex_stack_per_kw: float = field(validator=gte_zero)
    capex_hydrogen_supply_per_kw: float = field(validator=gte_zero, default=0.0)
    capex_air_supply_per_kw: float = field(validator=gte_zero)
    capex_cooling_per_kw: float = field(validator=gte_zero)
    capex_controls_instrumentation_per_kw: float = field(validator=gte_zero)
    capex_electrical_per_kw: float = field(validator=gte_zero)
    capex_assembly_per_kw: float = field(validator=gte_zero)
    capex_additional_labor_per_kw: float = field(validator=gte_zero)
    capex_battery_total: float = field(validator=gte_zero)
    fixed_opex_per_kw_per_year: float = field(validator=gte_zero)


class PEMH2FuelCellCostModel(CostModelBaseClass):
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
        self.config = PEMH2FuelCellCostConfig.from_dict(
            merge_shared_inputs(self.options["tech_config"]["model_inputs"], "cost"),
            additional_cls_name=self.__class__.__name__,
        )

        super().setup()

        self.add_input(
            "rated_electricity_production",
            val=0.0,
            units="kW",
            desc="Capacity of the h2 fuel cell system",
        )

        self.add_input(
            "unit_capex",
            val=self.config.capex_stack_per_kw
            + self.config.capex_hydrogen_supply_per_kw
            + self.config.capex_air_supply_per_kw
            + self.config.capex_cooling_per_kw
            + self.config.capex_controls_instrumentation_per_kw
            + self.config.capex_electrical_per_kw
            + self.config.capex_assembly_per_kw
            + self.config.capex_additional_labor_per_kw,
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
            inputs: OpenMDAO inputs object containing rated_electricity_production.
            outputs: OpenMDAO outputs object for capital_cost and fixed_operating_cost_per_year.
        """

        system_capacity_kw = inputs["rated_electricity_production"]

        # Calculate capital cost
        outputs["CapEx"] = (
            system_capacity_kw * inputs["unit_capex"] + self.config.capex_battery_total
        )

        # Calculate fixed operating cost per year
        outputs["OpEx"] = system_capacity_kw * inputs["fixed_opex_per_year"]
