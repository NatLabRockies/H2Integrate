import numpy as np
import pandas as pd
import pytest

from h2integrate.resource.utilities.time_tools import (
    is_leap_year,
    process_leap_day,
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
