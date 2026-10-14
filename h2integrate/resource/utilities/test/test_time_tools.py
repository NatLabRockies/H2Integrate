import numpy as np
import pandas as pd
import pytest

from h2integrate.resource.utilities.time_tools import (
    is_leap_year,
    process_leap_day,
    check_data_length,
    contains_leap_day,
    add_resource_start_end_times,
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
@pytest.mark.parametrize(
    "freq_seconds",
    [3600, 86_400, 172_800, 259_200],
    ids=["1-hour", "1-day", "2-day", "3-day"],
)
def test_add_resource_start_end_times_reports_dt_in_seconds(subtests, freq_seconds):
    # `timedelta.seconds` drops whole days, so steps of 24 h or more need `total_seconds()`.
    data = _make_timeseries(4, freq_seconds)
    result = add_resource_start_end_times(data)

    with subtests.test("timestep includes whole days in seconds"):
        assert result["dt"] == freq_seconds
    with subtests.test("timestep is an integer"):
        assert isinstance(result["dt"], int)


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
def test_resample_non_positive_deltas_raises():
    # If all deltas are non-positive (e.g. all identical timestamps), raise ValueError
    data = {
        "wind_speed_100m": np.arange(3, dtype=float),
        "year": np.array([2012, 2012, 2012], dtype=float),
        "month": np.array([1, 1, 1], dtype=float),
        "day": np.array([1, 1, 1], dtype=float),
        "hour": np.array([0, 0, 0], dtype=float),
        "minute": np.array([0, 0, 0], dtype=float),
    }
    with pytest.raises(ValueError, match="no positive time steps"):
        resample_resource_data_to_dt(data, 1800)


@pytest.mark.unit
def test_resample_negative_deltas_warns(subtests):
    # Out-of-order years (e.g. 2013 then 2011) produce a negative delta at the transition,
    # which should emit a warning but successfully resample.
    data1 = _make_timeseries(5, 3600, start="2013-01-01 00:00")
    data2 = _make_timeseries(5, 3600, start="2011-01-01 00:00")
    combined = {
        k: np.concatenate([data1[k], data2[k]])
        for k in ["year", "month", "day", "hour", "minute", "wind_speed_100m"]
    }
    with pytest.warns(UserWarning, match="negative time steps"):
        result = resample_resource_data_to_dt(combined, 1800, upsample_method="time")
    with subtests.test("upsampled length is 2x"):
        assert len(result["wind_speed_100m"]) == 20


@pytest.mark.unit
def test_resample_infers_native_dt_across_initial_calendar_gap(subtests):
    # Dataset starting adjacent to a removed leap day (Feb 28 23:00 to Mar 1 00:00).
    # The first delta is 25 hours (90000 s), but subsequent hourly steps are 3600 s.
    # Native dt must infer as 3600 s (not 90000 s).
    idx = pd.DatetimeIndex(
        [
            "2012-02-28 23:00",
            "2012-03-01 00:00",
            "2012-03-01 01:00",
            "2012-03-01 02:00",
            "2012-03-01 03:00",
        ]
    )
    data = {
        "wind_speed_100m": np.arange(len(idx), dtype=float),
        "year": idx.year.to_numpy().astype(float),
        "month": idx.month.to_numpy().astype(float),
        "day": idx.day.to_numpy().astype(float),
        "hour": idx.hour.to_numpy().astype(float),
        "minute": idx.minute.to_numpy().astype(float),
    }
    result = resample_resource_data_to_dt(data, 1800, upsample_method="time")
    with subtests.test("upsampled length doubles based on 3600s native dt"):
        assert len(result["wind_speed_100m"]) == 10
    with subtests.test("timestamps are at 30-minute intervals"):
        assert np.isclose(result["minute"][1] - result["minute"][0], 30.0)


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
def test_downsample_preserves_mean(subtests):
    rng = np.random.default_rng(0)
    values = rng.random(24)
    data = _make_timeseries(24, 900, values=values)  # 15-min data
    result = resample_resource_data_to_dt(data, 3600, downsample_method="mean")  # hourly

    with subtests.test("downsampling produces six hourly values"):
        assert len(result["wind_speed_100m"]) == 6
    with subtests.test("downsampling preserves the overall mean"):
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
    data = _make_timeseries(5, 3600)
    with pytest.raises(ValueError, match="requires upsampling"):
        resample_resource_data_to_dt(data, 1800)


@pytest.mark.unit
def test_resample_downsampling_without_method_raises():
    data = _make_timeseries(10, 1800)
    with pytest.raises(ValueError, match="requires downsampling"):
        resample_resource_data_to_dt(data, 3600)


@pytest.mark.unit
def test_resample_warns_when_resampling(subtests):
    with subtests.test("upsampling warns"):
        with pytest.warns(UserWarning, match="upsampling"):
            resample_resource_data_to_dt(_make_timeseries(5, 3600), 1800, upsample_method="time")
    with subtests.test("downsampling warns"):
        with pytest.warns(UserWarning, match="downsampling"):
            resample_resource_data_to_dt(_make_timeseries(10, 1800), 3600, downsample_method="mean")


@pytest.mark.unit
def test_resample_non_integer_ratio_guarantees_coverage(subtests):
    # Non-integer ratios must not round down and under-cover the original duration.
    with subtests.test("downsampling ceil covers span"):
        # 10 samples at 3600s = 36000s; 36000 / 7000 = 5.14 -> ceil must yield 6 steps, not 5
        data = _make_timeseries(10, 3600)
        res = resample_resource_data_to_dt(data, 7000, downsample_method="mean")
        assert len(res["wind_speed_100m"]) == 6

    with subtests.test("upsampling ceil covers span"):
        # 5 samples at 3600s = 18000s; 18000 / 2500 = 7.2 -> ceil must yield 8 steps, not 7
        data = _make_timeseries(5, 3600)
        res = resample_resource_data_to_dt(data, 2500, upsample_method="time")
        assert len(res["wind_speed_100m"]) == 8


@pytest.mark.unit
@pytest.mark.parametrize(
    "target_dt,expected_steps",
    [(6000.0, 6), (5999.9999999, 7), (6000.1, 6)],
    ids=["exact-division", "tiny-positive-remainder", "fractional-timestep"],
)
def test_resample_step_count_preserves_small_remainders(subtests, target_dt, expected_steps):
    data = _make_timeseries(10, 3600)
    result = resample_resource_data_to_dt(data, target_dt, downsample_method="mean")
    n_steps = len(result["wind_speed_100m"])

    with subtests.test("step count is the ceiling of the duration ratio"):
        assert n_steps == expected_steps
    with subtests.test("target intervals cover the complete source duration"):
        assert n_steps * pd.Timedelta(seconds=target_dt) >= pd.Timedelta(hours=10)


@pytest.mark.unit
def test_resample_non_uniform_deltas(subtests):
    # Non-uniform deltas within a series: 1h and 2h steps.
    # Spacing is proportional to physical duration: 2 steps for 1h, 4 steps for 2h.
    idx = pd.DatetimeIndex(
        [
            "2020-01-01 00:00",
            "2020-01-01 01:00",
            "2020-01-01 03:00",
            "2020-01-01 04:00",
            "2020-01-01 06:00",
        ]
    )
    data = {
        "year": idx.year.to_numpy().astype(float),
        "month": idx.month.to_numpy().astype(float),
        "day": idx.day.to_numpy().astype(float),
        "hour": idx.hour.to_numpy().astype(float),
        "minute": idx.minute.to_numpy().astype(float),
        "val": np.array([0.0, 10.0, 30.0, 40.0, 60.0]),
    }
    res = resample_resource_data_to_dt(data, 1800, upsample_method="time")
    with subtests.test("interpolated length covers 8 hours span at 30 min"):
        assert len(res["val"]) == 16
    with subtests.test("1h interval contains 2 steps and 2h contains 4 steps"):
        # At 30m: 00:00(0), 00:30(5), 01:00(10), 01:30(15), 02:00(20), 02:30(25), 03:00(30)
        np.testing.assert_allclose(res["val"][:3], [0.0, 5.0, 10.0])
        np.testing.assert_allclose(res["val"][2:7], [10.0, 15.0, 20.0, 25.0, 30.0])


@pytest.mark.unit
def test_resample_out_of_order_years_boundary_transition(subtests):
    # Year 1 (2015) followed by Year 2 (2012).
    # Transition across year boundary completes Year 1 using Year 2 first value.
    idx1 = pd.DatetimeIndex(["2015-12-31 22:00", "2015-12-31 23:00"])
    idx2 = pd.DatetimeIndex(["2012-01-01 00:00", "2012-01-01 01:00"])
    idx = idx1.append(idx2)
    data = {
        "year": idx.year.to_numpy().astype(float),
        "month": idx.month.to_numpy().astype(float),
        "day": idx.day.to_numpy().astype(float),
        "hour": idx.hour.to_numpy().astype(float),
        "minute": idx.minute.to_numpy().astype(float),
        "val": np.array([10.0, 20.0, 40.0, 50.0]),
    }
    with pytest.warns(UserWarning, match="negative time steps"):
        res = resample_resource_data_to_dt(data, 1800, upsample_method="time")
    with subtests.test("boundary step interpolates between Year 1 end and Year 2 start"):
        # At t=23:30 (index 3), value must interpolate between 20.0 and 40.0 -> 30.0
        assert res["val"][3] == 30.0
    with subtests.test("regenerated years preserve 2015 then 2012 order"):
        assert (res["year"][:4] == 2015).all()
        assert (res["year"][4:] == 2012).all()


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
