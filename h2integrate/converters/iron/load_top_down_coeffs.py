"""
Loads 'top-down' coefficients from a .csv
"""

from pathlib import Path

import numpy as np
import pandas as pd

from h2integrate.tools.inflation.inflate import inflate_cpi


CD = str(Path(__file__).parent.resolve())

# Set number of label columns at the left side of the input .csv (may change)
num_label_cols = 4


def load_top_down_coeffs(coeff_list=None, cost_year=None):
    """Loads top-down cost coefficients from a CSV file and adjusts for inflation if needed.

    Args:
        coeff_list (list, optional): A list of coefficient names to extract.
            If None, all coefficients are used. Defaults to None.
        cost_year (int, optional): The target year for cost adjustments.
            If provided, values with dollar-based units are
            adjusted for inflation using CPI. Defaults to None.

    Returns:
        dict: A dictionary containing:
            - "years" (numpy.ndarray): Array of years corresponding to the coefficient values.
            - Each coefficient as a key, with values:
                - "values" (numpy.ndarray): The numerical values of the coefficient.
                - "unit" (str): The unit of the coefficient.

    Example:
        >>> coeffs = load_top_down_coeffs(["Skilled Labor Cost"], 2015)
        >>> print(coeffs["Skilled Labor Cost"]["values"])
    """
    coeff_dict = {}

    coeff_df = pd.read_csv(CD + "/top_down_coeffs.csv")

    coeff_dict["years"] = np.array(coeff_df.columns.values[num_label_cols:], dtype=int)
    coeff_names = coeff_df.loc[:, "Name"].values
    coeff_units = coeff_df.loc[:, "Unit"].values

    if coeff_list is None:
        coeff_list = coeff_names

    for name in coeff_list:
        coeff_idx = np.where(coeff_names == name)[0][0]
        unit = coeff_units[coeff_idx]
        if cost_year:
            if unit[5] == "$":
                source_year = int(unit[:4])
                source_year_costs = coeff_df.iloc[coeff_idx, num_label_cols:]
                values = inflate_cpi(source_year_costs, source_year, cost_year)
            else:
                values = coeff_df.iloc[coeff_idx, 4:]
        else:
            values = coeff_df.iloc[coeff_idx, 4:]
        coeff_dict[name] = {"values": values.values, "unit": unit}

    return coeff_dict


if __name__ == "__main__":
    load_top_down_coeffs(
        [
            "Skilled Labor Cost",
        ],
        2015,
    )
