import numpy as np
import pandas as pd
import pytest

from h2integrate.resource.utilities.time_tools import (
    is_leap_year,
    process_leap_day,
    check_data_length,
    contains_leap_day,
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
