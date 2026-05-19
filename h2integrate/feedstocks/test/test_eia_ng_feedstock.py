import importlib
from pathlib import Path

import pytest

from h2integrate.feedstocks import eia_ng_price as eia


DUMMY_KEY = "xxxxxx"
RG_NOT_INSTALLED = importlib.util.find_spec("reverse_geocoder") is None

best_trailer_in_colorado_coords = (39.9140081, -105.2249155)


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
def test_EIANaturalGasFeedstockConfig(subtests, EIA_API_key_file):
    """Tests a failed API for basic parameterizations."""

    good_api_fn, bad_api_fn = EIA_API_key_file

    ng_feedstock = eia.EIANaturalGasFeedstockConfig(
        resource_year=2022,
        monthly=False,
        price_category="WELLHEAD",
        state="connecticut",
        latitude=best_trailer_in_colorado_coords[0],
        longitude=best_trailer_in_colorado_coords[1],
        cost_year=2025,
        annual_cost=1,
        start_up_cost=2,
        filename="data.csv",
        api_key_file=good_api_fn,
    )
    assert ng_feedstock.commodity == "natural_gas"
    assert ng_feedstock.commodity_rate_units == "MMBtu/h"
    assert ng_feedstock.commodity_amount_units == "MMBtu"
    assert ng_feedstock.filename == Path("./data.csv").resolve()
    assert not ng_feedstock.filename.exists()
    assert ng_feedstock.price.size == 8760
    assert ng_feedstock.price.price.sum() == 0
    assert ng_feedstock.resource_year == 2022
    assert not ng_feedstock.monthly
    assert ng_feedstock.price_category == "wellhead"
    assert ng_feedstock.state == "CT"
    assert ng_feedstock.latitude == best_trailer_in_colorado_coords[0]
    assert ng_feedstock.longitude == best_trailer_in_colorado_coords[1]
    assert ng_feedstock.cost_year == 2025
    assert ng_feedstock.annual_cost == 1.0
    assert ng_feedstock.start_up_cost == 2.0
    assert ng_feedstock.api_key_file == good_api_fn


@pytest.mark.unit
@pytest.mark.skipif(RG_NOT_INSTALLED, reason="reverse_geocoder is not installed")
def test_EIANaturalGasFeedstockConfig_with_coordinates():
    """Tests a failed API for basic parameterizations."""
    ng_feedstock = eia.EIANaturalGasFeedstockConfig(
        resource_year=2022,
        price_category="WELLHEAD",
        latitude=best_trailer_in_colorado_coords[0],
        longitude=best_trailer_in_colorado_coords[1],
        monthly=True,
    )
    assert ng_feedstock.commodity == "natural_gas"
    assert ng_feedstock.commodity_rate_units == "MMBtu/h"
    assert ng_feedstock.commodity_amount_units == "MMBtu"
    assert ng_feedstock.filename is None
    assert ng_feedstock.price.size == 8760
    assert ng_feedstock.price.price.sum() == 0
    assert ng_feedstock.resource_year == 2022
    assert ng_feedstock.monthly
    assert ng_feedstock.price_category == "wellhead"
    assert ng_feedstock.state == "CO"
    assert ng_feedstock.cost_year == eia.CURRENT_YEAR
    assert ng_feedstock.annual_cost == 0.0
    assert ng_feedstock.start_up_cost == 0.0
