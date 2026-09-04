from datetime import timezone, timedelta

import pandas as pd


def process_leap_day(data: dict, include_leap_day: bool, n_timesteps: int):
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
        data = pd.DataFrame(data)
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

    if case_of_time_cols == "lower":
        data = data.rename(columns={"Month": "month", "Day": "day"})

    if convert_to_dict:
        data_out = {k: data[k].values for k in data.columns.to_list()}
        return data_out
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
