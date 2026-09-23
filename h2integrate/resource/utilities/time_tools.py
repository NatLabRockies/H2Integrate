from datetime import timezone, timedelta

import pandas as pd

from h2integrate.resource.utilities.data_tools import separate_timeseries_and_meta_data


def is_leap_year(year):
    """Determine if a year is leap year

    Args:
        year (int): calendar year

    Returns:
        bool: True if the year is a leap year
    """
    is_leap = (year % 100 == 0 and year % 400 == 0 and year % 4 == 0) or (
        year % 4 == 0 and year % 100 != 0
    )
    return is_leap


def check_data_length(data, n_timesteps: int):
    """_summary_

    Args:
        data (dict): DataFrame-like dictionary of resource data containing
            "Month" and "Day" columns.
        n_timesteps (int): Number of timesteps in the simulation.

    Raises:
        ValueError: If the length of the data does not match ``n_timesteps``
            after leap day processing.
    """
    if isinstance(data, dict):
        _, ts_data = separate_timeseries_and_meta_data(data)
        data = pd.DataFrame(ts_data)

    data = data.rename(columns={"month": "Month", "day": "Day"})

    data_has_leap_day = int(data[data["Month"] == 2]["Day"].max()) == 29

    # Check if data is the same length as the number of timesteps
    if len(data) != n_timesteps:
        leap_day_msg = ""
        if data_has_leap_day and len(data) > n_timesteps:
            # Add extra detail to error message if error may be due to leap day
            leap_day_msg = (
                "This may be because the resource data includes a leap day. ",
                "To remove data from a leap day from resource data, please set "
                "`include_leap_day` to False.",
            )

        msg = (
            f"Resource data is not the same length as n_timesteps. "
            f"Resource data has length {len(data)}, n_timesteps is {n_timesteps}. "
            f"{leap_day_msg}"
        )
        raise ValueError(msg)


def process_leap_day(data: dict, include_leap_day: bool):
    """Process leap day data by optionally removing it and validating data length.

    Checks whether the provided resource data contains a leap day (February 29th).
    If ``include_leap_day`` is set to False in the config and the data contains a
    leap day, the leap day entries are removed. After processing, validates that
    the length of the data matches the expected number of timesteps.

    Args:
        data (dict): DataFrame-like dictionary of resource data containing
            "Month" and "Day" columns.
        include_leap_day (bool): Whether to include leap day in the resource data.
        n_timesteps (int): Number of timesteps in the simulation.

    Returns:
        dict: Processed resource data with leap day handled according to configuration.

    Raises:
        ValueError: If the length of the data does not match ``n_timesteps``
            after leap day processing.
    """

    convert_to_dict = False
    if isinstance(data, dict):
        meta_data, ts_data = separate_timeseries_and_meta_data(data)
        data = pd.DataFrame(ts_data)
        convert_to_dict = True

    case_of_time_cols = "lower" if "month" in data.columns.to_list() else "upper"
    data = data.rename(columns={"month": "Month", "day": "Day"})

    # Check if data includes leap day
    data_has_leap_day = int(data[data["Month"] == 2]["Day"].max()) == 29

    # Remove leap day if needed
    if not include_leap_day and data_has_leap_day:
        # Get index of dataframe that includes leap day
        leap_day_index = (
            data.reset_index(drop=False)
            .set_index(keys=["Month", "Day"], drop=True)
            .loc[(2, 29)]["index"]
            .to_list()
        )
        # Drop the leap day data from the dataframe
        data = data.drop(index=leap_day_index)

    # Check if data is the same length as the number of timesteps
    # if len(data) != n_timesteps:
    #     leap_day_msg = ""
    #     if data_has_leap_day and len(data) > n_timesteps:
    #         # Add extra detail to error message if error may be due to leap day
    #         leap_day_msg = (
    #             "This may be because the resource data includes a leap day. ",
    #             "To remove data from a leap day from resource data, please set "
    #             "`include_leap_day` to False.",
    #         )

    #     msg = (
    #         f"Resource data is not the same length as n_timesteps. "
    #         f"Resource data has length {len(data)}, n_timesteps is {n_timesteps}. "
    #         f"{leap_day_msg}"
    #     )
    #     raise ValueError(msg)

    if case_of_time_cols == "lower":
        data = data.rename(columns={"Month": "month", "Day": "day"})

    if convert_to_dict:
        data_out = {k: data[k].values for k in data.columns.to_list()}
        return meta_data | data_out
    return data


def add_resource_start_end_times(data: dict):
    """Add resource data start time, end time, and timestep to the resource data dictionary.

    The start and end time are represented as strings formatted as "yyyy/mm/dd hh:mm:ss (tz)"
    and the timestep is represented in seconds.

    Args:
        data (dict): dictionary of resource data

    Returns:
        data (dict): resource data dictionary with added time strings, modified in place
    """

    time_keys = ["year", "month", "day", "hour", "minute", "second"]
    time_dict = {k: data.get(k) for k in time_keys if k in data}

    # If no time information is in the resource data, return the dictionary unchanged
    if not bool(time_dict):
        return data

    df = pd.to_datetime(time_dict)

    # If theres not enough time information, return the dictionary unchanged
    if len(df) <= 1:
        return data

    start_date = df.iloc[0].strftime("%Y/%m/%d %H:%M:%S")
    end_date = df.iloc[-1].strftime("%Y/%m/%d %H:%M:%S")

    # Get resource time interval
    dt = df.iloc[1] - df.iloc[0]

    # Get timezone string
    tz_utc_offset = timedelta(hours=data.get("data_tz", 0))
    tz = timezone(offset=tz_utc_offset)
    tz_str = str(tz).replace("UTC", "").replace(":", "")
    if tz_str == "":
        tz_str = "+0000"

    # Create dictionary of time information with dt in seconds
    time_start_end_info = {
        "start_time": f"{start_date} ({tz_str})",
        "end_time": f"{end_date} ({tz_str})",
        "dt": dt.seconds,
    }

    # Update resource data with time information
    data.update(time_start_end_info)

    return data


def get_number_of_resource_years_needed(dt: int, n_timesteps: int, include_leap: bool):
    """Get the number of years required to get n_timesteps worth of resource data

    NOTE: this function is intended to be used if other ways of getting
    multiple years of resource data is desired (such as with filenames, or a list of years, etc)

    Args:
        dt (int): number of seconds in a timesteps
        n_timesteps (int): number of timesteps in the simulation
        include_leap (bool): whether to

    Returns:
        int: number of years needed to get n_timesteps worth of resource data
    """

    # Get the number of hours in the simulation
    hours_simulated = (dt / 3600) * n_timesteps

    if hours_simulated % 8760 == 0:
        n_years_needed = hours_simulated // 8760
        return n_years_needed

    # check if remainder is multiple of 24, indicating leap days
    remainder_hrs = hours_simulated % 8760
    if remainder_hrs % 24 == 0 and include_leap:
        # remaining hours is divisible by 24 and including leap-day
        n_leap_years = remainder_hrs // 24
        # number of hours from non-leap years
        n_hrs_leap_years = n_leap_years * (8760 + 24)
        n_hrs_non_leap = hours_simulated - n_hrs_leap_years
        if n_hrs_non_leap % 8760 == 0:
            n_years_needed = n_leap_years + (n_hrs_non_leap // 8760)
        else:
            # need an extra year
            n_years_needed = n_leap_years + (n_hrs_non_leap // 8760) + 1
        return n_years_needed
    return (hours_simulated // 8760) + 1
