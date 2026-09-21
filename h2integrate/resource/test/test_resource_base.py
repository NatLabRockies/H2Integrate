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

    def _load(latitude, longitude, site_changed, year_filename=None, resource_year=None):
        year = model.config.resource_year if resource_year is None else resource_year
        return _year_data(year, year_length)

    model._load_single_year_data = _load
    return model


class _StubConfig:
    """Model-agnostic stand-in config for exercising base-class acquisition logic.

    The base class does not know about any specific dataset; it only relies on the
    contract that assigning ``resource_year`` runs the config's validator (raising for an
    unsupported year). When ``max_year`` is set this stub mimics that contract by rejecting
    integer years beyond it, so the base class's year-advance handling can be verified
    without depending on a particular resource model. Real per-dataset validators and
    loaders are tested in each resource model's own test module.
    """

    def __init__(self, resource_year, resource_filename="", max_year=None):
        self.resource_filename = resource_filename
        self.max_year = max_year
        self._resource_year = resource_year

    @property
    def resource_year(self):
        return self._resource_year

    @resource_year.setter
    def resource_year(self, value):
        if self.max_year is not None and isinstance(value, int) and value > self.max_year:
            raise ValueError(f"resource_year {value} exceeds supported max {self.max_year}")
        self._resource_year = value


def _fake_model_from_config(config, n_timesteps, year_length=8760):
    """Build a model backed by ``config``, stubbing only the per-year loader.

    The loader records the ``resource_year`` seen on each call so tests can confirm which
    year was used for each load.
    """
    model = object.__new__(ResourceBaseAPIModel)
    model.config = config
    model.n_timesteps = n_timesteps
    model.seen_years = []

    def _load(latitude, longitude, site_changed, year_filename=None, resource_year=None):
        year = model.config.resource_year if resource_year is None else resource_year
        model.seen_years.append(year)
        return _year_data(2012, year_length)

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


@pytest.mark.unit
@pytest.mark.parametrize("n_timesteps", [100, 8760])
def test_tmy_string_year_single_year_covers_horizon(n_timesteps, subtests):
    # A typical-meteorological-year dataset (string resource_year) covers a sub-annual or
    # single-year horizon with one load of the representative year.
    model = _fake_model_from_config(
        _StubConfig("tmy-2022"), n_timesteps=n_timesteps, year_length=8760
    )
    data = model._acquire_resource_data(0.0, 0.0, False)
    with subtests.test("resource length is the representative year"):
        assert ResourceBaseAPIModel._resource_length(data) == 8760
    with subtests.test("representative year loaded exactly once"):
        assert model.seen_years == ["tmy-2022"]
    with subtests.test("resource year unchanged"):
        assert model.config.resource_year == "tmy-2022"


@pytest.mark.unit
def test_tmy_string_year_multiyear_reuses_same_year(subtests):
    # A multi-year horizon with a non-integer (typical-year) resource_year reuses the same
    # representative year for each additional year rather than advancing to a "next" year.
    model = _fake_model_from_config(_StubConfig("tmy-2022"), n_timesteps=3 * 8760, year_length=8760)
    data = model._acquire_resource_data(0.0, 0.0, False)
    with subtests.test("resource length covers all three years"):
        assert ResourceBaseAPIModel._resource_length(data) == 3 * 8760
    with subtests.test("same representative year reused for each year"):
        assert model.seen_years == ["tmy-2022", "tmy-2022", "tmy-2022"]
    with subtests.test("resource year unchanged after acquisition"):
        assert model.config.resource_year == "tmy-2022"


@pytest.mark.unit
def test_integer_year_out_of_range_raises():
    # When advancing to consecutive years runs past the range accepted by the config's
    # validator, the base class raises a clear error instead of a cryptic validator failure.
    model = _fake_model_from_config(_StubConfig(2012, max_year=2012), n_timesteps=2 * 8760)
    with pytest.raises(ValueError, match="outside the range"):
        model._acquire_resource_data(0.0, 0.0, False)


@pytest.mark.unit
def test_integer_year_restored_after_multiyear(subtests):
    # A multi-year integer-year acquisition advances the year on a duplicate config but
    # leaves the original config untouched, so the configured year is unchanged afterward.
    model = _fake_model_from_config(_StubConfig(2013, max_year=2100), n_timesteps=2 * 8760)
    data = model._acquire_resource_data(0.0, 0.0, False)
    with subtests.test("resource length covers both years"):
        assert ResourceBaseAPIModel._resource_length(data) == 2 * 8760
    with subtests.test("consecutive years loaded in order"):
        assert model.seen_years == [2013, 2014]
    with subtests.test("resource year unchanged"):
        assert model.config.resource_year == 2013
