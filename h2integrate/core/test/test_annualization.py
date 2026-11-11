"""Tests for the pure annualization and replacement-cycle helpers."""

import numpy as np
import pytest

from h2integrate.tools.constants import SECONDS_PER_YEAR
from h2integrate.core.annualization import (
    _expand_to_plant_life,
    time_weighted_annual_means,
    classify_simulation_horizon,
    _observed_replacement_schedule,
)


@pytest.mark.unit
@pytest.mark.parametrize(
    "n_timesteps,dt,plant_life,expected",
    [
        (8760, 3600, 30, "single_year"),
        (30 * 8760, 3600, 30, "full_life"),
        (8760, 3600, 1, "full_life"),
        (4380, 3600, 30, "partial"),
        (2 * 8760, 3600, 30, "partial"),
    ],
)
def test_classify_simulation_horizon(n_timesteps, dt, plant_life, expected) -> None:
    assert classify_simulation_horizon(n_timesteps, dt, plant_life) == expected


@pytest.mark.unit
def test_expand_to_plant_life(subtests) -> None:
    with subtests.test("a single simulated year is repeated across plant life"):
        np.testing.assert_allclose(_expand_to_plant_life(np.array([0.5]), 3), [0.5, 0.5, 0.5])
    with subtests.test("a full-life simulation is returned unchanged"):
        np.testing.assert_allclose(
            _expand_to_plant_life(np.array([0.5, 0.4, 0.3]), 3), [0.5, 0.4, 0.3]
        )
    with subtests.test("any other number of simulated years raises"):
        with pytest.raises(ValueError, match="one year or the full plant life"):
            _expand_to_plant_life(np.array([0.5, 0.4]), 3)


@pytest.mark.unit
def test_observed_replacement_schedule_counts_resets_by_plant_year(subtests) -> None:
    soh = np.array([1.0, 0.9, 1.0, 0.9, 1.0, 0.9, 0.8, 1.0])
    schedule = _observed_replacement_schedule(soh, SECONDS_PER_YEAR / 4, plant_life=2)

    with subtests.test("resets at 0.5 and 1.0 years fall in separate plant years"):
        np.testing.assert_array_equal(schedule, [1, 2])
    with subtests.test("schedule is an integer count"):
        assert schedule.dtype == int


@pytest.mark.unit
def test_observed_replacement_schedule_without_resets_is_zero() -> None:
    soh = np.linspace(1.0, 0.7, 8)
    schedule = _observed_replacement_schedule(soh, SECONDS_PER_YEAR / 4, plant_life=2)
    np.testing.assert_array_equal(schedule, [0, 0])


@pytest.mark.unit
def test_time_weighted_annual_means() -> None:
    """Return time-weighted means and durations for two complete plant years."""
    annual_means, durations = time_weighted_annual_means(
        timestep_values=np.array([0.5, 0.25]), dt=SECONDS_PER_YEAR
    )
    np.testing.assert_allclose(annual_means, [0.5, 0.25])
    np.testing.assert_allclose(durations, [1.0, 1.0])
