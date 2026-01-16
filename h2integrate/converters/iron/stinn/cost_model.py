"""
Calculates the total direct capital cost (C) in 2018 US dollars.

From:
Estimating the Capital Costs of Electrowinning Processes
Caspar Stinn and Antoine Allanore 2020 Electrochem. Soc. Interface 29 44
https://iopscience.iop.org/article/10.1149/2.F06202IF
"""

from pathlib import Path

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt


CD = Path(__file__).parent

# Physical constants
faraday_const = 96485.3321  # Electric charge per mole of electrons (Faraday constant), C/mol
F = 96485.3321  # Faraday constant: Electric charge per mole of electrons (Faraday constant), C/mol
M = 0.055845  # Fe molar mass (kg/mol)


def plot_capex_calc(
    a1n, a1d, a1t, a2n, a2d, a2t, a3n, e1, e2, e3, e4, T, P, p, z, F, j, A, e, M, Q, V, N
):
    # Pre-costs calculation
    a1 = a1n / (1 + np.exp(a1d * (T - a1t)))
    a2 = a2n / (1 + np.exp(a2d * (T - a2t)))
    a3 = a3n * Q

    pre_costs = a1 * P**e1

    # Electrolysis and product handling contribution to total cost
    electrolysis_product_handling = a2 * ((p * z * F) / (j * A * e * M)) ** e2

    # Power rectifying contribution
    power_rectifying_contribution = a3 * V**e3 * N**e4

    return pre_costs, electrolysis_product_handling, power_rectifying_contribution, a1, a2, a3


def main(config):
    """
    Calculates the total direct capital cost of an electrowinning system in 2018 US dollars.

    The cost estimation is based on the methodology from:
    "Estimating the Capital Costs of Electrowinning Processes"
    by Caspar Stinn and Antoine Allanore (2020).
    *Electrochem. Soc. Interface*, 29, 44.
    DOI: https://iopscience.iop.org/article/10.1149/2.F06202IF

    Args:
        config (object): Configuration object containing model inputs, including:
            cost_model (dict): Dictionary with the file path to cost coefficients.
            electrolysis_temp (float): Electrolysis temperature in degrees Celsius (°C).
            capacity (float): Installed capacity in tonnes per year (t/y).
            production_rate (float): Production rate in kilograms per second (kg/s).
            electron_moles (int): Moles of electrons per mole of product.
            faraday_const (float): Faraday constant in coulombs per mole (C/mol).
            current_density (float): Current density in amperes per square meter (A/m²).
            electrode_area (float): Electrode area in square meters (m²).
            current_efficiency (float): Current efficiency (dimensionless, fraction).
            molar_mass (float): Molar mass of the electrolysis product
                in kilograms per mole (kg/mol).
            installed_capacity (float): Installed power capacity in megawatts (MW).
            cell_voltage (float): Cell operating voltage in volts (V).
            rectifier_lines (int): Number of rectifier lines.

    Returns:
        dict: A dictionary containing:
            pre_costs (float): Pre-costs related to capacity and system preparation.
            electrowinning_costs (float): Costs associated with electrolysis
                and power rectification.
            total_costs (float): Sum of pre-costs and electrowinning costs.
    """
    # Load inputs
    inputs_fp = CD / config.cost_model["inputs_fp"]
    inputs_df = pd.read_csv(inputs_fp)
    inputs_df = inputs_df.set_index("Metal")

    # Load coefficients
    coeffs_fp = CD / config.cost_model["coeffs_fp"]
    coeffs_df = pd.read_csv(coeffs_fp)
    coeffs = coeffs_df.set_index("Name")["Coeff"].to_dict()

    # Extract coefficients
    a1n = coeffs["alpha_1_numerator"]
    a1d = coeffs["alpha_1_denominator"]
    a1t = coeffs["alpha_1_temp_offset"]
    a2n = coeffs["alpha_2_numerator"]
    a2d = coeffs["alpha_2_denominator"]
    a2t = coeffs["alpha_2_temp_offset"]
    a3n = coeffs["alpha_3"]
    e1 = coeffs["exp_1"]
    e2 = coeffs["exp_2"]
    e3 = coeffs["exp_3"]
    e4 = coeffs["exp_4"]

    metal_dict = {
        "Al": [0, 0, 0],
        "Mg": [0, 0.5, 1],
        "Na": [0, 1, 0],
        "Zn": [0, 1, 1],
        "Cu": [0, 0.5, 0],
        "Cl2": [0, 0, 0.5],
    }

    # Cycle through metals
    for metal, color in metal_dict.items():
        metal_df = inputs_df.loc[[metal]]
        cap = metal_df["Capacity [kt/y]"].values
        capex_per_cap = metal_df["Capex/ Capacity [2018 USD/ (t/y)]"].values
        plt.plot(cap, capex_per_cap, ".", color=color)

        T = metal_df["Temperature [C]"].values
        P = cap * 1000
        p = P * 1000 / 8760 / 3600
        z = metal_df["Electrons per product"].values
        f = faraday_const
        j = metal_df["Current Density [A/m^2]"].values
        A = metal_df["Electrode area/ cell [m^2]"].values
        e = metal_df["Current efficiency"].values
        M = metal_df["Product molar mass [kg]"].values
        Q = metal_df["Power / cell [MW]"].values
        V = metal_df["Operating potential [V]"].values
        N = metal_df["Cell Count"].values
        Q = Q * N

        F, E, R, a1, a2, a3 = plot_capex_calc(
            a1n, a1d, a1t, a2n, a2d, a2t, a3n, e1, e2, e3, e4, T, P, p, z, f, j, A, e, M, Q, V, 1
        )

        plt.plot(cap, (F + E + R) / P, "-", color=color)

    # Assign inputs from config
    T = config.electrolysis_temp  # Electrolysis temperature (°C)
    P = config.capacity  # installed capacity (t/y)
    p = config.production_rate  # Production rate (kg/s)
    z = config.electron_moles  # Moles of electrons per mole of product
    f = faraday_const  # Electric charge per mole of electrons (C/mol)
    j = config.current_density  # Current density (A/m²)
    A = config.electrode_area  # Electrode area (m²)
    e = config.current_efficiency  # Current efficiency (dimensionless)
    M = config.molar_mass  # Electrolysis product molar mass (kg/mol)
    Q = config.installed_capacity  # Installed power capacity (MW)
    V = config.cell_voltage  # Cell operating voltage (V)
    N = config.rectifier_lines  # Number of rectifier lines

    pre_costs, electrolysis_product_handling, power_rectifying_contribution, a1, a2, a3 = (
        plot_capex_calc(
            a1n, a1d, a1t, a2n, a2d, a2t, a3, e1, e2, e3, e4, T, P, p, z, f, j, A, e, M, Q, V, N
        )
    )

    # Electrowinning costs
    electrowinning_costs = electrolysis_product_handling + power_rectifying_contribution

    # Total costs
    pre_costs + electrowinning_costs

    plt.xscale("log")
    plt.show()

    # Return individual costs for modularity
    return {
        "pre_costs": pre_costs,
        "electrowinning_costs": electrowinning_costs,
        "total_costs": pre_costs + electrowinning_costs,
    }


if __name__ == "__main__":

    class Config:
        def __init__(self):
            self.cost_model = {"coeffs_fp": "cost_coeffs.csv", "inputs_fp": "table1.csv"}
            # Example values for each variable (replace with actual values)
            self.electrolysis_temp = 1000  # Temperature in °C, example value
            self.capacity = 1.5  # Installed capacity (t/y)
            self.production_rate = 1.0  # Total production rate, kg/s
            self.electron_moles = 3  # Moles of electrons per mole of product, example value
            self.current_density = 5000  # Current density, A/m², example value
            self.electrode_area = 30.0  # Electrode area, m², example value
            self.current_efficiency = 0.95  # Current efficiency (dimensionless), example value
            self.molar_mass = 0.018  # Electrolysis product molar mass, kg/mol (e.g., water)
            self.installed_capacity = 500.0  # Installed power capacity, MW, example value
            self.cell_voltage = 4.18  # Cell operating voltage, V, example value
            self.rectifier_lines = 3  # Number of rectifier lines, example value

    results = main(Config())
    print(results)
