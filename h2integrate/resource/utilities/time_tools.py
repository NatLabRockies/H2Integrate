import warnings
from datetime import timezone, timedelta

import numpy as np
import pandas as pd

from h2integrate.resource.utilities.data_tools import separate_timeseries_and_meta_data


TIME_DATA_KEYS = ["year", "month", "day", "hour", "minute", "second"]


def contains_leap_day(data):
    """Check whether timeseries data contains a data for leap day

    Args:
        data (dict): dataframe or dictionary of resource data containing
            "Month" (or "month") and "Day" (or "day") timeseries data

    Returns:
        bool: whether the data has data for leap day
    """
    if isinstance(data, dict):
        _, ts_data = separate_timeseries_and_meta_data(data)
        data = pd.DataFrame(ts_data)

    data = data.rename(columns={"month": "Month", "day": "Day"})

    # Check if data includes leap day
    february_days = data[data["Month"] == 2]["Day"]
    data_has_leap_day = not february_days.empty and february_days.max() == 29
    return data_has_leap_day


def is_leap_year(year: int):
    """Determine if a year is leap year. A year is a leap-year if it is:

    - divisible by 4 and not divisible by 100 (not a century-year) OR
    - divisible by 4, 100, and 400

    Args:
        year (int): calendar year

    Returns:
        bool: True if the year is a leap year
    """
    # NOTE: could replace with calendar.isleap()

    # Check if a century year and also a leap year
    # Or check if not a century year and also divisible by 4
    is_leap = (year % 100 == 0 and year % 400 == 0 and year % 4 == 0) or (
        year % 4 == 0 and year % 100 != 0
    )
    return is_leap


def check_data_length(data, n_timesteps: int):
    """Validates that the length of the data matches the expected number of timesteps.
    This function should be called after leap-days are removed (if needed) and data
    has been clipped to the number of timesteps.

    Args:
        data (dict): dataframe or dictionary of resource data containing
            "Month" (or "month") and "Day" (or "day") timeseries data
        n_timesteps (int): Number of timesteps in the simulation.

    Raises:
        ValueError: If the length of the data does not match ``n_timesteps``
            after leap day processing.
    """
    if isinstance(data, dict):
        _, ts_data = separate_timeseries_and_meta_data(data)
        data = pd.DataFrame(ts_data)

    data = data.rename(columns={"month": "Month", "day": "Day"})

    february_days = data[data["Month"] == 2]["Day"]
    data_has_leap_day = not february_days.empty and february_days.max() == 29

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
    leap day, the leap day entries are removed.

    Args:
        data (dict): dataframe or dictionary of resource data containing
            "Month" (or "month") and "Day" (or "day") timeseries data
        include_leap_day (bool): Whether to include leap day in the resource data.

    Returns:
        dict: Processed resource data with leap day handled according to configuration.

    """

    convert_to_dict = False
    if isinstance(data, dict):
        meta_data, ts_data = separate_timeseries_and_meta_data(data)
        data = pd.DataFrame(ts_data)
        convert_to_dict = True

    case_of_time_cols = "lower" if "month" in data.columns.to_list() else "upper"
    data = data.rename(columns={"month": "Month", "day": "Day"})

    # Check if data includes leap day
    february_days = data[data["Month"] == 2]["Day"]
    data_has_leap_day = not february_days.empty and february_days.max() == 29

    # Remove leap day if needed
    if not include_leap_day and data_has_leap_day:
        # Get index of dataframe that includes leap day
        leap_day_index = (
            data.reset_index(drop=False)
            .set_index(keys=["Month", "Day"], drop=True)
            .loc[(2, 29)]["index"]
        )

        # Drop the leap day data from the dataframe
        data = data.drop(index=leap_day_index)

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

    time_dict = {k: data.get(k) for k in TIME_DATA_KEYS if k in data}

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


def get_n_timesteps_from_year_list(dt: int, year_list: list, include_leap: bool):
    """Get the number of timesteps of data available from a list of resouce years.

    Args:
        dt (int): number of seconds in a timesteps
        year_list (list): list of resource years
        include_leap (bool): whether to include leap days or not.

    Returns:
        int | float: number of timesteps of data available from a year_list
    """
    if isinstance(year_list[0], str) or not include_leap:
        # year is a string if using TMY data, which doesnt allow for leap days
        n_hours_from_yearlist = len(year_list) * 8760
    else:
        # including leap and not using TMY data
        hours_per_simulation_year = [8784 if is_leap_year(y) else 8760 for y in year_list]
        n_hours_from_yearlist = sum(hours_per_simulation_year)

    # convert hours to dt
    n_dt_from_list = n_hours_from_yearlist * (3600 / dt)
    return n_dt_from_list


def get_number_of_resource_years_needed(dt: int, n_timesteps: int, include_leap: bool):
    """Get the number of years required to get n_timesteps worth of resource data.

    Note: this method may return a conservative estimate of the number of years needed.

    Args:
        dt (int): number of seconds in a timesteps
        n_timesteps (int): number of timesteps in the simulation
        include_leap (bool): whether to include leap days or not.

    Returns:
        int: number of years needed to get n_timesteps worth of resource data
    """

    # Get the number of hours in the simulation
    hours_simulated = (dt / 3600) * n_timesteps

    # simulation is definitely < 1 yr, only need 1 year of data
    if hours_simulated < 8760:
        return 1

    if not include_leap:
        # not including leap-year, so all years have 8760 hours
        n_years_needed = hours_simulated // 8760
        if hours_simulated % 8760 == 0:
            # using multiples of 8760, easy to calc number of years needed
            # make sure to use at least 1 resource year
            return int(np.max([n_years_needed, 1]))
        else:
            # requires a partial year, add 1 to account for partial year
            return int(n_years_needed + 1)

    # including leap days

    # check if remainder is multiple of 24, indicating leap days
    remainder_hrs = hours_simulated % 8760
    if remainder_hrs % 24 == 0:
        # remaining hours is divisible by 24 and including leap-day

        # estimate the number of leap-years based on the remaining hours
        n_leap_years = np.min([remainder_hrs // 24, hours_simulated // 8760])
        # number of hours simulated from leap years
        n_hrs_leap_years = n_leap_years * (8760 + 24)
        # number of hours from non-leap years
        n_hrs_non_leap = hours_simulated - n_hrs_leap_years
        #
        if n_hrs_non_leap % 8760 == 0:
            n_years_needed = n_leap_years + (n_hrs_non_leap // 8760)
        else:
            # need an extra year
            n_years_needed = n_leap_years + (n_hrs_non_leap // 8760) + 1
        return n_years_needed

    # conservative estimate of number of years needed
    return int((hours_simulated // 8760) + 1)


def _regenerate_time_columns_at_dt(
    data, start_timestamp, dt_seconds, n, present_time_keys, exclude_leap_day=False
):
    """Regenerate time columns as ``n`` steps of ``dt_seconds`` starting at a timestamp.

    When ``exclude_leap_day`` is True, February 29 is skipped so the regenerated calendar
    keeps the leap day excluded even at the new timestep (extra steps are generated to make
    up for the skipped timestamps).
    """
    freq = pd.Timedelta(seconds=dt_seconds)
    if exclude_leap_day:
        periods = n
        new_index = pd.date_range(start=start_timestamp, periods=periods, freq=freq)
        new_index = new_index[~((new_index.month == 2) & (new_index.day == 29))]
        while len(new_index) < n:
            periods += (n - len(new_index)) + 1
            new_index = pd.date_range(start=start_timestamp, periods=periods, freq=freq)
            new_index = new_index[~((new_index.month == 2) & (new_index.day == 29))]
        new_index = new_index[:n]
    else:
        new_index = pd.date_range(start=start_timestamp, periods=n, freq=freq)
    field_map = {
        "year": new_index.year,
        "month": new_index.month,
        "day": new_index.day,
        "hour": new_index.hour,
        "minute": new_index.minute,
        "second": new_index.second,
    }
    for k in present_time_keys:
        data[k] = np.asarray(field_map[k], dtype=float)
    return data


def resample_resource_data_to_dt(
    data: dict,
    target_dt,
    upsample_method: str | None = None,
    downsample_method: str | None = None,
):
    """Resample resource timeseries from its native timestep to ``target_dt``.

    Resampling is driven by the actual time span of the data (its native timestep, inferred
    from the time columns), not by the number of timesteps. When the simulation timestep is
    smaller than the native timestep the data is upsampled (finer resolution) using
    :meth:`pandas.DataFrame.interpolate`; when it is larger the data is downsampled (coarser
    resolution) using :meth:`pandas.core.resample.Resampler.agg`. Time columns are
    regenerated at ``target_dt`` and scalar metadata is left unchanged.

    Resampling operates on the samples as an evenly spaced sequence at the native timestep.
    Resource data may have non-contiguous calendar timestamps (for example when a leap day
    is removed to keep a clean annual length), so a contiguous synthetic time axis at the
    native timestep is used for the resampling itself and the calendar time columns are
    regenerated afterward.

    Args:
        data (dict): resource data dictionary with timeseries arrays and time columns.
        target_dt (int | float): desired simulation timestep in seconds.
        upsample_method (str | None): interpolation method passed to
            :meth:`pandas.DataFrame.interpolate` when upsampling. No default; when upsampling
            is required this must be set (for example ``"time"``) or a ``ValueError`` is
            raised, so resampling never happens automatically.
        downsample_method (str | None): aggregation passed to
            :meth:`pandas.core.resample.Resampler.agg` when downsampling. No default; when
            downsampling is required this must be set (for example ``"mean"``) or a
            ``ValueError`` is raised, so resampling never happens automatically.

    Returns:
        dict: resource data resampled to ``target_dt``.
    """
    if not isinstance(data, dict) or not target_dt:
        return data

    present_time_keys = [k for k in TIME_DATA_KEYS if k in data]
    if not present_time_keys:
        msg = (
            "Cannot resample resource data to the simulation timestep because the data has "
            "no time columns (year/month/day/hour/minute) to determine its native timestep. "
            "Provide resource data that includes time information."
        )
        raise ValueError(msg)

    assembly = {k: np.asarray(data[k]).astype(int) for k in present_time_keys}
    calendar_index = pd.DatetimeIndex(pd.to_datetime(assembly))
    if len(calendar_index) < 2:
        return data

    # Native timestep is taken from the first two samples so a calendar gap (such as a
    # removed leap day) does not distort it.
    native_dt = (calendar_index[1] - calendar_index[0]).total_seconds()
    if native_dt <= 0:
        msg = (
            "Cannot resample resource data: the native timestep derived from the data's time "
            "columns is non-positive. Ensure the resource data has valid, strictly "
            "increasing timestamps."
        )
        raise ValueError(msg)

    # Nothing to do if the native timestep already matches the target
    if abs(native_dt - float(target_dt)) < 1e-6:
        return data

    # Detect whether the source data has a leap day removed so the regenerated calendar keeps
    # February 29 excluded at the new timestep.
    has_feb29 = bool(((calendar_index.month == 2) & (calendar_index.day == 29)).any())
    spans_leap_year = any(is_leap_year(int(y)) for y in np.unique(calendar_index.year.to_numpy()))
    exclude_leap_day = spans_leap_year and not has_feb29

    native_len = len(calendar_index)
    target_n = round(native_len * native_dt / float(target_dt))
    if target_n < 1:
        msg = (
            f"Cannot resample resource data to a timestep of {target_dt} s: it is larger than "
            f"the total time span of the data ({native_len} samples at {native_dt} s = "
            f"{native_len * native_dt} s), so resampling would produce no timesteps. Use a "
            "smaller timestep or provide more resource data."
        )
        raise ValueError(msg)

    target_freq = pd.Timedelta(seconds=float(target_dt))
    # Use a contiguous synthetic axis anchored at the data's first timestamp so resampling is
    # based on the evenly spaced sample sequence rather than the (possibly gapped) calendar
    # timestamps; ``pd.date_range`` is always contiguous, avoiding removed-leap-day gaps.
    start = calendar_index[0]
    native_index = pd.date_range(
        start=start, periods=native_len, freq=pd.Timedelta(seconds=native_dt)
    )
    target_index = pd.date_range(start=start, periods=target_n, freq=target_freq)

    # Only numeric timeseries columns are resampled; time columns are regenerated afterward.
    _, ts_data = separate_timeseries_and_meta_data(data)
    data_keys = [
        k
        for k in ts_data
        if k not in present_time_keys and len(np.atleast_1d(ts_data[k])) == native_len
    ]
    frame = pd.DataFrame(
        {k: np.asarray(data[k], dtype=float) for k in data_keys}, index=native_index
    )

    upsampling = native_dt > float(target_dt)
    downsampling = native_dt < float(target_dt)
    if upsampling and upsample_method is None:
        raise ValueError(
            f"Resource data has a native timestep of {native_dt:g} s but the simulation uses a "
            f"finer timestep of {float(target_dt):g} s, which requires upsampling. Resampling is "
            "not performed automatically: set the resource `upsample_method` (for example "
            "'time') to explicitly enable upsampling."
        )
    if downsampling and downsample_method is None:
        raise ValueError(
            f"Resource data has a native timestep of {native_dt:g} s but the simulation uses a "
            f"coarser timestep of {float(target_dt):g} s, which requires downsampling. Resampling "
            "is not performed automatically: set the resource `downsample_method` (for example "
            "'mean') to explicitly enable downsampling."
        )

    method = upsample_method if upsampling else downsample_method
    direction = "upsampling" if upsampling else "downsampling"
    warnings.warn(
        f"Resampling resource data from a native timestep of {native_dt:g} s to the simulation "
        f"timestep of {float(target_dt):g} s ({direction} with method '{method}').",
        UserWarning,
        stacklevel=2,
    )

    if upsampling:
        # Upsample: interpolate onto the (finer) target grid
        union_index = frame.index.union(target_index)
        resampled_frame = (
            frame.reindex(union_index).interpolate(method=upsample_method).reindex(target_index)
        )
    elif downsampling:
        # Downsample: aggregate native samples within each (coarser) target interval
        resampled_frame = (
            frame.resample(target_freq, origin="start").agg(downsample_method).reindex(target_index)
        )

    # Fill any residual NaNs at the grid edges introduced by reindexing
    resampled_frame = resampled_frame.ffill().bfill()

    resampled = dict(data)
    for k in data_keys:
        resampled[k] = resampled_frame[k].to_numpy()

    # Regenerate calendar time columns at the target timestep starting from the original
    # first timestamp, keeping any removed leap day excluded.
    resampled = _regenerate_time_columns_at_dt(
        resampled,
        calendar_index[0],
        float(target_dt),
        target_n,
        present_time_keys,
        exclude_leap_day,
    )
    return resampled
