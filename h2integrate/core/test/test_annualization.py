"""Tests for the pure annualization and replacement-cycle helpers."""

import numpy as np
import pytest

from h2integrate.core.annualization import (
    _project_capacity_factors,
    _extrapolate_annual_values,
    _build_replacement_schedule,
    _time_weighted_annual_means,
    _degraded_replacement_cycles,
    _annualization_steps_per_year,
)


@pytest.mark.unit
@pytest.mark.parametrize(
    "soh,expected_completed",
    [
        (np.array([1.0, 0.9, 0.8, 0.8]), [False]),
        (np.array([1.0, 0.9, 0.8, 0.7]), [False]),
        (np.array([1.0, 0.8, 1.0, 0.8]), [True, False]),
        (np.zeros(4), [False]),
    ],
)
def test_observed_cycles_complete_only_at_soh_resets(subtests, soh, expected_completed) -> None:
    _, completed, durations = _degraded_replacement_cycles(
        timestep_capacity_factors=np.ones(soh.size),
        state_of_health_timeseries=soh,
        eol_soh=0.8,
        dt=31_536_000 / 4,
        plant_life=1,
    )

    with subtests.test("only observed upward SOH jumps complete cycles"):
        assert completed == expected_completed
    with subtests.test("no projection extends beyond the observed plant lifetime"):
        assert sum(np.sum(segment) for segment in durations) == pytest.approx(1.0)


@pytest.mark.unit
@pytest.mark.parametrize(
    "soh",
    [np.array([1.0, 0.8]), np.array([0.8, 0.7]), np.full(2, 0.8), np.array([0.8]), np.zeros(2)],
)
def test_projected_eol_at_or_below_final_observed_soh(subtests, soh) -> None:
    capacity_factors, completed, durations = _degraded_replacement_cycles(
        timestep_capacity_factors=soh.copy(),
        state_of_health_timeseries=soh,
        eol_soh=0.8,
        dt=31_536_000 / 4,
        plant_life=3,
    )

    with subtests.test("EOL completes the cycle only after a projected timestep"):
        assert completed == [True]
        assert np.sum(durations[0]) == pytest.approx((soh.size + 1) / 4)
    with subtests.test("zero SOH does not produce undefined capacity factors"):
        assert np.all(np.isfinite(capacity_factors[0]))


@pytest.mark.unit
def test_annualization_steps_per_year():
    assert _annualization_steps_per_year(dt=3600) == 8760
    assert _annualization_steps_per_year(dt=31_536_000) == 1
    # Never returns less than one step per year.
    assert _annualization_steps_per_year(dt=10 * 31_536_000) == 1


@pytest.mark.unit
def test_time_weighted_annual_means() -> None:
    """Return time-weighted means and durations for two complete plant years."""
    annual_means, durations = _time_weighted_annual_means(
        timestep_values=np.array([0.5, 0.25]), dt=31_536_000
    )
    np.testing.assert_allclose(annual_means, [0.5, 0.25])
    np.testing.assert_allclose(durations, [1.0, 1.0])


@pytest.mark.unit
def test_extrapolate_annual_values_modes():
    simulated = np.array([0.6, 0.5, 0.4])
    np.testing.assert_allclose(
        _extrapolate_annual_values(simulated_values=simulated, plant_life=6, method="tile"),
        [0.6, 0.5, 0.4, 0.6, 0.5, 0.4],
    )
    np.testing.assert_allclose(
        _extrapolate_annual_values(
            simulated_values=simulated, plant_life=6, method="final_sim_value"
        ),
        [0.6, 0.5, 0.4, 0.4, 0.4, 0.4],
    )
    np.testing.assert_allclose(
        _extrapolate_annual_values(
            simulated_values=simulated, plant_life=6, method="time_averaged_sim_value"
        ),
        [0.6, 0.5, 0.4, 0.5, 0.5, 0.5],
    )
    with pytest.raises(ValueError):
        _extrapolate_annual_values(simulated_values=simulated, plant_life=6, method="not_a_mode")


@pytest.mark.unit
@pytest.mark.parametrize(
    "method,expected_values",
    [
        ("tile", np.array([1.0, 0.0, 1.0, 0.0])),
        ("final_sim_value", np.array([1.0, 0.0, 0.0, 0.0])),
        ("time_averaged_sim_value", np.array([1.0, 0.0, 0.8, 0.8])),
    ],
)
def test_extrapolate_annual_values_with_partial_year(
    method: str, expected_values: np.ndarray
) -> None:
    """Use interval durations only when averaging beyond the simulated horizon."""
    projected_values = _extrapolate_annual_values(
        simulated_values=np.array([1.0, 0.0]),
        plant_life=4,
        method=method,
        simulated_durations_years=np.array([1.0, 0.25]),
    )
    np.testing.assert_allclose(projected_values, expected_values)


@pytest.mark.unit
def test_extrapolate_annual_values_requires_method_only_when_needed():
    with pytest.raises(ValueError, match="annual_extrapolation_method is required"):
        _extrapolate_annual_values(
            simulated_values=np.array([1.0, 0.0]),
            plant_life=3,
            method=None,
        )

    np.testing.assert_array_equal(
        _extrapolate_annual_values(
            simulated_values=np.array([1.0, 0.0]),
            plant_life=2,
            method=None,
        ),
        [1.0, 0.0],
    )


@pytest.mark.unit
def test_project_capacity_factors_repetition_modes():
    # Two completed cycles of lengths 2 and 1.
    cycle_cf_segments = [np.array([1.0, 0.9]), np.array([0.8])]
    np.testing.assert_allclose(
        _project_capacity_factors(
            cycle_cf_segments, soh_cycle_repetition="all_soh_cycles", plant_life=5
        ),
        [1.0, 0.9, 0.8, 1.0, 0.9],
    )
    np.testing.assert_allclose(
        _project_capacity_factors(
            cycle_cf_segments, soh_cycle_repetition="final_soh_cycle", plant_life=5
        ),
        [1.0, 0.9, 0.8, 0.8, 0.8],
    )


@pytest.mark.unit
def test_build_replacement_schedule_marks_post_eol_cycle_starts():
    # A single 3-year cycle that reaches end of life, tiled across a 5-year plant life,
    # triggers one replacement at the start of the second cycle (year 3).
    cycle_cf_segments = [np.array([1.0, 0.9, 0.8])]
    np.testing.assert_allclose(
        _build_replacement_schedule(
            cycle_cf_segments,
            cycle_has_replacement=[True],
            soh_cycle_repetition="all_soh_cycles",
            plant_life=5,
        ),
        [0.0, 0.0, 0.0, 1.0, 0.0],
    )
    # No replacements when the cycle never reaches end of life.
    np.testing.assert_allclose(
        _build_replacement_schedule(
            cycle_cf_segments,
            cycle_has_replacement=[False],
            soh_cycle_repetition="all_soh_cycles",
            plant_life=5,
        ),
        np.zeros(5),
    )
