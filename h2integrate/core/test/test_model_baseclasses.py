"""Tests for ``PerformanceModelBaseClass.calculate_annual_cf_and_replacement_schedule``."""

import numpy as np
import pytest

from h2integrate.tools.constants import SECONDS_PER_YEAR
from h2integrate.core.model_baseclass import CostModelBaseClass, PerformanceModelBaseClass


class _DummyPerformanceModel:
    """Minimal stand-in exposing the attributes the helper reads (``plant_life``, ``dt``)."""

    def __init__(self, plant_life=6, dt=SECONDS_PER_YEAR):
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
def test_full_life_with_soh_uses_observed_values_without_projection(subtests) -> None:
    capacity_factors, replacement_schedule = _run(
        _DummyPerformanceModel(plant_life=3, dt=SECONDS_PER_YEAR / 2),
        performance_timeseries=[1.0, 0.8, 1.0, 0.6, 0.4, 0.2],
        rated=1.0,
        soh=[0.95, 0.85, 1.0, 0.9, 0.82, 0.81],
        eol=0.8,
    )

    with subtests.test("capacity factors are simulated annual means"):
        np.testing.assert_allclose(capacity_factors, [0.9, 0.8, 0.3])
    with subtests.test("only the observed reset is counted"):
        np.testing.assert_array_equal(replacement_schedule, [0, 1, 0])


@pytest.mark.unit
def test_full_life_varopex_uses_simulated_annual_values() -> None:
    cost_model = CostModelBaseClass()
    cost_model.dt = SECONDS_PER_YEAR / 2
    cost_model.plant_life = 3
    np.testing.assert_allclose(
        cost_model.calculate_annual_varopex(np.array([1.0, 2.0, 3.0, 4.0, 5.0, 6.0])),
        [3.0, 7.0, 11.0],
    )


@pytest.mark.unit
def test_single_year_with_soh_raises() -> None:
    with pytest.raises(ValueError, match="requires simulating the full plant life"):
        _run(
            _DummyPerformanceModel(plant_life=6, dt=SECONDS_PER_YEAR / 4),
            performance_timeseries=[1.0, 1.0, 1.0, 1.0],
            rated=1.0,
            soh=[1.0, 0.95, 0.9, 0.85],
            eol=0.8,
        )


@pytest.mark.unit
def test_partial_horizon_raises(subtests) -> None:
    with subtests.test("capacity factors"):
        with pytest.raises(ValueError, match="one year or the full plant life"):
            _run(
                _DummyPerformanceModel(plant_life=3),
                performance_timeseries=[1.0, 0.0],
                rated=1.0,
                soh=None,
                eol=None,
            )

    with subtests.test("variable OPEX"):
        cost_model = CostModelBaseClass()
        cost_model.dt = SECONDS_PER_YEAR
        cost_model.plant_life = 3
        with pytest.raises(ValueError, match="one year or the full plant life"):
            cost_model.calculate_annual_varopex(np.array([10.0, 0.0]))


@pytest.mark.unit
def test_single_simulated_year_repeats_across_plant_life(subtests):
    with subtests.test("capacity factors"):
        capacity_factors, _ = _run(
            _DummyPerformanceModel(plant_life=3),
            performance_timeseries=[0.5],
            rated=1.0,
            soh=None,
            eol=None,
        )
        np.testing.assert_allclose(capacity_factors, [0.5, 0.5, 0.5])

    with subtests.test("variable OPEX"):
        cost_model = CostModelBaseClass()
        cost_model.dt = SECONDS_PER_YEAR
        cost_model.plant_life = 3
        np.testing.assert_allclose(
            cost_model.calculate_annual_varopex(np.array([10.0])), [10.0, 10.0, 10.0]
        )


@pytest.mark.unit
@pytest.mark.parametrize(
    "overrides,match",
    [
        ({"performance_timeseries": []}, "at least one"),
        ({"performance_timeseries": [[1.0] * 8]}, "one-dimensional"),
        ({"performance_timeseries": [np.nan] * 8}, "finite"),
        ({"performance_timeseries": [np.inf] * 8}, "finite"),
        ({"soh": np.ones(5)}, "match"),
        ({"soh": []}, "at least one"),
        ({"soh": [[1.0] * 8]}, "one-dimensional"),
        ({"soh": [np.nan] * 8}, "finite"),
        ({"soh": [np.inf] * 8}, "finite"),
        ({"soh": [-0.1] * 8}, "between zero and one"),
        ({"soh": [1.1] * 8}, "between zero and one"),
        ({"rated": 0}, "rated_performance"),
        ({"rated": -1}, "rated_performance"),
        ({"rated": np.inf}, "rated_performance"),
        ({"rated": np.nan}, "rated_performance"),
        ({"eol": None}, "eol_soh is required"),
        ({"eol": np.nan}, "eol_soh"),
        ({"eol": np.inf}, "eol_soh"),
        ({"eol": -0.1}, "eol_soh"),
        ({"eol": 1.1}, "eol_soh"),
    ],
)
def test_annualization_rejects_invalid_arrays_and_quantities(overrides, match):
    inputs = {"performance_timeseries": np.ones(8), "rated": 1.0, "soh": np.ones(8), "eol": 0.8}
    inputs.update(overrides)
    with pytest.raises(ValueError, match=match):
        _run(_DummyPerformanceModel(dt=SECONDS_PER_YEAR / 4), **inputs)
