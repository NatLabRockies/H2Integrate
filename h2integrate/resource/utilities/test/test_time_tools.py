import numpy as np
import pandas as pd
import pytest

from h2integrate.resource.utilities.time_tools import (
    is_leap_year,
    process_leap_day,
    check_data_length,
    contains_leap_day,
    resample_resource_data_to_dt,
    get_n_timesteps_from_year_list,
    get_number_of_resource_years_needed,
)


def _february_boundary_data(year, include_february_29):
    """Create daily resource data from February 28 to March 1, optionally including February 29."""
    if include_february_29:
        dates = pd.date_range(f"{year}-02-28", f"{year}-03-01", freq="1D")
    else:
        dates = pd.DatetimeIndex([pd.Timestamp(f"{year}-02-28"), pd.Timestamp(f"{year}-03-01")])

    return {
        "year": dates.year.to_numpy().astype(float),
        "month": dates.month.to_numpy().astype(float),
        "day": dates.day.to_numpy().astype(float),
        "ws": np.arange(len(dates), dtype=float),
    }


@pytest.mark.unit
@pytest.mark.parametrize(
    "year,expected",
    [(2012, True), (2000, True), (2014, False), (1900, False)],
    ids=["leap-year", "leap-century", "common-year", "common-century"],
)
def test_is_leap_year(year, expected):
    assert is_leap_year(year) is expected


@pytest.mark.unit
@pytest.mark.parametrize(
    "data,expected",
    [
        pytest.param(
            _february_boundary_data(2012, include_february_29=True), True, id="lowercase-dict"
        ),
        pytest.param(
            pd.DataFrame({"Month": [2, 3], "Day": [28, 1]}), False, id="uppercase-dataframe"
        ),
        pytest.param({"month": [1, 1], "day": [1, 2]}, False, id="no-february"),
    ],
)
def test_contains_leap_day(data, expected):
    assert contains_leap_day(data) == expected


@pytest.mark.unit
def test_check_data_length(subtests):
    data = _february_boundary_data(2013, include_february_29=False)
    check_data_length(data, n_timesteps=2)

    with subtests.test("uppercase dataframe has the expected length"):
        dataframe = pd.DataFrame({"Month": [2, 3], "Day": [28, 1], "ws": [0.0, 1.0]})
        check_data_length(dataframe, n_timesteps=2)

    with subtests.test("partial data without February has the expected length"):
        january_data = {"month": [1, 1], "day": [1, 1], "ws": [0.0, 1.0]}
        check_data_length(january_data, n_timesteps=2)

    with subtests.test("length mismatch without a leap day"):
        with pytest.raises(ValueError, match="Resource data is not the same length"):
            check_data_length(data, n_timesteps=3)

    with subtests.test("length mismatch identifies leap-day data"):
        leap_day_data = _february_boundary_data(2012, include_february_29=True)
        with pytest.raises(ValueError) as excinfo:
            check_data_length(leap_day_data, n_timesteps=2)
        assert "includes a leap day" in str(excinfo.value)
        assert "include_leap_day" in str(excinfo.value)


@pytest.mark.unit
@pytest.mark.parametrize(
    "dt,year_list,include_leap,expected",
    [
        (3600, [2019, 2020], False, 17520),
        (3600, [2019, 2020], True, 17544),
        (1800, ["tmy-2020", "tmy-2021"], True, 35040),
    ],
)
def test_get_n_timesteps_from_year_list(dt, year_list, include_leap, expected):
    assert get_n_timesteps_from_year_list(dt, year_list, include_leap) == expected


@pytest.mark.unit
@pytest.mark.parametrize(
    "year,has_february_29,include_leap_day,expected_days",
    [
        pytest.param(2012, True, False, [28, 1], id="remove-leap-day"),
        pytest.param(2012, True, True, [28, 29, 1], id="keep-leap-day"),
        pytest.param(2013, False, False, [28, 1], id="common-year-exclude"),
        pytest.param(2013, False, True, [28, 1], id="common-year-include"),
    ],
)
def test_process_leap_day(year, has_february_29, include_leap_day, expected_days):
    data = _february_boundary_data(year, include_february_29=has_february_29)
    result = process_leap_day(data, include_leap_day=include_leap_day)

    np.testing.assert_array_equal(result["day"], expected_days)


@pytest.mark.unit
def test_process_leap_day_without_february():
    data = {"month": np.array([1, 1]), "day": np.array([1, 2]), "ws": np.array([0.0, 1.0])}
    result = process_leap_day(data, include_leap_day=False)

    np.testing.assert_array_equal(result["day"], [1, 2])


@pytest.mark.unit
def _make_timeseries(n, freq_seconds, start="2012-01-01 00:00", values=None):
    """Build a resource data dict with time columns spaced at ``freq_seconds``."""

    idx = pd.date_range(start=start, periods=n, freq=pd.Timedelta(seconds=freq_seconds))
    if values is None:
        values = np.arange(n, dtype=float)
    return {
        "wind_speed_100m": np.asarray(values, dtype=float),
        "year": idx.year.to_numpy().astype(float),
        "month": idx.month.to_numpy().astype(float),
        "day": idx.day.to_numpy().astype(float),
        "hour": idx.hour.to_numpy().astype(float),
        "minute": idx.minute.to_numpy().astype(float),
        "units": {"wind_speed_100m": "m/s"},
        "site_lat": 1.0,
    }


@pytest.mark.unit
def test_resample_no_op_when_dt_matches():
    data = _make_timeseries(10, 3600)
    result = resample_resource_data_to_dt(data, 3600)
    assert result is data


@pytest.mark.unit
def test_resample_no_time_columns_raises():
    data = {"wind_speed_100m": np.arange(10, dtype=float), "site_lat": 1.0}
    with pytest.raises(ValueError, match="no time columns"):
        resample_resource_data_to_dt(data, 1800)


@pytest.mark.unit
def test_resample_target_dt_larger_than_span_raises():
    # 5 hourly samples span only a few hours; a 10-day timestep yields no full step
    data = _make_timeseries(5, 3600)
    with pytest.raises(ValueError, match="larger than the total time span"):
        resample_resource_data_to_dt(data, 10 * 86400)


@pytest.mark.unit
def test_resample_non_increasing_timestamps_raises():
    # The first two timestamps are identical, so the native timestep is non-positive
    data = {
        "wind_speed_100m": np.arange(3, dtype=float),
        "year": np.array([2012, 2012, 2012], dtype=float),
        "month": np.array([1, 1, 1], dtype=float),
        "day": np.array([1, 1, 1], dtype=float),
        "hour": np.array([0, 0, 1], dtype=float),
        "minute": np.array([0, 0, 0], dtype=float),
    }
    with pytest.raises(ValueError, match="non-positive"):
        resample_resource_data_to_dt(data, 1800)


@pytest.mark.unit
def test_upsample_interpolation(subtests):
    # hourly data upsampled to 30-minute resolution
    data = _make_timeseries(5, 3600, values=[0, 1, 2, 3, 4])
    result = resample_resource_data_to_dt(data, 1800, upsample_method="time")

    with subtests.test("upsampled length doubles"):
        assert len(result["wind_speed_100m"]) == 10
    expected = np.array([0, 0.5, 1, 1.5, 2, 2.5, 3, 3.5, 4, 4], dtype=float)
    with subtests.test("interpolated values match expectation"):
        np.testing.assert_allclose(result["wind_speed_100m"], expected)
    with subtests.test("minutes alternate on 30 minute grid"):
        np.testing.assert_array_equal(result["minute"][:4], [0, 30, 0, 30])


@pytest.mark.unit
def test_downsample_average(subtests):
    # 30-minute data downsampled to hourly resolution via pandas mean aggregation
    data = _make_timeseries(10, 1800, values=[0, 1, 2, 3, 4, 5, 6, 7, 8, 9])
    result = resample_resource_data_to_dt(data, 3600, downsample_method="mean")

    with subtests.test("downsampled length halves"):
        assert len(result["wind_speed_100m"]) == 5
    expected = np.array([0.5, 2.5, 4.5, 6.5, 8.5], dtype=float)
    with subtests.test("hourly means match expectation"):
        np.testing.assert_allclose(result["wind_speed_100m"], expected)
    with subtests.test("minutes stay on hour"):
        np.testing.assert_array_equal(result["minute"], np.zeros(5))


@pytest.mark.unit
def test_resample_keeps_leap_day_excluded_at_new_timestep(subtests):
    # Hourly data for a leap year with the leap day removed, resampled to 2-hour.
    # February 29 must stay excluded in the regenerated calendar at the new timestep.

    idx = pd.date_range("2012-01-01 00:30", "2012-12-31 23:30", freq="1h")
    idx = idx[~((idx.month == 2) & (idx.day == 29))]  # 8760 hourly, leap day removed
    data = {
        "wind_speed_100m": np.arange(len(idx), dtype=float),
        "year": idx.year.to_numpy().astype(float),
        "month": idx.month.to_numpy().astype(float),
        "day": idx.day.to_numpy().astype(float),
        "hour": idx.hour.to_numpy().astype(float),
        "minute": idx.minute.to_numpy().astype(float),
    }

    result = resample_resource_data_to_dt(data, 7200, downsample_method="mean")  # 2-hour timestep

    with subtests.test("result length matches excluded leap year at 2 hour dt"):
        assert len(result["wind_speed_100m"]) == 4380
    with subtests.test("february 29 remains excluded"):
        assert not ((result["month"] == 2) & (result["day"] == 29)).any()
    with subtests.test("starts on january 1"):
        assert int(result["month"][0]) == 1 and int(result["day"][0]) == 1
    with subtests.test("ends on december 31"):
        assert int(result["month"][-1]) == 12 and int(result["day"][-1]) == 31


@pytest.mark.unit
def test_resample_keeps_leap_day_when_present_at_new_timestep(subtests):
    # Leap year with the leap day retained, resampled to 2-hour: Feb 29 must remain.

    idx = pd.date_range("2012-01-01 00:30", "2012-12-31 23:30", freq="1h")  # 8784, leap kept
    data = {
        "wind_speed_100m": np.arange(len(idx), dtype=float),
        "year": idx.year.to_numpy().astype(float),
        "month": idx.month.to_numpy().astype(float),
        "day": idx.day.to_numpy().astype(float),
        "hour": idx.hour.to_numpy().astype(float),
        "minute": idx.minute.to_numpy().astype(float),
    }

    result = resample_resource_data_to_dt(data, 7200, downsample_method="mean")  # 2-hour timestep

    with subtests.test("result length matches leap year at 2 hour dt"):
        assert len(result["wind_speed_100m"]) == 4392
    with subtests.test("leap day remains present"):
        assert ((result["month"] == 2) & (result["day"] == 29)).any()


@pytest.mark.unit
def test_downsample_preserves_mean():
    rng = np.random.default_rng(0)
    values = rng.random(24)
    data = _make_timeseries(24, 900, values=values)  # 15-min data
    result = resample_resource_data_to_dt(data, 3600, downsample_method="mean")  # hourly

    assert len(result["wind_speed_100m"]) == 6
    # overall mean is conserved by the averaging
    np.testing.assert_allclose(result["wind_speed_100m"].mean(), values.mean())


@pytest.mark.unit
def test_downsample_with_calendar_gap_preserves_mean(subtests):
    # Hourly data whose timestamps have a one-day gap in the middle (as when a leap
    # day is removed). Resampling must treat the samples as an evenly spaced sequence,
    # so the downsampled mean matches the exact pairwise mean.

    part1 = pd.date_range("2012-02-28 00:30", periods=4, freq="1h")
    part2 = pd.date_range("2012-03-01 00:30", periods=4, freq="1h")
    idx = part1.append(part2)
    values = np.arange(8, dtype=float)
    data = {
        "wind_speed_100m": values.copy(),
        "year": idx.year.to_numpy().astype(float),
        "month": idx.month.to_numpy().astype(float),
        "day": idx.day.to_numpy().astype(float),
        "hour": idx.hour.to_numpy().astype(float),
        "minute": idx.minute.to_numpy().astype(float),
    }
    result = resample_resource_data_to_dt(data, 7200, downsample_method="mean")  # to 2-hour

    with subtests.test("downsampled length matches expected bins"):
        assert len(result["wind_speed_100m"]) == 4
    with subtests.test("pairwise averages preserved across gap"):
        np.testing.assert_allclose(result["wind_speed_100m"], [0.5, 2.5, 4.5, 6.5])
    with subtests.test("mean preserved despite gap"):
        np.testing.assert_allclose(result["wind_speed_100m"].mean(), values.mean())


@pytest.mark.unit
def test_resample_scalar_metadata_preserved(subtests):
    data = _make_timeseries(5, 3600, values=[0, 1, 2, 3, 4])
    result = resample_resource_data_to_dt(data, 1800, upsample_method="time")
    with subtests.test("units preserved"):
        assert result["units"] == {"wind_speed_100m": "m/s"}
    with subtests.test("site latitude preserved"):
        assert result["site_lat"] == 1.0


@pytest.mark.unit
def test_resample_unknown_upsample_method_raises():
    data = _make_timeseries(5, 3600)
    # An invalid pandas interpolation method raises. The exact message differs across
    # pandas versions, but the offending method name is always reported.
    with pytest.raises(ValueError, match="not_a_method"):
        resample_resource_data_to_dt(data, 1800, upsample_method="not_a_method")


@pytest.mark.unit
def test_resample_unknown_downsample_method_raises():
    data = _make_timeseries(10, 1800)
    # An invalid pandas aggregation raises. Different pandas versions raise different
    # exception types (AttributeError vs ValueError) with different messages, so match
    # on the offending method name that is common to all versions.
    with pytest.raises((AttributeError, ValueError), match="not_a_method"):
        resample_resource_data_to_dt(data, 3600, downsample_method="not_a_method")


@pytest.mark.unit
def test_resample_upsampling_without_method_raises():
    # A finer sim dt than the native timestep needs upsampling; without an explicit method
    # resampling must raise an error.
    data = _make_timeseries(5, 3600)
    with pytest.raises(ValueError, match="requires upsampling"):
        resample_resource_data_to_dt(data, 1800)


@pytest.mark.unit
def test_resample_downsampling_without_method_raises():
    # A coarser sim dt than the native timestep needs downsampling; without an explicit
    # method resampling must raise an error.
    data = _make_timeseries(10, 1800)
    with pytest.raises(ValueError, match="requires downsampling"):
        resample_resource_data_to_dt(data, 3600)


@pytest.mark.unit
def test_resample_warns_when_resampling(subtests):
    # Resampling notifies the user (but does not block) so the timestep change is visible.
    with subtests.test("upsampling warns"):
        with pytest.warns(UserWarning, match="upsampling"):
            resample_resource_data_to_dt(_make_timeseries(5, 3600), 1800, upsample_method="time")
    with subtests.test("downsampling warns"):
        with pytest.warns(UserWarning, match="downsampling"):
            resample_resource_data_to_dt(_make_timeseries(10, 1800), 3600, downsample_method="mean")


@pytest.mark.unit
@pytest.mark.parametrize(
    "n_timesteps,include_leap,expected_years",
    [
        pytest.param(8760 * 4, False, 4, id="four-years-without-leap-days"),
        pytest.param(8760 * 10, False, 10, id="ten-years-without-leap-days"),
        pytest.param(2920, False, 1, id="third-year-without-leap-days"),
        pytest.param(2920, True, 1, id="third-year-with-leap-days"),
        pytest.param(21900, False, 3, id="two-and-a-half-years"),
        pytest.param(8808, True, 2, id="one-year-plus-one-leap-day"),
        pytest.param(17544, True, 2, id="two-years-with-one-leap-day"),
        pytest.param(17520, True, 2, id="two-years-without-leap-days"),
    ],
)
def test_get_number_of_resource_years_needed(n_timesteps, include_leap, expected_years):
    assert get_number_of_resource_years_needed(3600, n_timesteps, include_leap) == expected_years
