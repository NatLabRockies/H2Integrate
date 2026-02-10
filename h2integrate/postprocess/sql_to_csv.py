from pathlib import Path

import numpy as np
import pandas as pd
import openmdao.api as om


def summarize_case(case, return_units=False):
    """Summarize scalar data from a case.

    Args:
        case (om.recorders.case.Case): OpenMDAO case object.
        return_units (bool, optional): Whether to return a dictionary of units
            corresponding to the variables. Defaults to False.

    Returns:
        tuple[dict] or dict: Return dictionary of variable names and the corresponding
            values and a dictionary of variable names and the corresponding units
            if `return_units` is True. Otherwise, returns dictionary of variable names
            and the corresponding values.
    """

    # get list of input and output variable names
    design_vars = case.get_design_vars()
    output_var_dict = case.list_outputs(val=False, out_stream=None, return_format="dict")
    input_var_dict = case.list_inputs(val=False, out_stream=None, return_format="dict")

    # create list of variables to loop through
    var_list = [v["prom_name"] for v in output_var_dict.values()]
    var_list += [v["prom_name"] for v in input_var_dict.values()]
    var_list.sort()

    # have the design variables as the first columns
    var_list = list(design_vars.keys()) + var_list

    # initialize output dictionaries
    var_to_values = {}  # variable to the units
    var_to_units = {}  # variable to the value
    for var in var_list:
        if var in var_to_values:
            # don't duplicate data
            continue

        # get the value
        val = case.get_val(var)

        # if discrete variable, don't include units
        if isinstance(val, int | float | str | bool):
            var_to_values.update({var: val})
            continue

        # skip resource data
        if isinstance(val, dict | pd.DataFrame | pd.Series):
            continue

        # save variable om for first year
        if "varopex" in var.lower():
            var_to_values.update({var: val[0]})
            var_to_units.update({var: case._get_units(var)})

        # save average capacity factor and annual production
        lifetime_prod_var = var.lower().split(".")[-1].startswith("annual") and var.lower().split(
            "."
        )[-1].endswith("production")
        if "capacity_factor" in var.lower() or lifetime_prod_var:
            if isinstance(val, np.ndarray):
                if not np.all(val == val[0]):
                    # take the average value if not all years are equal
                    val = [np.mean(val)]
                else:
                    # take the first year value if all years are equal
                    val = val[0]

        if isinstance(val, np.ndarray):
            # dont save information for non-scalar values
            if len(val) > 1:
                continue

        # save information for scalar values
        var_to_values.update({var: val[0]})
        var_to_units.update({var: case._get_units(var)})

    if return_units:
        return var_to_values, var_to_units

    return var_to_values


def convert_sql_to_csv_summary(sql_fpath: Path | str, save_to_file: bool = True):
    """Summarize scalar data from a sql recorder file (if ran in serial) or set of sql
    recorder files (if ran in parallel) to a DataFrame and save to csv file if
    `save_to_file` is True.

    The first columns of the output DataFrame are the design variables.
    Column names are formatted as:

    - "{promoted variable name} ({units})" for continuous variables
    - "{promoted variable name}" for discrete variables.

    Args:
        sql_fpath (Path | str): Filepath to sql recorder file.
        save_to_file (bool, optional): Whether to save the summary csv file to the same
            folder as the sql file(s). Defaults to True.

    Raises:
        FileNotFoundError: if sql_fpath does not point to a valid filename.

    Returns:
        pd.DataFrame: summary of scalar results from the sql file.
    """
    sql_fpath = Path(sql_fpath)

    sql_files = list(Path(sql_fpath.parent).glob(f"{sql_fpath.name}*"))

    # check that file exists
    if len(sql_files) == 0:
        raise FileNotFoundError(f"{sql_fpath} file does not exist.")

    # initialize results dataframe and counter
    results = pd.DataFrame()
    ii = 0

    # loop through the sql files (only multiple if ran in parallel)
    for sql_file in sql_files:
        if "_meta" in sql_file.suffix:
            # don't read meta data file (only created in ran in parallel)
            continue

        # load the sql file and extract cases
        cr = om.CaseReader(Path(sql_file))
        cases = list(cr.get_cases())

        # loop through cases
        for case in cases:
            if ii == 0:
                case_results, data_units = summarize_case(case, return_units=True)
            else:
                case_results = summarize_case(case, return_units=False)
            results = pd.concat([results, pd.DataFrame(case_results, index=[ii])], axis=0)

            ii += 1

    # rename columns to include units
    column_rename_mapper = {
        col: f"{col} ({data_units[col]})" for col in results.columns.to_list() if col in data_units
    }
    results = results.rename(columns=column_rename_mapper)

    # save file to csv
    if save_to_file:
        output_fpath = sql_fpath.parent / f"{sql_fpath.stem}.csv"
        results.to_csv(output_fpath)

    return results
