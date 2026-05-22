import importlib

import pytest

from h2integrate.preprocess import geospatial as geo


RG_NOT_INSTALLED = importlib.util.find_spec("reverse_geocoder") is None


@pytest.mark.unit
@pytest.mark.skipif(RG_NOT_INSTALLED, reason="reverse_geocoder is not installed")
def test_get_state_from_coords(subtests):
    """Test the reverse geocoding for state data functionality."""
    best_trailer_in_colorado_coords = (39.9140081, -105.2249155)
    definitely_not_the_us_coords = (53.5265263, -113.657807)

    with subtests.test("Test valid US coordinate pair"):
        assert "CO" == geo.get_state_from_coords(coordinates=best_trailer_in_colorado_coords)

        lat, lon = best_trailer_in_colorado_coords
        assert "CO" == geo.get_state_from_coords(latitude=lat, longitude=lon)

    with subtests.test("Test invalid US coordinate pair"):
        result = geo.get_state_from_coords(coordinates=definitely_not_the_us_coords)
        assert result not in geo.US_STATE_MAP.values()
        assert result == "Alberta"

    coords = [best_trailer_in_colorado_coords, definitely_not_the_us_coords]
    correct_result = ["CO", "Alberta"]
    with subtests.test("Multiple coordinates"):
        res = geo.get_state_from_coords(coordinates=coords)
        assert len(res) == 2
        assert res == correct_result

    lat = [c[0] for c in coords]
    lon = [c[1] for c in coords]
    with subtests.test("Multiple coordinates as lat/lon"):
        res = geo.get_state_from_coords(latitude=lat, longitude=lon)
        assert len(res) == 2
        assert res == correct_result

    with subtests.test("Verify fail points"):
        msg = "At least one value must be provided"
        with pytest.raises(ValueError, match=msg):
            geo.get_state_from_coords()

        msg = r"Length of `latitude` \(2\) and `longitude` \(1\) inputs not equal."
        with pytest.raises(ValueError, match=msg):
            geo.get_state_from_coords(latitude=lat, longitude=lon[0])


@pytest.mark.unit
@pytest.mark.skipif(not RG_NOT_INSTALLED, reason="reverse_geocoder is installed")
def test_get_state_from_coords_fail():
    """Tests that the correct error is raised when ``reverse_geocoder` is missing."""
    msg = "`reverse_geocoder` library required."
    with pytest.raises(ModuleNotFoundError, match=msg):
        geo.get_state_from_coords(latitude=0, longitude=0)


@pytest.mark.unit
def test_convert_state_value():
    """Tests the conversion of the state value to a compliant name or code format."""
    assert geo.convert_state_value("united states") == "United States"
    assert geo.convert_state_value("us") == "US"


@pytest.mark.unit
def test_convert_state_to_code():
    """Tests the conversion of a state name to a 2 letter code."""
    assert geo.convert_state_to_code("Washington") == "WA"
    assert geo.convert_state_to_code("DC") == "DC"
    assert geo.convert_state_to_code("JK") == "JK"
    assert geo.convert_state_to_code("washington") == "washington"
