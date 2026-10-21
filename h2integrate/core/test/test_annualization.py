"""Tests for the pure annualization and replacement-cycle helpers."""

import numpy as np
import pytest

from h2integrate.core.annualization import (
    _annual_cf_segments,
    _project_capacity_factors,
    _extrapolate_annual_values,
    _build_replacement_schedule,
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
def test_annual_cf_segments() -> None:
    """Return CF means and durations for two complete plant years."""
    capacity_factors, durations = _annual_cf_segments(
        capacity_factors=np.array([0.5, 0.25]), dt=31_536_000
    )
    np.testing.assert_allclose(capacity_factors, [0.5, 0.25])
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
            simulated_values=simulated, plant_life=6, method="average_sim_value"
        ),
        [0.6, 0.5, 0.4, 0.5, 0.5, 0.5],
    )
    with pytest.raises(ValueError):
        _extrapolate_annual_values(simulated_values=simulated, plant_life=6, method="not_a_mode")


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
