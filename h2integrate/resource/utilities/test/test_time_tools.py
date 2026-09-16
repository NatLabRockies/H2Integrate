"""Tests for the resource conform/concatenate helpers in ``time_tools``."""

import numpy as np
import pandas as pd
import pytest

from h2integrate.resource.utilities.time_tools import (
    process_leap_day,
    concatenate_resource_years,
    resample_resource_data_to_dt,
    conform_resource_data_to_n_timesteps,
)


def _feb_mar_days(year, include_feb29):
    """Build a small daily resource dict spanning Feb 28 - Mar 1 for ``year``."""

    if include_feb29:
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
def test_leap_day_removed_when_not_wanted(subtests):
    result = process_leap_day(_feb_mar_days(2012, include_feb29=True), include_leap_day=False)
    with subtests.test("leap day removed"):
        assert 29 not in result["day"].astype(int)
    with subtests.test("length reduced to two days"):
        assert len(result["day"]) == 2


@pytest.mark.unit
def test_no_leap_day_unchanged_when_not_wanted():
    data = _feb_mar_days(2013, include_feb29=False)
    result = process_leap_day(data, include_leap_day=False)
    assert len(result["day"]) == 2


@pytest.mark.unit
def test_leap_day_kept_when_wanted(subtests):
    result = process_leap_day(_feb_mar_days(2012, include_feb29=True), include_leap_day=True)
    with subtests.test("leap day retained"):
        assert 29 in result["day"].astype(int)
    with subtests.test("length remains three days"):
        assert len(result["day"]) == 3


@pytest.mark.unit
def test_missing_leap_day_in_leap_year_raises_when_wanted():
    data = _feb_mar_days(2012, include_feb29=False)  # 2012 is a leap year
    with pytest.raises(ValueError, match="does not contain a leap day"):
        process_leap_day(data, include_leap_day=True)


@pytest.mark.unit
def test_non_leap_year_no_error_when_wanted():
    data = _feb_mar_days(2013, include_feb29=False)  # 2013 is not a leap year
    result = process_leap_day(data, include_leap_day=True)
    assert len(result["day"]) == 2


def _make_annual_data(native_len=8760, year=2012):
    """Build a minimal one-year resource data dictionary for testing."""
    index = np.arange(native_len)
    hours = index % 24
    days = (index // 24) % 28 + 1
    months = (index // (24 * 28)) % 12 + 1
    return {
        "wind_speed_100m": index.astype(float),
        "temperature_2m": (index * 0.1).astype(float),
        "year": np.full(native_len, float(year)),
        "month": months.astype(float),
        "day": days.astype(float),
        "hour": hours.astype(float),
        "minute": np.zeros(native_len),
        # scalar metadata that must be preserved unchanged
        "site_lat": 35.2,
        "site_lon": -101.9,
        "units": {"wind_speed_100m": "m/s"},
        "filepath": "dummy.csv",
    }


@pytest.mark.unit
def test_no_op_when_length_matches():
    data = _make_annual_data(8760)
    result = conform_resource_data_to_n_timesteps(data, 8760)
    assert result is data


@pytest.mark.unit
def test_slices_for_sub_annual_horizon(subtests):
    data = _make_annual_data(8760)
    result = conform_resource_data_to_n_timesteps(data, 4380)

    with subtests.test("wind length matches horizon"):
        assert len(result["wind_speed_100m"]) == 4380
    with subtests.test("temperature length matches horizon"):
        assert len(result["temperature_2m"]) == 4380
    with subtests.test("wind values are sliced from the front"):
        np.testing.assert_array_equal(result["wind_speed_100m"], np.arange(4380, dtype=float))


@pytest.mark.unit
def test_slices_multiyear_data_down_to_horizon():
    # Two real years concatenated (17520) sliced to a slightly shorter horizon
    data = _make_annual_data(2 * 8760)
    result = conform_resource_data_to_n_timesteps(data, 2 * 8760 - 240)

    assert len(result["wind_speed_100m"]) == 2 * 8760 - 240


@pytest.mark.unit
def test_raises_when_not_enough_data():
    data = _make_annual_data(8760)
    with pytest.raises(ValueError, match="Not enough resource data"):
        conform_resource_data_to_n_timesteps(data, 2 * 8760)


@pytest.mark.unit
def test_scalar_metadata_preserved(subtests):
    data = _make_annual_data(8760)
    result = conform_resource_data_to_n_timesteps(data, 4380)

    with subtests.test("site latitude preserved"):
        assert result["site_lat"] == 35.2
    with subtests.test("site longitude preserved"):
        assert result["site_lon"] == -101.9
    with subtests.test("units preserved"):
        assert result["units"] == {"wind_speed_100m": "m/s"}
    with subtests.test("filepath preserved"):
        assert result["filepath"] == "dummy.csv"


@pytest.mark.unit
def test_returns_input_when_n_timesteps_is_none():
    data = _make_annual_data(8760)
    assert conform_resource_data_to_n_timesteps(data, None) is data


@pytest.mark.unit
def test_infers_length_without_time_columns(subtests):
    data = {
        "wind_speed_100m": np.arange(10, dtype=float),
        "temperature_2m": np.arange(10, dtype=float),
        "site_lat": 1.0,
    }
    result = conform_resource_data_to_n_timesteps(data, 5)

    with subtests.test("wind length inferred and sliced"):
        assert len(result["wind_speed_100m"]) == 5
    with subtests.test("temperature length inferred and sliced"):
        assert len(result["temperature_2m"]) == 5
    with subtests.test("scalar metadata preserved"):
        assert result["site_lat"] == 1.0


@pytest.mark.unit
def test_concatenate_single_year_is_passthrough():
    data = _make_annual_data(8760)
    assert concatenate_resource_years([data]) is data


@pytest.mark.unit
def test_concatenate_multiple_years_combines_timeseries(subtests):
    year1 = _make_annual_data(8760, year=2012)
    year2 = _make_annual_data(8760, year=2013)
    combined = concatenate_resource_years([year1, year2])

    with subtests.test("combined wind length"):
        assert len(combined["wind_speed_100m"]) == 2 * 8760
    with subtests.test("second year values appended in order"):
        np.testing.assert_array_equal(combined["wind_speed_100m"][8760:], year2["wind_speed_100m"])
    with subtests.test("scalar metadata comes from first year"):
        assert combined["units"] == {"wind_speed_100m": "m/s"}


@pytest.mark.unit
def test_concatenate_leap_removed_preserves_real_timestamps_minus_feb29(subtests):
    # With the leap day removed, the concatenated timestamps must match the real
    # downloaded calendar with only February 29 missing -- every other timestamp is
    # preserved, and the series stays strictly increasing across the year boundary.

    def _real_year(year, remove_leap=False):
        idx = pd.date_range(f"{year}-01-01 00:30", f"{year}-12-31 23:30", freq="1h")
        if remove_leap:
            idx = idx[~((idx.month == 2) & (idx.day == 29))]
        data = {
            "wind_speed_100m": np.arange(len(idx), dtype=float),
            "year": idx.year.to_numpy().astype(float),
            "month": idx.month.to_numpy().astype(float),
            "day": idx.day.to_numpy().astype(float),
            "hour": idx.hour.to_numpy().astype(float),
            "minute": idx.minute.to_numpy().astype(float),
        }
        return data, idx

    y2012, idx2012 = _real_year(2012, remove_leap=True)  # leap year, leap day removed -> 8760
    y2013, idx2013 = _real_year(2013)  # non-leap -> 8760
    combined = concatenate_resource_years([y2012, y2013])

    result = pd.to_datetime(
        {k: combined[k].astype(int) for k in ("year", "month", "day", "hour", "minute")}
    )
    expected = idx2012.append(idx2013)

    with subtests.test("timestamps match downloaded calendar except feb 29"):
        np.testing.assert_array_equal(result.to_numpy(), expected.to_numpy())
    with subtests.test("february 29 removed"):
        assert not (
            (combined["month"] == 2) & (combined["day"] == 29) & (combined["year"] == 2012)
        ).any()
    with subtests.test("timestamps remain strictly increasing"):
        assert (result.diff().dropna() > pd.Timedelta(0)).all()


@pytest.mark.unit
def test_concatenate_mixed_leap_and_non_leap_years_preserves_all_data(subtests):
    # A leap year (leap day retained, 8784 hourly) followed by a non-leap year (8760).
    leap = _make_annual_data(8784, year=2012)
    non_leap = _make_annual_data(8760, year=2013)
    combined = concatenate_resource_years([leap, non_leap])

    with subtests.test("combined length preserves both years"):
        assert len(combined["wind_speed_100m"]) == 8784 + 8760
    with subtests.test("leap year values preserved"):
        np.testing.assert_array_equal(combined["wind_speed_100m"][:8784], leap["wind_speed_100m"])
    with subtests.test("non leap year values preserved"):
        np.testing.assert_array_equal(
            combined["wind_speed_100m"][8784:], non_leap["wind_speed_100m"]
        )


@pytest.mark.unit
def test_concatenate_non_leap_then_leap_preserves_all_data(subtests):
    # Order reversed: non-leap year first, then a leap year with the leap day retained.
    non_leap = _make_annual_data(8760, year=2013)
    leap = _make_annual_data(8784, year=2016)
    combined = concatenate_resource_years([non_leap, leap])

    with subtests.test("combined length preserves both years"):
        assert len(combined["wind_speed_100m"]) == 8760 + 8784
    with subtests.test("non leap year values preserved"):
        np.testing.assert_array_equal(
            combined["wind_speed_100m"][:8760], non_leap["wind_speed_100m"]
        )
    with subtests.test("leap year values preserved"):
        np.testing.assert_array_equal(combined["wind_speed_100m"][8760:], leap["wind_speed_100m"])


@pytest.mark.unit
def test_concatenate_leap_kept_timestamps_match_real_calendar(subtests):
    # When the leap day is retained the yearly data is contiguous real calendar, so the
    # concatenated (rebuilt) time columns must reproduce the real calendar exactly.

    def _year(year):
        idx = pd.date_range(f"{year}-01-01 00:30", f"{year}-12-31 23:30", freq="1h")
        return {
            "wind_speed_100m": np.arange(len(idx), dtype=float),
            "year": idx.year.to_numpy().astype(float),
            "month": idx.month.to_numpy().astype(float),
            "day": idx.day.to_numpy().astype(float),
            "hour": idx.hour.to_numpy().astype(float),
            "minute": idx.minute.to_numpy().astype(float),
        }

    combined = concatenate_resource_years([_year(2012), _year(2013)])  # leap kept, then non-leap

    rebuilt = pd.to_datetime(
        {k: combined[k].astype(int) for k in ("year", "month", "day", "hour", "minute")}
    ).to_numpy()
    real = pd.date_range("2012-01-01 00:30", "2013-12-31 23:30", freq="1h").to_numpy()

    with subtests.test("rebuilt length matches combined years"):
        assert len(rebuilt) == 8784 + 8760
    with subtests.test("timestamps match real calendar"):
        np.testing.assert_array_equal(rebuilt, real)
    with subtests.test("retained leap day remains present"):
        assert bool(
            ((combined["month"] == 2) & (combined["day"] == 29) & (combined["year"] == 2012)).any()
        )


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
    result = resample_resource_data_to_dt(data, 1800)

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
    result = resample_resource_data_to_dt(data, 3600)

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

    result = resample_resource_data_to_dt(data, 7200)  # 2-hour timestep

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

    result = resample_resource_data_to_dt(data, 7200)  # 2-hour timestep

    with subtests.test("result length matches leap year at 2 hour dt"):
        assert len(result["wind_speed_100m"]) == 4392
    with subtests.test("leap day remains present"):
        assert ((result["month"] == 2) & (result["day"] == 29)).any()


@pytest.mark.unit
def test_downsample_preserves_mean():
    rng = np.random.default_rng(0)
    values = rng.random(24)
    data = _make_timeseries(24, 900, values=values)  # 15-min data
    result = resample_resource_data_to_dt(data, 3600)  # hourly

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
    result = resample_resource_data_to_dt(data, 7200)  # to 2-hour

    with subtests.test("downsampled length matches expected bins"):
        assert len(result["wind_speed_100m"]) == 4
    with subtests.test("pairwise averages preserved across gap"):
        np.testing.assert_allclose(result["wind_speed_100m"], [0.5, 2.5, 4.5, 6.5])
    with subtests.test("mean preserved despite gap"):
        np.testing.assert_allclose(result["wind_speed_100m"].mean(), values.mean())


@pytest.mark.unit
def test_resample_scalar_metadata_preserved(subtests):
    data = _make_timeseries(5, 3600, values=[0, 1, 2, 3, 4])
    result = resample_resource_data_to_dt(data, 1800)
    with subtests.test("units preserved"):
        assert result["units"] == {"wind_speed_100m": "m/s"}
    with subtests.test("site latitude preserved"):
        assert result["site_lat"] == 1.0


@pytest.mark.unit
def test_resample_unknown_upsample_method_raises():
    data = _make_timeseries(5, 3600)
    # an invalid pandas interpolation method raises
    with pytest.raises(ValueError, match="method must be one of"):
        resample_resource_data_to_dt(data, 1800, upsample_method="not_a_method")


@pytest.mark.unit
def test_resample_unknown_downsample_method_raises():
    data = _make_timeseries(10, 1800)
    # an invalid pandas aggregation raises
    with pytest.raises(AttributeError, match="is not a valid function"):
        resample_resource_data_to_dt(data, 3600, downsample_method="not_a_method")
