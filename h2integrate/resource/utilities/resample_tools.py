import warnings
from itertools import pairwise

import numpy as np
import pandas as pd

from h2integrate.resource.utilities.data_tools import separate_timeseries_and_meta_data
from h2integrate.resource.utilities.time_tools import TIME_DATA_KEYS, is_leap_year


# A step longer than one day is a calendar gap (e.g. a removed leap day), not a real native
# step, when the data is typically sub-daily.
SUBDAILY_GAP_THRESHOLD_S = 24 * 3600
# TMY files stitch together months from different years, so the step between two months can
# span weeks to years. Any step longer than the shortest month (28 days) is a month jump when
# the data is typically daily or coarser.
MONTH_JUMP_THRESHOLD_S = 28 * 86400


def _regenerate_time_columns_at_dt(
    start_timestamp, dt_seconds, n_timesteps, present_time_keys, include_leap_day=True
):
    """Generate time columns as ``n_timesteps`` steps of ``dt_seconds`` starting at
    ``start_timestamp``.

    When ``include_leap_day`` is False, February 29 is skipped so the regenerated calendar
    keeps the leap day excluded even at the new timestep.

    Args:
        start_timestamp (pandas.Timestamp | datetime.datetime): timestamp of the first sample.
        dt_seconds (int | float): new timestep duration in seconds.
        n_timesteps (int): number of timesteps to generate.
        present_time_keys (list[str]): list of time column keys (e.g. "year", "month",
            "day", "hour", "minute", "second") present in the data to regenerate.
        include_leap_day (bool, optional): whether to include February 29 when generating the
            calendar index. Defaults to True.

    Returns:
        dict[str, numpy.ndarray]: generated time columns keyed by ``present_time_keys``.
    """
    freq = pd.Timedelta(seconds=dt_seconds)
    n_periods = n_timesteps
    while True:
        new_index = pd.date_range(start=start_timestamp, periods=n_periods, freq=freq)
        if include_leap_day:
            break
        new_index = new_index[~((new_index.month == 2) & (new_index.day == 29))]
        if len(new_index) >= n_timesteps:
            break
        # Each skipped February 29 pushes the end later, so extend by the shortfall and retry.
        n_periods += n_timesteps - len(new_index)
    new_index = new_index[:n_timesteps]
    field_map = {
        "year": new_index.year,
        "month": new_index.month,
        "day": new_index.day,
        "hour": new_index.hour,
        "minute": new_index.minute,
        "second": new_index.second,
    }
    return {k: np.asarray(field_map[k], dtype=float) for k in present_time_keys}


def _find_block_starts(calendar_index: pd.DatetimeIndex):
    """Find the start index of each chronological block of a timestamp index.

    A new block starts wherever the month or year decreases from one sample to the next, which
    happens at annual boundaries, TMY month jumps, and out-of-order resource years.

    Args:
        calendar_index (pandas.DatetimeIndex): native timestamps of the resource data.

    Returns:
        list[int]: block start indices, beginning with 0 and ending with ``len(calendar_index)``.
    """
    months = calendar_index.month.to_numpy()
    years = calendar_index.year.to_numpy()
    resets = np.flatnonzero((months[1:] < months[:-1]) | (years[1:] < years[:-1])) + 1
    return [0, *resets.tolist(), len(calendar_index)]


def _get_effective_deltas(deltas: np.ndarray, block_starts: list[int], median_dt: float):
    """Replace non-physical steps with the duration of the preceding step.

    The steps between blocks (e.g. Dec 31 to Jan 1 of an out-of-order year) and calendar gaps
    (e.g. a removed leap day or a TMY month jump) do not describe the sampling interval. Each
    is replaced by the preceding step so the last sample of a block still covers one interval.

    Args:
        deltas (numpy.ndarray): step from each sample to the next, in seconds.
        block_starts (list[int]): block start indices from ``_find_block_starts()``.
        median_dt (float): median positive step in seconds, used if the first step is replaced.

    Returns:
        numpy.ndarray: step durations in seconds with non-physical steps replaced.
    """
    gap_threshold = SUBDAILY_GAP_THRESHOLD_S if median_dt <= 86400 else MONTH_JUMP_THRESHOLD_S
    is_non_physical = deltas > gap_threshold
    # The step into block b is the delta that ends at index block_starts[b] - 1
    is_non_physical[np.asarray(block_starts[1:-1], dtype=int) - 1] = True

    effective_deltas = deltas.copy()
    # Processed in order so consecutive replaced steps all inherit the same preceding step
    for i in np.flatnonzero(is_non_physical):
        effective_deltas[i] = effective_deltas[i - 1] if i > 0 else median_dt
    return effective_deltas


def _count_target_timesteps_per_block(
    step_durations: np.ndarray, block_starts: list[int], target_dt: float
):
    """Count the target timesteps needed to cover each block, rounding partial steps up.

    Args:
        step_durations (numpy.ndarray): duration in seconds covered by each native sample.
        block_starts (list[int]): block start indices from ``_find_block_starts()``.
        target_dt (float): target timestep in seconds.

    Returns:
        list[int]: number of target timesteps in each block.
    """
    # Integer nanoseconds allow exact ceiling division without a float tolerance.
    target_dt_ns = pd.Timedelta(seconds=target_dt).value
    counts = []
    for start, end in pairwise(block_starts):
        block_duration_ns = pd.to_timedelta(step_durations[start:end], unit="s").sum().value
        counts.append((block_duration_ns + target_dt_ns - 1) // target_dt_ns)
    return counts


def resample_resource_data_to_dt(
    data: dict,
    target_dt,
    upsample_method: str | None = None,
    downsample_method: str | None = None,
):
    """Resample resource timeseries from its native timestep to ``target_dt``.

    Resampling is driven by the actual time span of the data (its native timestep(s), inferred
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
            when upsampling. Must be explicitly set when upsampling is needed; otherwise a
            ``ValueError`` is raised.
        downsample_method (str | None): aggregation passed to
            `pandas.DataFrame.agg <https://pandas.pydata.org/docs/reference/api/pandas.DataFrame.agg.html>`_
            when downsampling. Must be explicitly set when downsampling is needed; otherwise a
            ``ValueError`` is raised.

    Returns:
        dict: resource data resampled to ``target_dt``.
    """
    if not isinstance(data, dict) or not target_dt:
        return data
    target_dt = float(target_dt)

    present_time_keys = [k for k in TIME_DATA_KEYS if k in data]
    if not present_time_keys:
        msg = (
            "Cannot resample resource data to the simulation timestep because the data has "
            "no time columns (year/month/day/hour/minute) to determine its native timestep(s). "
            "Provide resource data that includes time information."
        )
        raise ValueError(msg)

    time_dict = {k: np.asarray(data[k]).astype(int) for k in present_time_keys}
    calendar_index = pd.DatetimeIndex(pd.to_datetime(time_dict))
    if len(calendar_index) < 2:
        return data

    native_len = len(calendar_index)
    deltas = (calendar_index[1:] - calendar_index[:-1]).total_seconds().to_numpy()
    pos_deltas = deltas[deltas > 0]
    if pos_deltas.size == 0:
        msg = (
            "Cannot resample resource data: no positive time steps could be derived from the "
            "data's time columns. Ensure the resource data has increasing timestamps."
        )
        raise ValueError(msg)

    # Detect non-chronological transitions (e.g. out-of-order years or TMY month jumps)
    if (deltas < 0).any():
        warnings.warn(
            "Resource data contains negative time steps (e.g., timestamps out of chronological "
            "order or non-chronological resource years). Resampling will process segments in "
            "their given order, preserving block transitions.",
            UserWarning,
            stacklevel=2,
        )

    # Blocks are chronological runs of data; a new block starts where the year or month resets
    block_starts = _find_block_starts(calendar_index)

    # Positive steps exclude backward jumps; their median resists isolated large forward gaps.
    median_dt = float(np.median(pos_deltas))
    effective_deltas = _get_effective_deltas(deltas, block_starts, median_dt)

    # Check if native data already matches target timestep uniformly
    if abs(median_dt - target_dt) < 1e-6 and np.allclose(effective_deltas, target_dt, atol=1e-6):
        return data

    # Each sample covers the duration of its step; the last sample reuses the final step
    step_durations = np.append(effective_deltas, effective_deltas[-1])
    elapsed = np.insert(np.cumsum(effective_deltas), 0, 0.0)

    # Target step count per block to ensure correct time coverage
    block_target_n_timesteps = _count_target_timesteps_per_block(
        step_durations, block_starts, target_dt
    )

    target_n = sum(block_target_n_timesteps)
    total_duration = float(np.sum(step_durations))
    if target_dt > total_duration:
        msg = (
            f"Cannot resample resource data to a timestep of {target_dt:g} s: it is larger than "
            f"the total time span of the data ({native_len} samples, total span "
            f"{total_duration} s), so resampling would produce no timesteps. Use a smaller "
            "timestep or provide more resource data."
        )
        raise ValueError(msg)

    target_offsets = np.arange(target_n) * target_dt
    # Pandas 3 may infer second resolution, which cannot represent fractional resampling bins.
    native_index = pd.to_timedelta(elapsed, unit="s").as_unit("ns")
    target_index = pd.to_timedelta(target_offsets, unit="s").as_unit("ns")

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

    # Native steps coarser than the target need upsampling; finer steps need downsampling
    upsampling = np.max(effective_deltas) > target_dt
    downsampling = np.min(effective_deltas) < target_dt

    if upsampling and upsample_method is None:
        raise ValueError(
            f"Resource data has time steps larger than {target_dt:g} s, which requires "
            "upsampling. Resampling is not performed automatically: set the resource "
            "`upsample_method` (for example 'time') to explicitly enable upsampling."
        )
    if downsampling and downsample_method is None:
        raise ValueError(
            f"Resource data has time steps smaller than {target_dt:g} s, which requires "
            "downsampling. Resampling is not performed automatically: set the resource "
            "`downsample_method` (for example 'mean') to explicitly enable downsampling."
        )

    if upsampling and downsampling:
        direction = "mixed resampling"
        method_desc = f"upsample: '{upsample_method}', downsample: '{downsample_method}'"
    elif upsampling:
        direction = "upsampling"
        method_desc = f"'{upsample_method}'"
    else:
        direction = "downsampling"
        method_desc = f"'{downsample_method}'"
    warnings.warn(
        f"Resampling resource data to the simulation timestep of {target_dt:g} s "
        f"({direction} with {method_desc}).",
        UserWarning,
        stacklevel=2,
    )

    target_freq = pd.Timedelta(seconds=target_dt)
    if direction == "upsampling":
        # Interpolate onto the (finer) target grid
        union_index = frame.index.union(target_index)
        resampled_frame = (
            frame.reindex(union_index).interpolate(method=upsample_method).reindex(target_index)
        )
    elif direction == "downsampling":
        # Aggregate native samples within each (coarser) target interval
        resampled_frame = (
            frame.resample(target_freq, origin="start").agg(downsample_method).reindex(target_index)
        )
    else:
        # Mixed: first aggregate finer intervals, then interpolate coarser intervals
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

    # Detect whether the source data has a leap day removed so the regenerated calendar keeps
    # February 29 excluded at the new timestep.
    has_feb29 = bool(((calendar_index.month == 2) & (calendar_index.day == 29)).any())
    spans_leap_year = any(is_leap_year(int(y)) for y in np.unique(calendar_index.year.to_numpy()))
    include_leap_day = not spans_leap_year or has_feb29

    # Regenerate calendar time columns per block at target_dt, preserving original block order
    # (even when years are non-chronological) and leap-day settings.
    block_time_cols = [
        _regenerate_time_columns_at_dt(
            calendar_index[start],
            target_dt,
            n_block_timesteps,
            present_time_keys,
            include_leap_day=include_leap_day,
        )
        for start, n_block_timesteps in zip(block_starts[:-1], block_target_n_timesteps)
    ]
    for k in present_time_keys:
        resampled[k] = np.concatenate([cols[k] for cols in block_time_cols])
    return resampled
