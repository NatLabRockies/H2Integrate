"""Tests for ``PerformanceModelBaseClass.calculate_annual_cf_and_replacement_schedule``."""

import numpy as np
import pytest

from h2integrate.core.model_baseclasses import PerformanceModelBaseClass


class _DummyPerformanceModel:
    """Minimal stand-in exposing the attributes the helper reads (``plant_life``, ``dt``)."""

    def __init__(self, plant_life=6, dt=31_536_000):
        self.plant_life = plant_life
        self.dt = dt


def _run(dummy, performance_timeseries, rated, soh, eol, **kwargs):
    return PerformanceModelBaseClass.calculate_annual_cf_and_replacement_schedule(
        dummy,
        np.asarray(performance_timeseries, dtype=float),
        rated,
        None if soh is None else np.asarray(soh, dtype=float),
        eol,
        **kwargs,
    )


@pytest.mark.unit
def test_resets_on_replacement():
    cf_values, replacement_schedule = _run(
        _DummyPerformanceModel(plant_life=6),
        [1.0, 0.92, 0.84],
        1.0,
        [0.97, 0.89, 0.8],
        0.8,
    )

    np.testing.assert_allclose(cf_values, [1.0, 0.92, 0.84, 1.0, 0.92, 0.84])
    np.testing.assert_allclose(replacement_schedule, [0.0, 0.0, 0.0, 1.0, 0.0, 0.0])


@pytest.mark.unit
def test_without_degradation_tile():
    cf_values, replacement_schedule = _run(
        _DummyPerformanceModel(plant_life=6),
        [0.6, 0.5, 0.4],
        1.0,
        None,
        None,
    )

    np.testing.assert_allclose(cf_values, [0.6, 0.5, 0.4, 0.6, 0.5, 0.4])
    np.testing.assert_allclose(replacement_schedule, np.zeros(6))


@pytest.mark.unit
def test_without_degradation_final_sim_value():
    cf_values, replacement_schedule = _run(
        _DummyPerformanceModel(plant_life=6),
        [0.6, 0.5, 0.4],
        1.0,
        None,
        None,
        no_degradation_extrapolation="final_sim_value",
    )

    np.testing.assert_allclose(cf_values, [0.6, 0.5, 0.4, 0.4, 0.4, 0.4])
    np.testing.assert_allclose(replacement_schedule, np.zeros(6))


@pytest.mark.unit
def test_without_degradation_average_sim_value():
    cf_values, replacement_schedule = _run(
        _DummyPerformanceModel(plant_life=6),
        [0.6, 0.5, 0.4],
        1.0,
        None,
        None,
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
        [1.0, 0.9, 0.8],
        1.0,
        [0.95, 0.90, 0.85],
        0.8,
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
        [1.0, 0.95, 0.9, 0.85, 0.8],
        1.0,
        [0.85, 0.80, 0.90, 0.85, 0.80],
        0.8,
    )

    np.testing.assert_allclose(cf_values, [1.0, 0.95, 0.9, 0.85, 0.8, 1.0])
    np.testing.assert_allclose(replacement_schedule, [0, 0, 1, 0, 0, 1])


@pytest.mark.unit
def test_final_soh_cycle_vs_all_soh_cycles():
    performance_timeseries = [1.0, 0.95, 0.9, 0.85, 0.8]
    soh = [0.85, 0.80, 0.90, 0.85, 0.80]

    final_cf, final_repl = _run(
        _DummyPerformanceModel(plant_life=8),
        performance_timeseries,
        1.0,
        soh,
        0.8,
        soh_cycle_repetition="final_soh_cycle",
    )
    np.testing.assert_allclose(final_cf, [1.0, 0.95, 0.9, 0.85, 0.8, 0.9, 0.85, 0.8])
    np.testing.assert_allclose(final_repl, [0, 0, 1, 0, 0, 1, 0, 0])

    all_cf, all_repl = _run(
        _DummyPerformanceModel(plant_life=8),
        performance_timeseries,
        1.0,
        soh,
        0.8,
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
        [1.0, 0.95, 0.9, 0.85, 0.8],
        1.0,
        [0.85, 0.82, 1.0, 0.9, 0.82],
        0.8,
    )

    extrapolated_cf = 0.8 * 0.74 / 0.82
    np.testing.assert_allclose(cf_values, [1.0, 0.95, 0.9, 0.85, 0.8, extrapolated_cf])
    np.testing.assert_allclose(replacement_schedule, [0, 0, 1, 0, 0, 0])


@pytest.mark.unit
def test_invalid_soh_cycle_repetition_raises():
    with pytest.raises(ValueError):
        _run(
            _DummyPerformanceModel(plant_life=6),
            [1.0, 0.9, 0.8],
            1.0,
            [0.95, 0.9, 0.85],
            0.8,
            soh_cycle_repetition="not_a_mode",
        )


@pytest.mark.unit
def test_invalid_no_degradation_extrapolation_raises():
    with pytest.raises(ValueError):
        _run(
            _DummyPerformanceModel(plant_life=6),
            [0.6, 0.5, 0.4],
            1.0,
            None,
            None,
            no_degradation_extrapolation="not_a_mode",
        )
