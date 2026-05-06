import os
import importlib

import numpy as np
import pandas as pd
import pytest

from h2integrate.feedstocks import eia_ng_pricing as eia


DUMMY_KEY = "xxxxxx"


@pytest.fixture
def EIA_API_key_file(temp_dir):
    """Creates a dummy EIA API key configuration file and returns the file path object."""
    good_api_fn = temp_dir / ".eiarc"
    bad_api_fn = temp_dir / ".badeiarc"
    with good_api_fn.open("w") as f:
        f.write(f"EIA_API_KEY: {DUMMY_KEY}")
    with bad_api_fn.open("w") as f:
        f.write(f"EIA_API: {DUMMY_KEY}")
    return good_api_fn, bad_api_fn


@pytest.mark.unit
def test_convert_to_monthly(subtests):
    """Test the annual and month-start conversions."""
    correct_ix = pd.DatetimeIndex(pd.date_range("2000-01", "2000-12", freq="MS"), name="period")

    annual_df = pd.DataFrame(
        [[10]], columns=["price"], index=pd.Index(pd.to_datetime(["2000-01-01"]), name="period")
    )
    with subtests.test("Convert annual to monthly value"):
        df = eia.convert_to_monthly(annual_df)
        assert (df.index == correct_ix).all()
        assert all(df.price.values == 10)

    ms_ix = pd.to_datetime([f"2000-{x:02d}-01" for x in range(1, 13)])
    me_ix = pd.to_datetime([f"2000-{x:02d}-28" for x in range(1, 13)])
    correct_monthly_vals = np.arange(1, 13)

    with subtests.test("Test month start inputs for monthly conversion to month starts"):
        df = pd.DataFrame(
            correct_monthly_vals, columns=["price"], index=pd.Index(ms_ix, name="period")
        )
        df = eia.convert_to_monthly(df)
        assert (df.index == correct_ix).all()
        assert (df.price.to_numpy() == correct_monthly_vals).all()

    with subtests.test("Test month start inputs for monthly conversion to month starts"):
        df = pd.DataFrame(
            correct_monthly_vals, columns=["price"], index=pd.Index(me_ix, name="period")
        )
        df = eia.convert_to_monthly(df)
        assert (df.index == correct_ix).all()
        assert (df.price.to_numpy() == correct_monthly_vals).all()


@pytest.mark.unit
@pytest.mark.skipif(
    importlib.util.find_spec("reverse_geocoder") is None, reason="reverse_geocoder is not installed"
)
def test_get_state_from_coords(subtests):
    """Test the reverse geocoding for state data functionality."""
    best_trailer_in_colorado_coords = (39.9140081, -105.2249155)
    definitely_not_the_us_coords = (53.5265263, -113.657807)

    with subtests.test("Test valid US coordinate pair"):
        assert "CO" == eia.get_state_from_coords(*best_trailer_in_colorado_coords)

    with subtests.test("Test invalid US coordinate pair"):
        result = eia.get_state_from_coords(*definitely_not_the_us_coords)
        assert result not in eia.STATE_MAP.values()
        assert result == "Alberta"


@pytest.mark.unit
@pytest.mark.skipif(
    importlib.util.find_spec("reverse_geocoder") is not None, reason="reverse_geocoder is installed"
)
def test_get_state_from_coords_fail():
    """Tests that the correct error is raised when ``reverse_geocoder` is missing."""
    msg = "EIA natural gas feedstock coordinate input requires `reverse_geocoder`"
    with pytest.raises(ModuleNotFoundError, match=msg):
        eia.get_state_from_coords(0, 0)


@pytest.mark.unit
def test_convert_state_value():
    """Tests the conversion of the state value to a compliant name or code format."""
    assert eia.convert_state_value("united states") == "United States"
    assert eia.convert_state_value("us") == "US"


@pytest.mark.unit
def test_convert_state_to_code():
    """Tests the conversion of a state name to a 2 letter code."""
    assert eia.convert_state_to_code("Washington") == "WA"
    assert eia.convert_state_to_code("DC") == "DC"
    assert eia.convert_state_to_code("JK") == "JK"
    assert eia.convert_state_to_code("washington") == "washington"


@pytest.mark.unit
def test_get_eia_api_key(subtests, EIA_API_key_file):
    """Tests the API Key retrieval."""
    good_api_fn, bad_api_fn = EIA_API_key_file

    with subtests.test("Use a dummy file"):
        assert eia.get_eia_api_key(good_api_fn) == DUMMY_KEY

    if (api_key := os.environ.get("EIA_API_KEY")) is None:
        api_key = DUMMY_KEY
        os.environ["EIA_API_KEY"] = api_key
    with subtests.test("Use the environment variable"):
        assert eia.get_eia_api_key(None) == api_key
        del os.environ["EIA_API_KEY"]

    with subtests.test("Error is raised for no file nor env variable"):
        msg = "No `api_key_file` provided for the EIA API, and 'EIA_API_KEY'"
        with pytest.raises(ValueError, match=msg):
            eia.get_eia_api_key(None)

    with subtests.test("Error is raised for file with bad key name"):
        msg = "No 'EIA_API_KEY' defined"
        with pytest.raises(ValueError, match=msg):
            eia.get_eia_api_key(bad_api_fn)


@pytest.mark.unit
def test_EIANaturalGasFeedstockConfig(): ...
