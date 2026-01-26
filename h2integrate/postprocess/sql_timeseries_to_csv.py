from pathlib import Path

import numpy as np
import pandas as pd
import openmdao.api as om


def check_get_units_for_var(case, var, electricity_base_unit: str, user_specified_unit=None):
    """Check the units for a variable within a case, with the following logic:

    0) If ``user_specified_unit`` is a string, get the variable value in units of
        ``user_specified_unit`` then continue to Step 5.
        If ``user_specified_unit`` is None, continue to Step 1.
    1) Get the default units of the variable. Continue to Step 2.
    2) Check if the default units contain electricity units.
        If the default units do contain an electricity unit, then continue to Step 3.
        Otherwise, continue to Step 4.
    3) Replace the default electricity unit in the default units with ``electricity_base_unit``.
        Get the variable value in units of the updated units and continue to Step 5.
    4) Get the variable value in the default units and continue to Step 5.
    5) Return the variable value and the corresponding units.

    Args:
        case (om.recorders.case.Case): OpenMDAO case object.
        var (str): variable name
        electricity_base_unit (str): Units to save any electricity-based profiles in.
            Must be either "W", "kW", "MW", or "GW".
        user_specified_unit (str | None, optional): _description_. Defaults to None.

    Returns:
        2-element tuple containing

        - **val** (np.ndarray | list | tuple): value of the `var` in units `var_unit`.
        - **var_unit** (str): units that `val` is returned in.
    """
    electricity_type_units = ["W", "kW", "MW", "GW"]
    # 0) check if user_specified_unit is not None
    if user_specified_unit is not None:
        # Get the variable value in units of ``user_specified_unit``
        val = case.get_val(var, units=user_specified_unit)
        return val, user_specified_unit

    # 1) Get the default units of the variable
    var_unit = case._get_units(var)

    # 2) Check if the default units contain electricity units.
    is_electric = any(electricity_unit in var_unit for electricity_unit in electricity_type_units)
    if is_electric:
        var_electricity_unit = [
            electricity_unit
            for electricity_unit in electricity_type_units
            if electricity_unit in var_unit
        ]
        # 3) Replace the default electricity unit in var_unit with electricity_base_unit
        new_var_unit = var_unit.replace(var_electricity_unit[-1], electricity_base_unit)
        val = case.get_val(var, units=new_var_unit)
        return val, new_var_unit

    # 4) Get the variable value in the default units
    val = case.get_val(var, units=var_unit)

    # 5) Return the variable value and the corresponding units
    return val, var_unit


def save_case_timeseries_as_csv(
    sql_fpath: Path | str,
    case_index: int = -1,
    electricity_base_unit="MW",
    vars_to_save: dict | list = {},
    save_to_file: bool = True,
):
    """Summarize timeseries data from a case within an sql recorder file to a DataFrame
    and save to csv file if `save_to_file` is True.

    Each column is a variable, each row is a timestep.
    Column names are formatted as:

    - "{promoted variable name} ({units})" for continuous variables

    Args:
        sql_fpath (Path | str): Filepath to sql recorder file.
        case_index (int, optional): Index of the case in the sql file to save results for.
            Defaults to -1.
        electricity_base_unit (str, optional): Units to save any electricity-based profiles in.
            Must be either "W", "kW", "MW", or "GW". Defaults to "MW".
        vars_to_save (dict | list, optional): An empty list or dictionary indicates to save
            all the timeseries variables in the case. If a list, should be a list of variable names
            to save. If a dictionary, should have keys of variable names and either values of units
            for the corresponding variable or a dictionary containing the keys "units" and/or
            "alternative_name". Defaults to {}.
        save_to_file (bool, optional): Whether to save the summary csv file to the same
            folder as the sql file(s). Defaults to True.

    Raises:
        ValueError: if electricity_base_unit is not "W", "kW", "MW", or "GW".
        FileNotFoundError: If the sql file does not exist or multiple sql files have the same name.
        ValueError: If no valid timeseries variables are input with vars_to_save and
            vars_to_save is not an empty list or dictionary.

    Returns:
        pd.DataFrame: summary of timeseries results from the sql file.
    """
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
            f"{sql_fpath} points to {len(sql_files)} different sql files, please specify the "
            f"filepath of a single sql file."
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
    if vars_to_save:
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
    var_to_alternative_names = []  # variable to the alternative name
    for var in var_list:
        if var in var_to_values:
            # don't duplicate data
            continue

        # get the value
        val = case.get_val(var)

        # Skip costs that are per year of plant life (not per timestep)
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
                alternative_name = None
                # Only do this if vars_to_save is a dict and it is not empty
                if vars_to_save and isinstance(vars_to_save, dict):
                    # Only do this if the vars_to_save[var] is a dict for units and alternative name
                    if isinstance(vars_to_save[var], dict):
                        user_units = vars_to_save[var].get("units", None)
                        alternative_name = vars_to_save[var].get("alternative_name", None)
                    # Otherwise, just pull the units directly
                    # This means that you can only specify units by itself, not alternative names
                    # Should we make all of these be entered as dicts then?
                    else:
                        user_units = vars_to_save.get(var, None)

                var_val, var_units = check_get_units_for_var(
                    case, var, electricity_base_unit, user_specified_unit=user_units
                )
                var_to_units[var] = var_units
                var_to_values[var] = var_val
                var_to_alternative_names.append(alternative_name)

    # map alternative names to variable names if not None
    alt_name_mapper = {
        old_name: new_name if new_name is not None else old_name
        for old_name, new_name in zip(var_to_values.keys(), var_to_alternative_names)
    }
    # update var_to_values and var_to_units with alternative names
    var_to_values = {alt_name_mapper[k]: v for k, v in var_to_values.items()}
    var_to_units = {alt_name_mapper[k]: v for k, v in var_to_units.items()}

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
