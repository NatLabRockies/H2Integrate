import numpy as np
from attrs import field, define, validators
from openmdao.utils import units

from h2integrate.core.utilities import BaseConfig, merge_shared_inputs
from h2integrate.tools.constants import H_MW, O2_MW, CH4_MW, CO2_MW, faraday
from h2integrate.core.model_baseclasses import PerformanceModelBaseClass


@define(kw_only=True)
class SONGFuelCellPerformanceConfig(BaseConfig):
    """Configuration class for the solid oxide natural gas fuel cell performance model.

    Attributes:
        system_capacity_kw (float): The capacity of the fuel cell system in kilowatts (kW).
        n_stacks (int): The number of stacks in the fuel cell system.
        stack_temperature_K (float): The operating temperature of the fuel cell stack in Kelvin (K).
        hhv (float): higher heating value of the fuel in kWh/kg
    """

    # TODO: how to size the fuel cell? N_cells + N_stacks?
    # How does N_cells translate to electricity rating?

    system_capacity_kw: float = field(validator=validators.ge(0))
    n_stacks: int = field(validator=validators.ge(0))
    stack_temperature_K: float = field(validator=validators.ge(0))
    hhv: float = field(validator=validators.ge(0))
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


class SONGFuelCellPerformanceModel(PerformanceModelBaseClass):
    """
    Performance model for a solid oxide natural gas fuel cell.

    The model calculates electricity output based on natural gas and oxygen inputs,
    with current and voltage determined from power density using IV curves.
    Produces water and carbon dioxide as byproducts.
    Possible source: https://www.pnnl.gov/main/publications/external/technical_reports/PNNL-18338.pdf

    where:
    - natural_gas_in is the mass flow rate of natural gas in kg/hr
    - oxygen_in is the mass flow rate of oxygen in kg/hr
    - water_out is the mass flow rate of water produced in kg/hr
    - co2_out is the mass flow rate of carbon dioxide produced in kg/hr
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

        self.config = SONGFuelCellPerformanceConfig.from_dict(
            merge_shared_inputs(self.options["tech_config"]["model_inputs"], "performance"),
            additional_cls_name=self.__class__.__name__,
        )

        # Add natural gas input, default to 0 --> set using feedstock component
        # or upstream hydrogen converter component
        self.add_input(
            "natural_gas_in",
            val=0.0,
            shape=self.n_timesteps,
            units="MMBtu/h",
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
            desc="Rated electricity production of the SOFC system",
        )

        self.add_output(
            "natural_gas_consumed",
            val=0.0,
            shape=self.n_timesteps,
            units="MMBtu/h",
            desc="Mass flow rate of natural gas consumed by the fuel cell",
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
            "co2_out",
            val=0.0,
            shape=self.n_timesteps,
            units=f"kg/({self.dt}*s)",
            desc="Mass flow rate of carbon dioxide produced by the fuel cell",
        )

        self.add_output(
            "heat_out",
            val=0.0,
            shape=self.n_timesteps,
            units=self.commodity_rate_units,
            desc="Heat generated by the fuel cell",
        )

        self.add_output(
            "rated_natural_gas_consumed",
            val=0.0,
            units="MMBtu/h",
            desc="Rated natural gas consumed by the fuel cell",
        )

        self.add_output(
            "rated_oxygen_consumed",
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
            "rated_co2_out",
            val=0.0,
            units=f"kg/({self.dt}*s)",
            desc="Rated carbon dioxide produced by the fuel cell",
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
            desc="Electricity command value for SOFC plant",
        )

    def compute(self, inputs, outputs):
        """
        Compute electricity output from the SOFC based on natural gas input,
            oxygen availability, and fuel cell electrochemical reactions.

        Args:
            inputs: OpenMDAO inputs object containing natural_gas_in, oxygen_in,
                stack_temperature, electricity_command_value, and system_capacity.
            outputs: OpenMDAO outputs object for electricity_out, natural_gas_consumed,
                oxygen_consumed, water_out, and co2_out.
        """
        # Set calculation constants:
        M_H2 = H_MW * 2 / 1000  # Molar mass of H2 in kg/mol
        M_O2 = O2_MW / 1000  # Molar mass of O2 in kg/mol
        M_H2O = M_H2 + M_O2 / 2  # Molar mass of H2O in kg/mol
        M_CH4 = CH4_MW / 1000  # Molar mass of CH4 in kg/mol
        M_CO2 = CO2_MW / 1000  # Molar mass of CO2 in kg/mol
        # Electron transfer constants
        n_ng = 8  # number of electrons transferred per mole of CH4
        n_o2 = 4  # number of electrons transferred per mole of O2
        n_h2o = 2  # number of electrons transferred per mole of H2O
        n_co2 = 8  # number of electrons transferred per mole of CO2

        # calculate max input and output
        inputs["stack_temperature"]
        natural_gas_in = inputs["natural_gas_in"]  # MMBtu/h

        ############################################################################
        # Convert from MMBtu/h to kg/h for CH4 using LHV
        lhv_ch4 = 50.0  # Lower heating value of CH4 in MJ/kg from https://www.engineeringtoolbox.com/fuels-higher-calorific-values-d_169.html#gsc.tab=0
        natural_gas_in_MJ_per_hr = units.convert_units(natural_gas_in, "MMBtu/h", "MJ/h")
        natural_gas_kg_hr = natural_gas_in_MJ_per_hr / lhv_ch4  # Convert MJ/h to kg/h for CH4

        # TODO: Add consumption of water for steam reforming of natural gas to hydrogen

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
        rated_ng_consumed = ((rated_I_cell * M_CH4) / (n_ng * faraday)) * (
            self.dt * self.config.n_stacks * n_cells
        )  # kg/time step
        rated_o2_consumed = ((rated_I_cell * M_O2) / (n_o2 * faraday)) * (
            self.dt * self.config.n_stacks * n_cells
        )  # kg/time step
        rated_h2o_out = ((rated_I_cell * M_H2O) / (n_h2o * faraday)) * (
            self.dt * self.config.n_stacks * n_cells
        )  # kg/time step
        rated_co2_out = ((rated_I_cell * M_CO2) / (n_co2 * faraday)) * (
            self.dt * self.config.n_stacks * n_cells
        )  # kg/time step
        # Convert rated natural gas from kg/time step to MMBtu/h for output units
        rated_ng_consumed_MJ_per_hr = (
            rated_ng_consumed * lhv_ch4 * (3600 / self.dt)
        )  # Convert kg/time step to MJ/h
        rated_ng_consumed_mmbtu_per_hr = units.convert_units(
            rated_ng_consumed_MJ_per_hr, "MJ/h", "MMBtu/h"
        )  # Convert MJ/h to MMBtu/h
        rated_heat_out = (
            rated_ng_consumed * (3600 / self.dt) * self.config.hhv - rated_power_production
        )
        # in kW

        ################## Model Calculations ##################
        # 1. Receive power setpoint into fuel cell
        power_reference = np.clip(
            inputs[f"{self.commodity}_command_value"], a_min=0.0, a_max=rated_power_production
        )  # in commodity rate units (kW)

        # 2. Find stack current from power reference
        commanded_I_stack, V_J_curve = calc_current(
            power_reference * 1e3, cell_active_area, n_cells, self.config.n_stacks
        )  # current in Amps per stack

        # 3. Find available hydrogen and oxygen for each timestep
        ng_in_kg_per_s = natural_gas_kg_hr / 3600  # convert from kg/h to kg/s
        o2_in_kg_per_s = inputs["oxygen_in"] / 3600  # convert from kg/h to kg/s

        # convert from kg/s to A per stack - current that feedstocks in can support
        I_stack_from_ng = (ng_in_kg_per_s * n_ng * faraday) / (M_CH4 * self.config.n_stacks)
        I_stack_from_o2 = (o2_in_kg_per_s * n_o2 * faraday) / (M_O2 * self.config.n_stacks)

        # 4. Take minimum current from power reference, hydrogen available, and oxygen available
        I_stack = np.minimum(commanded_I_stack, np.minimum(I_stack_from_ng, I_stack_from_o2))
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
        ng_consumed = ((I_cell * M_CH4) / (n_ng * faraday)) * (
            self.dt * self.config.n_stacks * n_cells
        )  # kg/time step
        o2_consumed = ((I_cell * M_O2) / (n_o2 * faraday)) * (
            self.dt * self.config.n_stacks * n_cells
        )  # kg/time step
        h2o_generated = ((I_cell * M_H2O) / (n_h2o * faraday)) * (
            self.dt * self.config.n_stacks * n_cells
        )  # kg/time step
        co2_generated = ((I_cell * M_CO2) / (n_co2 * faraday)) * (
            self.dt * self.config.n_stacks * n_cells
        )  # kg/time step

        # 8. Calculate heat generated by the fuel cell
        heat_generated = natural_gas_kg_hr * (3600 / self.dt) * self.config.hhv - power_out  # in kW

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
            self.config.system_capacity_kw * self.n_timesteps * (self.dt / 3600)
        )
        ng_consumed_MJ_per_hr = (
            ng_consumed * lhv_ch4 * (3600 / self.dt)
        )  # Convert kg/time step to MJ/h
        ng_consumed_mmbtu_per_hr = units.convert_units(
            ng_consumed_MJ_per_hr, "MJ/h", "MMBtu/h"
        )  # Convert MJ/h to MMBtu/h
        outputs["natural_gas_consumed"] = ng_consumed_mmbtu_per_hr  # Convert back to MMBtu/h
        outputs["oxygen_consumed"] = o2_consumed
        outputs["water_out"] = h2o_generated
        outputs["co2_out"] = co2_generated
        outputs["heat_out"] = heat_generated

        # Set rated outputs
        outputs["rated_natural_gas_consumed"] = rated_ng_consumed_mmbtu_per_hr
        outputs["rated_oxygen_consumed"] = rated_o2_consumed
        outputs["rated_water_out"] = rated_h2o_out
        outputs["rated_co2_out"] = rated_co2_out
        outputs["rated_heat_out"] = rated_heat_out

        # TODO: implement a natural gas and oxygen conversion efficiency based on stack
        #   temperature and other factors
