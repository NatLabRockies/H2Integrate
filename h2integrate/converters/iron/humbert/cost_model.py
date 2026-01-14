"""
Calculations in Excel spreadsheet SI of Humbert doi.org/10.1149.2/2.F06202IF
"""

import numpy as np


def humbert_opex_calc(
    capacity,
    positions,
    NaOH_ratio,
    CaCl2_ratio,
    limestone_ratio,
    anode_ratio,
    anode_interval,
    ore_in,
    ore_price,
    elec_in,
    elec_price,
):
    # Default costs - adjusted to 2018 to match Stinn via CPI
    labor_rate = 55.90  # USD/person-hour
    NaOH_cost = 415.179  # USD/tonne
    CaCl2_cost = 207.59  # USD/tonne
    limestone_cost = 0
    anode_cost = 1660.716  # USD/tonne
    hours = 2000  # hours/position-year

    # All linear OpEx for now - TODO: apply scaling models
    labor_opex = labor_rate * capacity * positions * hours  # Labor OpEx USD/year
    NaOH_varopex = NaOH_ratio * capacity * NaOH_cost  # NaOH VarOpEx USD/year
    CaCl2_varopex = CaCl2_ratio * capacity * CaCl2_cost  # CaCl2 VarOpEx USD/year
    limestone_varopex = limestone_ratio * capacity * limestone_cost  # CaCl2 VarOpEx USD/year
    anode_varopex = anode_ratio * capacity * anode_cost / anode_interval  # Anode VarOpEx USD/year
    ore_varopex = np.sum(ore_in * ore_price, keepdims=True)  # Ore VarOpEx USD/year
    elec_varopex = np.sum(elec_in * elec_price, keepdims=True)  # Electricity VarOpEx USD/year

    return (
        labor_opex,
        NaOH_varopex,
        CaCl2_varopex,
        limestone_varopex,
        anode_varopex,
        ore_varopex,
        elec_varopex,
    )
