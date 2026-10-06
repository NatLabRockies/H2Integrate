import numpy as np
import pandas as pd
import pytest
import openmdao.api as om
from attrs import field, define, validators

from h2integrate.resource.resource_baseclass import ResourceBaseAPIModel, ResourceBaseAPIConfig


@pytest.fixture
def input_config(n_timesteps, resource_year, include_leap, resource_fname, yr_order):
    plant = {
        "plant_life": 30,
        "simulation": {
            "dt": 3600,
            "n_timesteps": n_timesteps,
            "start_time": "01/01/1900 00:30:00",
            "timezone": 0,
        },
    }
    site_config = {
        "latitude": 40.0,
        "longitude": -95.0,
        "resource_year": resource_year,
        "include_leap_day": include_leap,
        "resource_year_order": yr_order,
        "resource_filename": resource_fname,
        "timezone": 0,
    }

    return {"plant": plant, "site": site_config}


# TODO: add config and class for TMY models
@define(kw_only=True)
class FakeResourceConfig(ResourceBaseAPIConfig):
    resource_year: int = field(converter=int, validator=(validators.ge(2010), validators.le(2020)))
    dataset_desc: str = "fake_api"
    resource_type: str = "fake"
    valid_intervals: list[int] = field(factory=lambda: [30, 60])


class FakeResource(ResourceBaseAPIModel):
    def setup(self):
        resource_specs = self.helper_setup_method()
        self.config = FakeResourceConfig.from_dict(
            resource_specs,
            additional_cls_name=self.__class__.__name__,
        )

        # setup from baseclass
        super().setup()
        self.utc = False
        self.interval = 60  # minutes

        # get the data dictionary
        data = self.get_data(self.config.latitude, self.config.longitude)
        self.resource_data = data

        # add resource data dictionary as an out
        self.add_discrete_output("fake_resource_data", val=data, desc="Dict of fake resource data")

    def get_data_for_year(
        self, latitude, longitude, resource_year, resource_filename="", forced_download=False
    ):
        # simple method that overwrites get_data_for_year in resource baseclass
        dates = pd.date_range(
            start=f"{resource_year}-01-01 00:30:00",
            end=f"{resource_year}-12-31 23:30:00",
            freq="1h",
        )

        return {
            "year": dates.year.to_numpy().astype(float),
            "month": dates.month.to_numpy().astype(float),
            "day": dates.day.to_numpy().astype(float),
            "hour": dates.hour.to_numpy().astype(float),
            "minute": dates.hour.to_numpy().astype(float),
            "ws": np.arange(len(dates), dtype=float),
            "latitude": latitude,
            "longitude": longitude,
            "filename": resource_filename,
            "forced_download": forced_download,
            "id": 1111,
            "units": {"ws": "m/s"},
        }


@pytest.mark.unit
@pytest.mark.parametrize(
    "resource_year,n_timesteps,include_leap,resource_fname,yr_order,expected_msg",
    [
        # Invalid setting with <= 1 year
        (2015, 8760, False, "", [2015, 2016], "`resource_year_order` is an extran"),
        (2015, 8760, False, [""], None, "`resource_filename` must be a single"),
        (2012, 4380, False, "", [2012], "`resource_year_order` is an extran"),
        (2012, 8784, True, [""], None, "`resource_filename` must be a single"),
        # Not enough inputs
        (2012, 17520, False, "", [2012], "2 resource years are req"),
        (2012, 17520, False, [""], None, "2 resource filenames are req"),
        # Too many inputs
        (2012, 17520, False, "", [2012, 2012, 2012], "2 resource years are req"),
        (2012, 17520, False, ["", "", ""], None, "2 resource filenames are req"),
        # Invalid combination for filename and year order
        (2012, 17520, False, "f.csv", [2012, 2013], "_filename` cannot be a single"),
        (2012, 17520, False, ["f.csv"], [2012, 2013], "must be the same length"),
        (2012, 17520, False, ["a", "b", "c"], [2012, 2013, 2014], "elements but 2 are requi"),
    ],
    ids=[
        # Invalid setting with <= 1 year
        "start_year-extra_attr",
        "start_year-invalid_type",
        "yr_order-0.5yr",
        "filenames-1yr-leap",
        # Not enough inputs
        "yr_order-too_short",
        "filenames-too_short",
        # Too many inputs
        "yr_order-too_long",
        "filenames-too_long",
        # Invalid
        "single-filename_with_yr_order",
        "length-mismatch",
        "incorrect-lengths",
    ],
)
def test_setup_errors(input_config, expected_msg):
    # this test is pretty dependent on the function
    # `get_number_of_resource_years_needed`

    prob = om.Problem()
    comp = FakeResource(
        plant_config=input_config,
        resource_config=input_config["site"],
        driver_config={},
    )
    prob.model.add_subsystem("resource", comp)

    with pytest.raises(ValueError) as excinfo:
        prob.setup()
    assert expected_msg in str(excinfo.value)


# @pytest.mark.unit
# def test_check_resource_year(subtests):
#     pass

# @pytest.mark.unit
# def test_get_resource_years_from_start_year(subtests):
#     pass

# @pytest.mark.unit
# def test_process_final_resource_data(subtests):
#     pass

# @pytest.mark.unit
# def test_process_final_resource_data(subtests):
#     pass


@pytest.mark.unit
@pytest.mark.parametrize(
    "resource_year,n_timesteps,include_leap,resource_fname,yr_order",
    [(2012, 17544, True, ["data_2013.csv", "data_2012.csv"], None)],
)
def test_get_data_filenames(subtests, input_config):
    # This is testing whether the resource years are properly estimated from the first call

    prob = om.Problem()
    comp = FakeResource(
        plant_config=input_config,
        resource_config=input_config["site"],
        driver_config={},
    )
    prob.model.add_subsystem("resource", comp)
    prob.setup()
    prob.run_model()

    data_site0 = prob.get_val("resource.fake_resource_data").copy()

    with subtests.test("Initial filename"):
        assert data_site0["filename"] == "data_2012.csv"

    # Run again, dont change the site
    prob.run_model()

    with subtests.test("Initial filename after rerun"):
        assert prob.get_val("resource.fake_resource_data")["filename"] == "data_2012.csv"

    # Change the site
    prob.set_val("resource.latitude", 35.0, units="deg")
    prob.set_val("resource.longitude", -100.0, units="deg")
    prob.run_model()

    data_site1 = prob.get_val("resource.fake_resource_data").copy()

    with subtests.test("Year order was estimated correctly."):
        assert np.allclose(data_site0["year"], data_site1["year"])

    with subtests.test("Month order was estimated correctly."):
        assert np.allclose(data_site0["month"], data_site1["month"])

    with subtests.test("Latitude changed"):
        assert data_site0["latitude"] != data_site1["latitude"]

    with subtests.test("Longitude changed"):
        assert data_site0["longitude"] != data_site1["longitude"]

    with subtests.test("Filenames changed"):
        assert data_site0["filename"] != data_site1["filename"]

    with subtests.test("Second filename"):
        assert data_site1["filename"] == ""

    with subtests.test("Data length"):
        assert len(data_site1["year"]) == 17544

    # Run again without changing site, make sure filename is still ""
    prob.run_model()
    with subtests.test("Third filename"):
        assert prob.get_val("resource.fake_resource_data")["filename"] == ""
