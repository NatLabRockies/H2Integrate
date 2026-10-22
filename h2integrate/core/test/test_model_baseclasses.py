"""Tests for ``PerformanceModelBaseClass.calculate_annual_cf_and_replacement_schedule``."""

import math

import numpy as np
import pytest

from h2integrate.core.model_baseclass import CostModelBaseClass, PerformanceModelBaseClass


class _DummyPerformanceModel:
    """Minimal stand-in exposing the attributes the helper reads (``plant_life``, ``dt``)."""

    def __init__(self, plant_life=6, dt=31_536_000, annual_extrapolation_method="tile"):
        self.plant_life = plant_life
        self.dt = dt
        self.annual_extrapolation_method = annual_extrapolation_method


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

    projected_cf = 0.84 * 0.71 / 0.8
    np.testing.assert_allclose(cf_values, [1.0, 0.92, 0.84, projected_cf, 1.0, 0.92])
    np.testing.assert_allclose(replacement_schedule, [0, 0, 0, 0, 1, 0])


@pytest.mark.unit
def test_without_degradation_tile():
    cf_values, replacement_schedule = _run(
        _DummyPerformanceModel(plant_life=6),
        performance_timeseries=[1.2, 1.0, 0.8],
        rated=2.0,
        soh=None,
        eol=None,
        no_degradation_extrapolation="tile",
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
def test_without_degradation_time_averaged_sim_value():
    cf_values, replacement_schedule = _run(
        _DummyPerformanceModel(plant_life=6),
        performance_timeseries=[0.6, 0.5, 0.4],
        rated=1.0,
        soh=None,
        eol=None,
        no_degradation_extrapolation="time_averaged_sim_value",
    )

    np.testing.assert_allclose(cf_values, [0.6, 0.5, 0.4, 0.5, 0.5, 0.5])
    np.testing.assert_allclose(replacement_schedule, np.zeros(6))


@pytest.mark.unit
def test_average_capacity_factor_weights_partial_year() -> None:
    """Weight a full year and a partial year by their elapsed durations."""
    capacity_factors, replacement_schedule = _run(
        _DummyPerformanceModel(plant_life=4, dt=31_536_000 / 4),
        performance_timeseries=np.array([1.0, 1.0, 1.0, 1.0, 0.0]),
        rated=1.0,
        soh=None,
        eol=None,
        no_degradation_extrapolation="time_averaged_sim_value",
    )
    np.testing.assert_allclose(capacity_factors, [1.0, 0.0, 0.8, 0.8])
    np.testing.assert_array_equal(replacement_schedule, np.zeros(4, dtype=int))


@pytest.mark.unit
def test_extrapolation_method_required_for_multiple_simulated_years():
    with pytest.raises(ValueError, match="annual_extrapolation_method is required"):
        _run(
            _DummyPerformanceModel(plant_life=3, annual_extrapolation_method=None),
            performance_timeseries=[1.0, 0.0],
            rated=1.0,
            soh=None,
            eol=None,
        )

    cost_model = CostModelBaseClass()
    cost_model.dt = 31_536_000
    cost_model.plant_life = 3
    with pytest.raises(ValueError, match="annual_extrapolation_method is required"):
        cost_model.calculate_annual_varopex(np.array([10.0, 0.0]))


@pytest.mark.unit
def test_extrapolation_method_not_required_for_single_simulated_year(subtests):
    with subtests.test(
        "single simulated year does not require extrapolation method for capacity factors"
    ):
        capacity_factors, _ = _run(
            _DummyPerformanceModel(plant_life=3, annual_extrapolation_method=None),
            performance_timeseries=[0.5],
            rated=1.0,
            soh=None,
            eol=None,
        )
        np.testing.assert_allclose(capacity_factors, [0.5, 0.5, 0.5])

    with subtests.test(
        "single simulated year does not require extrapolation method for variable OPEX"
    ):
        cost_model = CostModelBaseClass()
        cost_model.dt = 31_536_000
        cost_model.plant_life = 3
        np.testing.assert_allclose(
            cost_model.calculate_annual_varopex(np.array([10.0])), [10.0, 10.0, 10.0]
        )


@pytest.mark.unit
def test_average_varopex_weights_partial_year() -> None:
    """Weight annualized variable costs by the duration of each observed interval."""
    cost_model = CostModelBaseClass()
    cost_model.dt = 31_536_000 / 4
    cost_model.plant_life = 4
    annual_varopex = cost_model.calculate_annual_varopex(
        np.array([10.0, 10.0, 10.0, 10.0, 0.0]),
        annual_extrapolation_method="time_averaged_sim_value",
    )
    np.testing.assert_allclose(annual_varopex, [40.0, 0.0, 32.0, 32.0])


@pytest.mark.unit
@pytest.mark.parametrize(
    "annual_extrapolation_method,expected_capacity_factors,expected_varopex",
    [
        ("tile", [1.0, 0.0, 1.0, 0.0], [10.0, 0.0, 10.0, 0.0]),
        ("final_sim_value", [1.0, 0.0, 0.0, 0.0], [10.0, 0.0, 0.0, 0.0]),
        ("time_averaged_sim_value", [1.0, 0.0, 0.5, 0.5], [10.0, 0.0, 5.0, 5.0]),
    ],
)
def test_plant_annual_extrapolation_method_is_base_class_default(
    annual_extrapolation_method: str,
    expected_capacity_factors: list[float],
    expected_varopex: list[float],
) -> None:
    performance_model = _DummyPerformanceModel(
        plant_life=4, dt=31_536_000, annual_extrapolation_method=annual_extrapolation_method
    )
    capacity_factors, _ = _run(
        performance_model,
        performance_timeseries=[1.0, 0.0],
        rated=1.0,
        soh=None,
        eol=None,
    )

    cost_model = CostModelBaseClass()
    cost_model.dt = 31_536_000
    cost_model.plant_life = 4
    cost_model.annual_extrapolation_method = annual_extrapolation_method
    annual_varopex = cost_model.calculate_annual_varopex(np.array([10.0, 0.0]))

    np.testing.assert_allclose(capacity_factors, expected_capacity_factors)
    np.testing.assert_allclose(annual_varopex, expected_varopex)


@pytest.mark.regression
@pytest.mark.parametrize("dt", [300, 600])
def test_exact_three_year_horizon_tiles_capacity_factor_and_varopex(subtests, dt: int) -> None:
    """Tile year-one values after exact three-year simulations without a spurious segment."""
    steps_per_year = 31_536_000 // dt
    timeseries = np.zeros(3 * steps_per_year)
    timeseries[:steps_per_year] = 1.0

    capacity_factors, replacement_schedule = _run(
        _DummyPerformanceModel(plant_life=4, dt=dt),
        performance_timeseries=timeseries,
        rated=1.0,
        soh=None,
        eol=None,
        no_degradation_extrapolation="tile",
    )

    cost_model = CostModelBaseClass()
    cost_model.dt = dt
    cost_model.plant_life = 4
    annual_varopex = cost_model.calculate_annual_varopex(
        timeseries, annual_extrapolation_method="tile"
    )

    with subtests.test("capacity factor tiles the first year after the horizon"):
        np.testing.assert_allclose(capacity_factors, [1.0, 0.0, 0.0, 1.0])
        np.testing.assert_array_equal(replacement_schedule, np.zeros(4, dtype=int))
    with subtests.test("variable OpEx tiles the first year after the horizon"):
        np.testing.assert_allclose(annual_varopex, [steps_per_year, 0.0, 0.0, steps_per_year])


@pytest.mark.regression
@pytest.mark.parametrize("dt", [300, 600])
def test_exact_three_year_horizon_final_sim_value_uses_last_complete_year(
    subtests, dt: int
) -> None:
    """Do not use a roundoff-sized segment as the final simulated annual value."""
    steps_per_year = 31_536_000 // dt
    timeseries = np.zeros(3 * steps_per_year)
    timeseries[:steps_per_year] = 1.0
    timeseries[-1] = 1.0

    capacity_factors, _ = _run(
        _DummyPerformanceModel(plant_life=4, dt=dt),
        performance_timeseries=timeseries,
        rated=1.0,
        soh=None,
        eol=None,
        no_degradation_extrapolation="final_sim_value",
    )

    cost_model = CostModelBaseClass()
    cost_model.dt = dt
    cost_model.plant_life = 4
    annual_varopex = cost_model.calculate_annual_varopex(
        timeseries, annual_extrapolation_method="final_sim_value"
    )

    with subtests.test("capacity factor repeats the last complete year"):
        np.testing.assert_allclose(
            capacity_factors, [1.0, 0.0, 1.0 / steps_per_year, 1.0 / steps_per_year]
        )
    with subtests.test("variable OpEx repeats the last complete year"):
        np.testing.assert_allclose(annual_varopex, [steps_per_year, 0.0, 1.0, 1.0])


@pytest.mark.unit
@pytest.mark.parametrize("method", ["tile", "final_sim_value", "time_averaged_sim_value"])
def test_varopex_splits_timestep_at_year_boundary(subtests, method: str) -> None:
    """Allocate a crossing timestep's cost by elapsed time before annualizing."""
    cost_model = CostModelBaseClass()
    cost_model.dt = 10_000
    cost_model.plant_life = 3
    timestep_costs = np.zeros(4000)
    timestep_costs[3153] = 100.0
    annual_varopex = cost_model.calculate_annual_varopex(
        timestep_costs, annual_extrapolation_method=method
    )
    partial_year_duration = (timestep_costs.size * cost_model.dt - 31_536_000) / 31_536_000
    partial_year_annual_cost = 40.0 / partial_year_duration
    expected_fill = {
        "tile": 60.0,
        "final_sim_value": partial_year_annual_cost,
        "time_averaged_sim_value": 100.0 / (1.0 + partial_year_duration),
    }[method]

    with subtests.test("the crossing timestep contributes 60 dollars and 40 dollars"):
        np.testing.assert_allclose(annual_varopex[:2], [60.0, partial_year_annual_cost])
    with subtests.test("future costs follow the selected extrapolation mode"):
        assert annual_varopex[2] == pytest.approx(expected_fill)


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
    np.testing.assert_allclose(final_cf, [1.0, 0.95, 0.9, 0.85, 0.8, 0.75, 0.9, 0.85])
    np.testing.assert_allclose(final_repl, [0, 0, 1, 0, 0, 0, 1, 0])

    all_cf, all_repl = _run(
        _DummyPerformanceModel(plant_life=8),
        performance_timeseries=performance_timeseries,
        rated=1.0,
        soh=soh,
        eol=0.8,
        soh_cycle_repetition="all_soh_cycles",
    )
    np.testing.assert_allclose(all_cf, [1.0, 0.95, 0.9, 0.85, 0.8, 0.75, 1.0, 0.95])
    np.testing.assert_allclose(all_repl, [0, 0, 1, 0, 0, 0, 1, 0])


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
def test_replacement_schedule_counts_multiple_soh_resets_per_year(subtests):
    steps_per_year = 8760
    n_sim_years = 2
    soh = np.linspace(0.99, 0.95, n_sim_years * steps_per_year)
    soh[[100, 200, steps_per_year + 300]] = 1.0

    _, replacement_schedule = _run(
        _DummyPerformanceModel(plant_life=6, dt=3600),
        performance_timeseries=np.ones(n_sim_years * steps_per_year),
        rated=1.0,
        soh=soh,
        eol=0.8,
    )

    with subtests.test("two replacements are counted in simulated year one"):
        assert replacement_schedule[0] == pytest.approx(2.0)
    with subtests.test("one replacement is counted in simulated year two"):
        assert replacement_schedule[1] == pytest.approx(1.0)
    with subtests.test("schedule covers full plant life"):
        assert replacement_schedule.shape == (6,)


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
@pytest.mark.parametrize(
    "mode,expected_cf,expected_schedule",
    [
        ("all_soh_cycles", [0.8, 0.65125, 0.767083333333, 0.684166666667], [1, 1, 1, 1]),
        ("final_soh_cycle", [0.8, 0.67625, 0.67625, 0.734166666667], [1, 1, 0, 1]),
    ],
)
def test_subyear_cycles_project_cf_and_replacements_together(
    subtests, mode, expected_cf, expected_schedule
):
    cf_values, schedule = _run(
        _DummyPerformanceModel(plant_life=4, dt=31_536_000 / 4),
        performance_timeseries=[1.0, 0.5, 0.9, 0.8, 0.7, 0.6],
        rated=1.0,
        soh=[0.9, 0.8, 0.97, 0.92, 0.86, 0.8],
        eol=0.8,
        soh_cycle_repetition=mode,
    )
    with subtests.test("cycle-specific annual segments retain their half-year overlaps"):
        np.testing.assert_allclose(cf_values, expected_cf)
    with subtests.test("replacement counts follow the same cycle starts"):
        np.testing.assert_array_equal(schedule, expected_schedule)


@pytest.mark.unit
def test_incomplete_and_observed_eol_cycles_project_future_replacements(subtests) -> None:
    """Do not treat observed EOL as an observed reset when completing short cycles."""
    dummy = _DummyPerformanceModel(plant_life=3, dt=31_536_000 / 10)
    incomplete_cf, incomplete_schedule = _run(
        dummy,
        performance_timeseries=np.array([1.0, 0.9]),
        rated=1.0,
        soh=np.array([1.0, 0.9]),
        eol=0.8,
    )
    observed_eol_cf, observed_eol_schedule = _run(
        dummy,
        performance_timeseries=np.array([1.0, 0.9, 0.8]),
        rated=1.0,
        soh=np.array([1.0, 0.9, 0.8]),
        eol=0.8,
    )
    with subtests.test("observed EOL requires its own future timestep before replacement"):
        np.testing.assert_allclose(incomplete_cf, np.full(3, 0.9))
        np.testing.assert_allclose(observed_eol_cf, np.full(3, 0.85))
    with subtests.test("multiple replacements per year remain whole counts"):
        np.testing.assert_array_equal(incomplete_schedule, np.full(3, 3))
        np.testing.assert_array_equal(observed_eol_schedule, [2, 2, 3])
        assert np.issubdtype(incomplete_schedule.dtype, np.integer)


@pytest.mark.unit
def test_final_subyear_cycle_retains_its_own_performance(subtests) -> None:
    """Do not mix production from different cycles before selecting a repeat cycle."""
    cf_values, schedule = _run(
        _DummyPerformanceModel(plant_life=3, dt=31_536_000 / 4),
        performance_timeseries=np.array([0.0, 0.0, 1.0, 1.0]),
        rated=1.0,
        soh=np.array([1.0, 0.8, 1.0, 0.8]),
        eol=0.8,
        soh_cycle_repetition="final_soh_cycle",
    )
    with subtests.test("only the final cycle supplies projected production"):
        np.testing.assert_allclose(cf_values, [0.5, 0.875, 0.9375])
    with subtests.test("the final cycle includes a projected timestep before repeating"):
        np.testing.assert_array_equal(schedule, [1, 1, 2])


@pytest.mark.unit
@pytest.mark.parametrize(
    "soh,eol,dt_years,plant_life,expected_schedule",
    [
        (np.array([1.0, 0.9]), 0.85, 0.25, 3, np.array([1, 1, 1])),
        (np.array([0.1, 0.05]), 0.0, 0.25, 3, np.array([1, 1, 1])),
        (np.array([1.0, 0.99]), 0.1, 0.3, 2, np.array([0, 0])),
    ],
)
def test_timestep_cycle_completion_boundaries(
    subtests,
    soh: np.ndarray,
    eol: float,
    dt_years: float,
    plant_life: int,
    expected_schedule: np.ndarray,
) -> None:
    """Keep projected EOL on timestep boundaries and exclude retirement events."""
    cf_values, schedule = _run(
        _DummyPerformanceModel(plant_life=plant_life, dt=dt_years * 31_536_000),
        performance_timeseries=soh.copy(),
        rated=1.0,
        soh=soh,
        eol=eol,
    )
    with subtests.test("only completed cycles before retirement cause replacements"):
        np.testing.assert_array_equal(schedule, expected_schedule)
        assert np.issubdtype(schedule.dtype, np.integer)
    with subtests.test("projection remains finite through zero SOH or an incomplete cycle"):
        assert cf_values.shape == (plant_life,)
        assert np.all(np.isfinite(cf_values))
        assert np.all(cf_values >= 0.0)


@pytest.mark.unit
def test_partial_year_cycle_projects_future_replacements(subtests):
    cf_values, schedule = _run(
        _DummyPerformanceModel(plant_life=3, dt=31_536_000 / 4),
        performance_timeseries=[1.0, 0.5],
        rated=1.0,
        soh=[0.9, 0.8],
        eol=0.8,
    )
    with subtests.test("partial-year cycle fills the entire projected lifetime"):
        projected_cf = 0.5 * 0.7 / 0.8
        np.testing.assert_allclose(cf_values, np.full(3, (1.0 + 0.5 + projected_cf) / 3))
    with subtests.test("events at 0.75, 1.5, and 2.25 remain whole replacement counts"):
        np.testing.assert_array_equal(schedule, [1, 1, 1])


@pytest.mark.unit
@pytest.mark.parametrize(
    "mode,expected_cf,expected_schedule",
    [
        ("all_soh_cycles", [0.8, 0.54375, 0.8, 0.54375], [1, 1, 2, 1]),
        ("final_soh_cycle", [0.8, 0.54375, 0.491666666667, 0.491666666667], [1, 1, 2, 1]),
    ],
)
def test_midyear_resets_preserve_trailing_cycle_phase(
    subtests, mode, expected_cf, expected_schedule
):
    cf_values, schedule = _run(
        _DummyPerformanceModel(plant_life=4, dt=31_536_000 / 4),
        performance_timeseries=[1.0, 0.5, 0.9, 0.8, 0.7, 0.6, 0.5],
        rated=1.0,
        soh=[1.0, 0.9, 1.0, 0.9, 0.8, 1.0, 0.8],
        eol=0.8,
        soh_cycle_repetition=mode,
    )
    with subtests.test("annual means retain observed and repeated partial-year durations"):
        np.testing.assert_allclose(cf_values, expected_cf)
    with subtests.test("observed event at 1.25 precedes the projected event at 2.0"):
        np.testing.assert_array_equal(schedule, expected_schedule)
    with subtests.test("all observed and projected replacements are whole units"):
        assert np.issubdtype(schedule.dtype, np.integer)


@pytest.mark.unit
@pytest.mark.parametrize("mode", ["all_soh_cycles", "final_soh_cycle"])
def test_multiple_observed_and_extrapolated_resets(subtests, mode):
    _, schedule = _run(
        _DummyPerformanceModel(plant_life=5, dt=31_536_000 / 4),
        performance_timeseries=np.ones(7),
        rated=1.0,
        soh=[0.8, 1.0, 0.8, 1.0, 0.8, 1.0, 0.9],
        eol=0.8,
        soh_cycle_repetition=mode,
    )
    expected = [2, 1, 3, 1, 3] if mode == "all_soh_cycles" else [2, 1, 2, 1, 1]
    with subtests.test("events at 0.25, 0.75, 1.25 and extrapolated 2.0 precede repetition"):
        np.testing.assert_array_equal(schedule, expected)


@pytest.mark.unit
@pytest.mark.parametrize(
    "soh,mode,expected_schedule",
    [
        (np.ones(6), "all_soh_cycles", np.zeros(4, dtype=int)),
        (np.full(6, 0.9), "all_soh_cycles", np.zeros(4, dtype=int)),
        (np.array([0.9, 1.0]), "all_soh_cycles", np.full(4, 2, dtype=int)),
        (np.array([0.9, 1.0]), "final_soh_cycle", np.array([1, 0, 0, 0])),
    ],
)
def test_stalled_or_unmeasured_post_reset_degradation(
    subtests, soh: np.ndarray, mode: str, expected_schedule: np.ndarray
) -> None:
    """Do not infer degradation from constant SOH or a single post-reset sample."""
    cf_values, schedule = _run(
        _DummyPerformanceModel(plant_life=4, dt=31_536_000 / 4),
        performance_timeseries=np.ones(len(soh)),
        rated=1.0,
        soh=soh,
        eol=0.8,
        soh_cycle_repetition=mode,
    )
    with subtests.test("stalling does not invent an EOL replacement"):
        np.testing.assert_array_equal(schedule, expected_schedule)
    with subtests.test("annual CF remains available across the full plant life"):
        np.testing.assert_allclose(cf_values, np.ones(4))


@pytest.mark.unit
@pytest.mark.parametrize("sample_count", [8, 6])
def test_partial_final_year_normalizes_soh_degradation(subtests, sample_count):
    soh = np.linspace(1.0, 0.9, 8)[:sample_count]
    cf_values, schedule = _run(
        _DummyPerformanceModel(plant_life=10, dt=31_536_000 / 4),
        performance_timeseries=np.ones(sample_count),
        rated=1.0,
        soh=soh,
        eol=0.8,
    )
    degradation_per_step = (1.0 - 0.9) / 7
    projected_steps_in_year = 4 - sample_count % 4
    first_projected_cf = (
        soh[-1] - degradation_per_step * np.arange(1, projected_steps_in_year + 1)
    ) / soh[-1]
    observed_duration = sample_count / 4
    observed_fraction = observed_duration - math.floor(observed_duration)
    expected_first_cf = observed_fraction + (1.0 - observed_fraction) * first_projected_cf.mean()
    with subtests.test("partial final year uses the same SOH loss per elapsed year"):
        assert cf_values[math.floor(observed_duration)] == pytest.approx(expected_first_cf)
    with subtests.test("both observation lengths complete the same 3.75-year cycle"):
        expected = np.zeros(10, dtype=int)
        for event_time in np.arange(3.75, 10, 3.75):
            expected[math.floor(event_time)] += 1
        np.testing.assert_array_equal(schedule, expected)


@pytest.mark.unit
def test_reset_tolerance_does_not_infer_unobservable_events(subtests):
    cf_values, schedule = _run(
        _DummyPerformanceModel(plant_life=3, dt=31_536_000 / 4),
        performance_timeseries=np.ones(4),
        rated=1.0,
        soh=[1.0 - 5e-10, 1.0, 1.0, 1.0],
        eol=0.8,
    )
    with subtests.test("SOH jumps no larger than tolerance are not counted"):
        np.testing.assert_array_equal(schedule, [0, 0, 0])
    with subtests.test("fresh equal samples do not imply repeated replacements"):
        np.testing.assert_allclose(cf_values, [1, 1, 1])


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
        _run(_DummyPerformanceModel(dt=31_536_000 / 4), **inputs)


@pytest.mark.unit
@pytest.mark.parametrize(
    "attribute,value",
    [
        ("dt", 0),
        ("dt", np.inf),
        ("dt", -1),
        ("plant_life", 0),
        ("plant_life", 1.5),
        ("plant_life", np.nan),
    ],
)
def test_annualization_rejects_invalid_clock(attribute, value):
    dummy = _DummyPerformanceModel()
    setattr(dummy, attribute, value)
    with pytest.raises(ValueError, match=attribute):
        _run(dummy, performance_timeseries=[1.0], rated=1.0, soh=None, eol=None)


@pytest.mark.unit
def test_annual_means_weight_timesteps_crossing_fixed_year_boundaries(subtests):
    cf_values, schedule = _run(
        _DummyPerformanceModel(plant_life=3, dt=0.3 * 31_536_000),
        performance_timeseries=[0.2, 0.4, 0.6, 0.8],
        rated=1.0,
        soh=[0.9, 0.85, 0.8, 0.75],
        eol=0.8,
    )
    with subtests.test("projected 1.5-year cycles share the same projection clock"):
        np.testing.assert_allclose(cf_values, [0.44, 0.604, 0.604])
    with subtests.test("replacement at 1.5 is counted and retirement at 3.0 is excluded"):
        np.testing.assert_array_equal(schedule, [0, 1, 0])


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
