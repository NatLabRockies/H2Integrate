import warnings

import numpy as np
import pandas as pd


def separate_timeseries_and_meta_data(data):
    """Separate a dictionary into meta-data and timeseries data components

    Args:
        data (dict): dictionary of resource data

    Returns:
        tuple[dict, dict]: dictionary of meta-data and dictionary of timeseries data
    """
    meta_data = {}
    timeseries_data = {}
    for k, v in data.items():
        if isinstance(v, (str | bool | int | float | dict)):
            meta_data[k] = v
        else:
            timeseries_data[k] = v

    return meta_data, timeseries_data


def append_timeseries_data(data_full, new_data, return_with_metadata=False):
    """Append timeseries data from `new_data` to `data_full` and return the resulting dictionary.

    Args:
        data_full (dict): dictionary of existing timeseries data
        ts_data (dict): dictionary of new timeseries data to append to data_full
        return_with_metadata (bool, optional): If true, return the combined
        timeseries data dictionary with any meta-data possible extracted from
        the data_full dictionary

    Returns:
        dict: dictionary containing timeseries data from data_full and new_data
    """
    meta_data, ts_data_full = separate_timeseries_and_meta_data(data_full)
    _, new_ts_data = separate_timeseries_and_meta_data(new_data)
    shared_keys = set(ts_data_full) & set(new_ts_data)
    if len(shared_keys) != len(set(ts_data_full)):
        missing_data = (set(new_ts_data) - shared_keys) & (set(ts_data_full) - shared_keys)
        msg = (
            "Mismatch in timeseries data. Non-shared data keys of "
            f"{sorted(missing_data)} will be removed. "
        )
        warnings.warn(msg, UserWarning)

    ts_data = {}
    for k in list(shared_keys):
        if isinstance(ts_data_full[k], list) and isinstance(new_ts_data[k], list):
            ts_data[k] = ts_data_full[k] + new_ts_data[k]
        else:
            ts_data[k] = np.concat([np.array(ts_data_full[k]), np.array(new_ts_data[k])], axis=0)

    if return_with_metadata:
        return meta_data | ts_data

    return ts_data


def clip_data_to_n_timesteps(data, n_timesteps):
    """Clip timeseries data to `n_timesteps`

    Args:
        data (dict): dictionary of resource data
        n_timesteps (int): number of timesteps that the data should contain

    Returns:
        dict: resource data, where timeseries data is clipped to n_timesteps
    """
    meta_data, ts_data = separate_timeseries_and_meta_data(data)
    ts_clipped = {k: v[: int(n_timesteps)] for k, v in ts_data.items()}
    return meta_data | ts_clipped


def clip_data_to_resource_year(data, resource_year):
    """Remove extraneous resource year data from the resource data dictionary

    Args:
        data (dict): resource data
        resource_year (str | int): resource year to pull data for.
        If resource_year is a string, it should be formatted as 'tmy-{year}' or similar.

    Raises:
        ValueError: if data is missing a 'year' or 'Year' key

    Returns:
        dict: dictionary of resource data only containing data for resource_year
    """
    if isinstance(resource_year, str):
        # for TMY datasets, year is different across the months
        # return data as-is
        return data

    if ("year" in data) or ("Year" in data):
        yr_col = "year" if "year" in data else "Year"

        if (yr_ts := data.get(yr_col)) is not None:
            if len(set(yr_ts)) == 1:
                # data only has 1 year, just return the data
                return data
        # separate the meta-data from timeseries data
        meta_data, ts_data = separate_timeseries_and_meta_data(data)
        # make sure the year key is an integer
        ts_data[yr_col] = np.array(ts_data[yr_col]).astype(int)
        # convert timeseries data to a dataframe to filter out extra years
        # (np.argwhere doesn't work for some reason)
        ts_df = pd.DataFrame(ts_data)
        ts_df = ts_df[ts_df[yr_col] == resource_year]
        # convert the dataframe back to a dictionary
        ts_clipped = {c: ts_df[c].values for c in ts_df.columns.to_list()}

        return meta_data | ts_clipped

    raise ValueError("Missing 'year' timeseries info")
