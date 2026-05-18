import os

import pandas as pd
import pytest
from requests.exceptions import HTTPError

from h2integrate.feedstocks import eia_ng_price as eia


DUMMY_KEY = "xxxxxx"


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
