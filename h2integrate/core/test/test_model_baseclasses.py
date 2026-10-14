"""Tests for ``PerformanceModelBaseClass.calculate_annual_cf_and_replacement_schedule``."""

import numpy as np
import pytest

from h2integrate.core.model_baseclass import (
    PerformanceModelBaseClass,
    _project_capacity_factors,
    _extrapolate_annual_values,
    _build_replacement_schedule,
    _annualization_steps_per_year,
    _simulated_annual_capacity_factors,
)


class _DummyPerformanceModel:
    """Minimal stand-in exposing the attributes the helper reads (``plant_life``, ``dt``)."""

    def __init__(self, plant_life=6, dt=31_536_000):
        self.plant_life = plant_life
        self.dt = dt


def _run(dummy, performance_timeseries, rated, soh, eol, **kwargs):
    return PerformanceModelBaseClass.calculate_annual_cf_and_replacement_schedule(
        dummy,
        performance_timeseries=np.asarray(performance_timeseries, dtype=float),
        rated_performance=rated,
        state_of_health_timeseries=None if soh is None else np.asarray(soh, dtype=float),
        eol_soh=eol,
        **kwargs,
    )


@pytest.mark.unit
def test_resets_on_replacement():
    cf_values, replacement_schedule = _run(
        _DummyPerformanceModel(plant_life=6),
        performance_timeseries=[1.0, 0.92, 0.84],
        rated=1.0,
        soh=[0.97, 0.89, 0.8],
        eol=0.8,
    )

    np.testing.assert_allclose(cf_values, [1.0, 0.92, 0.84, 1.0, 0.92, 0.84])
    np.testing.assert_allclose(replacement_schedule, [0.0, 0.0, 0.0, 1.0, 0.0, 0.0])


@pytest.mark.unit
def test_without_degradation_tile():
    cf_values, replacement_schedule = _run(
        _DummyPerformanceModel(plant_life=6),
        performance_timeseries=[0.6, 0.5, 0.4],
        rated=1.0,
        soh=None,
        eol=None,
    )

    np.testing.assert_allclose(cf_values, [0.6, 0.5, 0.4, 0.6, 0.5, 0.4])
    np.testing.assert_allclose(replacement_schedule, np.zeros(6))


@pytest.mark.unit
def test_without_degradation_final_sim_value():
    cf_values, replacement_schedule = _run(
        _DummyPerformanceModel(plant_life=6),
        performance_timeseries=[0.6, 0.5, 0.4],
        rated=1.0,
        soh=None,
        eol=None,
        no_degradation_extrapolation="final_sim_value",
    )

    np.testing.assert_allclose(cf_values, [0.6, 0.5, 0.4, 0.4, 0.4, 0.4])
    np.testing.assert_allclose(replacement_schedule, np.zeros(6))


@pytest.mark.unit
def test_without_degradation_average_sim_value():
    cf_values, replacement_schedule = _run(
        _DummyPerformanceModel(plant_life=6),
        performance_timeseries=[0.6, 0.5, 0.4],
        rated=1.0,
        soh=None,
        eol=None,
        no_degradation_extrapolation="average_sim_value",
    )

    np.testing.assert_allclose(cf_values, [0.6, 0.5, 0.4, 0.5, 0.5, 0.5])
    np.testing.assert_allclose(replacement_schedule, np.zeros(6))


@pytest.mark.unit
def test_extrapolates_incomplete_trailing_cycle_then_tiles():
    # SOH never reaches EOL during simulation, so the trailing cycle is completed by
    # extrapolation before the completed cycle is tiled across plant life.
    cf_values, replacement_schedule = _run(
        _DummyPerformanceModel(plant_life=8),
        performance_timeseries=[1.0, 0.9, 0.8],
        rated=1.0,
        soh=[0.95, 0.90, 0.85],
        eol=0.8,
    )

    extrapolated_cf = 0.8 * 0.80 / 0.85
    np.testing.assert_allclose(
        cf_values,
        [1.0, 0.9, 0.8, extrapolated_cf, 1.0, 0.9, 0.8, extrapolated_cf],
    )
    np.testing.assert_allclose(replacement_schedule, [0, 0, 0, 0, 1, 0, 0, 0])


@pytest.mark.unit
def test_preserves_multiple_simulated_cycles_all_soh_cycles():
    # Two completed cycles are observed (EOL crossing at year 1 and year 4).
    cf_values, replacement_schedule = _run(
        _DummyPerformanceModel(plant_life=6),
        performance_timeseries=[1.0, 0.95, 0.9, 0.85, 0.8],
        rated=1.0,
        soh=[0.85, 0.80, 0.90, 0.85, 0.80],
        eol=0.8,
    )

    np.testing.assert_allclose(cf_values, [1.0, 0.95, 0.9, 0.85, 0.8, 1.0])
    np.testing.assert_allclose(replacement_schedule, [0, 0, 1, 0, 0, 1])


@pytest.mark.unit
def test_final_soh_cycle_vs_all_soh_cycles():
    performance_timeseries = [1.0, 0.95, 0.9, 0.85, 0.8]
    soh = [0.85, 0.80, 0.90, 0.85, 0.80]

    final_cf, final_repl = _run(
        _DummyPerformanceModel(plant_life=8),
        performance_timeseries=performance_timeseries,
        rated=1.0,
        soh=soh,
        eol=0.8,
        soh_cycle_repetition="final_soh_cycle",
    )
    np.testing.assert_allclose(final_cf, [1.0, 0.95, 0.9, 0.85, 0.8, 0.9, 0.85, 0.8])
    np.testing.assert_allclose(final_repl, [0, 0, 1, 0, 0, 1, 0, 0])

    all_cf, all_repl = _run(
        _DummyPerformanceModel(plant_life=8),
        performance_timeseries=performance_timeseries,
        rated=1.0,
        soh=soh,
        eol=0.8,
        soh_cycle_repetition="all_soh_cycles",
    )
    np.testing.assert_allclose(all_cf, [1.0, 0.95, 0.9, 0.85, 0.8, 1.0, 0.95, 0.9])
    np.testing.assert_allclose(all_repl, [0, 0, 1, 0, 0, 1, 0, 1])


@pytest.mark.unit
def test_detects_reset_via_upward_soh_jump():
    # SOH never falls to EOL, but resets upward between years 1 and 2, marking a
    # completed cycle. The trailing cycle is then completed via extrapolation.
    cf_values, replacement_schedule = _run(
        _DummyPerformanceModel(plant_life=6),
        performance_timeseries=[1.0, 0.95, 0.9, 0.85, 0.8],
        rated=1.0,
        soh=[0.85, 0.82, 1.0, 0.9, 0.82],
        eol=0.8,
    )

    extrapolated_cf = 0.8 * 0.74 / 0.82
    np.testing.assert_allclose(cf_values, [1.0, 0.95, 0.9, 0.85, 0.8, extrapolated_cf])
    np.testing.assert_allclose(replacement_schedule, [0, 0, 1, 0, 0, 0])


@pytest.mark.unit
def test_invalid_soh_cycle_repetition_raises():
    with pytest.raises(ValueError):
        _run(
            _DummyPerformanceModel(plant_life=6),
            performance_timeseries=[1.0, 0.9, 0.8],
            rated=1.0,
            soh=[0.95, 0.9, 0.85],
            eol=0.8,
            soh_cycle_repetition="not_a_mode",
        )


@pytest.mark.unit
def test_invalid_no_degradation_extrapolation_raises():
    with pytest.raises(ValueError):
        _run(
            _DummyPerformanceModel(plant_life=6),
            performance_timeseries=[0.6, 0.5, 0.4],
            rated=1.0,
            soh=None,
            eol=None,
            no_degradation_extrapolation="not_a_mode",
        )


@pytest.mark.unit
def test_annualization_steps_per_year():
    assert _annualization_steps_per_year(dt=3600) == 8760
    assert _annualization_steps_per_year(dt=31_536_000) == 1
    # Never returns less than one step per year.
    assert _annualization_steps_per_year(dt=10 * 31_536_000) == 1


@pytest.mark.unit
def test_simulated_annual_capacity_factors():
    # Two years at a 1-year timestep; CF is simply value / rated per year.
    cf = _simulated_annual_capacity_factors(
        performance_timeseries=np.array([0.5, 0.25]), rated_performance=1.0, dt=31_536_000
    )
    np.testing.assert_allclose(cf, [0.5, 0.25])


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
            cycle_reached_eol=[True],
            soh_cycle_repetition="all_soh_cycles",
            plant_life=5,
        ),
        [0.0, 0.0, 0.0, 1.0, 0.0],
    )
    # No replacements when the cycle never reaches end of life.
    np.testing.assert_allclose(
        _build_replacement_schedule(
            cycle_cf_segments,
            cycle_reached_eol=[False],
            soh_cycle_repetition="all_soh_cycles",
            plant_life=5,
        ),
        np.zeros(5),
    )
