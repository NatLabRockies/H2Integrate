import numpy as np
import pandas as pd
import pytest

from h2integrate.resource.utilities.time_tools import (
    is_leap_year,
    process_leap_day,
    resample_resource_data_to_dt,
    get_number_of_resource_years_needed,
)


# from h2integrate.resource.utilities.time_tools import (
#     add_resource_start_end_times,
#     get_n_timesteps_from_year_list
# )
# TODO: add test for check_data_length


@pytest.mark.unit
def test_is_leap_year(subtests):
    with subtests.test("2012 is a leap year"):
        assert is_leap_year(2012)
    with subtests.test("2000 is a leap year"):
        assert is_leap_year(2000)
    with subtests.test("2014 is not a leap year"):
        assert not is_leap_year(2014)
    with subtests.test("1900 is not a leap year"):
        assert not is_leap_year(1900)


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
def test_non_leap_year_no_error_when_wanted():
    data = _feb_mar_days(2013, include_feb29=False)  # 2013 is not a leap year
    result = process_leap_day(data, include_leap_day=True)
    assert len(result["day"]) == 2


@pytest.mark.unit
def test_number_of_years_needed_without_leap(subtests):
    dt = 3600
    n_years = get_number_of_resource_years_needed(dt, 8760 * 4, False)
    with subtests.test("4 years without leap"):
        assert n_years == 4

    n_years = get_number_of_resource_years_needed(dt, 8760 * 10, False)
    with subtests.test("10 years without leap"):
        assert n_years == 10

    n_years = get_number_of_resource_years_needed(dt, 8760 * (1 / 3), False)
    with subtests.test("1/3 year without leap"):
        assert n_years == 1

    n_years = get_number_of_resource_years_needed(dt, 8760 * 2.5, False)
    with subtests.test("2.5 year without leap"):
        assert n_years == 3


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
