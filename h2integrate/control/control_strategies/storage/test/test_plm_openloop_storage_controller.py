from types import SimpleNamespace
from pathlib import Path
from datetime import time

import numpy as np
import pandas as pd
import pytest

from h2integrate.control.control_strategies.storage.plm_openloop_storage_controller import (
    PeakLoadManagementOpenLoopStorageController,
)


def _controller_without_setup():
    """Create a controller instance for testing pure helper methods."""
    return object.__new__(PeakLoadManagementOpenLoopStorageController)


@pytest.mark.unit
def test_get_peaks_daily_expected_peaks():
    controller = _controller_without_setup()

    demand_profile = {
        "time_date": pd.date_range("2025-01-01", periods=8, freq="6h"),
        "demand": [1.0, 9.0, 3.0, 2.0, 4.0, 5.0, 2.0, 8.0],
    }

    expected_peak_times = [
        pd.Timestamp("2025-01-01 06:00:00"),
        pd.Timestamp("2025-01-02 18:00:00"),
    ]

    peaks = controller.get_peaks(demand_profile)
    actual_peak_times = peaks.loc[peaks["is_peak"], "time_date"].tolist()

    assert actual_peak_times == expected_peak_times


@pytest.mark.unit
def test_get_peaks_with_global_event_limit_expected_peak():
    controller = _controller_without_setup()

    demand_profile = {
        "time_date": pd.date_range("2025-01-01", periods=8, freq="6h"),
        "demand": [1.0, 9.0, 3.0, 2.0, 4.0, 5.0, 2.0, 8.0],
    }

    expected_peak_times = [pd.Timestamp("2025-01-01 06:00:00")]

    peaks = controller.get_peaks(demand_profile, n_max_events=1, max_events_period=None)
    actual_peak_times = peaks.loc[peaks["is_peak"], "time_date"].tolist()

    assert actual_peak_times == expected_peak_times


@pytest.mark.unit
def test_get_peaks_with_month_period_expected_peaks():
    controller = _controller_without_setup()

    demand_profile = {
        "time_date": [
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

    peaks = controller.get_peaks(demand_profile, n_max_events=1, max_events_period="M")
    actual_peak_times = peaks.loc[peaks["is_peak"], "time_date"].tolist()

    assert actual_peak_times == expected_peak_times


@pytest.mark.unit
def test_get_peaks_with_month_period_from_csv_expected_peaks():
    controller = _controller_without_setup()
    data_dir = Path(__file__).resolve().parent / "data"
    demand_profile_df = pd.read_csv(data_dir / "lmp_month_1.csv")
    expected_peaks_df = pd.read_csv(data_dir / "lmp_peaks_month_1.csv")

    demand_profile = {
        "time_date": demand_profile_df["time_mountain"].to_list(),
        "demand": demand_profile_df["energy"].to_list(),
    }

    expected_peak_times = pd.to_datetime(expected_peaks_df["time_mountain"]).to_list()

    peaks = controller.get_peaks(demand_profile, n_max_events=10, max_events_period="M")
    actual_peak_times = pd.to_datetime(peaks.loc[peaks["is_peak"], "time_date"]).tolist()

    assert actual_peak_times == expected_peak_times


@pytest.mark.unit
def test_get_peaks_invalid_period_string_raises():
    controller = _controller_without_setup()

    demand_profile = {
        "time_date": pd.date_range("2025-01-01", periods=4, freq="6h"),
        "demand": [1.0, 2.0, 3.0, 4.0],
    }

    with pytest.raises(ValueError, match="Invalid max_events_period string"):
        controller.get_peaks(demand_profile, n_max_events=1, max_events_period="not_a_period")


@pytest.mark.unit
def test_get_peaks_respects_peak_range_12pm_to_5pm():
    controller = _controller_without_setup()

    demand_profile = {
        "time_date": [
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
        peak_range={"start": time(12, 0), "end": time(17, 0)},
    )
    actual_peak_times = peaks.loc[peaks["is_peak"], "time_date"].tolist()

    expected_peak_times = [
        pd.Timestamp("2025-01-01 14:00:00"),
        pd.Timestamp("2025-01-02 13:00:00"),
    ]

    assert actual_peak_times == expected_peak_times


@pytest.mark.unit
def test_get_peaks_invalid_min_proximity_raises():
    controller = _controller_without_setup()

    demand_profile = {
        "time_date": pd.date_range("2025-01-01", periods=10, freq="6h"),
        "demand": [1.0, 2.0, 4.0, 3.0, 3.0, 4.0, 3.0, 2.0, 1.0, 2.0],
    }

    with pytest.raises(ValueError, match="Selected peaks violate min_proximity."):
        controller.get_peaks(
            demand_profile,
            n_max_events=2,
            max_events_period="W",
            min_proximity={"units": "D", "val": 1},
        )


@pytest.mark.unit
def test_merge_peaks_without_supervisor_returns_secondary_flags(subtests):
    secondary_peaks_df = pd.DataFrame(
        {
            "time_date": pd.to_datetime(
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

    merged = PeakLoadManagementOpenLoopStorageController.merge_peaks(None, secondary_peaks_df)

    with subtests.test("peak flags unchanged"):
        assert merged["is_peak"].tolist() == secondary_peaks_df["is_peak"].tolist()


@pytest.mark.unit
def test_merge_peaks_supervisor_takes_precedence_on_same_day(subtests):
    secondary_peaks_df = pd.DataFrame(
        {
            "time_date": pd.to_datetime(
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
    supervisory_peaks_df = pd.DataFrame(
        {
            "time_date": pd.to_datetime(
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

    merged = PeakLoadManagementOpenLoopStorageController.merge_peaks(
        supervisory_peaks_df,
        secondary_peaks_df,
    )

    with subtests.test("day1 follows supervisor flags"):
        np.testing.assert_array_equal(
            merged["is_peak"].iloc[0:2], supervisory_peaks_df["is_peak"].iloc[0:2]
        )

    with subtests.test("day2 follows secondary flags"):
        np.testing.assert_array_equal(
            merged["is_peak"].iloc[2:4],
            secondary_peaks_df["is_peak"].iloc[2:4],
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
            "time_date": times,
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
            "time_date": times,
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
def test_get_allowed_discharge_always_true_when_charge_allowed_in_peak_range():
    """When allow_charge_in_peak_range=True every row should allow charging."""
    controller = _make_controller_with_config(
        allow_charge_in_peak_range=True,
        peak_range={"start": time(12, 0), "end": time(17, 0)},
    )
    controller.peaks_df = pd.DataFrame(
        {
            "time_date": pd.to_datetime(
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

    controller.get_allowed_discharge()

    assert controller.peaks_df["allow_charge"].tolist() == [True, True, True]


@pytest.mark.unit
def test_get_allowed_discharge_blocks_charge_inside_peak_range(subtests):
    """When allow_charge_in_peak_range=False, rows inside the window get allow_charge=False."""
    controller = _make_controller_with_config(
        allow_charge_in_peak_range=False,
        peak_range={"start": time(12, 0), "end": time(17, 0)},
    )
    controller.peaks_df = pd.DataFrame(
        {
            "time_date": pd.to_datetime(
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

    controller.get_allowed_discharge()

    with subtests.test("before range allows charge"):
        assert controller.peaks_df["allow_charge"].iloc[0] is np.True_
    with subtests.test("inside range blocks charge (first)"):
        assert controller.peaks_df["allow_charge"].iloc[1] is np.False_
    with subtests.test("inside range blocks charge (second)"):
        assert controller.peaks_df["allow_charge"].iloc[2] is np.False_
    with subtests.test("after range allows charge"):
        assert controller.peaks_df["allow_charge"].iloc[3] is np.True_
