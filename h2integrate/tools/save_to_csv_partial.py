import numpy as np
from matplotlib import pyplot as plt

import openmdao.api as om
from pathlib import Path
import pandas as pd

def save_as_csv(variable_list, units_list, case, filename, alternative_name_list=None):
    data = pd.DataFrame()
    if alternative_name_list is None:
        alternative_name_list = [None]*len(variable_list)

    for loc, var in enumerate(variable_list):
        if alternative_name_list[loc] is not None:
            save_key = alternative_name_list[loc] # Formatting of this may need work
        else:
            name_list = var.split(".")
            name_list.append(units_list[loc])
            save_key = " ".join(name_list)
        data[save_key] = case.get_val(var, units=units_list[loc])

    data.to_csv(filename, index=False)

if __name__ == "__main__":
    # set the path for the recorder from stuff specified in the driver_config.yaml
    fpath = Path.cwd() / "outputs" / "cases.sql"

    # load the cases
    cr = om.CaseReader(fpath)

    # get the cases as a list
    cases = list(cr.get_cases())

    variable_list = [
        "battery.SOC",
        "battery.electricity_in",
        "battery.unused_electricity_out",
        "battery.electricity_out",
        "battery.bought_electricity_out",
        "battery.battery_electricity_discharge",
        "battery.electricity_demand",
    ]
    units_list = [
        "percent",
        "MW",
        "MW",
        "MW",
        "MW",
        "MW",
        "MW",
    ]
    alternative_name_list = [
        "Battery SOC (%)",
        "Wind Electricity (MW)",
        "Excess Electricity (MW)",
        "Electricity to Load (MW)",
        "Grid Purchased Electricity (MW)",
        "Battery Electricity (MW)",
        "Electrical Demand (MW)",
    ]

    save_as_csv(
        variable_list,
        units_list,
        cases[-1],
        Path.cwd() / "outputs" / "wind_battery_grid_plant.csv",
        alternative_name_list=alternative_name_list,
    )

