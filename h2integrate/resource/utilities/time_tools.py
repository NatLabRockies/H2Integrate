from calendar import isleap
from datetime import timezone, timedelta

import numpy as np
import pandas as pd


def process_leap_day(data: dict, include_leap_day: bool):
    """Add or remove leap-day handling based on ``include_leap_day`` and the data.

    Behavior:

    - ``include_leap_day=False``: if the data contains a leap day (February 29) it is
      removed; if the data has no leap day the data is returned unchanged.
    - ``include_leap_day=True``: if the data contains a leap day it is kept unchanged; if
      the data is for a leap year but does not contain a leap day a ``ValueError`` is
      raised (a leap day cannot be added when it is not present in the source data). For
      a non-leap year there is no leap day and the data is returned unchanged.

    Args:
        data (dict): DataFrame-like dictionary of resource data containing year, month,
            and day columns.
        include_leap_day (bool): Whether the leap day should be included.

    Returns:
        dict: Resource data with leap-day handling applied.

    Raises:
        ValueError: If ``include_leap_day`` is True for a leap year whose data does not
            contain a leap day.
    """

    convert_to_dict = False
    if isinstance(data, dict):
        data = pd.DataFrame(data)
        convert_to_dict = True

    case_of_time_cols = "lower" if "month" in data.columns.to_list() else "upper"
    data = data.rename(columns={"year": "Year", "month": "Month", "day": "Day"})

    february = data[data["Month"] == 2]
    data_has_leap_day = (not february.empty) and int(february["Day"].max()) == 29

    if include_leap_day:
        # Keep the leap day when present; error only if a leap year is missing it
        if not data_has_leap_day and "Year" in data.columns:
            year = int(data["Year"].iloc[0])
            if isleap(year):
                msg = (
                    f"include_leap_day is True but the resource data for leap year {year} "
                    "does not contain a leap day (February 29). A leap day cannot be added "
                    "when it is not present in the source data; either provide data that "
                    "includes the leap day or set include_leap_day to False."
                )
                raise ValueError(msg)
    elif data_has_leap_day:
        # Remove the leap day when it is present but not wanted
        leap_day_rows = data[(data["Month"] == 2) & (data["Day"] == 29)]
        data = data.drop(index=leap_day_rows.index)

    if case_of_time_cols == "lower":
        data = data.rename(columns={"Year": "year", "Month": "month", "Day": "day"})

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


TIME_COLUMN_KEYS = ["year", "month", "day", "hour", "minute", "second"]


def _is_timeseries_value(value):
    """Return True if ``value`` is an array-like of numeric timeseries data."""
    return isinstance(value, np.ndarray | list | tuple) and not isinstance(value, str | bytes)


def _infer_native_length(data: dict, present_time_keys: list):
    """Infer the native (per-timestep) length of the resource timeseries data.

    The length is taken from the time columns when present, otherwise from the
    most common array length among the dictionary values.

    Args:
        data (dict): resource data dictionary.
        present_time_keys (list): time-column keys that exist in ``data``.

    Returns:
        int | None: the inferred native length, or None if it cannot be determined.
    """
    if present_time_keys:
        return len(np.asarray(data[present_time_keys[0]]))

    lengths = [len(v) for v in data.values() if _is_timeseries_value(v)]
    if not lengths:
        return None
    # Use the most common array length as the native timeseries length
    return max(set(lengths), key=lengths.count)


def conform_resource_data_to_n_timesteps(data: dict, n_timesteps: int):
    """Slice resource timeseries data to match the simulation horizon.

    Resource data is expected to contain at least ``n_timesteps`` of data. When
    the native resource length is longer than ``n_timesteps`` (for example a full
    year of data for a sub-annual simulation, or the trailing year of a multi-year
    download), the timeseries are sliced to ``n_timesteps``. Scalar metadata (site
    info, units, etc.) is left unchanged.

    Args:
        data (dict): resource data dictionary with timeseries arrays and metadata.
        n_timesteps (int): target number of timesteps for the simulation.

    Returns:
        dict: resource data with timeseries sliced to ``n_timesteps``.

    Raises:
        ValueError: if the resource data contains fewer than ``n_timesteps`` of data.
    """
    if not isinstance(data, dict) or n_timesteps is None:
        return data

    present_time_keys = [k for k in TIME_COLUMN_KEYS if k in data]
    native_len = _infer_native_length(data, present_time_keys)

    # Nothing to do if the native length is unknown or already matches the horizon
    if not native_len or native_len == n_timesteps:
        return data

    if native_len < n_timesteps:
        msg = (
            f"Not enough resource data to cover the simulation horizon. The resource "
            f"data provides {native_len} timesteps, but the simulation requires "
            f"{n_timesteps} timesteps. Provide additional years of resource data or "
            f"shorten the simulation horizon."
        )
        raise ValueError(msg)

    conformed = {}
    for key, value in data.items():
        if _is_timeseries_value(value) and len(value) == native_len:
            conformed[key] = np.asarray(value)[:n_timesteps]
        else:
            conformed[key] = value

    return conformed


def concatenate_resource_years(yearly_data: list):
    """Concatenate multiple years of resource data into a single continuous series.

    The timeseries arrays from each year -- including the calendar time columns --
    are concatenated in order, so the combined series preserves the real timestamps
    of the source data (for example a removed leap day leaves a February 29 gap while
    every other timestamp still matches the downloaded data). Scalar metadata (site
    info, units, etc.) is taken from the first year.

    Args:
        yearly_data (list): list of resource data dictionaries, one per year, in
            chronological order.

    Returns:
        dict: a single resource data dictionary spanning all provided years.
    """
    if not yearly_data:
        return {}
    if len(yearly_data) == 1:
        return yearly_data[0]

    base = yearly_data[0]
    native_len = _infer_native_length(base, [k for k in TIME_COLUMN_KEYS if k in base])

    combined = dict(base)
    for key, value in base.items():
        if _is_timeseries_value(value) and len(value) == native_len:
            combined[key] = np.concatenate(
                [np.asarray(year_data[key]) for year_data in yearly_data]
            )

    return combined


def _regenerate_time_columns_at_dt(
    data, start_timestamp, dt_seconds, n, present_time_keys, exclude_leap_day=False
):
    """Regenerate time columns as ``n`` steps of ``dt_seconds`` starting at a timestamp.

    When ``exclude_leap_day`` is True, February 29 is skipped so the regenerated
    calendar keeps the leap day excluded even at the new timestep (extra steps are
    generated to make up for the skipped timestamps).
    """
    freq = pd.Timedelta(seconds=dt_seconds)
    if exclude_leap_day:
        periods = n
        new_index = pd.date_range(start=start_timestamp, periods=periods, freq=freq)
        new_index = new_index[~((new_index.month == 2) & (new_index.day == 29))]
        # Generate additional steps until enough non-leap-day timestamps are available
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
    upsample_method: str = "time",
    downsample_method: str = "mean",
):
    """Resample resource timeseries from its native timestep to ``target_dt``.

    Resampling is driven by the actual time span of the data (its native timestep,
    inferred from the time columns), not by the number of timesteps. When the
    simulation timestep is smaller than the native timestep the data is upsampled
    (finer resolution) using :meth:`pandas.DataFrame.interpolate`; when it is larger
    the data is downsampled (coarser resolution) using
    :meth:`pandas.core.resample.Resampler.agg`. Time columns are regenerated at
    ``target_dt`` and scalar metadata is left unchanged.

    Resampling operates on the samples as an evenly spaced sequence at the native
    timestep. Resource data may have non-contiguous calendar timestamps (for example
    when a leap day is removed to keep a clean annual length), so a contiguous
    synthetic time axis at the native timestep is used for the resampling itself and
    the calendar time columns are regenerated afterward.

    Args:
        data (dict): resource data dictionary with timeseries arrays and time columns.
        target_dt (int | float): desired simulation timestep in seconds.
        upsample_method (str): interpolation method passed to
            :meth:`pandas.DataFrame.interpolate` when upsampling. Defaults to ``"time"``
            (linear interpolation that respects the sample spacing).
        downsample_method (str): aggregation passed to
            :meth:`pandas.core.resample.Resampler.agg` when downsampling. Defaults to
            ``"mean"``.

    Returns:
        dict: resource data resampled to ``target_dt``.
    """
    if not isinstance(data, dict) or not target_dt:
        return data

    present_time_keys = [k for k in TIME_COLUMN_KEYS if k in data]
    if not present_time_keys:
        # Without time columns the native timestep cannot be determined, so the data
        # cannot be resampled to the requested timestep.
        msg = (
            "Cannot resample resource data to the simulation timestep because the data "
            "has no time columns (year/month/day/hour/minute) to determine its native "
            "timestep. Provide resource data that includes time information."
        )
        raise ValueError(msg)

    assembly = {k: np.asarray(data[k]).astype(int) for k in present_time_keys}
    calendar_index = pd.DatetimeIndex(pd.to_datetime(assembly))
    if len(calendar_index) < 2:
        return data

    # Native timestep is taken from the first two samples so that a calendar gap
    # (such as a removed leap day) does not distort it.
    native_dt = (calendar_index[1] - calendar_index[0]).total_seconds()
    if native_dt <= 0:
        msg = (
            "Cannot resample resource data: the native timestep derived from the data's "
            "time columns is non-positive. Ensure the resource data has valid, strictly "
            "increasing timestamps."
        )
        raise ValueError(msg)

    # Nothing to do if the native timestep already matches the target
    if abs(native_dt - float(target_dt)) < 1e-6:
        return data

    # Detect whether the source data has a leap day removed so the regenerated
    # calendar keeps February 29 excluded at the new timestep.
    has_feb29 = bool(((calendar_index.month == 2) & (calendar_index.day == 29)).any())
    spans_leap_year = any(isleap(int(y)) for y in np.unique(calendar_index.year.to_numpy()))
    exclude_leap_day = spans_leap_year and not has_feb29

    native_len = len(calendar_index)
    target_n = int(round(native_len * native_dt / float(target_dt)))
    if target_n < 1:
        msg = (
            f"Cannot resample resource data to a timestep of {target_dt} s: it is larger "
            f"than the total time span of the data ({native_len} samples at {native_dt} s "
            f"= {native_len * native_dt} s), so resampling would produce no timesteps. Use "
            "a smaller timestep or provide more resource data."
        )
        raise ValueError(msg)

    target_freq = pd.Timedelta(seconds=float(target_dt))
    # Use a contiguous synthetic axis anchored at the data's first timestamp so that
    # resampling is based on the evenly spaced sample sequence rather than the
    # (possibly gapped) calendar timestamps. ``pd.date_range`` is always contiguous,
    # so this avoids the gaps a removed leap day would otherwise introduce.
    start = calendar_index[0]
    native_index = pd.date_range(
        start=start, periods=native_len, freq=pd.Timedelta(seconds=native_dt)
    )
    target_index = pd.date_range(start=start, periods=target_n, freq=target_freq)

    # Only the numeric timeseries columns are resampled; time columns are regenerated
    data_keys = [
        k
        for k in data
        if k not in present_time_keys
        and _is_timeseries_value(data[k])
        and len(data[k]) == native_len
    ]
    frame = pd.DataFrame(
        {k: np.asarray(data[k], dtype=float) for k in data_keys}, index=native_index
    )

    if native_dt > float(target_dt):
        # Upsample: interpolate onto the (finer) target grid
        union_index = frame.index.union(target_index)
        resampled_frame = (
            frame.reindex(union_index).interpolate(method=upsample_method).reindex(target_index)
        )
    else:
        # Downsample: aggregate native samples within each (coarser) target interval
        resampled_frame = (
            frame.resample(target_freq, origin="start").agg(downsample_method).reindex(target_index)
        )

    # Fill any residual NaNs at the grid edges introduced by reindexing
    resampled_frame = resampled_frame.ffill().bfill()

    resampled = dict(data)
    for k in data_keys:
        resampled[k] = resampled_frame[k].to_numpy()

    # Regenerate calendar time columns at the target timestep starting from the
    # original first timestamp, keeping any removed leap day excluded.
    resampled = _regenerate_time_columns_at_dt(
        resampled,
        calendar_index[0],
        float(target_dt),
        target_n,
        present_time_keys,
        exclude_leap_day,
    )
    return resampled
