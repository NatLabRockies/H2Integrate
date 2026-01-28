import numpy as np

from h2integrate.converters.iron.load_top_down_coeffs import load_top_down_coeffs


def martin_ore_variable_om_cost(mine_name, cost_df, analysis_start, cost_year, plant_life):
    cost_ds = cost_df.loc[:, mine_name]
    cost_names = cost_df.index.values
    cost_types = cost_df.loc[:, "Type"].values
    cost_units = cost_df.loc[:, "Unit"].values

    var_td_idxs = np.where(cost_types == "variable opex td")[0]
    var_td_names = cost_names[var_td_idxs]
    var_td_input_costs = load_top_down_coeffs(var_td_names, cost_year)
    var_td_years = var_td_input_costs["years"]
    year_start_idx = np.where(var_td_years == analysis_start)[0][0]
    analysis_end = min(max(var_td_years), analysis_start + plant_life)
    year_end_idx = np.where(var_td_years == analysis_end)[0][0]
    year_idxs = range(year_start_idx, year_end_idx)
    var_om_td = 0
    for idx in var_td_idxs:
        name = cost_names[idx]
        cost_units[idx]  # Should be "<unit top-down input> per <unit plant output>"
        var_td_usage = cost_ds.iloc[idx]

        var_td_dict = var_td_input_costs[name]
        var_td_dict["unit"]  # Should be "<YYYY> $ per <unit top-down input"
        var_td_price = var_td_dict["values"]
        var_td_price = np.mean(var_td_price[year_idxs])

        cost = var_td_usage * var_td_price
        var_om_td += cost
    return var_om_td
