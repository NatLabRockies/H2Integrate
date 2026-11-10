"""Annual capacity-factor projection and replacement-cycle calculations.

Simulations covering one year or the full plant life are annualized directly. The public
names (``classify_simulation_horizon``, ``time_weighted_annual_means``) are shared with the
finance components and input validation.
"""

import math

import numpy as np

from h2integrate.tools.constants import SECONDS_PER_YEAR


def classify_simulation_horizon(n_timesteps: int, dt: float, plant_life: int) -> str:
    """Classify the simulated horizon relative to one year and the plant life.

    Args:
        n_timesteps (int): Number of simulated timesteps.
        dt (float): Positive duration of each timestep in seconds.
        plant_life (int): Positive integer number of plant years.

    Returns:
        str: ``"full_life"`` when the horizon equals the plant life, ``"single_year"`` when it
        equals one year, and ``"partial"`` otherwise. ``"full_life"`` takes precedence when
        the plant life is one year.
    """
    years_simulated = n_timesteps * dt / SECONDS_PER_YEAR
    if math.isclose(years_simulated, plant_life, rel_tol=1e-9):
        return "full_life"
    if math.isclose(years_simulated, 1.0, rel_tol=1e-9):
        return "single_year"
    return "partial"


def _expand_to_plant_life(simulated_values: np.ndarray, plant_life: int) -> np.ndarray:
    """Expand annual values from a single-year or full-life simulation to the plant life.

    Args:
        simulated_values (np.ndarray): One value for a single simulated year, or one value per
            plant year for a full-life simulation.
        plant_life (int): Positive integer number of plant years to return.

    Returns:
        np.ndarray: One value for each of the ``plant_life`` years.

    Raises:
        ValueError: If the values cover neither one year nor the full plant life.
    """
    if simulated_values.size == plant_life:
        return simulated_values.copy()
    if simulated_values.size == 1:
        return np.full(plant_life, simulated_values[0], dtype=float)
    raise ValueError(
        f"Expected 1 or {plant_life} annual values, got {simulated_values.size}. Simulations "
        "must cover either one year or the full plant life."
    )


def _observed_replacement_schedule(
    state_of_health_timeseries: np.ndarray, dt: float, plant_life: int
) -> np.ndarray:
    """Count observed state-of-health resets in each plant year.

    An upward state-of-health (SOH) jump greater than 1e-9 marks a replacement at the first
    sample with reset SOH. Events are binned into intervals ``[year, year + 1)``. Times within
    1e-10 years of an integer year are treated as exactly on that boundary to absorb
    floating-point error.

    Args:
        state_of_health_timeseries (np.ndarray): One-dimensional SOH fractions in [0, 1].
        dt (float): Positive duration of each simulation timestep in seconds.
        plant_life (int): Positive integer number of plant years to return.

    Returns:
        np.ndarray: Integer replacement counts for each plant year.
    """
    reset_indices = np.flatnonzero(np.diff(state_of_health_timeseries) > 1e-9) + 1
    replacement_schedule = np.zeros(plant_life, dtype=int)
    for reset_index in reset_indices:
        event_time = reset_index * dt / SECONDS_PER_YEAR
        nearest_year = round(event_time)
        if math.isclose(event_time, nearest_year, rel_tol=0.0, abs_tol=1e-10):
            event_time = float(nearest_year)
        if 0.0 < event_time < plant_life:
            replacement_schedule[math.floor(event_time)] += 1
    return replacement_schedule


def _validate_annualization_inputs(
    performance_timeseries,
    rated_performance,
    state_of_health_timeseries,
    eol_soh,
):
    """Validate and normalize performance and SOH inputs.

    When SOH is absent, leave it as ``None`` and do not validate ``eol_soh``.
    Timestep duration and plant lifetime are validated by the calling model.

    Args:
        performance_timeseries (array-like): Nonempty, finite, one-dimensional
            performance rates at equal timesteps.
        rated_performance (float): Finite, positive rated performance in the
            same units as the performance rates.
        state_of_health_timeseries (array-like | None): Finite SOH fractions in
            [0, 1], matching the performance array's shape, or ``None`` to
            disable degradation and replacement tracking.
        eol_soh (float | None): EOL threshold in [0, 1]. Required only when SOH
            is supplied.

    Returns:
        tuple[np.ndarray, float, np.ndarray | None, bool]: Float performance
        array, scalar rated performance, float SOH array or ``None``, and a flag
        indicating whether SOH was supplied, in that order.

    Raises:
        ValueError: If an array is empty, nonfinite, or has an invalid shape;
            rated performance is not finite and positive; or supplied SOH or its
            threshold is invalid.
    """
    performance_timeseries = np.asarray(performance_timeseries, dtype=float)
    if performance_timeseries.size == 0:
        raise ValueError("performance_timeseries must contain at least one value.")
    if performance_timeseries.ndim != 1 or not np.all(np.isfinite(performance_timeseries)):
        raise ValueError("performance_timeseries must be a finite one-dimensional array.")

    rated_performance = float(rated_performance)
    if not np.isfinite(rated_performance) or rated_performance <= 0.0:
        raise ValueError("rated_performance must be finite and greater than zero.")

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


def time_weighted_annual_means(
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
    sample_duration = dt / SECONDS_PER_YEAR
    sample_edges = start_year + (np.arange(timestep_values.size + 1) * dt) / SECONDS_PER_YEAR
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
