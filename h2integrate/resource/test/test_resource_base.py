"""Unit tests for ``ResourceBaseAPIModel`` multi-year / leap-safe acquisition."""

from types import SimpleNamespace

import numpy as np
import pandas as pd
import pytest

from h2integrate.resource.resource_base import ResourceBaseAPIModel


def _year_data(year, length):
    """Build a synthetic one-year resource data dict with time columns."""
    idx = pd.date_range(f"{year}-01-01 00:00", periods=length, freq="1h")
    return {
        "wind_speed_100m": np.zeros(length, dtype=float),
        "year": idx.year.to_numpy().astype(float),
        "month": idx.month.to_numpy().astype(float),
        "day": idx.day.to_numpy().astype(float),
        "hour": idx.hour.to_numpy().astype(float),
        "minute": idx.minute.to_numpy().astype(float),
        "units": {"wind_speed_100m": "m/s"},
    }


def _fake_model(resource_filename="", resource_year=2012, n_timesteps=8760, year_length=8760):
    """Build a bare model whose per-year loader returns fixed-length synthetic data."""
    model = object.__new__(ResourceBaseAPIModel)
    model.config = SimpleNamespace(resource_filename=resource_filename, resource_year=resource_year)
    model.n_timesteps = n_timesteps

    def _load(latitude, longitude, site_changed, year_filename=None):
        return _year_data(model.config.resource_year, year_length)

    model._load_single_year_data = _load
    return model


@pytest.mark.unit
def test_resource_length():
    data = _year_data(2012, 100)
    assert ResourceBaseAPIModel._resource_length(data) == 100


@pytest.mark.unit
def test_single_year_covers_sub_annual_horizon():
    model = _fake_model(n_timesteps=100, year_length=8760)
    data = model._acquire_resource_data(0.0, 0.0, False)
    # a single year is enough; acquisition returns that one year
    assert ResourceBaseAPIModel._resource_length(data) == 8760


@pytest.mark.unit
def test_loads_multiple_years_until_horizon_covered(subtests):
    model = _fake_model(n_timesteps=2 * 8760, year_length=8760)
    data = model._acquire_resource_data(0.0, 0.0, False)
    with subtests.test("resource length covers both years"):
        assert ResourceBaseAPIModel._resource_length(data) == 2 * 8760
    with subtests.test("resource year restored after acquisition"):
        assert model.config.resource_year == 2012


@pytest.mark.unit
def test_leap_year_single_year_not_split():
    # a retained leap year (8784) covers an 8784-step horizon with a single year
    model = _fake_model(n_timesteps=8784, resource_year=2012, year_length=8784)
    data = model._acquire_resource_data(0.0, 0.0, False)
    assert ResourceBaseAPIModel._resource_length(data) == 8784


@pytest.mark.unit
def test_filename_list_used_in_order():
    model = _fake_model(
        resource_filename=["a.csv", "b.csv"], n_timesteps=2 * 8760, year_length=8760
    )
    data = model._acquire_resource_data(0.0, 0.0, False)
    assert ResourceBaseAPIModel._resource_length(data) == 2 * 8760


@pytest.mark.unit
def test_filename_list_exhausted_raises():
    model = _fake_model(resource_filename=["a.csv"], n_timesteps=2 * 8760, year_length=8760)
    with pytest.raises(ValueError, match="resource file"):
        model._acquire_resource_data(0.0, 0.0, False)


@pytest.mark.unit
def test_single_filename_multiyear_raises():
    model = _fake_model(resource_filename="a.csv", n_timesteps=2 * 8760, year_length=8760)
    with pytest.raises(ValueError, match="cannot satisfy a multi-year"):
        model._acquire_resource_data(0.0, 0.0, False)
