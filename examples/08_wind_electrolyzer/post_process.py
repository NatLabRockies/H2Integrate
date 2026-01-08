import openmdao.api as om
from pathlib import Path
import pandas as pd
from h2integrate.postprocess.timeseries_to_csv import save_timeseries_vars_as_csv


# set the path for the recorder from stuff specified in the driver_config.yaml
fpath = Path.cwd() / "wind_electrolyzer" / "cases.sql"

# load the cases
cr = om.CaseReader(fpath)

# get the cases as a list
cases = list(cr.get_cases())

variable_list = [
    "electrolyzer.hydrogen_out",
    "wind.electricity_out",
]
units_list = [
    "kg/h",
    "MW",
]
alternative_name_list = [
    "Hydrogen Produced (kg/hr)",
    "Wind Electricity (MW)",
]

save_timeseries_vars_as_csv(
    variable_list,
    units_list,
    cases[-1],
    Path.cwd() / "wind_electrolyzer" / "wind_electrolyzer_ouputs.csv",
    # alternative_name_list=alternative_name_list,
)

