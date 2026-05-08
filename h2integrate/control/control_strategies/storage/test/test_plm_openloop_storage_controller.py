from types import SimpleNamespace
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
import openmdao.api as om
from pytest import fixture

from h2integrate.storage.storage_performance_model import StoragePerformanceModel
from h2integrate.control.control_strategies.storage.plm_openloop_storage_controller import (
    PeakLoadManagementHeuristicOpenLoopStorageController,
)


@fixture
def tech_config_base():
    """Base technology configuration fixture for storage controller tests."""
    tech_config_dict = {
        "name": "technology_config",
        "description": "This hybrid plant produces hydrogen",
        "technologies": {
            "h2_storage": {
                "control_strategy": {
                    "model": "SimpleStorageOpenLoopController",
                },
                "performance_model": {
                    "model": "StoragePerformanceModel",
                },
                "model_inputs": {
                    "shared_parameters": {
                        "commodity": "hydrogen",
                        "commodity_rate_units": "kg/h",
                    },
                },
            },
        },
    }

    return tech_config_dict


@fixture
def plant_config_base():
    plant_config = {
        "plant": {
            "plant_life": 30,
            "simulation": {
                "n_timesteps": 24,
                "dt": 3600,
                "timezone": 0,
                "start_time": "01/01/2000 00:00:00",
            },
        }
    }

    return plant_config


def _controller_without_setup():
    """Create a controller instance for testing pure helper methods."""
    return object.__new__(PeakLoadManagementHeuristicOpenLoopStorageController)


@pytest.mark.unit
def test_get_peaks_daily_expected_peaks():
    controller = _controller_without_setup()

    demand_profile = {
        "date_time": pd.date_range("2025-01-01", periods=8, freq="6h"),
        "demand": [1.0, 9.0, 3.0, 2.0, 4.0, 5.0, 2.0, 8.0],
    }

    expected_peak_times = [
        pd.Timestamp("2025-01-01 06:00:00"),
        pd.Timestamp("2025-01-02 18:00:00"),
    ]

    peaks = controller.get_peaks(demand_profile)
    actual_peak_times = peaks.loc[peaks["is_peak"], "date_time"].tolist()

    assert actual_peak_times == expected_peak_times


@pytest.mark.unit
def test_get_peaks_with_global_event_limit_expected_peak():
    controller = _controller_without_setup()

    demand_profile = {
        "date_time": pd.date_range("2025-01-01", periods=8, freq="6h"),
        "demand": [1.0, 9.0, 3.0, 2.0, 4.0, 5.0, 2.0, 8.0],
    }

    expected_peak_times = [pd.Timestamp("2025-01-01 06:00:00")]

    peaks = controller.get_peaks(demand_profile, n_override_events=1, override_events_period=None)
    actual_peak_times = peaks.loc[peaks["is_peak"], "date_time"].tolist()

    assert actual_peak_times == expected_peak_times


@pytest.mark.unit
def test_get_peaks_with_month_period_expected_peaks():
    controller = _controller_without_setup()

    demand_profile = {
        "date_time": [
            pd.Timestamp("2025-01-01 00:00:00"),
            pd.Timestamp("2025-01-01 12:00:00"),
            pd.Timestamp("2025-01-02 00:00:00"),
            pd.Timestamp("2025-01-02 12:00:00"),
            pd.Timestamp("2025-02-01 00:00:00"),
            pd.Timestamp("2025-02-01 12:00:00"),
            pd.Timestamp("2025-02-02 00:00:00"),
            pd.Timestamp("2025-02-02 12:00:00"),
        ],
        "demand": [
            5.0,
            2.0,
            9.0,
            3.0,
            4.0,
            12.0,
            8.0,
            1.0,
        ],
    }

    expected_peak_times = [
        pd.Timestamp("2025-01-02 00:00:00"),
        pd.Timestamp("2025-02-01 12:00:00"),
    ]

    peaks = controller.get_peaks(demand_profile, n_override_events=1, override_events_period="M")
    actual_peak_times = peaks.loc[peaks["is_peak"], "date_time"].tolist()

    assert actual_peak_times == expected_peak_times


@pytest.mark.unit
def test_get_peaks_with_month_period_from_csv_expected_peaks():
    controller = _controller_without_setup()
    data_dir = Path(__file__).resolve().parent / "data"
    demand_profile_df = pd.read_csv(data_dir / "lmp_month_1.csv")
    expected_peaks_df = pd.read_csv(data_dir / "lmp_peaks_month_1.csv")

    demand_profile = {
        "date_time": demand_profile_df["time_mountain"].to_list(),
        "demand": demand_profile_df["energy"].to_list(),
    }

    expected_peak_times = pd.to_datetime(expected_peaks_df["time_mountain"]).to_list()

    peaks = controller.get_peaks(demand_profile, n_override_events=10, override_events_period="M")
    actual_peak_times = pd.to_datetime(peaks.loc[peaks["is_peak"], "date_time"]).tolist()

    assert actual_peak_times == expected_peak_times


@pytest.mark.unit
def test_get_peaks_invalid_period_string_raises():
    controller = _controller_without_setup()

    demand_profile = {
        "date_time": pd.date_range("2025-01-01", periods=4, freq="6h"),
        "demand": [1.0, 2.0, 3.0, 4.0],
    }

    with pytest.raises(ValueError, match="Invalid override_events_period string"):
        controller.get_peaks(
            demand_profile, n_override_events=1, override_events_period="not_a_period"
        )


@pytest.mark.unit
def test_get_peaks_respects_peak_range_12pm_to_5pm():
    controller = _controller_without_setup()

    demand_profile = {
        "date_time": [
            pd.Timestamp("2025-01-01 09:00:00"),
            pd.Timestamp("2025-01-01 14:00:00"),
            pd.Timestamp("2025-01-01 18:00:00"),
            pd.Timestamp("2025-01-01 22:00:00"),
            pd.Timestamp("2025-01-02 10:00:00"),
            pd.Timestamp("2025-01-02 13:00:00"),
            pd.Timestamp("2025-01-02 20:00:00"),
            pd.Timestamp("2025-01-02 23:00:00"),
        ],
        "demand": [
            100.0,
            30.0,
            40.0,
            120.0,
            95.0,
            50.0,
            60.0,
            110.0,
        ],
    }

    peaks = controller.get_peaks(
        demand_profile,
        peak_range={"start": "12:00:00", "end": "17:00:00"},
    )
    actual_peak_times = peaks.loc[peaks["is_peak"], "date_time"].tolist()

    expected_peak_times = [
        pd.Timestamp("2025-01-01 14:00:00"),
        pd.Timestamp("2025-01-02 13:00:00"),
    ]

    assert actual_peak_times == expected_peak_times


@pytest.mark.unit
def test_get_peaks_rejects_non_string_peak_range_values():
    controller = _controller_without_setup()

    demand_profile = {
        "date_time": pd.date_range("2025-01-01", periods=4, freq="6h"),
        "demand": [1.0, 9.0, 3.0, 2.0],
    }

    with pytest.raises(ValueError, match="HH:MM:SS string"):
        controller.get_peaks(
            demand_profile,
            peak_range={"start": pd.Timestamp("2025-01-01 12:00:00").time(), "end": "17:00:00"},
        )


@pytest.mark.unit
def test_get_peaks_invalid_min_proximity_raises():
    controller = _controller_without_setup()

    demand_profile = {
        "date_time": pd.date_range("2025-01-01", periods=10, freq="6h"),
        "demand": [1.0, 2.0, 4.0, 3.0, 3.0, 4.0, 3.0, 2.0, 1.0, 2.0],
    }

    with pytest.raises(ValueError, match="Selected peaks violate min_proximity."):
        controller.get_peaks(
            demand_profile,
            n_override_events=2,
            override_events_period="W",
            min_proximity={"units": "D", "val": 1},
        )


@pytest.mark.unit
def test_merge_peaks_with_single_demand_profile_returns_correct_peaks_flags(subtests):
    peaks_1_df = pd.DataFrame(
        {
            "date_time": pd.to_datetime(
                [
                    "2025-01-01 14:00:00",
                    "2025-01-01 18:00:00",
                    "2025-01-02 13:00:00",
                    "2025-01-02 20:00:00",
                ]
            ),
            "is_peak": [False, True, False, True],
            "demand": [1.0, 5.0, 1.0, 6.0],
        }
    )

    merged = PeakLoadManagementHeuristicOpenLoopStorageController.merge_peaks(peaks_1_df, None)

    with subtests.test("peak flags unchanged"):
        assert merged["is_peak"].tolist() == peaks_1_df["is_peak"].tolist()


@pytest.mark.unit
def test_merge_peaks_profile2_takes_precedence_on_same_day(subtests):
    peaks_1_df = pd.DataFrame(
        {
            "date_time": pd.to_datetime(
                [
                    "2025-01-01 14:00:00",
                    "2025-01-01 18:00:00",
                    "2025-01-02 13:00:00",
                    "2025-01-02 20:00:00",
                ]
            ),
            "is_peak": [False, True, False, True],
            "demand": [1.0, 5.0, 1.0, 6.0],
        }
    )
    peaks_2_df = pd.DataFrame(
        {
            "date_time": pd.to_datetime(
                [
                    "2025-01-01 14:00:00",
                    "2025-01-01 18:00:00",
                    "2025-01-02 13:00:00",
                    "2025-01-02 20:00:00",
                ]
            ),
            "is_peak": [True, False, False, False],
            "demand": [9.0, 4.0, 6.0, 4.0],
        }
    )

    merged = PeakLoadManagementHeuristicOpenLoopStorageController.merge_peaks(
        peaks_2_df,
        peaks_1_df,
    )

    with subtests.test("day1 follows peaks_2 flags"):
        np.testing.assert_array_equal(merged["is_peak"].iloc[0:2], peaks_2_df["is_peak"].iloc[0:2])

    with subtests.test("day2 follows peaks_1 flags"):
        np.testing.assert_array_equal(
            merged["is_peak"].iloc[2:4],
            peaks_1_df["is_peak"].iloc[2:4],
        )


@pytest.mark.unit
def test_get_time_to_peak_single_peak(subtests):
    """Time-to-peak counted down from each row toward the one True is_peak entry."""
    controller = _controller_without_setup()
    controller.n_timesteps = 4
    times = pd.to_datetime(
        [
            "2025-01-01 12:00:00",
            "2025-01-01 14:00:00",
            "2025-01-01 16:00:00",  # peak
            "2025-01-01 18:00:00",
        ]
    )
    controller.peaks_df = pd.DataFrame(
        {
            "date_time": times,
            "is_peak": [False, False, True, False],
            "demand": [1.0, 2.0, 5.0, 3.0],
        }
    )

    controller.get_time_to_peak()

    with subtests.test("four hours before peak"):
        assert controller.peaks_df["time_to_peak"].iloc[0] == pd.Timedelta(hours=4)
    with subtests.test("two hours before peak"):
        assert controller.peaks_df["time_to_peak"].iloc[1] == pd.Timedelta(hours=2)
    with subtests.test("zero at peak"):
        assert controller.peaks_df["time_to_peak"].iloc[2] == pd.Timedelta(0)


@pytest.mark.unit
def test_get_time_to_peak_multiple_peaks(subtests):
    """Each row resolves to the *next upcoming* peak, not a later one."""
    controller = _controller_without_setup()
    controller.n_timesteps = 5
    times = pd.to_datetime(
        [
            "2025-01-01 08:00:00",
            "2025-01-01 10:00:00",  # first peak
            "2025-01-01 12:00:00",
            "2025-01-01 16:00:00",  # second peak
            "2025-01-01 18:00:00",
        ]
    )
    controller.peaks_df = pd.DataFrame(
        {
            "date_time": times,
            "is_peak": [False, True, False, True, False],
            "demand": [1.0, 8.0, 2.0, 7.0, 1.0],
        }
    )

    controller.get_time_to_peak()

    with subtests.test("before first peak resolves to first peak"):
        assert controller.peaks_df["time_to_peak"].iloc[0] == pd.Timedelta(hours=2)

    with subtests.test("at first peak is zero"):
        assert controller.peaks_df["time_to_peak"].iloc[1] == pd.Timedelta(0)

    with subtests.test("between peaks resolves to second peak"):
        assert controller.peaks_df["time_to_peak"].iloc[2] == pd.Timedelta(hours=4)

    with subtests.test("at second peak is zero"):
        assert controller.peaks_df["time_to_peak"].iloc[3] == pd.Timedelta(0)


def _make_controller_with_config(allow_charge_in_peak_range, peak_range):
    controller = _controller_without_setup()
    controller.config = SimpleNamespace(
        allow_charge_in_peak_range=allow_charge_in_peak_range,
        peak_range=peak_range,
    )
    return controller


@pytest.mark.unit
def test_get_allowed_charge_always_true_when_charge_allowed_in_peak_range():
    """When allow_charge_in_peak_range=True every row should allow charging."""
    controller = _make_controller_with_config(
        allow_charge_in_peak_range=True,
        peak_range={"start": "12:00:00", "end": "17:00:00"},
    )
    controller.peaks_df = pd.DataFrame(
        {
            "date_time": pd.to_datetime(
                [
                    "2025-01-01 09:00:00",
                    "2025-01-01 14:00:00",  # inside peak range
                    "2025-01-01 18:00:00",
                ]
            ),
            "is_peak": [False, True, False],
            "demand": [1.0, 5.0, 2.0],
        }
    )
    controller.n_timesteps = 3

    controller.get_allowed_charge()

    assert controller.peaks_df["allow_charge"].tolist() == [True, True, True]


@pytest.mark.unit
def test_get_allowed_charge_blocks_charge_inside_peak_range(subtests):
    """When allow_charge_in_peak_range=False, rows inside the window get allow_charge=False."""
    controller = _make_controller_with_config(
        allow_charge_in_peak_range=False,
        peak_range={"start": "12:00:00", "end": "17:00:00"},
    )
    controller.peaks_df = pd.DataFrame(
        {
            "date_time": pd.to_datetime(
                [
                    "2025-01-01 09:00:00",  # before range  → allow
                    "2025-01-01 14:00:00",  # inside range  → block
                    "2025-01-01 16:59:00",  # inside range  → block
                    "2025-01-01 18:00:00",  # after range   → allow
                ]
            ),
            "is_peak": [False, True, False, False],
            "demand": [1.0, 5.0, 4.0, 2.0],
        }
    )
    controller.n_timesteps = 4

    controller.get_allowed_charge()

    with subtests.test("before range allows charge"):
        assert controller.peaks_df["allow_charge"].iloc[0] is np.True_
    with subtests.test("inside range blocks charge (first)"):
        assert controller.peaks_df["allow_charge"].iloc[1] is np.False_
    with subtests.test("inside range blocks charge (second)"):
        assert controller.peaks_df["allow_charge"].iloc[2] is np.False_
    with subtests.test("after range allows charge"):
        assert controller.peaks_df["allow_charge"].iloc[3] is np.True_


@pytest.mark.regression
def test_plm_controller_basic_discharge_before_peak(subtests, tech_config_base, plant_config_base):
    """Test PLM controller discharges before detected peak and charges after."""

    # Load base tech config
    tech_config = tech_config_base

    # Configure PLM-specific parameters
    tech_config["technologies"]["h2_storage"]["model_inputs"]["shared_parameters"] = {
        "commodity": "hydrogen",
        "commodity_rate_units": "kg/h",
        "max_capacity": 100.0,  # kg
        "max_soc_fraction": 1.0,
        "min_soc_fraction": 0.1,
        "init_soc_fraction": 0.9,
        "max_charge_rate": 20.0,  # kg/time step
        "max_discharge_rate": 30.0,  # kg/time step
        "charge_equals_discharge": False,
        "charge_efficiency": 0.95,
        "discharge_efficiency": 0.95,
        "demand_profile": np.concatenate(
            (np.full(10, 10.0), np.full(4, 50.0), np.full(10, 10.0))
        ),  # Peak at hours 10-14
        "peak_range": {"start": "10:00:00", "end": "14:00:00"},
        "advance_discharge_period": {"units": "h", "val": 2},
        "delay_charge_period": {"units": "h", "val": 1},
        "allow_charge_in_peak_range": False,
        "demand_profile_upstream": None,
        "dispatch_priority_demand_profile": "demand_profile",
        "min_peak_proximity": {"units": "h", "val": 4},
    }

    tech_config["technologies"]["h2_storage"]["control_strategy"]["model"] = (
        "PeakLoadManagementHeuristicOpenLoopStorageController"
    )

    plant_config = plant_config_base

    # Set up OpenMDAO problem
    prob = om.Problem()

    prob.model.add_subsystem(
        name="IVC",
        subsys=om.IndepVarComp(name="hydrogen_in", val=[30.0] * 24),
        promotes=["*"],
    )

    prob.model.add_subsystem(
        "plm_controller",
        PeakLoadManagementHeuristicOpenLoopStorageController(
            plant_config=plant_config, tech_config=tech_config["technologies"]["h2_storage"]
        ),
        promotes=["*"],
    )

    prob.model.add_subsystem(
        "storage",
        StoragePerformanceModel(
            plant_config=plant_config, tech_config=tech_config["technologies"]["h2_storage"]
        ),
        promotes=["*"],
    )

    prob.setup()
    prob.run_model()

    set_point = prob.get_val("hydrogen_set_point", units="kg/h")
    soc = prob.get_val("SOC", units="unitless")

    with subtests.test("Discharge occurs before peak (hours 8-9)"):
        # Hours 8-9 are 2 hours before peak at hour 10
        # We expect discharge (positive set_point)
        assert set_point[8] > 0 and set_point[9] > 0

    with subtests.test("Peak triggers discharge (hours 10-13)"):
        # High demand period should be reduced by discharge
        assert all(set_point[10:13] >= 0)

    with subtests.test("SOC decreases during discharge phase"):
        # SOC should drop after discharge begins
        assert soc[8] < soc[7]

    with subtests.test("SOC recovers during charging phase"):
        # After peak, SOC should increase due to charging
        assert any(soc[15:] > soc[14])


@pytest.mark.regression
def test_plm_controller_respects_soc_bounds(subtests, tech_config_base, plant_config_base):
    """Test PLM controller respects min/max SOC constraints."""
    tech_config = tech_config_base

    tech_config["technologies"]["h2_storage"]["model_inputs"]["shared_parameters"] = {
        "commodity": "hydrogen",
        "commodity_rate_units": "kg/h",
        "max_capacity": 50.0,
        "max_soc_fraction": 0.95,
        "min_soc_fraction": 0.15,
        "init_soc_fraction": 0.5,
        "max_charge_rate": 15.0,
        "max_discharge_rate": 15.0,
        "charge_equals_discharge": True,
        "charge_efficiency": 0.9,
        "discharge_efficiency": 0.9,
        "demand_profile": [5.0] * 12,
        "peak_range": {"start": "06:00:00", "end": "09:00:00"},
        "advance_discharge_period": {"units": "h", "val": 1},
        "delay_charge_period": {"units": "h", "val": 1},
        "allow_charge_in_peak_range": True,
        "demand_profile_upstream": None,
        "dispatch_priority_demand_profile": "demand_profile",
        "min_peak_proximity": {"units": "h", "val": 4},
    }

    tech_config["technologies"]["h2_storage"]["control_strategy"]["model"] = (
        "PeakLoadManagementHeuristicOpenLoopStorageController"
    )

    plant_config = plant_config_base
    plant_config["plant"]["simulation"]["n_timesteps"] = 12

    prob = om.Problem()

    prob.model.add_subsystem(
        name="IVC",
        subsys=om.IndepVarComp(name="hydrogen_in", val=20, shape=12),
        promotes=["*"],
    )

    prob.model.add_subsystem(
        "plm_controller",
        PeakLoadManagementHeuristicOpenLoopStorageController(
            plant_config=plant_config, tech_config=tech_config["technologies"]["h2_storage"]
        ),
        promotes=["*"],
    )

    prob.model.add_subsystem(
        "storage",
        StoragePerformanceModel(
            plant_config=plant_config, tech_config=tech_config["technologies"]["h2_storage"]
        ),
        promotes=["*"],
    )

    prob.setup()
    prob.run_model()

    soc = prob.get_val("SOC", units="unitless")
    min_soc = 0.15
    max_soc = 0.95

    with subtests.test("SOC never exceeds maximum"):
        assert np.all(soc <= max_soc + 1e-6)

    with subtests.test("SOC never falls below minimum"):
        assert np.all(soc >= min_soc - 1e-6)


@pytest.mark.regression
def test_plm_controller_blocking_charge_in_peak_range(
    subtests, tech_config_base, plant_config_base
):
    """Test PLM controller blocks charging during peak window when configured."""
    tech_config = tech_config_base

    peak_window_start = "10:00:00"
    peak_window_end = "14:00:00"

    tech_config["technologies"]["h2_storage"]["model_inputs"]["shared_parameters"] = {
        "commodity": "hydrogen",
        "commodity_rate_units": "kg/h",
        "max_capacity": 80.0,
        "max_soc_fraction": 1.0,
        "min_soc_fraction": 0.05,
        "init_soc_fraction": 0.3,
        "max_charge_rate": 15.0,
        "max_discharge_rate": 25.0,
        "charge_equals_discharge": False,
        "charge_efficiency": 0.92,
        "discharge_efficiency": 0.92,
        "demand_profile": np.full(24, 5.0),
        "demand_profile_upstream": None,
        "peak_range": {"start": peak_window_start, "end": peak_window_end},
        "advance_discharge_period": {"units": "h", "val": 3},
        "delay_charge_period": {"units": "h", "val": 1},
        "allow_charge_in_peak_range": False,  # Block charging in peak window
        "dispatch_priority_demand_profile": "demand_profile",
        "min_peak_proximity": {"units": "h", "val": 4},
    }

    tech_config["technologies"]["h2_storage"]["control_strategy"]["model"] = (
        "PeakLoadManagementHeuristicOpenLoopStorageController"
    )

    plant_config = plant_config_base

    prob = om.Problem()

    prob.model.add_subsystem(
        name="IVC",
        subsys=om.IndepVarComp(name="hydrogen_in", val=40.0, shape=24),
        promotes=["*"],
    )

    prob.model.add_subsystem(
        "plm_controller",
        PeakLoadManagementHeuristicOpenLoopStorageController(
            plant_config=plant_config, tech_config=tech_config["technologies"]["h2_storage"]
        ),
        promotes=["*"],
    )

    prob.model.add_subsystem(
        "storage",
        StoragePerformanceModel(
            plant_config=plant_config, tech_config=tech_config["technologies"]["h2_storage"]
        ),
        promotes=["*"],
    )

    prob.setup()
    prob.run_model()

    set_point = prob.get_val("hydrogen_set_point", units="kg/h")
    soc = prob.get_val("SOC", units="unitless")

    with subtests.test("Controller instantiates and runs without error"):
        assert len(set_point) == 24
        assert len(soc) == 24

    with subtests.test("Initial discharge phase occurs before peak window"):
        # Hours 7-9 are before the peak window (10-14)
        # Some discharge should occur
        assert any(set_point[7:10] > 1.0)

    with subtests.test("SOC is lower after peak window than before"):
        # After discharge and attempted peak meeting, SOC should be lower
        assert soc[14] < soc[6]


@pytest.mark.regression
def test_plm_controller_warns_when_requested_charge_exceeds_input(
    tech_config_base, plant_config_base
):
    """Warn when controller asks to charge faster than available commodity input."""
    tech_config = tech_config_base

    tech_config["technologies"]["h2_storage"]["model_inputs"]["shared_parameters"] = {
        "commodity": "hydrogen",
        "commodity_rate_units": "kg/h",
        "max_capacity": 100.0,
        "max_soc_fraction": 1.0,
        "min_soc_fraction": 0.1,
        "init_soc_fraction": 0.2,
        "max_charge_rate": 25.0,
        "max_discharge_rate": 25.0,
        "charge_equals_discharge": False,
        "charge_efficiency": 0.95,
        "discharge_efficiency": 0.95,
        "demand_profile": np.full(24, 1.0),
        "demand_profile_upstream": None,
        "peak_range": {"start": "23:00:00", "end": "23:59:59"},
        "advance_discharge_period": {"units": "h", "val": 1},
        "delay_charge_period": {"units": "h", "val": 1},
        "allow_charge_in_peak_range": True,
        "dispatch_priority_demand_profile": "demand_profile",
        "min_peak_proximity": {"units": "h", "val": 4},
    }

    tech_config["technologies"]["h2_storage"]["control_strategy"]["model"] = (
        "PeakLoadManagementHeuristicOpenLoopStorageController"
    )

    plant_config = plant_config_base

    prob = om.Problem()

    # Keep available input intentionally low so requested charging exceeds it.
    prob.model.add_subsystem(
        name="IVC",
        subsys=om.IndepVarComp(name="hydrogen_in", val=np.full(24, 1.0), units="kg/h"),
        promotes=["*"],
    )

    prob.model.add_subsystem(
        "plm_controller",
        PeakLoadManagementHeuristicOpenLoopStorageController(
            plant_config=plant_config, tech_config=tech_config["technologies"]["h2_storage"]
        ),
        promotes=["*"],
    )

    prob.setup()

    with pytest.warns(UserWarning, match="WARNING: At time step index 1, requested charging rate"):
        prob.run_model()
