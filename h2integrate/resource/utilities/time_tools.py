import math
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
        "dt": int(dt.total_seconds()),
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
    data, start_timestamp, dt_seconds, n_timesteps, present_time_keys, exclude_leap_day=False
):
    """Regenerate time columns as ``n`` steps of ``dt_seconds`` starting at a timestamp.

    When ``exclude_leap_day`` is True, February 29 is skipped so the regenerated calendar
    keeps the leap day excluded even at the new timestep (extra steps are generated to make
    up for the skipped timestamps).

    Args:
        data (dict): resource data dictionary whose time column arrays are to be updated.
        start_timestamp (pandas.Timestamp | datetime.datetime): timestamp of the first sample.
        dt_seconds (int | float): new timestep duration in seconds.
        n_timesteps (int): number of timesteps to generate.
        present_time_keys (list[str]): list of time column keys (e.g. "year", "month",
            "day", "hour", "minute", "second") present in the data to regenerate.
        exclude_leap_day (bool, optional): whether to skip February 29 when generating the
            calendar index. Defaults to False.

    Returns:
        dict: resource data dictionary with updated time columns.
    """
    freq = pd.Timedelta(seconds=dt_seconds)
    if exclude_leap_day:
        periods = n_timesteps
        new_index = pd.date_range(start=start_timestamp, periods=periods, freq=freq)
        new_index = new_index[~((new_index.month == 2) & (new_index.day == 29))]
        while len(new_index) < n_timesteps:
            periods += (n_timesteps - len(new_index)) + 1
            new_index = pd.date_range(start=start_timestamp, periods=periods, freq=freq)
            new_index = new_index[~((new_index.month == 2) & (new_index.day == 29))]
        new_index = new_index[:n_timesteps]
    else:
        new_index = pd.date_range(start=start_timestamp, periods=n_timesteps, freq=freq)
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
    `pandas.DataFrame.interpolate <https://pandas.pydata.org/docs/reference/api/pandas.DataFrame.interpolate.html>`_;
    when it is larger the data is downsampled (coarser resolution) using
    `pandas.DataFrame.agg <https://pandas.pydata.org/docs/reference/api/pandas.DataFrame.agg.html>`_.
    Time columns are regenerated at ``target_dt`` and scalar metadata is left unchanged.

    Resampling operates on an elapsed timeline constructed from the input timestamps,
    so non-uniform sample intervals (for example 1-hour and 2-hour intervals) receive target
    timestamps proportional to their physical duration. For multi-year or discontinuous data,
    the transition between segments completes each period using the preceding interval,
    interpolating across the boundary between the final value of the preceding segment and the
    first value of the subsequent segment. Time columns are regenerated at ``target_dt``,
    preserving the original sequence of years and leap-day settings.

    Args:
        data (dict): resource data dictionary with timeseries arrays and time columns.
        target_dt (int | float): desired simulation timestep in seconds.
        upsample_method (str | None): interpolation method passed to
            `pandas.DataFrame.interpolate <https://pandas.pydata.org/docs/reference/api/pandas.DataFrame.interpolate.html>`_
            when upsampling. Must be explicitly set (for example ``"time"``) when upsampling is
            needed; otherwise a ``ValueError`` is raised.
        downsample_method (str | None): aggregation passed to
            `pandas.DataFrame.agg <https://pandas.pydata.org/docs/reference/api/pandas.DataFrame.agg.html>`_
            when downsampling. Must be explicitly set (for example ``"mean"``)  when downsampling
            is needed; otherwise a ``ValueError`` is raised.

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

    # Infer native timestep from the median/mean positive step across consecutive samples
    # so an edge calendar gap (e.g., a series starting adjacent to a removed leap day)
    # does not distort it.
    deltas = pd.Series((calendar_index[1:] - calendar_index[:-1]).total_seconds())
    pos_deltas = deltas[deltas > 0]
    if pos_deltas.empty:
        msg = (
            "Cannot resample resource data: no positive time steps could be derived from the "
            "data's time columns. Ensure the resource data has increasing timestamps."
        )
        raise ValueError(msg)

    native_len = len(calendar_index)
    median_dt = float(pos_deltas.median())

    # Detect whether the source data has a leap day removed so the regenerated calendar keeps
    # February 29 excluded at the new timestep.
    has_feb29 = bool(((calendar_index.month == 2) & (calendar_index.day == 29)).any())
    spans_leap_year = any(is_leap_year(int(y)) for y in np.unique(calendar_index.year.to_numpy()))
    exclude_leap_day = spans_leap_year and not has_feb29

    # Detect non-chronological transitions (e.g. out-of-order years or TMY month jumps)
    len(np.unique(calendar_index.year)) > 1 and len(calendar_index) <= 8784
    has_negative_deltas = bool((deltas < 0).any())
    if has_negative_deltas:
        warnings.warn(
            "Resource data contains negative time steps (e.g., timestamps out of chronological "
            "order or non-chronological resource years). Resampling will process segments in "
            "their given order, preserving block transitions.",
            UserWarning,
            stacklevel=2,
        )

    # Detect annual or segment boundaries where chronological year/month resets
    block_starts = [0]
    for i in range(native_len - 1):
        if calendar_index.month[i + 1] < calendar_index.month[i]:
            block_starts.append(i + 1)
        elif calendar_index.year[i + 1] < calendar_index.year[i]:
            block_starts.append(i + 1)
    block_starts.append(native_len)

    # Compute effective step durations across samples
    # For transitions across boundaries, large TMY gaps, or calendar gaps (e.g. removed leap day),
    # complete the period using the local step duration of the preceding sample.
    effective_deltas = deltas.to_numpy().copy()
    for b_idx in range(1, len(block_starts) - 1):
        trans_i = block_starts[b_idx] - 1
        effective_deltas[trans_i] = effective_deltas[trans_i - 1] if trans_i > 0 else median_dt
    for i in range(len(effective_deltas)):
        # Any delta exceeding 24 hours when typical step is sub-daily represents a calendar gap
        if deltas.iloc[i] > 24 * 3600 and median_dt <= 24 * 3600:
            effective_deltas[i] = effective_deltas[i - 1] if i > 0 else median_dt
        elif deltas.iloc[i] > 28 * 86400:
            effective_deltas[i] = effective_deltas[i - 1] if i > 0 else median_dt

    # Check if native data already matches target timestep uniformly
    if abs(median_dt - float(target_dt)) < 1e-6 and np.allclose(
        effective_deltas, float(target_dt), atol=1e-6
    ):
        return data

    step_durations = np.append(effective_deltas, effective_deltas[-1])
    elapsed = np.insert(np.cumsum(effective_deltas), 0, 0.0)

    # Calculate target step count per block to ensure correct time coverage
    block_target_ns = []
    for b in range(len(block_starts) - 1):
        s_i = block_starts[b]
        e_i = block_starts[b + 1]
        b_dur = float(np.sum(step_durations[s_i:e_i]))
        block_target_ns.append(math.ceil((b_dur / float(target_dt)) - 1e-9))

    target_n = sum(block_target_ns)
    total_duration = float(np.sum(step_durations))
    if float(target_dt) > total_duration:
        msg = (
            f"Cannot resample resource data to a timestep of {target_dt} s: it is larger than "
            f"the total time span of the data ({native_len} samples, total span "
            f"{total_duration} s), so resampling would produce no timesteps. Use a smaller "
            "timestep or provide more resource data."
        )
        raise ValueError(msg)

    target_offsets = np.arange(target_n) * float(target_dt)
    native_index = pd.to_timedelta(elapsed, unit="s")
    target_index = pd.to_timedelta(target_offsets, unit="s")

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

    min_step = np.min(effective_deltas)
    max_step = np.max(effective_deltas)
    upsampling = min_step > float(target_dt) or max_step > float(target_dt)
    downsampling = min_step < float(target_dt) or max_step < float(target_dt)

    if upsampling and upsample_method is None:
        raise ValueError(
            f"Resource data has time steps larger than {float(target_dt):g} s, which requires "
            "upsampling. Resampling is not performed automatically: set the resource "
            "`upsample_method` (for example 'time') to explicitly enable upsampling."
        )
    if downsampling and downsample_method is None:
        raise ValueError(
            f"Resource data has time steps smaller than {float(target_dt):g} s, which requires "
            "downsampling. Resampling is not performed automatically: set the resource "
            "`downsample_method` (for example 'mean') to explicitly enable downsampling."
        )

    direction = (
        "upsampling"
        if (upsampling and not downsampling)
        else ("downsampling" if (downsampling and not upsampling) else "mixed resampling")
    )
    method_desc = (
        f"'{upsample_method}'"
        if (upsampling and not downsampling)
        else (
            f"'{downsample_method}'"
            if (downsampling and not upsampling)
            else f"upsample: '{upsample_method}', downsample: '{downsample_method}'"
        )
    )
    warnings.warn(
        f"Resampling resource data to the simulation timestep of {float(target_dt):g} s "
        f"({direction} with {method_desc}).",
        UserWarning,
        stacklevel=2,
    )

    if upsampling and not downsampling:
        # Upsample: interpolate onto the (finer) target grid
        union_index = frame.index.union(target_index)
        resampled_frame = (
            frame.reindex(union_index).interpolate(method=upsample_method).reindex(target_index)
        )
    elif downsampling and not upsampling:
        # Downsample: aggregate native samples within each (coarser) target interval
        target_freq = pd.Timedelta(seconds=float(target_dt))
        resampled_frame = (
            frame.resample(target_freq, origin="start").agg(downsample_method).reindex(target_index)
        )
    else:
        # Mixed: first aggregate finer intervals, then interpolate coarser intervals
        target_freq = pd.Timedelta(seconds=float(target_dt))
        resampled_frame = (
            frame.resample(target_freq, origin="start")
            .agg(downsample_method)
            .reindex(target_index)
            .interpolate(method=upsample_method)
        )

    # Fill any residual NaNs at the grid edges introduced by reindexing
    resampled_frame = resampled_frame.ffill().bfill()

    resampled = dict(data)
    for k in data_keys:
        resampled[k] = resampled_frame[k].to_numpy()

    # Regenerate calendar time columns per block at target_dt, preserving original block order
    # (even when years are non-chronological) and leap-day settings.
    if len(block_starts) > 2:
        reg_time_cols = {k: [] for k in present_time_keys}
        for b in range(len(block_starts) - 1):
            b_start_idx = block_starts[b]
            b_start_ts = calendar_index[b_start_idx]
            b_target_n = block_target_ns[b]
            b_dict = {}
            _regenerate_time_columns_at_dt(
                b_dict,
                b_start_ts,
                float(target_dt),
                b_target_n,
                present_time_keys,
                exclude_leap_day,
            )
            for k in present_time_keys:
                reg_time_cols[k].append(b_dict[k])
        for k in present_time_keys:
            resampled[k] = np.concatenate(reg_time_cols[k])
    else:
        resampled = _regenerate_time_columns_at_dt(
            resampled,
            calendar_index[0],
            float(target_dt),
            target_n,
            present_time_keys,
            exclude_leap_day,
        )
    return resampled
