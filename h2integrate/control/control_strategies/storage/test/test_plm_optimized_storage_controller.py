from types import SimpleNamespace

import numpy as np
import pandas as pd
import pytest
import openmdao.api as om
import pyomo.environ as pyomo

from h2integrate.storage.storage_performance_model import StoragePerformanceModel
from h2integrate.control.control_strategies.storage.plm_optimized_storage_controller import (
    PeakLoadManagementOptimizedControllerConfig,
    PeakLoadManagementOptimizedStorageController,
)


def _make_controller():
    return object.__new__(PeakLoadManagementOptimizedStorageController)


def _make_controller_with_config(config, n_timesteps=24, dt_seconds=3600):
    """Build a controller with pre-computed masks, bypassing OpenMDAO setup."""
    controller = _make_controller()
    controller.config = config
    controller.dt_seconds = dt_seconds
    controller.updated_initial_soc = config.init_soc_fraction
    controller.time_index = pd.date_range("2024-01-01", periods=n_timesteps, freq="h")
    controller.in_peak_window = controller._compute_peak_window_mask()
    controller.month_ids = controller._compute_month_ids()
    if config.event_duration is not None:
        controller.steps_per_event = max(
            1,
            int(
                round(
                    pd.Timedelta(
                        value=config.event_duration["val"],
                        unit=config.event_duration["units"],
                    ).total_seconds()
                    / dt_seconds
                )
            ),
        )
    else:
        controller.steps_per_event = 1
    return controller


@pytest.fixture
def base_config():
    n = 24
    return PeakLoadManagementOptimizedControllerConfig(
        max_capacity=10.0,
        max_soc_fraction=1.0,
        min_soc_fraction=0.0,
        init_soc_fraction=1.0,
        n_control_window_hours=n,
        commodity="electricity",
        commodity_rate_units="kW",
        tech_name="battery",
        system_commodity_interface_limit=100.0,
        max_charge_rate=1.0,
        supervisory_signal=list(range(n)),
        peak_window={"start": "08:00:00", "end": "18:00:00"},
        performance_incentive=10.0,
        n_max_events=24,
        signal_threshold_percentile=0.0,
    )


@pytest.mark.unit
def test_parse_peak_window(subtests):
    controller = _make_controller()
    controller.config = SimpleNamespace(peak_window={"start": "08:00:00", "end": "18:40:20"})
    start, end = controller._parse_peak_window()
    with subtests.test("start hour"):
        assert start.hour == 8
    with subtests.test("start minute"):
        assert start.minute == 0
    with subtests.test("start second"):
        assert start.second == 0
    with subtests.test("end hour"):
        assert end.hour == 18
    with subtests.test("end minute"):
        assert end.minute == 40
    with subtests.test("end second"):
        assert end.second == 20


@pytest.mark.unit
def test_parse_peak_window_invalid_format():
    controller = _make_controller()
    controller.config = SimpleNamespace(peak_window={"start": "08", "end": "18:40:20"})
    with pytest.raises(
        ValueError,
    ):
        controller._parse_peak_window()


@pytest.mark.unit
def test_parse_peak_window_missing_key_raises():
    controller = _make_controller()
    controller.config = SimpleNamespace(peak_window={"start": "08:00:00"})
    with pytest.raises(ValueError, match="peak_window must contain 'start' and 'end' keys"):
        controller._parse_peak_window()


@pytest.mark.unit
def test_compute_peak_window_mask(subtests):
    controller = _make_controller()
    controller.config = SimpleNamespace(peak_window={"start": "00:00:00", "end": "02:00:00"})
    controller.time_index = pd.date_range("2024-01-01", periods=24, freq="h")
    mask = controller._compute_peak_window_mask()
    expected = np.array([i < 2 for i in range(24)])
    with subtests.test("Returns ndarray"):
        assert isinstance(mask, np.ndarray)
    with subtests.test("Correct values"):
        assert np.array_equal(mask, expected)


@pytest.mark.unit
def test_compute_month_ids():
    controller = _make_controller()
    controller.time_index = pd.date_range("2024-01-01", periods=744 + 696 + 744, freq="h")
    month_ids = controller._compute_month_ids()
    expected = np.array([1] * 744 + [2] * 696 + [3] * 744)
    assert np.array_equal(month_ids, expected), f"Expected {expected} but got {month_ids}"


@pytest.mark.unit
def test_compute_eligible_mask_zero_percentile_all_eligible(subtests):
    """All timesteps are eligible when signal_threshold_percentile=0."""
    controller = _make_controller()
    controller.config = SimpleNamespace(signal_threshold_percentile=0.0, min_peak_separation=None)
    signal = np.array([1.0, 5.0, 3.0, 2.0, 8.0])
    mask = controller._compute_eligible_mask(signal)
    with subtests.test("_compute_eligible_mask Returns ndarray"):
        assert isinstance(mask, np.ndarray)
    with subtests.test("_compute_eligible_mask returns Bool dtype"):
        assert mask.dtype == bool
    with subtests.test("_compute_eligible_mask returns correct length"):
        assert len(mask) == len(signal)
    with subtests.test("_compute_eligible_mask marks all as eligible when percentile=0`"):
        assert mask.all()


@pytest.mark.unit
def test_compute_eligible_mask_50th_percentile():
    """Only values at or above the 50th percentile are eligible."""
    controller = _make_controller()
    controller.config = SimpleNamespace(signal_threshold_percentile=50.0, min_peak_separation=None)
    signal = np.array([1.0, 2.0, 3.0, 4.0, 5.0])
    mask = controller._compute_eligible_mask(signal)
    expected = signal >= np.percentile(signal, 50.0)
    assert np.array_equal(mask, expected), f"Expected {expected} but got {mask}"


@pytest.mark.unit
def test_compute_eligible_mask_100th_percentile_only_max_eligible():
    """Only the maximum value(s) are eligible at percentile=100."""
    controller = _make_controller()
    controller.config = SimpleNamespace(signal_threshold_percentile=100.0, min_peak_separation=None)
    signal = np.array([1.0, 2.0, 10.0, 3.0, 10.0])
    mask = controller._compute_eligible_mask(signal)
    expected = np.array([False, False, True, False, True])
    assert np.array_equal(mask, expected), f"Expected {expected} but got {mask}"


@pytest.mark.unit
def test_compute_eligible_mask_uniform_signal_all_eligible():
    """All timesteps are eligible when the signal is uniform, regardless of percentile."""
    controller = _make_controller()
    controller.config = SimpleNamespace(signal_threshold_percentile=75.0, min_peak_separation=None)
    signal = np.full(10, 5.0)
    mask = controller._compute_eligible_mask(signal)
    assert mask.all(), f"Expected all True but got {mask}"


@pytest.mark.regression
def test_optimizer_dispatch_only_in_peak_window(subtests, base_config):
    """Solver must never set 1 outside the peak window."""
    controller = _make_controller_with_config(base_config)
    model = controller._build_dr_model(
        window_start=0,
        window_len=24,
        init_soc=base_config.init_soc_fraction,
        remaining_budget={1: base_config.n_max_events},
        P_max=base_config.max_charge_rate,
        storage_capacity=base_config.max_capacity,
    )

    PeakLoadManagementOptimizedStorageController.glpk_solve_call(model)

    peak_start, peak_end = controller._parse_peak_window()
    for t in range(24):
        hour = pd.Timestamp("2024-01-01") + pd.Timedelta(hours=t)
        in_window = peak_start <= hour.time() <= peak_end
        if not in_window:
            with subtests.test(f"No discharge outside peak window at t={t}"):
                assert pyomo.value(model.discharge[t]) < 1e-3  # type: ignore[index]


@pytest.mark.regression
def test_optimizer_dispatch_only_on_eligible_timesteps(subtests, base_config):
    """Solver must never set 1 on ineligible timesteps."""
    controller = _make_controller_with_config(base_config)
    model = controller._build_dr_model(
        window_start=0,
        window_len=24,
        init_soc=base_config.init_soc_fraction,
        remaining_budget={1: base_config.n_max_events},
        P_max=base_config.max_charge_rate,
        storage_capacity=base_config.max_capacity,
    )

    PeakLoadManagementOptimizedStorageController.glpk_solve_call(model)

    signal = np.array(controller.config.supervisory_signal)
    eligible_mask = controller._compute_eligible_mask(signal)
    for t in range(24):
        if not eligible_mask[t]:
            with subtests.test(f"No discharge on ineligible timestep at t={t}"):
                assert pyomo.value(model.discharge[t]) < 1e-3  # type: ignore[index]


@pytest.mark.regression
def test_optimizer_dispatch_respects_event_budget(base_config):
    """Solver must never set more than n_max_events timesteps to 1."""
    controller = _make_controller_with_config(base_config)
    model = controller._build_dr_model(
        window_start=0,
        window_len=24,
        init_soc=base_config.init_soc_fraction,
        remaining_budget={1: 4},
        P_max=base_config.max_charge_rate,
        storage_capacity=base_config.max_capacity,
    )

    PeakLoadManagementOptimizedStorageController.glpk_solve_call(model)

    total_events = sum(pyomo.value(model.discharge[t]) for t in range(24))  # type: ignore[index]
    assert total_events <= 4 + 1e-3, f"Total events {total_events} exceeds budget of 4"


@pytest.mark.regression
def test_optimizer_dispatch_respects_soc_constraints(subtests, base_config):
    """Solver must never violate SOC constraints."""
    controller = _make_controller_with_config(base_config)
    model = controller._build_dr_model(
        window_start=0,
        window_len=24,
        init_soc=base_config.init_soc_fraction,
        remaining_budget={2: base_config.n_max_events},
        P_max=base_config.max_charge_rate,
        storage_capacity=base_config.max_capacity,
    )

    PeakLoadManagementOptimizedStorageController.glpk_solve_call(model)

    E_max = base_config.max_capacity * (base_config.max_soc_fraction - base_config.min_soc_fraction)
    eta_c = base_config.charge_efficiency
    eta_d = base_config.discharge_efficiency
    dt_hours = 3600 / 3600.0
    soc = base_config.init_soc_fraction
    for t in range(24):
        p_charge = pyomo.value(model.p_charge[t])  # type: ignore[index]
        p_discharge = pyomo.value(model.p_discharge[t])  # type: ignore[index]
        if t > 0:
            soc += eta_c * p_charge * dt_hours / E_max - p_discharge * dt_hours / (eta_d * E_max)
        with subtests.test(f"SOC above min at t={t}"):
            assert soc >= base_config.min_soc_fraction - 1e-6
        with subtests.test(f"SOC below max at t={t}"):
            assert soc <= base_config.max_soc_fraction + 1e-6


@pytest.mark.unit
def test_compute_eligible_mask_min_peak_separation_drops_nearby_peak(subtests):
    """A later peak within min_peak_separation of an earlier peak is dropped."""
    controller = _make_controller()
    controller.config = SimpleNamespace(
        signal_threshold_percentile=50.0,
        min_peak_separation={"units": "h", "val": 3},
    )
    controller.dt_seconds = 3600
    signal = np.array([1.0, 1.0, 1.0, 1.0, 1.0, 10.0, 1.0, 8.0, 1.0, 1.0])
    mask = controller._compute_eligible_mask(signal)
    with subtests.test("First eligible peak kept"):
        assert mask[0]
    with subtests.test("Adjacent peak within separation dropped"):
        assert not mask[1]


@pytest.mark.unit
def test_compute_eligible_mask_min_peak_separation_keeps_far_peaks(subtests):
    """Peaks separated by more than min_peak_separation are both kept."""
    controller = _make_controller()
    controller.config = SimpleNamespace(
        signal_threshold_percentile=0.0,
        min_peak_separation={"units": "h", "val": 3},
    )
    controller.dt_seconds = 3600
    # t=2 (signal=10) and t=6 (signal=8) are 4h apart
    signal = np.array([1.0, 1.0, 10.0, 1.0, 1.0, 1.0, 8.0, 1.0, 1.0, 1.0])
    mask = controller._compute_eligible_mask(signal)
    with subtests.test("First peak kept"):
        assert mask[2]
    with subtests.test("Distant peak also kept"):
        assert mask[6]


@pytest.mark.unit
def test_compute_eligible_mask_min_peak_separation_none_no_pruning():
    """min_peak_separation=None leaves all percentile-eligible peaks unchanged."""
    controller = _make_controller()
    controller.config = SimpleNamespace(
        signal_threshold_percentile=0.0,
        min_peak_separation=None,
    )
    signal = np.array([1.0, 5.0, 6.0, 5.0, 1.0])
    mask = controller._compute_eligible_mask(signal)
    assert mask.all(), f"Expected all True but got {mask}"


@pytest.mark.regression
def test_optimizer_dispatch_respects_charge_discharge_exclusivity(subtests, base_config):
    """Solver must never set charge and discharge to 1 in the same timestep."""
    controller = _make_controller_with_config(base_config)
    model = controller._build_dr_model(
        window_start=0,
        window_len=24,
        init_soc=base_config.init_soc_fraction,
        remaining_budget={1: base_config.n_max_events},
        P_max=base_config.max_charge_rate,
        storage_capacity=base_config.max_capacity,
    )

    PeakLoadManagementOptimizedStorageController.glpk_solve_call(model)

    for t in range(24):
        charge = pyomo.value(model.charge[t])  # type: ignore[index]
        discharge = pyomo.value(model.discharge[t])  # type: ignore[index]
        with subtests.test(f"No simultaneous charge and discharge at t={t}"):
            assert not (charge > 0.5 and discharge > 0.5)


@pytest.mark.regression
def test_power_zero_when_binary_zero(subtests, base_config):
    """p_discharge[t] must be 0 whenever discharge[t] == 0."""
    controller = _make_controller_with_config(base_config)
    model = controller._build_dr_model(
        window_start=0,
        window_len=24,
        init_soc=base_config.init_soc_fraction,
        remaining_budget={1: base_config.n_max_events},
        P_max=base_config.max_charge_rate,
        storage_capacity=base_config.max_capacity,
    )

    PeakLoadManagementOptimizedStorageController.glpk_solve_call(model)

    for t in range(24):
        u = pyomo.value(model.discharge[t])  # type: ignore[index]
        p_d = pyomo.value(model.p_discharge[t])  # type: ignore[index]
        v = pyomo.value(model.charge[t])  # type: ignore[index]
        p_c = pyomo.value(model.p_charge[t])  # type: ignore[index]
        with subtests.test(f"p_discharge zero when binary zero at t={t}"):
            if u < 0.5:
                assert p_d < 1e-6, f"p_discharge[{t}]={p_d} but discharge[{t}]={u}"
        with subtests.test(f"p_charge zero when binary zero at t={t}"):
            if v < 0.5:
                assert p_c < 1e-6, f"p_charge[{t}]={p_c} but charge[{t}]={v}"


@pytest.mark.regression
def test_performance_incentive_per_event_matches_equivalent_kwh_rate(subtests):
    """$/event and its equivalent $/kWh rate must produce identical dispatch.

    With event_duration=2h, dt=1h, P_max=1.0 kW:
      steps_per_event=2, dt_hours=1.0
      10.0 $/event / (2 * 1.0 * 1.0) = 5.0 $/kWh
    """
    common = {
        "max_capacity": 10.0,
        "max_soc_fraction": 1.0,
        "min_soc_fraction": 0.0,
        "init_soc_fraction": 1.0,
        "n_control_window_hours": 24,
        "commodity": "electricity",
        "commodity_rate_units": "kW",
        "tech_name": "battery",
        "system_commodity_interface_limit": 100.0,
        "max_charge_rate": 1.0,
        "supervisory_signal": list(range(24)),
        "peak_window": {"start": "08:00:00", "end": "18:00:00"},
        "n_max_events": 24,
        "signal_threshold_percentile": 0.0,
        "event_duration": {"val": 2, "units": "h"},
    }
    config_kwh = PeakLoadManagementOptimizedControllerConfig(**common, performance_incentive=5.0)
    config_event = PeakLoadManagementOptimizedControllerConfig(
        **common, performance_incentive_per_event=10.0
    )

    build_kwargs = {
        "window_start": 0,
        "window_len": 24,
        "init_soc": 1.0,
        "remaining_budget": {1: 24},
        "P_max": 1.0,
        "storage_capacity": 10.0,
    }
    model_kwh = _make_controller_with_config(config_kwh)._build_dr_model(**build_kwargs)
    model_event = _make_controller_with_config(config_event)._build_dr_model(**build_kwargs)

    PeakLoadManagementOptimizedStorageController.glpk_solve_call(model_kwh)
    PeakLoadManagementOptimizedStorageController.glpk_solve_call(model_event)

    for t in range(24):
        with subtests.test(f"dispatch match at t={t}"):
            assert (
                abs(
                    pyomo.value(model_kwh.p_discharge[t])  # type: ignore[index]
                    - pyomo.value(model_event.p_discharge[t])  # type: ignore[index]
                )
                < 1e-4
            ), f"Dispatch mismatch at t={t}"


@pytest.fixture
def om_plant_config():
    return {
        "plant": {
            "plant_life": 30,
            "simulation": {
                "n_timesteps": 24,
                "dt": 3600,
                "timezone": 0,
                "start_time": "01/01/2024 00:00:00",
            },
        },
        "tech_to_dispatch_connections": [["controller", "storage"]],
    }


@pytest.fixture
def om_tech_config():
    n = 24
    return {
        "model_inputs": {
            "shared_parameters": {
                "tech_name": "battery",
                "commodity": "electricity",
                "commodity_rate_units": "kW",
                "max_charge_rate": 1.0,
                "max_capacity": 10.0,
                "max_soc_fraction": 1.0,
                "min_soc_fraction": 0.0,
                "init_soc_fraction": 1.0,
                "charge_efficiency": 1.0,
                "discharge_efficiency": 1.0,
            },
            "performance_parameters": {
                "demand_profile": 10.0,
            },
            "control_parameters": {
                "system_commodity_interface_limit": 1.0e9,
                "supervisory_signal": np.ones(n).tolist(),
                "peak_window": {"start": "02:00:00", "end": "04:00:00"},
                "performance_incentive": 10.0,
                "n_max_events": 24,
                "signal_threshold_percentile": 0.0,
                "n_control_window_hours": n,
            },
        }
    }


@pytest.mark.regression
def test_plm_optimized_controller_om_problem_soc_bounds(subtests, om_plant_config, om_tech_config):
    """Controller and StoragePerformanceModel wired as an om.Problem respect SOC bounds
    and discharge only within the peak window."""
    n = om_plant_config["plant"]["simulation"]["n_timesteps"]

    prob = om.Problem()

    prob.model.add_subsystem(
        name="IVC",
        subsys=om.IndepVarComp(name="electricity_in", val=np.ones(n), units="kW"),
        promotes=["*"],
    )
    prob.model.add_subsystem(
        "controller",
        PeakLoadManagementOptimizedStorageController(
            plant_config=om_plant_config,
            tech_config=om_tech_config,
        ),
        promotes=["*"],
    )
    prob.model.add_subsystem(
        "storage",
        StoragePerformanceModel(
            plant_config=om_plant_config,
            tech_config=om_tech_config,
        ),
        promotes=["*"],
    )

    prob.setup()
    prob.run_model()

    soc = prob.get_val("SOC", units="unitless")
    discharge = prob.get_val("storage_electricity_discharge", units="kW")

    with subtests.test("SOC never below min"):
        assert np.all(soc >= 0.0 - 1e-1)

    with subtests.test("SOC never above max"):
        assert np.all(soc <= 1.0 + 1e-1)

    pw = om_tech_config["model_inputs"]["control_parameters"]["peak_window"]
    pw_start = pd.Timestamp(f"2024-01-01 {pw['start']}").time()
    pw_end = pd.Timestamp(f"2024-01-01 {pw['end']}").time()
    time_index = pd.date_range("2024-01-01", periods=n, freq="h")
    for t in range(n):
        in_window = pw_start <= time_index[t].time() < pw_end
        if not in_window:
            with subtests.test(f"No discharge outside peak window at t={t}"):
                assert (
                    discharge[t] <= 1e-4
                ), f"Discharge {discharge[t]:.4f} kW outside peak window at t={t}"

    with subtests.test("Discharge never negative"):
        assert np.all(discharge >= -1e-4)

    with subtests.test("Discharge never above max_charge_rate"):
        assert np.all(discharge <= 1.0 + 1e-4)

    with subtests.test("SOC at t=0 equal to init_soc_fraction"):
        assert abs(soc[0] - 1.0) < 1e-4

    shared = om_tech_config["model_inputs"]["shared_parameters"]
    E_max = shared["max_capacity"] * (shared["max_soc_fraction"] - shared["min_soc_fraction"])
    charge = prob.get_val("storage_electricity_charge", units="kW")
    expected_soc = np.zeros(n)
    expected_soc[0] = shared["init_soc_fraction"]
    for t in range(1, n):
        expected_soc[t] = expected_soc[t - 1] + charge[t] / E_max - discharge[t] / E_max
    for t in range(n):
        with subtests.test(f"SOC evolution at t={t}"):
            assert (
                abs(soc[t] - expected_soc[t]) < 1e-4
            ), f"SOC mismatch at t={t}: got {soc[t]:.4f}, expected {expected_soc[t]:.4f}"
