import os
import itertools
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
from requests.exceptions import HTTPError

from h2integrate.preprocess import eia


DUMMY_KEY = "xxxxxx"
VALID_API_KEY_EXISTS = os.environ.get("EIA_API_KEY") is not None


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
    correct_ix_multi = pd.DatetimeIndex(
        pd.date_range("2000-01", "2001-12", freq="MS"), name="period"
    )

    annual_df = pd.DataFrame(
        [[10]], columns=["price"], index=pd.Index(pd.to_datetime(["2000-01-01"]), name="period")
    )
    with subtests.test("Convert annual to monthly value"):
        df = eia.convert_to_monthly(annual_df, start_year=2000, end_year=2000)
        assert (df.index == correct_ix).all()
        assert all(df.price.values == 10)

    _df = annual_df.assign(state="AK")
    annual_df_multi_ix = pd.concat([_df, _df.replace("AK", "CO").replace(10, 15)]).set_index(
        "state", append=True
    )
    annual_df_multi_ix.loc[(pd.to_datetime("2001-01-01"), "AK"), "price"] = 20
    annual_df_multi_ix.loc[(pd.to_datetime("2001-01-01"), "CO"), "price"] = 30
    annual_df_multi_ix = annual_df_multi_ix.swaplevel("state", "period")
    with subtests.test("Convert multi-index annual to monthly value"):
        df = eia.convert_to_monthly(annual_df_multi_ix, start_year=2000, end_year=2001)
        assert df.shape[0] == 48  # 2 states x 2 years x 12 months
        assert df.index.names == ["period", "state"]
        assert (df.index.get_level_values("period").unique() == correct_ix_multi).all()

        ak_ix = df.index.get_level_values("state") == "AK"
        co_ix = df.index.get_level_values("state") == "CO"
        assert (df.loc[ak_ix, "price"] == [10] * 12 + [20] * 12).all()
        assert (df.loc[co_ix, "price"] == [15] * 12 + [30] * 12).all()

    ms_ix = pd.to_datetime([f"2000-{x:02d}-01" for x in range(1, 13)])
    me_ix = pd.to_datetime([f"2000-{x:02d}-28" for x in range(1, 13)])
    correct_monthly_vals = np.arange(1, 13)

    with subtests.test("Test month start inputs for monthly conversion to month starts"):
        df = pd.DataFrame(
            correct_monthly_vals, columns=["price"], index=pd.Index(ms_ix, name="period")
        )
        df = eia.convert_to_monthly(df, 2000, 2000)
        assert (df.index == correct_ix).all()
        assert (df.price.to_numpy() == correct_monthly_vals).all()

    with subtests.test("Test month start inputs for monthly conversion to month starts"):
        df = pd.DataFrame(
            correct_monthly_vals, columns=["price"], index=pd.Index(me_ix, name="period")
        )
        df = eia.convert_to_monthly(df, 2000, 2000)
        assert (df.index == correct_ix).all()
        assert (df.price.to_numpy() == correct_monthly_vals).all()


@pytest.mark.unit
def test_convert_to_hourly(subtests):
    dt_ix = pd.DatetimeIndex(pd.date_range("2000-01", "2001-12", freq="MS"), name="period")

    with subtests.test("Check single index conversion"):
        df = pd.DataFrame(np.arange(1, 25).reshape(-1, 1), columns=["price"], index=dt_ix)
        new_df = eia.convert_to_hourly(df)
        assert new_df.shape == (8760 * 2, 1)
        assert new_df.index.name == df.index.name
        assert new_df.columns == ["price"]
        assert (df.price.unique() == np.arange(1, 25)).all()

    with subtests.test("Check multi index conversion"):
        ix = pd.MultiIndex.from_product(
            [dt_ix, ["industrial", "wellhead"], ["CO", "AK"]], names=["period", "category", "state"]
        )
        df = pd.DataFrame([[0.0]], columns=["price"], index=ix)
        df.loc[(slice(None), "industrial", "CO"), "price"] = np.arange(1, 25)
        df.loc[(slice(None), "wellhead", "CO"), "price"] = np.arange(1, 25) * 2
        df.loc[(slice(None), "industrial", "AK"), "price"] = np.arange(1, 25) * 3
        df.loc[(slice(None), "wellhead", "AK"), "price"] = np.arange(1, 25) * 4

        new_df = eia.convert_to_hourly(df)
        assert new_df.shape == (8760 * 8, 1)
        assert new_df.index.names == df.index.names
        assert new_df.columns == ["price"]

        ind_co = new_df.loc[(slice(None), "industrial", "CO"), "price"].unique()
        well_co = new_df.loc[(slice(None), "wellhead", "CO"), "price"].unique()
        ind_ak = new_df.loc[(slice(None), "industrial", "AK"), "price"].unique()
        well_ak = new_df.loc[(slice(None), "wellhead", "AK"), "price"].unique()
        assert (ind_co == np.arange(1, 25)).all()
        assert (well_co == np.arange(1, 25) * 2).all()
        assert (ind_ak == np.arange(1, 25) * 3).all()
        assert (well_ak == np.arange(1, 25) * 4).all()


@pytest.mark.unit
def test_validate_resource_year():
    assert eia._validate_resource_year(2005) == (2005, 2005)
    assert eia._validate_resource_year((2010, 2011)) == (2010, 2011)

    with pytest.raises(ValueError):
        assert eia._validate_resource_year((2010, 2011, 2013))

    with pytest.raises(TypeError):
        assert eia._validate_resource_year("2010")


@pytest.mark.unit
def test_validate_state():
    assert eia._validate_state("alaska") == ["AK"]
    assert eia._validate_state("US") == ["US"]
    assert eia._validate_state(["cOlOrAdO", "AK"]) == ["CO", "AK"]
    with pytest.raises(ValueError):
        eia._validate_state(["British Columbia", "AK"])


@pytest.mark.unit
def test_validate_price_category():
    assert eia._validate_price_category("industrial") == ["industrial"]
    assert eia._validate_price_category(["INDUSTRIAL", "Imports"]) == ["industrial", "imports"]
    with pytest.raises(ValueError):
        eia._validate_price_category("city gate")


@pytest.mark.unit
def test_validate_file_name():
    HERE = Path(__file__).parent
    exists = HERE / "conftest.py"
    nonexistent = HERE / "nope.txt"
    assert isinstance(eia._validate_file_name(exists), Path)
    assert isinstance(eia._validate_file_name(nonexistent), Path)


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
def test_create_eia_ng_api_url(subtests):
    """Tests API URL generation for basic parameterizations."""
    if not VALID_API_KEY_EXISTS:
        api_key = DUMMY_KEY
        os.environ["EIA_API_KEY"] = api_key

    correct_single_url = (
        "https://api.eia.gov/v2/natural-gas/pri/sum/data/"
        "?frequency=annual"
        "&data[0]=value"
        "&facets[series][]=N3035AK3"
        "&start=2022"
        "&end=2022"
        "&sort[0][column]=period"
        "&sort[0][direction]=asc"
        f"&api_key={api_key}"
    )
    correct_multi_url = (
        "https://api.eia.gov/v2/natural-gas/pri/sum/data/"
        "?frequency=monthly"
        "&data[0]=value"
        "&facets[series][]=N3035AK3"
        "&facets[series][]=N3035CO3"
        "&facets[series][]=N9190AK3"
        "&facets[series][]=N9190CO3"
        "&start=2022-01"
        "&end=2024-12"
        "&sort[0][column]=period"
        "&sort[0][direction]=asc"
        f"&api_key={api_key}"
    )
    with subtests.test("Check API URL for a single entry query"):
        url = eia.create_eia_ng_api_url(
            state="ak",
            resource_year=2022,
            monthly=False,
            price_category="industrial",
        )
        assert url == correct_single_url

    with subtests.test("Check API URL for a multiple entry query"):
        url = eia.create_eia_ng_api_url(
            state=("ak", "CO"),
            resource_year=(2022, 2024),
            monthly=True,
            price_category=["industrial", "wellhead"],
        )
        assert url == correct_multi_url


@pytest.mark.unit
@pytest.mark.skipif(VALID_API_KEY_EXISTS, reason="No valid API key found to test data download")
def test_failed_get_eia_ng_data():
    with pytest.raises(HTTPError):
        eia.get_eia_ng_data(
            state="ak",
            resource_year=2022,
            price_category="industrial",
        )


@pytest.mark.unit
@pytest.mark.skipif(not VALID_API_KEY_EXISTS, reason="No valid API key found to test data download")
def test_get_eia_ng_data():
    """Check the data for correct dimensionality and extrapolation properties."""

    df = eia.create_eia_ng_api_url(
        state=("ak", "CO"),
        resource_year=(2022, 2024),
        monthly=True,
        price_category=["industrial", "wellhead"],
    )
    assert df.index.names == ["period", "state", "category"]
    assert df.columns == ["price"]
    assert df.shape == (144, 1)  # 2 states x 2 categories x 3 years x 12 months
    assert df.index.get_level_values("state").unique() == ["AK", "CO"]
    assert df.index.get_level_values("category").unique() == ["industrial", "wellhead"]

    df = eia.create_eia_ng_api_url(
        state=("ak", "CO"),
        resource_year=(2022, 2024),
        monthly=False,
        price_category=["industrial", "wellhead"],
    )
    assert df.index.names == ["period", "category", "state"]
    assert df.columns == ["price"]
    assert df.shape == (144, 1)  # 2 states x 2 categories x 3 years x 12 months
    assert df.index.get_level_values("state").unique() == ["AK", "CO"]
    assert df.index.get_level_values("category").unique() == ["industrial", "wellhead"]

    # Ensure an extrapolated annual value is the same value for all 12 months
    combinations = itertools.product(range(2022, 2025), ("AK", "CO"), ("industrial", "wellhead"))
    for year, state, category in combinations:
        dt_ix = df.index.get_level_values("period").year == year
        st_ix = df.index.get_level_values("state") == state
        cat_ix = df.index.get_level_values("category") == category
        assert len(df.loc[dt_ix & st_ix & cat_ix].unique()) == 1
