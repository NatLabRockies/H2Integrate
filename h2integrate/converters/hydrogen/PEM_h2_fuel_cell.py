import numpy as np
from attrs import field, define
from scipy.interpolate import make_interp_spline

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
        fuel_cell_efficiency_hhv (float): The higher heating value efficiency of the
            fuel cell (0 <= efficiency <= 1).
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

    power_I_curve = make_interp_spline(power_curve, current_curve, k=3)
    V_I_curve = make_interp_spline(current_curve, voltage_curve, k=5)

    # convert power_ref to Watts
    power_ref = power_ref * 1e3
    # print(power_ref, cell_area, stack_number, n_cells)
    power_density = power_ref / cell_area / stack_number / n_cells
    # print("Power density", power_density)

    I_cell = power_I_curve(power_density)
    V_cell = V_I_curve(I_cell)
    I_cell = I_cell * cell_area
    return I_cell, V_cell


class PEMH2FuelCellPerformanceModel(PerformanceModelBaseClass):
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

        # Add natural gas input, default to 0 --> set using feedstock component
        # or upstream hydrogen converter component
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
            desc="Mass flow rate of water consumed by the fuel cell",
        )

        # Default the electricity set point input as the rated capacity
        self.add_input(
            f"{self.commodity}_set_point",
            val=self.config.system_capacity_kw,
            shape=self.n_timesteps,
            units=self.commodity_rate_units,
            desc="Electricity set point for PEM fuel cell",
        )

    def compute(self, inputs, outputs):
        """
        Compute electricity output from the fuel cell based on hydrogen input
            and fuel cell HHV efficiency.

        Args:
            inputs: OpenMDAO inputs object containing hydrogen_in, fuel cell
                HHV efficiency, electricity_set_point, and system_capacity.
            outputs: OpenMDAO outputs object for electricity_out,
                hydrogen_consumed.
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
        self.stack_size = self.config.system_capacity_kw / self.config.n_stacks
        self.cell_active_area = 400  # [cm^2] from Battelle (https://www.energy.gov/sites/prod/files/2018/02/f49/fcto_battelle_mfg_cost_analysis_1%20_to_25kw_pp_chp_fc_systems_jan2017_0.pdf)
        self.n_cells = round(
            self.stack_size / (self.cell_active_area * self.max_cell_power_density)
        )

        # PSUEDO CODE:
        """
        1. Receive power setpoint into fuel cell
        2. Find current with I-V curve - NEED THIS
        3. Calculate power out with current - NEED TO FIND CELL ELECTRICITY CALC
        4. Calculate H2 consumed, O2 consumed, water out
        5. See if H2 in and O2 in can provide this
        6. Repeat step 4 if H2 or O2 limit power out

        """

        h2_consumed = np.zeros(self.n_timesteps)
        o2_consumed = np.zeros(self.n_timesteps)
        commodity_out = np.zeros(self.n_timesteps)

        for i in range(self.n_timesteps):
            power_reference = inputs[f"{self.commodity}_set_point"][i]
            inputs["hydrogen_in"][i]
            inputs["oxygen_in"][i]

            # Find current and voltage from IV curve with power setpoint
            I_cell, V_cell = calc_current(
                power_reference, self.cell_active_area, self.n_cells, self.config.n_stacks
            )

            # Calculate hydrogen and oxygen consumed
            # print("I_cell", I_cell)
            # print("f_c", self.f_c)
            # print("M_H2", self.M_H2)
            H2_consumed_rate = ((I_cell * self.N_series * self.M_H2) / (2.0 * self.f_c)) * (
                self.dt * self.config.n_stacks * self.n_cells
            )  # kg/time step
            O2_consumed_rate = ((I_cell * self.N_series * self.M_O2) / (4.0 * self.f_c)) * (
                self.dt * self.config.n_stacks * self.n_cells
            )  # kg/time step

            print("H2 and O2 consumed per hour", H2_consumed_rate, O2_consumed_rate)
            print(self.stack_size, self.n_cells)

            # if H2_consumed_rate > H2in or O2_consumed_rate > O2in:
            # print("Not enough H2 or O2 for this power point")
            # implement an adjustment based on H2 & O2 available

            # Compute electricity from the system
            electricity_produced = (
                V_cell * I_cell * self.n_cells * self.config.n_stacks / 1e3
            )  # Calculated in watts, convert to kW

            # Need to implement this function
            # self.calculate_water_production(H2_consumed_rate, O2_consumed_rate)

            # Compute H2O out (is this needed?)

            h2_consumed[i] = H2_consumed_rate
            o2_consumed[i] = O2_consumed_rate
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

        # # conversion factor: kW electricity to kg/h hydrogen, units: (kg/h)/kW
        # kw_to_kgh_h2 = (3600.0 * 0.001) / (fuel_cell_efficiency * HHV_H2_MJ_PER_KG)

        # # TODO: Calculate max H2 and O2 consumption of the stacks
        # max_h2_consumption = system_capacity * kw_to_kgh_h2

        # # electrical set point, saturated at maximum rated system capacity
        # electricity_set_point = np.where(
        #     inputs["electricity_set_point"] > system_capacity,
        #     system_capacity,
        #     inputs["electricity_set_point"],
        # )

        # h2_demand = electricity_set_point * kw_to_kgh_h2

        # # available feedstock, saturated at maximum system feedstock consumption
        # h2_available = np.where(
        #     inputs["hydrogen_in"] > max_h2_consumption,
        #     max_h2_consumption,
        #     inputs["hydrogen_in"],
        # )

        # # h2 consumed is minimum between available feedstock and output demand
        # hydrogen_in = np.minimum(h2_available, h2_demand)

        # # make any negative hydrogen input zero
        # hydrogen_in = np.maximum(hydrogen_in, 0.0)

        # # calculate electricity output in kW
        # electricity_out_kw = hydrogen_in / kw_to_kgh_h2

        # # clip the electricity output to the system capacity
        # outputs["electricity_out"] = np.minimum(electricity_out_kw, system_capacity)
        # outputs["total_electricity_produced"] = np.sum(outputs["electricity_out"]) * (
        #     self.dt / 3600
        # )
        # outputs["rated_electricity_production"] = system_capacity
        # outputs["annual_electricity_produced"] = outputs["total_electricity_produced"] * (
        #     1 / self.fraction_of_year_simulated
        # )
        # outputs["capacity_factor"] = outputs["total_electricity_produced"] / (
        #     system_capacity * self.n_timesteps * (self.dt / 3600)
        # )
        # outputs["hydrogen_consumed"] = outputs["electricity_out"] * kw_to_kgh_h2

        # ##############################################################################
        # # Helper functions for energy balance and water production calculations

        # def enthalpy_flow(self, m, cp, T, Tref, h0):
        #     """Mass-specific enthalpy flow: Hdot = m * (cp*(T - Tref) + h0)"""
        #     return m * (cp * (T - Tref) + h0)

        # def calculate_water_production(self, h2_consumed_rate, o2_consumed_rate):
        #     # Calculate water production based on stoichiometry of the reaction
        #     # 2H2 + O2 --> 2H2O
        #     # For every 2 moles of H2 consumed, 2 moles of H2O are produced
        #     # For every 1 mole of O2 consumed, 2 moles of H2O are produced

        #     # Calculuate the energy balance of the reaction to find the water production
        #     # Enthalpy change of the reaction:
        #           ΔH = (m_H2 * hhv_h2) + (m_O2 * hhv_o2) - (m_H2O * hhv_water)
        #     # Assuming hhv_o2 and hhv_water are 0, we can simplify to:
        #     # ΔH = (m_H2 * hhv_h2) - (m_H2O * hhv_water)
        #     # Since hhv_water is 0, we can further simplify to:
        #     # ΔH = m_H2 * hhv_h2
        #     # The energy released by the reaction is equal to the energy produced by the fuel cell
        #   which is the power output (electricity produced) plus the heat produced (which we can
        #   assume is a certain percentage of the energy released by the reaction, say 50% for a PEM
        #   fuel cell).
        #     # Therefore, we can calculate the water production based on the energy balance of the
        #       reaction and the power output of the fuel cell.
        #     H_H2_in  = self.enthalpy_flow(mH2_in,  self.cp_H2,  T_H2_in,  self.Tref, self.hhv_h2)
        #     H_H2_out = self.enthalpy_flow(mH2_out, self.cp_H2,  T_H2_out, self.Tref, self.hhv_h2)

        #     H_air_in = self.enthalpy_flow(mO2_in,  self.cp_air, T_air_in,  self.Tref, 0.0)
        #     H_air_out = (
        #         self.enthalpy_flow(mO2_out, self.cp_O2, T_air_out, self.Tref, 0.0) +
        #         self.enthalpy_flow(mN2_out, self.cp_N2, T_air_out, self.Tref, 0.0)
        #     ) # consider just oxygen for a first pass

        #     H_H2O_in  = self.enthalpy_flow(mH2O_in,
        #                   self.cp_H2O, T_H2O_in, self.Tref, self.hhv_H2O)
        #     H_H2O_out = self.enthalpy_flow(mH2O_out,
        #                   self.cp_H2O, T_H2O_out, self.Tref, self.hhv_H2O)

        #     return (H_H2_in + H_air_in + H_H2O_in
        #            - H_H2_out - H_air_out - H_H2O_out
        #            - Wel - Q)

        # ##############################################################################

        # # Convert mass flow rates to molar flow rates
        # h2_molar_flow = h2_consumed_rate / self.M_H2  # mol/time step
        # o2_molar_flow = o2_consumed_rate / self.M_O2  # mol/time step

        # # Calculate water production based on limiting reactant
        # h2o_from_h2 = h2_molar_flow * (self.M_H2O / 1)  # kg/time step
        # h2o_from_o2 = o2_molar_flow * (self.M_H2O / 0.5)  # kg/time step

        # # The actual water produced is the minimum of the two calculations
        # water_produced = np.minimum(h2o_from_h2, h2o_from_o2)

        # return water_produced


@define(kw_only=True)
class H2FuelCellCostConfig(CostModelBaseConfig):
    """Configuration class for the hydrogen fuel cell cost model.

    Fields include `system_capacity_kw`, `capex_per_kw`, and `fixed_opex_per_kw_per_year`.
    The `cost_year` field is inherited from `CostModelBaseConfig`.
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
