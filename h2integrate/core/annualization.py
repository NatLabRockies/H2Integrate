"""Annual capacity-factor projection and replacement-cycle calculations."""

import math
from itertools import pairwise

import numpy as np


_VALID_EXTRAPOLATION_METHODS = ("tile", "final_sim_value", "average_sim_value")


def _annualization_steps_per_year(dt):
    """Number of timesteps that make up one year for a timestep length ``dt`` (seconds)."""
    return max(1, round(31_536_000 / dt))


def _extrapolate_annual_values(simulated_values, plant_life, method):
    """Extend per-simulated-year values across the full plant life.

    Args:
        simulated_values (np.ndarray): one value per simulated year.
        plant_life (int): number of years to project across.
        method (str): one of ``"tile"`` (repeat simulated years cyclically),
            ``"final_sim_value"`` (hold the last simulated year), or
            ``"average_sim_value"`` (hold the simulated average).

    Returns:
        np.ndarray: ``plant_life`` annual values.
    """
    if method not in _VALID_EXTRAPOLATION_METHODS:
        raise ValueError(
            f"extrapolation method must be one of {_VALID_EXTRAPOLATION_METHODS}; got {method!r}."
        )

    n_sim_years = simulated_values.size
    if method == "tile":
        n_tiles = math.ceil(plant_life / n_sim_years)
        return np.tile(simulated_values, n_tiles)[:plant_life]

    fill_value = (
        simulated_values[-1] if method == "final_sim_value" else float(np.mean(simulated_values))
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
    """Validate and coerce the inputs to ``calculate_annual_cf_and_replacement_schedule``.

    Returns:
        tuple: the coerced ``performance_timeseries`` array, ``rated_performance`` float,
        ``state_of_health_timeseries`` (array or None), and a ``use_degradation`` flag.
    """
    performance_timeseries = np.asarray(performance_timeseries, dtype=float)
    if performance_timeseries.size == 0:
        raise ValueError("performance_timeseries must contain at least one value.")
    if performance_timeseries.ndim != 1 or not np.all(np.isfinite(performance_timeseries)):
        raise ValueError("performance_timeseries must be a finite one-dimensional array.")

    rated_performance = float(rated_performance)
    if not np.isfinite(rated_performance) or rated_performance <= 0.0:
        raise ValueError("rated_performance must be finite and greater than zero.")

    if no_degradation_extrapolation not in _VALID_EXTRAPOLATION_METHODS:
        raise ValueError(
            "no_degradation_extrapolation must be one of "
            f"{_VALID_EXTRAPOLATION_METHODS}; got {no_degradation_extrapolation!r}."
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


def _annual_cf_segments(
    capacity_factors: np.ndarray, dt: float, start_year: float = 0.0
) -> tuple[np.ndarray, np.ndarray]:
    """Average timestep CF into fixed 365-day plant-year segments.

    Args:
        capacity_factors (np.ndarray): One-dimensional CF values, each constant
            over its timestep.
        dt (float): Duration of each timestep in seconds.
        start_year (float): Elapsed plant years at the start of the series.

    Returns:
        tuple[np.ndarray, np.ndarray]: Time-weighted mean CF and duration in
        years for each segment, including partial first and final years.
    """
    # Keep the series' actual start and end, splitting at intervening plant-year boundaries.
    sample_duration = dt / 31_536_000
    sample_edges = start_year + np.arange(capacity_factors.size + 1) * sample_duration
    annual_edges = np.arange(math.floor(start_year) + 1, math.ceil(sample_edges[-1]), dtype=float)
    segment_edges = np.concatenate(([start_year], annual_edges, [sample_edges[-1]]))
    durations = np.diff(segment_edges)

    # Accumulate CF multiplied by elapsed time, starting with zero before the first sample.
    cumulative_cf = np.concatenate(([0.0], np.cumsum(capacity_factors))) * sample_duration

    # Find running totals at segment boundaries and subtract adjacent totals.
    # If 4 hours of a 10-hour timestep fall in one year, that year receives 40%
    # of its contribution and the next year receives 60%.
    segment_totals = np.diff(np.interp(segment_edges, sample_edges, cumulative_cf))

    # Divide by each segment's actual duration to get its mean CF, including for partial years.
    return segment_totals / durations, durations


def _degraded_replacement_cycles(
    timestep_capacity_factors: np.ndarray,
    state_of_health_timeseries: np.ndarray,
    eol_soh: float,
    dt: float,
    plant_life: int,
) -> tuple[list[np.ndarray], list[bool], list[np.ndarray]]:
    """Complete timestep-level cycles before aggregating their annual CF segments.

    An upward state-of-health (SOH) jump greater than 1e-9 marks a replacement
    and closes the preceding cycle. The final cycle is also complete if its last
    observed SOH is at or below the end-of-life (EOL) threshold.

    If the final cycle is incomplete, extrapolate SOH using the loss between its
    last two samples. Extend at the simulation timestep until EOL is reached or
    the remaining plant life is covered. Projected CF scales the last timestep's
    CF by projected SOH divided by the last observed SOH, clipping negative SOH
    to zero. No extension is made with fewer than two samples or no SOH loss.

    Aggregate each cycle's CF into time-weighted means, splitting at fixed
    365-day plant-year boundaries and retaining partial-year segment durations.
    This helper does not repeat cycles or build the annual replacement schedule.

    Args:
            timestep_capacity_factors (np.ndarray): One-dimensional, dimensionless CF
                    values, each constant over its simulation timestep.
            state_of_health_timeseries (np.ndarray): One-dimensional SOH fractions in
                    [0, 1], aligned with and the same length as the timestep CF array.
            eol_soh (float): SOH fraction in [0, 1] at or below which a cycle ends.
            dt (float): Duration of each simulation timestep in seconds.
            plant_life (int): Plant lifetime in 365-day years, limiting how far the
                    final cycle is extended beyond the simulation.

    Returns:
            tuple[list[np.ndarray], list[bool], list[np.ndarray]]: Three parallel
            lists in observed cycle order:

                    - Cycle CF arrays containing the mean CF for each annual or
                        partial-year segment of that cycle.
                    - Completion flags indicating whether each cycle ends in an
                        observed replacement or reaches EOL. A completed cycle represents
                        one replacement event at its end; the final cycle may be incomplete.
                    - Segment-duration arrays in years, matching the corresponding CF
                        arrays element by element. Their sums give the cycle durations.
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
        capacity_factors, durations = _annual_cf_segments(
            timestep_capacity_factors[start_index:end_index],
            dt,
            start_year=start_index * sample_duration,
        )
        cycle_cf_segments.append(capacity_factors)
        cycle_segment_durations.append(durations)

    return cycle_cf_segments, cycle_has_replacement, cycle_segment_durations


def _cycle_timeline(cycle_cf_segments, cycle_segment_durations, soh_cycle_repetition, plant_life):
    """Yield cycle indices and offsets on the shared CF/replacement clock."""
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
    """Duration-weight annual CF segments into fixed plant-year bins."""
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
    """Count discrete cycle-end events in [year, year + 1), excluding retirement."""
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
