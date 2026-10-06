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


@pytest.mark.unit
def test_contains_leap_day(subtests):
    leap_day_data = _feb_mar_days(2012, include_feb29=True)
    non_leap_day_data = _feb_mar_days(2013, include_feb29=False)

    with subtests.test("lowercase dictionary with leap day"):
        assert contains_leap_day(leap_day_data)

    with subtests.test("uppercase dataframe without leap day"):
        data = pd.DataFrame({"Month": non_leap_day_data["month"], "Day": non_leap_day_data["day"]})
        assert not contains_leap_day(data)

    with subtests.test("partial data without February"):
        assert not contains_leap_day({"month": [1, 1], "day": [1, 2]})


@pytest.mark.unit
def test_check_data_length(subtests):
    data = _feb_mar_days(2013, include_feb29=False)
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
        leap_day_data = _feb_mar_days(2012, include_feb29=True)
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
def test_process_leap_day_without_february():
    data = {"month": np.array([1, 1]), "day": np.array([1, 2]), "ws": np.array([0.0, 1.0])}
    result = process_leap_day(data, include_leap_day=False)

    np.testing.assert_array_equal(result["day"], [1, 2])


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

    n_years = get_number_of_resource_years_needed(dt, 8760 * (1 / 3), True)
    with subtests.test("1/3 year with leap"):
        assert n_years == 1

    n_years = get_number_of_resource_years_needed(dt, 8760 * 2.5, False)
    with subtests.test("2.5 year without leap"):
        assert n_years == 3

    n_years = get_number_of_resource_years_needed(dt, 8808, True)
    with subtests.test("1 year + 1 day year with leap"):
        assert n_years == 2

    n_years = get_number_of_resource_years_needed(dt, 17544, True)
    with subtests.test("2 years (1 is leap)"):
        assert n_years == 2

    n_years = get_number_of_resource_years_needed(dt, 17520, True)
    with subtests.test("2 years (both are leap)"):
        assert n_years == 2
