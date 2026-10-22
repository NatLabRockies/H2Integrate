"""Annual capacity-factor projection and replacement-cycle calculations."""

import math
from itertools import pairwise

import numpy as np


_VALID_ANNUAL_EXTRAPOLATION_METHODS = ("tile", "final_sim_value", "time_averaged_sim_value")


def _annualization_steps_per_year(dt):
    """Estimate the number of equal timesteps in a fixed 365-day year.

    Args:
        dt (float): Positive timestep duration in seconds.

    Returns:
        int: Timesteps per year, rounded to the nearest integer and clamped to
        at least one. This is an estimate when ``dt`` does not divide a year evenly.
    """
    return max(1, round(31_536_000 / dt))


def _extrapolate_annual_values(
    simulated_values: np.ndarray,
    plant_life: int,
    method: str | None,
    simulated_durations_years: np.ndarray | None = None,
) -> np.ndarray:
    """Extend or truncate simulated annual values to the plant lifetime.

    Preserve the simulated values first, then fill any remaining plant years
    using the selected method. The average method weights each supplied value
    by the duration it represents, so a partial year contributes proportionally.

    Args:
        simulated_values (np.ndarray): Nonempty, one-dimensional array with one
            value per full or partial simulated year.
        plant_life (int): Positive integer number of plant years to return.
        method (str | None): ``"tile"`` to repeat the values cyclically,
            ``"final_sim_value"`` to hold the last value, or
            ``"time_averaged_sim_value"`` to hold their time-weighted mean. If None,
            a method is required only when multiple simulated segments need to
            be extended to cover plant life; a single segment repeats naturally.
        simulated_durations_years (np.ndarray | None): Positive elapsed duration
            in years for each supplied value. Used only by the average method.
            Defaults to ``None``, treating all values as equal-duration years.

    Returns:
        np.ndarray: One value for each of the ``plant_life`` years, in the
        same units as the supplied values.

    Raises:
        ValueError: If ``method`` is unsupported or needed but not provided.
    """
    if method is not None and method not in _VALID_ANNUAL_EXTRAPOLATION_METHODS:
        raise ValueError(
            f"extrapolation method must be one of {_VALID_ANNUAL_EXTRAPOLATION_METHODS}; "
            f"got {method!r}."
        )

    n_sim_years = simulated_values.size
    if n_sim_years >= plant_life:
        return simulated_values[:plant_life].copy()

    if method is None:
        if n_sim_years == 1:
            method = "tile"
        else:
            raise ValueError(
                "An annual_extrapolation_method is required to extrapolate multiple simulated "
                "annual values across the remaining plant life. Set it in "
                "plant_config['plant']['simulation']['annual_extrapolation_method']."
            )

    if method == "tile":
        n_tiles = math.ceil(plant_life / n_sim_years)
        return np.tile(simulated_values, n_tiles)[:plant_life]

    fill_value = (
        simulated_values[-1]
        if method == "final_sim_value"
        else float(np.average(simulated_values, weights=simulated_durations_years))
    )
    projected = np.full(plant_life, fill_value, dtype=float)
    projected[:n_sim_years] = simulated_values[:plant_life]
    return projected


def _validate_annualization_inputs(
    performance_timeseries,
    rated_performance,
    state_of_health_timeseries,
    eol_soh,
    no_degradation_extrapolation,
    soh_cycle_repetition,
):
    """Validate and normalize performance, SOH, and annualization options.

    Validate both extrapolation options regardless of whether SOH is supplied.
    When SOH is absent, leave it as ``None`` and do not validate ``eol_soh``.
    Timestep duration and plant lifetime are validated by the calling model.

    Args:
        performance_timeseries (array-like): Nonempty, finite, one-dimensional
            performance rates at equal timesteps.
        rated_performance (float): Finite, positive rated performance in the
            same units as the performance rates.
        state_of_health_timeseries (array-like | None): Finite SOH fractions in
            [0, 1], matching the performance array's shape, or ``None`` to
            disable degradation and replacement projection.
        eol_soh (float | None): EOL threshold in [0, 1]. Required only when SOH
            is supplied.
        no_degradation_extrapolation (str): ``"tile"``, ``"final_sim_value"``,
            or ``"time_averaged_sim_value"`` for extrapolating without SOH.
        soh_cycle_repetition (str): ``"all_soh_cycles"`` to repeat all cycles
            or ``"final_soh_cycle"`` to repeat the final cycle.

    Returns:
        tuple[np.ndarray, float, np.ndarray | None, bool]: Float performance
        array, scalar rated performance, float SOH array or ``None``, and a flag
        indicating whether SOH was supplied, in that order.

    Raises:
        ValueError: If an array is empty, nonfinite, or has an invalid shape;
            rated performance is not finite and positive; supplied SOH or its
            threshold is invalid; or either extrapolation option is unsupported.
    """
    performance_timeseries = np.asarray(performance_timeseries, dtype=float)
    if performance_timeseries.size == 0:
        raise ValueError("performance_timeseries must contain at least one value.")
    if performance_timeseries.ndim != 1 or not np.all(np.isfinite(performance_timeseries)):
        raise ValueError("performance_timeseries must be a finite one-dimensional array.")

    rated_performance = float(rated_performance)
    if not np.isfinite(rated_performance) or rated_performance <= 0.0:
        raise ValueError("rated_performance must be finite and greater than zero.")

    if (
        no_degradation_extrapolation is not None
        and no_degradation_extrapolation not in _VALID_ANNUAL_EXTRAPOLATION_METHODS
    ):
        raise ValueError(
            "no_degradation_extrapolation must be one of "
            f"{_VALID_ANNUAL_EXTRAPOLATION_METHODS}; got {no_degradation_extrapolation!r}."
        )

    valid_soh_cycle_repetition_modes = ("all_soh_cycles", "final_soh_cycle")
    if soh_cycle_repetition not in valid_soh_cycle_repetition_modes:
        raise ValueError(
            "soh_cycle_repetition must be one of "
            f"{valid_soh_cycle_repetition_modes}; got {soh_cycle_repetition!r}."
        )

    use_degradation = state_of_health_timeseries is not None
    if use_degradation:
        if eol_soh is None:
            raise ValueError("eol_soh is required when state_of_health_timeseries is provided.")
        state_of_health_timeseries = np.asarray(state_of_health_timeseries, dtype=float)
        if state_of_health_timeseries.size == 0:
            raise ValueError(
                "state_of_health_timeseries must contain at least one value when provided."
            )
        if (
            state_of_health_timeseries.ndim != 1
            or not np.all(np.isfinite(state_of_health_timeseries))
            or state_of_health_timeseries.shape != performance_timeseries.shape
        ):
            raise ValueError(
                "state_of_health_timeseries must be finite, one-dimensional, and match "
                "performance_timeseries length."
            )
        if not np.isfinite(eol_soh) or not 0.0 <= eol_soh <= 1.0:
            raise ValueError("eol_soh must be finite and between zero and one.")
        if np.any((state_of_health_timeseries < 0.0) | (state_of_health_timeseries > 1.0)):
            raise ValueError("state_of_health_timeseries values must be between zero and one.")

    return performance_timeseries, rated_performance, state_of_health_timeseries, use_degradation


def _time_weighted_annual_means(
    timestep_values: np.ndarray, dt: float, start_year: float = 0.0
) -> tuple[np.ndarray, np.ndarray]:
    """Calculate time-weighted means over fixed 365-day plant-year segments.

    Split the series at integer elapsed plant years, preserving its actual
    start and end. A timestep crossing a boundary contributes to both segments
    according to its duration in each. Partial-year means use their actual
    durations rather than treating the unobserved part of a year as zero.

    Args:
        timestep_values (np.ndarray): Nonempty, one-dimensional values, each
            constant over its timestep, such as CF or cost per timestep.
        dt (float): Positive duration of each timestep in seconds.
        start_year (float): Elapsed 365-day plant years at the start of the
            series, not a calendar year. Defaults to zero.

    Returns:
        tuple[np.ndarray, np.ndarray]: Equally sized arrays of time-weighted
        means and durations in years for each segment, in chronological order.
        Means retain the input values' units. The first and final segments can
        be shorter than one year.
    """
    # Keep the series' actual start and end, splitting at intervening plant-year boundaries.
    seconds_per_year = 31_536_000
    sample_duration = dt / seconds_per_year
    sample_edges = start_year + (np.arange(timestep_values.size + 1) * dt) / seconds_per_year
    annual_edges = np.arange(math.floor(start_year) + 1, math.ceil(sample_edges[-1]), dtype=float)
    segment_edges = np.concatenate(([start_year], annual_edges, [sample_edges[-1]]))
    durations = np.diff(segment_edges)

    # Accumulate values multiplied by elapsed time, starting with zero before the first sample.
    cumulative_values = np.concatenate(([0.0], np.cumsum(timestep_values))) * sample_duration

    # Find running totals at segment boundaries and subtract adjacent totals.
    # If 4 hours of a 10-hour timestep fall in one year, that year receives 40%
    # of its contribution and the next year receives 60%.
    segment_totals = np.diff(np.interp(segment_edges, sample_edges, cumulative_values))

    # Divide by each segment's actual duration to get its mean, including for partial years.
    return segment_totals / durations, durations


def _degraded_replacement_cycles(
    timestep_capacity_factors: np.ndarray,
    state_of_health_timeseries: np.ndarray,
    eol_soh: float,
    dt: float,
    plant_life: int,
) -> tuple[list[np.ndarray], list[bool], list[np.ndarray]]:
    """Complete timestep-level cycles before aggregating their annual CF segments.

    An upward state-of-health (SOH) jump greater than 1e-9 marks an observed
    replacement at the first sample with reset SOH, closing the preceding cycle.
    Reaching the end-of-life (EOL) threshold in observed data is not itself a
    replacement; the trailing observed cycle always remains open initially.

    Extend that trailing cycle using the nonnegative SOH loss between its last
    two samples. Project at timestep resolution until EOL is reached, within a
    tolerance of 1e-12, or the remaining plant life is covered. A projected
    replacement requires at least one future timestep, even if the last observed
    SOH is already at or below EOL. Without measurable loss, extend by one step
    only when the last observed SOH is already at or below EOL; otherwise leave
    the cycle incomplete. No extension is made if no plant life remains.

    Projected CF scales the last observed timestep's CF by projected SOH divided
    by the last observed SOH. Negative projected SOH and CF projected from zero
    observed SOH give zero CF. The extension uses whole timesteps, so its final
    timestep may extend past retirement; downstream projection clips that excess.

    Aggregate each cycle's CF into time-weighted means, splitting at fixed
    365-day plant-year boundaries and retaining partial-year segment durations.
    This helper does not repeat cycles or build the annual replacement schedule.

    Args:
        timestep_capacity_factors (np.ndarray): Nonempty, one-dimensional,
            dimensionless CF values, each constant over its simulation timestep.
        state_of_health_timeseries (np.ndarray): One-dimensional SOH fractions
            in [0, 1], aligned with and the same length as the timestep CF array.
        eol_soh (float): SOH threshold in [0, 1] used to predict replacement in
            projected data, not to detect replacement in observed data.
        dt (float): Positive duration of each simulation timestep in seconds.
        plant_life (int): Positive plant lifetime in 365-day years, limiting
            extension of the final cycle beyond the simulation.

    Returns:
        tuple[list[np.ndarray], list[bool], list[np.ndarray]]: Three parallel
        lists in cycle order: arrays of segment mean CF, flags indicating an
        observed or projected replacement at each cycle's end, and arrays of
        segment durations in years. Each duration array matches its CF array
        element by element; its sum is the cycle duration. The final replacement
        flag can remain false when the cycle cannot be completed.
    """
    sample_duration = dt / 31_536_000
    simulation_duration = state_of_health_timeseries.size * sample_duration
    # The difference index identifies the preceding sample; +1 identifies the first
    # sample with reset SOH, which starts the new unit's cycle.
    reset_indices = np.flatnonzero(np.diff(state_of_health_timeseries) > 1e-9) + 1
    trailing_start_index = int(reset_indices[-1]) if reset_indices.size else 0

    # Estimate future SOH loss from the last two samples of the current unit only.
    # A single sample or a nondecreasing SOH cannot establish a degradation rate.
    trailing_soh = state_of_health_timeseries[trailing_start_index:]
    degradation_per_step = (
        max(float(trailing_soh[-2] - trailing_soh[-1]), 0.0) if trailing_soh.size >= 2 else 0.0
    )
    last_observed_soh = float(trailing_soh[-1])
    trailing_has_replacement = False
    if degradation_per_step > 0.0 or last_observed_soh <= eol_soh:
        # Round up to the first future timestep reaching EOL, never an observed sample.
        # Require at least one step even if already below EOL; allow for SOH roundoff.
        steps_to_eol = 1
        if degradation_per_step > 0.0:
            steps_to_eol = max(
                1, math.ceil((last_observed_soh - eol_soh - 1e-12) / degradation_per_step)
            )
        # Extend only as far as the timesteps needed to cover the remaining plant life.
        remaining_steps = max(0, math.ceil((plant_life - simulation_duration) / sample_duration))
        projection_steps = min(steps_to_eol, remaining_steps)
        projected_soh = last_observed_soh - degradation_per_step * np.arange(
            1, projection_steps + 1
        )
        # Scale the last observed CF by the fraction of its SOH remaining at each step.
        # Clip negative SOH to zero; zero starting SOH gives zero CF without division.
        extrapolated_cf = np.zeros(projection_steps)
        if last_observed_soh > 0.0:
            extrapolated_cf = (
                timestep_capacity_factors[-1] * np.maximum(projected_soh, 0.0) / last_observed_soh
            )
        timestep_capacity_factors = np.concatenate((timestep_capacity_factors, extrapolated_cf))
        # Mark a predicted replacement only if a future step actually reaches EOL.
        # A projection cut short by plant life can leave the cycle incomplete.
        trailing_has_replacement = bool(
            projection_steps > 0 and projected_soh[-1] <= eol_soh + 1e-12
        )

    # Each observed reset closes a cycle; the final cycle needs a projected replacement.
    cycle_has_replacement = [True] * reset_indices.size + [trailing_has_replacement]
    cycle_boundaries = np.concatenate(([0], reset_indices, [timestep_capacity_factors.size]))
    # Aggregate each cycle separately so its mean CF uses only that cycle's performance.
    # Split at plant-year boundaries, retaining partial segments at either end of a cycle.
    cycle_cf_segments = []
    cycle_segment_durations = []
    for start_index, end_index in pairwise(cycle_boundaries):
        capacity_factors, durations = _time_weighted_annual_means(
            timestep_capacity_factors[start_index:end_index],
            dt,
            start_year=start_index * sample_duration,
        )
        cycle_cf_segments.append(capacity_factors)
        cycle_segment_durations.append(durations)

    return cycle_cf_segments, cycle_has_replacement, cycle_segment_durations


def _cycle_timeline(cycle_cf_segments, cycle_segment_durations, soh_cycle_repetition, plant_life):
    """Yield observed and repeated cycle placements on one elapsed-year clock.

    Place every supplied cycle once in order, then repeat either the full set
    or the final cycle until plant life is covered. Cycle durations must be
    positive. The final placement can extend beyond retirement; callers clip
    CF contributions or exclude replacement events outside the plant lifetime.

    Args:
        cycle_cf_segments (list[np.ndarray]): CF segment arrays, one per cycle.
            Their order determines the initial cycle sequence.
        cycle_segment_durations (list[np.ndarray]): Segment durations in 365-day
            years, matching each cycle's CF segments element by element.
        soh_cycle_repetition (str): ``"all_soh_cycles"`` to repeat all cycles
            or ``"final_soh_cycle"`` to repeat only the final cycle.
        plant_life (int): Positive integer number of plant years to cover.

    Yields:
        tuple[int, float, np.ndarray]: Cycle index, start offset in elapsed
        plant years, and that cycle's segment-duration array. Only cycles
        starting before retirement are yielded.
    """
    start = 0.0
    indices = range(len(cycle_cf_segments))
    while start < plant_life:
        for index in indices:
            if start >= plant_life:
                return
            durations = cycle_segment_durations[index]
            yield index, start, durations
            start += float(np.sum(durations))
        indices = (
            range(len(cycle_cf_segments))
            if soh_cycle_repetition == "all_soh_cycles"
            else [len(cycle_cf_segments) - 1]
        )


def _project_capacity_factors(
    cycle_cf_segments, soh_cycle_repetition, plant_life, cycle_segment_durations=None
):
    """Project cycle CF segments into annual means across plant life.

    Place all supplied cycles before repeating the selected cycle sequence.
    Weight each segment's contribution by its overlap with each fixed 365-day
    plant year, clipping the final contribution at retirement. This projects
    segment means, not the original timestep-level CF pattern.

    Args:
        cycle_cf_segments (list[np.ndarray]): Nonempty list of dimensionless CF
            segment arrays, in initial cycle order.
        soh_cycle_repetition (str): ``"all_soh_cycles"`` to repeat all cycles
            or ``"final_soh_cycle"`` to repeat only the final cycle.
        plant_life (int): Positive integer number of plant years to return.
        cycle_segment_durations (list[np.ndarray] | None): Segment durations in
            years, matching each cycle's CF array. Defaults to ``None``, which
            treats each segment as one full year. Cycle durations must be positive.

    Returns:
        np.ndarray: Dimensionless mean CF for each of the ``plant_life`` years.
    """
    if cycle_segment_durations is None:
        cycle_segment_durations = [np.ones(segment.size) for segment in cycle_cf_segments]
    annual_cf = np.zeros(plant_life)
    for index, start, durations in _cycle_timeline(
        cycle_cf_segments, cycle_segment_durations, soh_cycle_repetition, plant_life
    ):
        for value, duration in zip(cycle_cf_segments[index], durations, strict=True):
            end = min(start + duration, plant_life)
            for year in range(math.floor(start), math.ceil(end)):
                annual_cf[year] += value * (min(end, year + 1) - max(start, year))
            start += duration
            if start >= plant_life:
                break
    return annual_cf


def _build_replacement_schedule(
    cycle_cf_segments,
    cycle_has_replacement,
    soh_cycle_repetition,
    plant_life,
    cycle_segment_durations=None,
):
    """Count observed and projected replacements in each plant year.

    Each flagged cycle contributes one event at its end, including when that
    cycle is repeated. Bin events into intervals ``[year, year + 1)``; a year
    boundary event belongs to the following year. Exclude initial installation
    and events at or after retirement. Times within 1e-10 years of an integer
    year are treated as exactly on that boundary to absorb floating-point error.

    Args:
        cycle_cf_segments (list[np.ndarray]): Nonempty list of CF segment arrays.
            Used to determine the number of cycles and, when durations are
            omitted, the number of one-year segments in each cycle.
        cycle_has_replacement (list[bool]): One flag per cycle indicating an
            observed or projected replacement at its end.
        soh_cycle_repetition (str): ``"all_soh_cycles"`` to repeat all cycles
            or ``"final_soh_cycle"`` to repeat only the final cycle, after the
            initial sequence has been placed.
        plant_life (int): Positive integer number of plant years to return.
        cycle_segment_durations (list[np.ndarray] | None): Segment durations in
            years, matching each cycle's CF array. Defaults to ``None``, which
            treats each segment as one full year. Cycle durations must be positive.

    Returns:
        np.ndarray: Integer replacement counts for each plant year. Counts can
        exceed one; they are neither annualized rates nor fractions of a replacement.
    """
    if cycle_segment_durations is None:
        cycle_segment_durations = [np.ones(segment.size) for segment in cycle_cf_segments]
    replacement_schedule = np.zeros(plant_life, dtype=int)
    for index, start, durations in _cycle_timeline(
        cycle_cf_segments, cycle_segment_durations, soh_cycle_repetition, plant_life
    ):
        event_time = start + float(np.sum(durations))
        nearest_year = round(event_time)
        if math.isclose(event_time, nearest_year, rel_tol=0.0, abs_tol=1e-10):
            event_time = float(nearest_year)
        if cycle_has_replacement[index] and 0.0 < event_time < plant_life:
            replacement_schedule[math.floor(event_time)] += 1
    return replacement_schedule
