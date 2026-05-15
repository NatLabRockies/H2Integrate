import os

import numpy as np
import pandas as pd
import pytest
from requests.exceptions import HTTPError

from h2integrate.feedstocks import eia_ng_price as eia


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
def test_EIANaturalGasFeedstockConfig(subtests, EIA_API_key_file):
    """Tests a failed API for basic parameterizations."""
    if (api_key := os.environ.get("EIA_API_KEY")) is None:
        api_key = DUMMY_KEY
        os.environ["EIA_API_KEY"] = api_key

    correct_url = (
        "https://api.eia.gov/v2/natural-gas/pri/sum/data/"
        "?frequency=monthly"
        "&data[0]=value"
        "&facets[series][]=N3035AK3"
        "&start=2022-01"
        "&end=2022-12"
        "&sort[0][column]=period"
        "&sort[0][direction]=asc"
        f"&api_key={api_key}"
    )
    if api_key == DUMMY_KEY:
        with subtests.test("Ensure API URL is correct for no API key"):
            with pytest.raises(HTTPError):
                config = eia.EIANaturalGasFeedstockConfig(
                    state="ak",
                    resource_year=2022,
                    cost_year=2025,
                    monthly=True,
                    price_category="industrial",
                )
                assert config.url == correct_url
        del os.environ["EIA_API_KEY"]
    else:
        with subtests.test("Ensure API works if a valid API environment variable exists"):
            config = eia.EIANaturalGasFeedstockConfig(
                state="ak",
                resource_year=2022,
                cost_year=2025,
                monthly=True,
                price_category="industrial",
            )
            assert config.url == correct_url
            assert isinstance(config.price, pd.DataFrame)
            assert config.price.shape == (12, 1)
            assert (
                config.price.index == pd.Index(pd.date_range("2022-01", "2022-12", freq="MS"))
            ).all()

    with subtests.test("Check no location data failure"):
        msg = (
            "The EIA natural gas feedstock model require one of `state` or"
            " `latitude` and `longitude`."
        )
        with pytest.raises(ValueError, match=msg):
            eia.EIANaturalGasFeedstockConfig(
                resource_year=2022,
                cost_year=2025,
                monthly=True,
                price_category="industrial",
            )
