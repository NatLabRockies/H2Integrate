import numpy as np
import pytest

from h2integrate.core.model_baseclasses import PerformanceModelBaseClass


class _DummyPerformanceModel:
    plant_life = 6
    dt = 31_536_000


@pytest.mark.regression
def test_calculate_annual_cf_and_replacement_schedule_resets_on_replacement():
    performance_timeseries = np.array([1.0, 0.92, 0.84])
    state_of_health_timeseries = np.array([0.97, 0.89, 0.8])

    projected_values, replacement_schedule = (
        PerformanceModelBaseClass.calculate_annual_cf_and_replacement_schedule(
            _DummyPerformanceModel(),
            performance_timeseries,
            1.0,
            state_of_health_timeseries,
            0.8,
        )
    )

    np.testing.assert_allclose(projected_values, [1.0, 0.92, 0.84, 1.0, 0.92, 0.84])
    np.testing.assert_allclose(replacement_schedule, [0.0, 0.0, 0.0, 1.0, 0.0, 0.0])


@pytest.mark.regression
def test_calculate_annual_cf_and_replacement_schedule_without_degradation():
    performance_timeseries = np.array([0.6, 0.5, 0.4])

    projected_values, replacement_schedule = (
        PerformanceModelBaseClass.calculate_annual_cf_and_replacement_schedule(
            _DummyPerformanceModel(),
            performance_timeseries,
            1.0,
            None,
            None,
        )
    )

    np.testing.assert_allclose(projected_values, [0.6, 0.5, 0.4, 0.6, 0.5, 0.4])
    np.testing.assert_allclose(replacement_schedule, np.zeros(6))


@pytest.mark.regression
def test_calculate_annual_cf_and_replacement_schedule_without_degradation_final_sim_value():
    performance_timeseries = np.array([0.6, 0.5, 0.4])

    projected_values, replacement_schedule = (
        PerformanceModelBaseClass.calculate_annual_cf_and_replacement_schedule(
            _DummyPerformanceModel(),
            performance_timeseries,
            1.0,
            None,
            None,
            no_degradation_extrapolation="final_sim_value",
        )
    )

    np.testing.assert_allclose(projected_values, [0.6, 0.5, 0.4, 0.4, 0.4, 0.4])
    np.testing.assert_allclose(replacement_schedule, np.zeros(6))


@pytest.mark.regression
def test_calculate_annual_cf_and_replacement_schedule_without_degradation_average_sim_value():
    performance_timeseries = np.array([0.6, 0.5, 0.4])

    projected_values, replacement_schedule = (
        PerformanceModelBaseClass.calculate_annual_cf_and_replacement_schedule(
            _DummyPerformanceModel(),
            performance_timeseries,
            1.0,
            None,
            None,
            no_degradation_extrapolation="average_sim_value",
        )
    )

    np.testing.assert_allclose(projected_values, [0.6, 0.5, 0.4, 0.5, 0.5, 0.5])
    np.testing.assert_allclose(replacement_schedule, np.zeros(6))
