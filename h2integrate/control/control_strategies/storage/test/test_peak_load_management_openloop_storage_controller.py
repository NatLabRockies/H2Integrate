from pathlib import Path

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
