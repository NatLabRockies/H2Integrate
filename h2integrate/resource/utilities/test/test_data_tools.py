import numpy as np
import pytest

from h2integrate.resource.utilities.data_tools import separate_timeseries_and_meta_data


# from h2integrate.resource.utilities.data_tools import (
#     append_timeseries_data,
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
