import openmdao.api as om
from pathlib import Path
from h2integrate.postprocess.timeseries_to_csv import save_case_timeseries_as_csv, save_timeseries_vars_as_csv


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
    "Hydrogen Produced",
    # "Wind Electricity",
    None,
]

save_timeseries_vars_as_csv(
    variable_list,
    units_list,
    cases[-1],
    Path.cwd() / "wind_electrolyzer" / "wind_electrolyzer_ouputs.csv",
    # alternative_name_list=alternative_name_list,
)

save_case_timeseries_as_csv("wind_electrolyzer/cases.sql",
                            case_index=-1,
                            electricity_base_unit="MW",
                            vars_to_save=["electrolyzer.hydrogen_out",
                                          "wind.electricity_out"],
                            save_to_file=True,
                            alternative_name_list=alternative_name_list)



