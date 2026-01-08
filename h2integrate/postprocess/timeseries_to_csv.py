import pandas as pd

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



