import numpy as np
from attrs import field, define

from h2integrate.core.utilities import BaseConfig, merge_shared_inputs
from h2integrate.core.validators import gte_zero
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
    # min_system_power_fraction_kw: float
    # fuel_cell_efficiency_hhv: float = field(validator=range_val(0, 1))


def calc_current(power_ref, cell_area, n_cells, stack_number):
    # Calculates the current and voltage from IV curve based on power reference
    current_curve = [
        0.0356,
        0.05413333,
        0.0796,
        0.11366667,
        0.244,
        0.454,
        # 0.70366667,
        # 0.96933333,
        # 1.24,
        # 1.52666667,
        # 1.80333333,
        # 2.07,
        # 2.32,
        # 2.54333333,
        # 2.73666667,
        # 2.9,
    ]  # in A
    voltage_curve = [
        0.987,
        0.936,
        0.884,
        0.838,
        0.786,
        0.736,
        # 0.686,
        # 0.636,
        # 0.586,
        # 0.53566667,
        # 0.486,
        # 0.436,
        # 0.386,
        # 0.33533333,
        # 0.286,
        # 0.236,
    ]  # in V
    power_curve = [
        35.16666667,
        50.53333333,
        70.33333333,
        95.46666667,
        191.66666667,
        334.33333333,
        # 482.66666667,
        # 616.66666667,
        # 729.0,
        # 817.0,
        # 875.33333333,
        # 902.0,
        # 895.0,
        # 854.33333333,
        # 782.66666667,
        # 684.33333333,
    ]

    # Change power from mW to W
    power_curve = [x / 1e3 for x in power_curve]

    power_coefs = np.polyfit(power_curve, current_curve, 5)
    power_I_curve = np.poly1d(power_coefs)
    V_coefs = np.polyfit(current_curve, voltage_curve, 5)
    V_I_curve = np.poly1d(V_coefs)

    # convert power_ref to Watts
    power_ref = power_ref * 1e3
    power_density = power_ref / cell_area / stack_number / n_cells
    # print("Power density", power_density)

    I_cell = max(power_I_curve(power_density), 0)
    V_cell = V_I_curve(I_cell)
    I_cell = I_cell * cell_area
    return I_cell, V_cell


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

        # self.add_input(
        #     "fuel_cell_efficiency",
        #     val=self.config.fuel_cell_efficiency_hhv,
        #     units=None,
        #     desc="HHV efficiency of the fuel cell (0 <= efficiency <= 1)",
        # )

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

        self.add_output(
            "oxygen_consumed",
            val=0.0,
            shape=self.n_timesteps,
            units="kg/h",
            desc="Mass flow rate of oxygen consumed by the fuel cell",
        )

        self.add_output(
            "water_out",
            val=0.0,
            shape=self.n_timesteps,
            units="kg/h",
            desc="Mass flow rate of water produced by the fuel cell",
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

        # calculate max input and output
        inputs["system_capacity"]  # plant capacity in kW
        inputs["hydrogen_in"]  # kg/h
        inputs["oxygen_in"]  # kg/h
        inputs["stack_temperature"]
        # fuel_cell_efficiency = inputs["fuel_cell_efficiency"]

        # Set calculation constants:
        self.f_c = 96485.33  # Faraday's constant in A/mol
        self.M_H2 = 0.002016  # Molar mass of H2 in kg/mol
        self.M_O2 = 0.032  # Molar mass of O2 in kg/mol
        self.M_H2O = 0.018  # Molar mass of H2O in kg/mol
        self.Tref = 298.15  # Standard room temperature in K [25 deg Celsius]
        self.cp_H2 = 14300  # Specific heat of H2 in J/(kg*K)
        self.cp_air = 1005  # Specific heat of air in J/(kg*K)
        self.cp_H2O = 4184  # Specific heat of water in J/(kg*K)
        self.cp_N2 = 1040  # Specific heat of nitrogen in J/(kg*K)
        self.cp_O2 = 918  # Specific heat of oxygen in J/(kg*K)
        self.hhv_h2 = 141.8 * 1e6  # Higher heating value of hydrogen in J/kg
        self.hhv_air = 0  # No higher heating value of air
        self.hhv_H2O = 2260  # Higher heating value of water in J/kg

        # Sizing the cells
        self.max_cell_power_density = 0.000334
        # is n_cells = N_series?
        self.N_series = 1
        self.stack_size = inputs["system_capacity"] / self.config.n_stacks
        self.cell_active_area = 400  # [cm^2] from Battelle (https://www.energy.gov/sites/prod/files/2018/02/f49/fcto_battelle_mfg_cost_analysis_1%20_to_25kw_pp_chp_fc_systems_jan2017_0.pdf)
        self.n_cells = round(
            self.stack_size / (self.cell_active_area * self.max_cell_power_density)
        )

        # PSUEDO CODE:
        """
        1. Receive power setpoint into fuel cell
        2. Find current with I-V curve
        3. Calculate H2 consumed and O2 consumed
        4. Check if provided H2 and O2 can meet the demand
        5. If not, adjust current
        6. Calculate power out with current and voltage
        7. Calculate the water produced from the reaction

        """

        h2_consumed = np.zeros(self.n_timesteps)
        o2_consumed = np.zeros(self.n_timesteps)
        h2o_generated = np.zeros(self.n_timesteps)
        commodity_out = np.zeros(self.n_timesteps)

        for i in range(self.n_timesteps):
            power_reference = inputs[f"{self.commodity}_command_value"][i]
            H2in = inputs["hydrogen_in"][i]
            O2in = inputs["oxygen_in"][i]

            # Find current and voltage from IV curve with power setpoint
            I_cell, V_cell = calc_current(
                power_reference, self.cell_active_area, self.n_cells, self.config.n_stacks
            )

            # Calculate hydrogen and oxygen consumed
            H2_consumed_rate = ((I_cell * self.N_series * self.M_H2) / (2.0 * self.f_c)) * (
                self.dt * self.config.n_stacks * self.n_cells
            )  # kg/time step
            O2_consumed_rate = ((I_cell * self.N_series * self.M_O2) / (4.0 * self.f_c)) * (
                self.dt * self.config.n_stacks * self.n_cells
            )  # kg/time step

            # print("H2 and O2 consumed per hour", H2_consumed_rate, O2_consumed_rate)
            # print(self.stack_size, self.n_cells)

            # TODO:
            if H2_consumed_rate > H2in or O2_consumed_rate > O2in:
                # implement an adjustment based on H2 & O2 available
                new_i_h2 = (
                    H2in
                    / (self.dt * self.config.n_stacks * self.n_cells)
                    * (2.0 * self.f_c)
                    / (self.N_series * self.M_H2)
                )
                new_i_o2 = (
                    O2in
                    / (self.dt * self.config.n_stacks * self.n_cells)
                    * (4.0 * self.f_c)
                    / (self.N_series * self.M_O2)
                )
                I_cell = min(new_i_h2, new_i_o2)
                # TODO: recalc voltage based on new current
                print("Not enough H2 or O2 for this power point")
                # Calculate hydrogen and oxygen consumed
                H2_consumed_rate = ((I_cell * self.N_series * self.M_H2) / (2.0 * self.f_c)) * (
                    self.dt * self.config.n_stacks * self.n_cells
                )  # kg/time step
                O2_consumed_rate = ((I_cell * self.N_series * self.M_O2) / (4.0 * self.f_c)) * (
                    self.dt * self.config.n_stacks * self.n_cells
                )  # kg/time step

            # Compute electricity from the system
            electricity_produced = (
                V_cell * I_cell * self.n_cells * self.config.n_stacks / 1e3
            )  # Calculated in watts, convert to kW

            # Compute H2O out
            H2O_generated = (
                (I_cell * self.N_series / (2 * self.f_c))
                * self.M_H2O
                * (self.dt * self.config.n_stacks * self.n_cells)
            )  # in kg/time step

            h2_consumed[i] = H2_consumed_rate
            o2_consumed[i] = O2_consumed_rate
            h2o_generated[i] = H2O_generated
            commodity_out[i] = electricity_produced

        # Set Outputs
        # clip the electricity output to the system capacity
        outputs["electricity_out"] = np.minimum(commodity_out, self.config.system_capacity_kw)
        outputs["total_electricity_produced"] = np.sum(outputs["electricity_out"]) * (
            self.dt / 3600
        )
        outputs["rated_electricity_production"] = self.config.system_capacity_kw
        outputs["annual_electricity_produced"] = outputs["total_electricity_produced"] * (
            1 / self.fraction_of_year_simulated
        )
        outputs["capacity_factor"] = outputs["total_electricity_produced"] / (
            self.config.system_capacity_kw * self.n_timesteps * (self.dt / 3600)
        )
        outputs["hydrogen_consumed"] = h2_consumed
        outputs["oxygen_consumed"] = o2_consumed
        outputs["water_out"] = h2o_generated

        # TODO: implement a hydrogen and oxygen conversion efficiency based on stack
        #   temperature and other factors


@define(kw_only=True)
class PEMH2FuelCellCostConfig(CostModelBaseConfig):
    """Configuration class for the hydrogen fuel cell cost model.

    Fields include `system_capacity_kw`, `capex_stack_per_kw`, `capex_hydrogen_supply_per_kw`,
    `capex_air_supply_per_kw`, `capex_cooling_per_kw`, `capex_controls_instrumentation_per_kw`,
    `capex_electrical_per_kw`, `capex_assembly_per_kw`, `capex_additional_labor_per_kw`,
    and `fixed_opex_per_kw_per_year`. The `cost_year` field is inherited from `CostModelBaseConfig`.
    """

    system_capacity_kw: float = field(validator=gte_zero)
    capex_stack_per_kw: float = field(validator=gte_zero)
    capex_hydrogen_supply_per_kw: float = field(validator=gte_zero)
    capex_air_supply_per_kw: float = field(validator=gte_zero)
    capex_cooling_per_kw: float = field(validator=gte_zero)
    capex_controls_instrumentation_per_kw: float = field(validator=gte_zero)
    capex_electrical_per_kw: float = field(validator=gte_zero)
    capex_assembly_per_kw: float = field(validator=gte_zero)
    capex_additional_labor_per_kw: float = field(validator=gte_zero)
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
            "system_capacity",
            val=self.config.system_capacity_kw,
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
            inputs: OpenMDAO inputs object containing system_capacity.
            outputs: OpenMDAO outputs object for capital_cost and fixed_operating_cost_per_year.
        """

        system_capacity_kw = inputs["system_capacity"]

        # Calculate capital cost
        outputs["CapEx"] = system_capacity_kw * inputs["unit_capex"]

        # Calculate fixed operating cost per year
        outputs["OpEx"] = system_capacity_kw * inputs["fixed_opex_per_year"]
