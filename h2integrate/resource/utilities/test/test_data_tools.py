import numpy as np
import pytest

from h2integrate.resource.utilities.data_tools import (
    append_timeseries_data,
    separate_timeseries_and_meta_data,
)


# from h2integrate.resource.utilities.data_tools import (
#     clip_data_to_n_timesteps,
#     clip_data_to_resource_year,
#     estimate_resource_year_from_data
# )


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

    # TODO: add subtests for the timeseries data

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
