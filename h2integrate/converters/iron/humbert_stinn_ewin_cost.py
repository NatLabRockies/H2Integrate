"""Iron electronwinning cost model based on Humbert et al. and Stinn and Allanore

This module contains H2I cost configs and components for modeling iron electrowinning. It is
based on the work of Humbert et al. (doi.org/10.1007/s40831-024-00878-3), which contains relevant
iron electrowinning performance and cost data, and Stinn & Allanore (doi.org/10.1149.2/2.F06202IF),
which presents an empirical capex model for electrowinning of many different metals based on many
physical parameters of the electrowinning process.

The opex model developed by Humbert et al. is imported from ./humbert/cost_model.py

The capex model developed by Stinn & Allanore is imported from ./stinn/cost_model.py

This technology is selected in the tech_config as the cost_model
"humbert_stinn_electrowinning_cost"

Classes:
    HumbertEwinCostConfig: Sets the required model_inputs fields.
    HumbertEwinCostComponent: Defines initialize(), setup(), and compute() methods.

"""

import numpy as np
from attrs import field, define

from h2integrate.core.utilities import merge_shared_inputs
from h2integrate.core.validators import contains, must_equal
from h2integrate.core.model_baseclasses import CostModelBaseClass, CostModelBaseConfig


@define
class HumbertStinnEwinCostConfig(CostModelBaseConfig):
    """Configuration class for the Humbert iron electrowinning performance model.

    Args:
        electrolysis_type (str): The type of electrowinning being performed. Options:
            "ahe": Aqueous Hydroxide Electrolysis (AHE)
            "mse": Molten Salt Electrolysis (MSE)
            "moe": Molten Oxide Electrolysis (MOE)
        cost_year (int): The dollar year of costs output by the model. Defaults to 2018, the dollar
            year in which data was given in the Stinn paper
    """

    electrolysis_type: str = field(
        kw_only=True, converter=(str.lower, str.strip), validator=contains(["ahe", "mse", "moe"])
    )  # product selection
    # Set cost year to 2018 - fixed for Stinn modeling
    cost_year: int = field(default=2018, converter=int, validator=must_equal(2018))


class HumbertStinnEwinCostComponent(CostModelBaseClass):
    """OpenMDAO component for the Humbert/Stinn iron electrowinning cost model.

    Default values for many inputs are set for 3 technology classes:
        - Aqueous Hydroxide Electrolysis (AHE)
        - Molten Salt Electrolysis (MSE)
        - Molten Oxide Electrolysis (MOE)
    All of these values come from the SI spreadsheet for the Humbert paper that can be downloaded
    at doi.org/10.1007/s40831-024-00878-3 except for the default anode replacement interval.
    These are exposed to OpenMDAO for potential future optimization/sensitivity analysis.

    We calculate both CapEx and OpEx in this component.
    CapEx is calculated using the Stinn & Allanore model.
    OpEx is calculated using the Humbert et al. model.

    Inputs:
        output_capacity (float):
        iron_ore_in (array): Iron ore mass flow available in kg/h for each timestep.
        iron_transport_cost (float):
        price_iron_ore (float)
        electricity_in (array): Electric power input available in kW for each timestep.
        price_electricity (float):
        specific_energy_electrolysis (float): The specific electrical energy consumption required
            to win pure iron (Fe) from iron ore - JUST the electrolysis step.
        electrolysis_temp (float): Electrolysis temperature (°C).
        electron_moles (float): Moles of electrons per mole of iron product.
        current_density (float): Current density (A/m²).
        electrode_area (float): Electrode area per cell (m²).
        current_efficiency (float): Current efficiency (dimensionless).
        cell_voltage (float): Cell operating voltage (V).
        rectifier_lines (float): Number of rectifier lines.
        positions (float): Labor rate (position-years/tonne).
        NaOH_ratio (float): Ratio of NaOH consumed to Fe produced.
        CaCl2_ratio (float): Ratio of CaCl2 consumed to Fe produced.
        limestone_ratio (float): Ratio of limestone consumed to Fe produced.
        anode_ratio (float): Ratio of anode mass to annual iron production.
        anode_replacement_interval (float): Replacement interval of anodes (years)

    Outputs:
        CapEx (float): Total capital cost of the electrowinning plant (USD).
        OpEx (float): Yearly operating expenses in USD/year which do NOT depend on plant output.
        VarOpEx (float): Yearly operating expenses in USD/year which DO depend on plant output.
        processing_capex (float): Portion of the capex that is apportioned to preprocessing of ore.
        electrolysis_capex (float): Portion of the capex that is apportioned to electrolysis.
        rectifier_capex (float): Portion of the capex that is apportioned to rectifiers.
        labor_opex (float): Portion of the opex that is apportioned to labor.
        NaOH_opex (float): Portion of the opex that is apportioned to NaOH.
        CaCl2_opex (float): Portion of the opex that is apportioned to CaCl2.
        limestone_opex (float): Portion of the opex that is apportioned to limestone.
        anode_opex (float): Portion of the opex that is apportioned to anodes.
        ore_opex (float): Portion of the opex that is apportioned to ore.
        elec_opex (float): Portion of the opex that is apportioned to electricity.
    """

    def initialize(self):
        self.options.declare("driver_config", types=dict)
        self.options.declare("plant_config", types=dict)
        self.options.declare("tech_config", types=dict)

    def setup(self):
        n_timesteps = self.options["plant_config"]["plant"]["simulation"]["n_timesteps"]
        self.config = HumbertStinnEwinCostConfig.from_dict(
            merge_shared_inputs(self.options["tech_config"]["model_inputs"], "performance"),
            strict=False,
        )
        super().setup()

        ewin_type = self.config.electrolysis_type

        # Lookup specific inputs for electrowinning types, mostly from the Humbert SI spreadsheet
        # (noted where values did not come from this spreadsheet)
        if ewin_type == "ahe":
            # AHE - Capex
            T = 100  # Electrolysis temperature (°C)
            z = 2  # Moles of electrons per mole of iron product
            V = 1.7  # Cell operating voltage (V)
            j = 1000  # Current density (A/m²)
            A = 250  # Electrode area per cell (m²)
            e = 0.66  # Current efficiency (dimensionless)
            N = 12  # Number of rectifier lines

            # AHE - Opex
            positions = 739.2 / 2e6  # Labor rate (position-years/tonne)
            NaOH_ratio = 25130.2 * 0.1 / 2e6  # Ratio of NaOH consumption to annual iron production
            CaCl2_ratio = 0  # Ratio of CaCl2 consumption to annual iron production
            limestone_ratio = 0  # Ratio of limestone consumption to annual iron production
            anode_ratio = 0  # Ratio of anode mass to annual iron production
            # Anode replacement interval not considered by Humbert, 3 years assumed here
            anode_replace_int = 3  # Replacement interval of anodes (years)

        elif ewin_type == "mse":
            # MSE - Capex
            T = 900  # Temperature (deg C)
            z = 3  # Moles of electrons per mole of iron product
            V = 3  # Cell operating voltage (V)
            j = 300  # Current density (A/m²)
            A = 250  # Electrode area per cell (m²)
            e = 0.66  # Current efficiency (dimensionless)
            N = 8  # Number of rectifier lines

            # MSE - Opex
            positions = 499.2 / 2e6  # Labor rate (position-years/tonne)
            NaOH_ratio = 0  # Ratio of NaOH consumption to annual iron production
            CaCl2_ratio = 23138 * 0.1 / 2e6  # Ratio of CaCl2 consumption to annual iron production
            limestone_ratio = 0  # Ratio of limestone consumption to annual iron production
            anode_ratio = 1589.3 / 2e6  # Ratio of anode mass to annual iron production
            # Anode replacement interval not considered by Humbert, 3 years assumed here
            anode_replace_int = 3  # Replacement interval of anodes (years)

        elif ewin_type == "moe":
            # MOE - Capex
            T = 1600  # Temperature (deg C)
            z = 2  # Moles of electrons per mole of iron product
            V = 4.22  # Cell operating voltage (V)
            j = 10000  # Current density (A/m²)
            A = 30  # Electrode area per cell (m²)
            e = 0.95  # Current efficiency (dimensionless)
            N = 6  # Number of rectifier lines

            # AHE - Opex
            positions = 230.4 / 2e6  # Labor rate (position-years/tonne)
            NaOH_ratio = 0  # Ratio of NaOH consumption to annual iron production
            CaCl2_ratio = 0  # Ratio of CaCl2 consumption to annual iron production
            limestone_ratio = 0  # Ratio of limestone consumption to annual iron production
            anode_ratio = 8365.6 / 2e6  # Ratio of anode mass to annual iron production
            # Anode replacement interval not considered by Humbert, 3 years assumed here
            anode_replace_int = 3  # Replacement interval of anodes (years)

        # Set up connected inputs
        self.add_input("output_capacity", val=0.0, units="Mg/year")  # Mg = tonnes
        self.add_input("iron_ore_in", val=0.0, shape=n_timesteps, units="kg/h")
        self.add_input("iron_transport_cost", val=0.0, units="USD/t")
        self.add_input("price_iron_ore", val=0.0, units="USD/Mg")
        self.add_input("electricity_in", val=0.0, shape=n_timesteps, units="kW")
        self.add_input("price_electricity", val=0.0, units="USD/kW/h")
        self.add_input("specific_energy_electrolysis", val=0.0, units="kW*h/kg")

        # Set inputs for Stinn Capex model
        self.add_input("electrolysis_temp", val=T, units="C")
        self.add_input("electron_moles", val=z, units=None)
        self.add_input("current_density", val=j, units="A/m**2")
        self.add_input("electrode_area", val=A, units="m**2")
        self.add_input("current_efficiency", val=e, units=None)
        self.add_input("cell_voltage", val=V, units="V")
        self.add_input("rectifier_lines", val=N, units=None)

        # Set outputs for Stinn Capex model
        self.add_output("processing_capex", val=0.0, units="USD")
        self.add_output("electrolysis_capex", val=0.0, units="USD")
        self.add_output("rectifier_capex", val=0.0, units="USD")

        # Set inputs for Humbert Opex model
        self.add_input("positions", val=positions, units="year/Mg")
        self.add_input("NaOH_ratio", val=NaOH_ratio, units=None)
        self.add_input("CaCl2_ratio", val=CaCl2_ratio, units=None)
        self.add_input("limestone_ratio", val=limestone_ratio, units=None)
        self.add_input("anode_ratio", val=anode_ratio, units=None)
        self.add_input("anode_replacement_interval", val=anode_replace_int, units="year")

        # Set outputs for Humbert Opex model
        self.add_output("labor_opex", val=0.0, units="USD/year")
        self.add_output("NaOH_opex", val=0.0, units="USD/year")
        self.add_output("CaCl2_opex", val=0.0, units="USD/year")
        self.add_output("limestone_opex", val=0.0, units="USD/year")
        self.add_output("anode_opex", val=0.0, units="USD/year")
        self.add_output("ore_opex", val=0.0, units="USD/year")
        self.add_output("elec_opex", val=0.0, units="USD/year")

    def compute(self, inputs, outputs, discrete_inputs, discrete_outputs):
        # Physical constants
        F = 96485.3321  # Faraday constant: Electric charge per mole of electrons (C/mol)
        M = 0.055845  # Fe molar mass (kg/mol)

        # Parse inputs for Stinn Capex model (doi.org/10.1149/2.F06202IF)
        T = inputs["electrolysis_temp"]
        z = inputs["electron_moles"]
        j = inputs["current_density"]
        A = inputs["electrode_area"]
        e = inputs["current_efficiency"]
        V = inputs["cell_voltage"]
        N = inputs["rectifier_lines"]
        E_spec = inputs["specific_energy_electrolysis"]
        P = inputs["output_capacity"]
        p = P * 1000 / 8760 / 3600  # kg/s

        # Calculate total power
        j_cell = A * j  # current/cell [A]
        Q_cell = j_cell * V  # power/cell [W]
        P_cell = Q_cell * 8760 / E_spec  # annual production capacity/cell [kg]
        N_cell = P * 1e6 / P_cell  # number of cells [-]
        Q = Q_cell * N_cell / 1e6  # total installed power [MW]

        # Stinn Capex model - Equation (7) from doi.org/10.1149/2.F06202IF
        # Default coefficients
        a1n = 51010
        a1d = -3.82e-03
        a1t = -631
        a2n = 5634000
        a2d = -7.1e-03
        a2t = 349
        a3n = 750000
        e1 = 0.8
        e2 = 0.9
        e3 = 0.15
        e4 = 0.5

        # Alpha coefficients
        a1 = a1n / (1 + np.exp(a1d * (T - a1t)))
        a2 = a2n / (1 + np.exp(a2d * (T - a2t)))
        a3 = a3n * Q

        # Pre-costs calculation
        processing_capex = a1 * P**e1

        # Electrolysis and product handling contribution to total cost
        electrolysis_capex = a2 * ((p * z * F) / (j * A * e * M)) ** e2

        # Power rectifying contribution
        rectifier_capex = a3 * V**e3 * N**e4

        # Capex outputs
        outputs["CapEx"] = processing_capex + electrolysis_capex + rectifier_capex
        outputs["processing_capex"] = processing_capex
        outputs["electrolysis_capex"] = electrolysis_capex
        outputs["rectifier_capex"] = rectifier_capex

        # Parse inputs for Humbert Opex model (doi.org/10.1007/s40831-024-00878-3)
        positions = inputs["positions"]
        NaOH_ratio = inputs["NaOH_ratio"]
        CaCl2_ratio = inputs["CaCl2_ratio"]
        limestone_ratio = inputs["limestone_ratio"]
        anode_ratio = inputs["anode_ratio"]
        anode_interval = inputs["anode_replacement_interval"]
        ore_in = inputs["iron_ore_in"]
        ore_price = inputs["price_iron_ore"]
        ore_transport_cost = inputs["iron_transport_cost"]
        elec_in = inputs["electricity_in"]
        elec_price = inputs["price_electricity"]

        # Add ore transport cost TODO: turn iron_transport into proper transporter
        ore_price += ore_transport_cost

        # Humbert Opex model - from SI spreadsheet (doi.org/10.1007/s40831-024-00878-3)
        # Default costs - adjusted to 2018 to match Stinn via CPI
        labor_rate = 55.90  # USD/person-hour
        NaOH_cost = 415.179  # USD/tonne
        CaCl2_cost = 207.59  # USD/tonne
        limestone_cost = 0
        anode_cost = 1660.716  # USD/tonne
        hours = 2000  # hours/position-year

        # All linear OpEx for now - TODO: apply scaling models
        labor_opex = labor_rate * P * positions * hours  # Labor OpEx USD/year
        NaOH_opex = NaOH_ratio * P * NaOH_cost  # NaOH VarOpEx USD/year
        CaCl2_opex = CaCl2_ratio * P * CaCl2_cost  # CaCl2 VarOpEx USD/year
        limestone_opex = limestone_ratio * P * limestone_cost  # Limestone VarOpEx USD/year
        anode_opex = anode_ratio * P * anode_cost / anode_interval  # Anode VarOpEx USD/year
        ore_opex = np.sum(ore_in * ore_price, keepdims=True)  # Ore VarOpEx USD/year
        elec_opex = np.sum(elec_in * elec_price, keepdims=True)  # Electricity VarOpEx USD/year

        # Opex outputs
        outputs["OpEx"] = (
            labor_opex + NaOH_opex + CaCl2_opex + limestone_opex + anode_opex + ore_opex + elec_opex
        )
        outputs["VarOpEx"] = (
            NaOH_opex + CaCl2_opex + limestone_opex + anode_opex + ore_opex + elec_opex
        )
        outputs["labor_opex"] = labor_opex
        outputs["NaOH_opex"] = NaOH_opex
        outputs["CaCl2_opex"] = CaCl2_opex
        outputs["limestone_opex"] = limestone_opex
        outputs["anode_opex"] = anode_opex
        outputs["ore_opex"] = ore_opex
        outputs["elec_opex"] = elec_opex
