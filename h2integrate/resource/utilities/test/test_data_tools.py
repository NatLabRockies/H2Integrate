import numpy as np
import pytest

from h2integrate.resource.utilities.data_tools import (
    append_timeseries_data,
    clip_data_to_n_timesteps,
    clip_data_to_resource_year,
    estimate_resource_year_from_data,
    separate_timeseries_and_meta_data,
)


@pytest.mark.unit
def test_separate_data(subtests):
    fake_meta_data = {
        "site_id": 4400,  # int
        "is_data": True,  # bool
        "site_lat": 41.88,  # float
        "site_lon": np.max([-102.74, -103.00]),  # np.float64,
        "units": {"a": "m", "c": "deg/s"},  # dict
        "country": "USA",  # str
    }
    fake_timeseries_data = {"ghi": (1, 2, 3), "dhi": [1, 2, 3], "dni": np.array([1, 2, 3])}

    fake_data = fake_meta_data | fake_timeseries_data

    meta_data, ts_data = separate_timeseries_and_meta_data(fake_data)

    with subtests.test("meta data"):
        assert meta_data == fake_meta_data

    with subtests.test("ts data"):
        assert ts_data == fake_timeseries_data


@pytest.mark.unit
def test_append_timeseries_data(subtests):
    data_full = {
        "site_id": 4400,
        "array_data": np.array([1, 2]),
        "list_data": [3, 4],
    }
    new_data = {
        "site_id": 4401,
        "array_data": np.array([5]),
        "list_data": [6],
    }

    with subtests.test("metadata is retained by default"):
        result = append_timeseries_data(data_full, new_data)
        assert result["site_id"] == 4400
        np.testing.assert_array_equal(result["array_data"], [1, 2, 5])
        assert result["list_data"] == [3, 4, 6]

    with subtests.test("metadata can be omitted"):
        result = append_timeseries_data(data_full, new_data, return_with_metadata=False)
        assert set(result) == {"array_data", "list_data"}
        np.testing.assert_array_equal(result["array_data"], [1, 2, 5])
        assert result["list_data"] == [3, 4, 6]


@pytest.mark.unit
def test_clip_data_to_n_timesteps():
    data = {
        "site_id": 4400,
        "ghi": np.arange(5),
        "year": [2012, 2012, 2012, 2012, 2012],
    }

    result = clip_data_to_n_timesteps(data, n_timesteps=3)

    assert result["site_id"] == 4400
    np.testing.assert_array_equal(result["ghi"], [0, 1, 2])
    assert result["year"] == [2012, 2012, 2012]
    assert len(data["ghi"]) == 5


@pytest.mark.unit
def test_estimate_resource_year_from_data(subtests):
    with subtests.test("single uppercase year"):
        assert estimate_resource_year_from_data({"Year": [2012, 2012]}) == 2012

    with subtests.test("most common year in buffered annual data"):
        data = {"year": [2011, 2012, 2012, 2012, 2013]}
        assert estimate_resource_year_from_data(data) == 2012

    with subtests.test("tie warns and returns None"):
        data = {"year": [2012, 2012, 2013, 2013]}
        with pytest.warns(UserWarning, match="Multiple years have the same number"):
            assert estimate_resource_year_from_data(data) is None

    with subtests.test("missing year raises"):
        with pytest.raises(ValueError, match="year"):
            estimate_resource_year_from_data({"ghi": [1, 2]})


@pytest.mark.unit
def test_clip_data_to_resource_year(subtests):
    data = {
        "site_id": 4400,
        "year": np.array([2012, 2013, 2012]),
        "ghi": np.array([1.0, 2.0, 3.0]),
    }
    clipped = clip_data_to_resource_year(data, resource_year=2012)

    with subtests.test("lowercase year filters timeseries and retains metadata"):
        assert clipped["site_id"] == 4400
        np.testing.assert_array_equal(clipped["year"], [2012, 2012])
        np.testing.assert_array_equal(clipped["ghi"], [1.0, 3.0])

    with subtests.test("uppercase year key is supported"):
        uppercase_data = {"Year": [2012, 2013], "ghi": [1.0, 2.0]}
        result = clip_data_to_resource_year(uppercase_data, resource_year=2013)
        assert result["Year"].tolist() == [2013]
        assert result["ghi"].tolist() == [2.0]

    with subtests.test("TMY data is returned unchanged"):
        tmy_data = {"year": [2001], "ghi": [1.0]}
        assert clip_data_to_resource_year(tmy_data, resource_year="tmy-2020") is tmy_data

    with subtests.test("missing year raises"):
        with pytest.raises(ValueError, match="Missing 'year' timeseries info"):
            clip_data_to_resource_year({"ghi": [1.0]}, resource_year=2012)


@pytest.mark.unit
def test_append_timeseries_data_warning(subtests):
    fake_data_1 = {
        "site_id": 4400,
        "ghi": np.ones(8760),
        "dni": np.ones(8760),
        "ws": np.ones(8760),
        "year": [2012] * 8760,
    }
    fake_data_2 = {
        "site_id": 4401,
        "state": "colorado",
        "ghi": np.zeros(8760),
        "dni": np.zeros(8760),
        "year": [2013] * 8760,
    }

    with subtests.test("Add-on data has missing key"):
        with pytest.warns(UserWarning) as excinfo:
            combined_data = append_timeseries_data(
                fake_data_1, fake_data_2, return_with_metadata=True
            )
        assert "['ws'] will be removed" in str(excinfo.list[0].message)

    with subtests.test("Meta data contains site id 4400"):
        assert combined_data["site_id"] == 4400

    with subtests.test("Meta data does not contain state"):
        assert "state" not in combined_data

    with subtests.test("Shared timeseries data is appended"):
        assert len(combined_data["ghi"]) == 17520
        assert np.all(combined_data["ghi"][:8760] == 1)
        assert np.all(combined_data["ghi"][8760:] == 0)
        assert combined_data["year"] == [2012] * 8760 + [2013] * 8760

    with subtests.test("Full data has missing key"):
        with pytest.warns(UserWarning) as excinfo:
            combined_data = append_timeseries_data(
                fake_data_2, fake_data_1, return_with_metadata=True
            )
        assert "['ws'] will be removed" in str(excinfo.list[0].message)

    with subtests.test("Meta data contains site id 4401"):
        assert combined_data["site_id"] == 4401

    with subtests.test("Meta data contains state"):
        assert "state" in combined_data
