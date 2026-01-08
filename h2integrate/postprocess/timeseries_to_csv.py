from pathlib import Path

import numpy as np
import pandas as pd
import openmdao.api as om


def save_timeseries_vars_as_csv(
    variable_list, units_list, case, filename, alternative_name_list=None
):
    data = pd.DataFrame()
    if alternative_name_list is None:
        alternative_name_list = [None] * len(variable_list)

    for loc, var in enumerate(variable_list):
        if alternative_name_list[loc] is not None:
            save_key = alternative_name_list[loc]
        else:
            name_list = var.split(".")
            name_list.append(units_list[loc])
            save_key = " ".join(name_list)
        data[save_key] = case.get_val(var, units=units_list[loc])

    data.to_csv(filename, index=False)


def check_get_units_for_var(case, var, electricity_base_unit: str, user_specified_unit=None):
    electricity_type_units = ["W", "kW", "MW", "GW"]

    if user_specified_unit is not None:
        val = case.get_val(var, units=user_specified_unit)
        return val, user_specified_unit

    var_unit = case._get_units(var)
    is_electric = any(electricity_unit in var_unit for electricity_unit in electricity_type_units)
    if is_electric:
        var_electricity_unit = [
            electricity_unit
            for electricity_unit in electricity_type_units
            if electricity_unit in var_unit
        ]
        new_var_unit = var_unit.replace(var_electricity_unit[-1], electricity_base_unit)
        val = case.get_val(var, units=new_var_unit)
        return val, new_var_unit

    # get the value
    val = case.get_val(var, units=var_unit)
    return val, var_unit


def save_case_timeseries_as_csv(
    sql_fpath: Path | str,
    case_index: int = 0,
    electricity_base_unit="MW",
    vars_to_save: dict | list = {},
    save_to_file: bool = True,
):
    electricity_type_units = ["W", "kW", "MW", "GW"]
    if electricity_base_unit not in electricity_type_units:
        msg = (
            f"Invalid input for electricity_base_unit {electricity_base_unit}. "
            f"Valid options are {electricity_type_units}."
        )
        raise ValueError(msg)

    sql_fpath = Path(sql_fpath)

    # check if multiple sql files exist with the same name and suffix.
    sql_files = list(Path(sql_fpath.parent).glob(f"{sql_fpath.name}*"))

    # check that at least one sql file exists
    if len(sql_files) == 0:
        raise FileNotFoundError(f"{sql_fpath} file does not exist.")

    # check if a metadata file is contained in sql_files
    contains_meta_sql = any("_meta" in sql_file.suffix for sql_file in sql_files)
    if contains_meta_sql:
        # remove metadata file from filelist
        sql_files = [sql_file for sql_file in sql_files if "_meta" not in sql_file.suffix]
    # check that only one sql file was input
    if len(sql_files) > 1:
        msg = (
            f"{sql_fpath} points to {len(sql_files)} sql files, please specify the filepath "
            "of a single sql file."
        )
        raise FileNotFoundError(msg)

    # load the sql file and extract cases
    cr = om.CaseReader(Path(sql_files[0]))
    case = cr.get_case(case_index)

    # get list of input and output names
    output_var_dict = case.list_outputs(val=False, out_stream=None, return_format="dict")
    input_var_dict = case.list_inputs(val=False, out_stream=None, return_format="dict")

    # create list of variables to loop through
    var_list = [v["prom_name"] for v in output_var_dict.values()]
    var_list += [v["prom_name"] for v in input_var_dict.values()]
    var_list.sort()

    # if vars_to_save is not empty, then only include the variables in var_list
    if bool(vars_to_save):
        if isinstance(vars_to_save, dict):
            varnames_to_save = list(vars_to_save.keys())
            var_list = [v for v in var_list if v in varnames_to_save]
        if isinstance(vars_to_save, list):
            var_list = [v for v in var_list if v in vars_to_save]

    if len(var_list) == 0:
        raise ValueError("No variables were found to be saved")

    # initialize output dictionaries
    var_to_values = {}  # variable to the units
    var_to_units = {}  # variable to the value
    for var in var_list:
        if var in var_to_values:
            # don't duplicate data
            continue

        # get the value
        val = case.get_val(var)

        # Skip costs that are per year of plant life
        if "varopex" in var.lower() or "annual_fixed_costs" in var.lower():
            continue

        # skip discrete inputs/outputs (like resource data)
        if isinstance(val, (dict, pd.DataFrame, pd.Series)):
            continue

        # skip scalar data
        if isinstance(val, (int, float, str, bool)):
            continue

        if isinstance(val, (np.ndarray, list, tuple)):
            if len(val) > 1:
                user_units = None
                if isinstance(vars_to_save, dict):
                    user_units = vars_to_save.get(var, None)

                var_val, var_units = check_get_units_for_var(
                    case, var, electricity_base_unit, user_specified_unit=user_units
                )
                var_to_units[var] = var_units
                var_to_values[var] = var_val

    # rename columns to include units
    column_rename_mapper = {
        v_name: f"{v_name} ({v_units})" for v_name, v_units in var_to_units.items()
    }

    results = pd.DataFrame(var_to_values)

    results = results.rename(columns=column_rename_mapper)

    # save file to csv
    if save_to_file:
        csv_fname = f"{sql_fpath.name.replace('.sql','_').strip('_')}_Case{case_index}.csv"
        output_fpath = sql_fpath.parent / csv_fname
        results.to_csv(output_fpath, index=False)

    return results
