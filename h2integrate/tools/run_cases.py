import operator
from functools import reduce

import pandas as pd


def cast_by_name(type_name, value):
    """Cast a string read in from an input file as a data type also given as a string.
    Currently allowed data types: int, float, bool, str

    Args:
        type_name (str): The data type to cast into, as a string.
        value (str): The value, as a string.

    Returns:
        The value in the specified data type
    """

    bool_map = {"true": True, "false": False, "yes": True, "no": False, "1": True, "0": False}

    trusted_types = ["int", "float", "bool", "str"]  ## others as needed
    if type_name in trusted_types:
        if type_name == "bool":
            return bool_map.get(value.lower())
        else:
            return __builtins__[type_name](value)
    else:
        msg = f"Specified data type {type_name} invalid, must be one of {trusted_types}"
        raise TypeError(msg)


def get_from_dict(dataDict, mapList):
    """Get value from nested dictionary using a list of keys.

    Allows for programmatic calling of items in a nested dict using a variable-length list.
    Instead of dataDict[item1][item2][item3][item4][item5], you can use
    get_from_dict(dataDict, [item1, item2, item3, item4, item5]).

    Args:
        dataDict (dict): The nested dictionary to access.
        mapList (list): List of keys to traverse the nested dictionary.

    Returns:
        The value at the specified nested location in the dictionary.

    Example:
        >>> data = {"a": {"b": {"c": 42}}}
        >>> get_from_dict(data, ["a", "b", "c"])
        42
    """
    return reduce(operator.getitem, mapList, dataDict)


def set_in_dict(dataDict, mapList, value):
    """Set value in nested dictionary using a list of keys.

    Allows for programmatic setting of items in a nested dict using a variable-length list.
    Instead of dataDict[item1][item2][item3][item4][item5] = value, you can use
    set_in_dict(dataDict, [item1, item2, item3, item4, item5], value).

    Args:
        dataDict (dict): The nested dictionary to modify.
        mapList (list): List of keys to traverse the nested dictionary.
        value: The value to set at the specified nested location.

    Example:
        >>> data = {"a": {"b": {}}}
        >>> set_in_dict(data, ["a", "b", "c"], 42)
        >>> data["a"]["b"]["c"]
        42
    """
    get_from_dict(dataDict, mapList[:-1])[mapList[-1]] = value


def load_tech_config_cases(case_file):
    """Load extensive lists of values from a spreadsheet to run many different cases.

    Loads tech_config values from a CSV file to run multiple cases with different
    technology configuration values.

    Args:
        case_file (Path): Path to the .csv file where the different tech_config values
            are listed. The CSV must be formatted with "Index 1", "Index 2", etc.
            columns followed by case name columns. Each row should have "technologies"
            as the first index value, followed by tech_name and parameter names.

    Returns:
        pd.DataFrame: DataFrame with the indexes of the tech_config as a MultiIndex
            and the different case names as the column names.

    Note:
        The CSV format should be::

            |   "Index 1"    |...|  "Index <N>"   | "Type"  | <Case 1 Name>  |...| <Case N Name>  |
            | "technologies" |...| <param_1_name> | "float" | <Case 1 value> |...| <Case N value> |
            | "technologies" |...| <param_2_name> | "str"   | <Case 1 value> |...| <Case N value> |

    If some parameters are nested deeper than others, make as many Index columns for the deepest-
    nested parameters and leave any unused Indexes blank.

    See example .csv in h2integrate/tools/test/test_inputs.csv
    """
    tech_config_cases = pd.read_csv(case_file)
    column_names = tech_config_cases.columns.values
    index_names = list(filter(lambda x: "Index" in x, column_names))
    index_names.append("Type")
    tech_config_cases = tech_config_cases.set_index(index_names)

    return tech_config_cases


def modify_tech_config(h2i_model, tech_config_case, run_setup=True):
    """Modify particular tech_config values on an existing H2I model before it is run.

    Args:
        h2i_model: H2IntegrateModel that has been set up but not run.
        tech_config_case (pd.Series): Series that was indexed from tech_config_cases
            DataFrame containing the parameter values to modify.
        run_setup (bool): defaults to True. In case the user wishes to delay calling setup,
            run_setup may be set to False, this may be useful to allow multiple calls to
            modify_tech_config prior to running a simulation.

    Returns:
        H2IntegrateModel: The H2IntegrateModel with modified tech_config values.
    """
    for index_tup, value in tech_config_case.items():
        index_list = list(index_tup)
        data_type = index_list[-1]
        index_list = index_list[:-1]
        # Remove nans from blank index fields
        while type(index_list[-1]) is not str:
            index_list = index_list[:-1]
        set_in_dict(h2i_model.technology_config, index_list, cast_by_name(data_type, value))

    if run_setup:
        h2i_model.setup()

    return h2i_model
