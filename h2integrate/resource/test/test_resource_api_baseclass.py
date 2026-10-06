import numpy as np
import pandas as pd
import pytest
import openmdao.api as om
from attrs import field, define, validators

import h2integrate.resource.resource_baseclass as resource_baseclass
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


@define(kw_only=True)
class FakeTMYResourceConfig(ResourceBaseAPIConfig):
    resource_year: str = field(validator=validators.in_(["tmy-2020", "tmy-2021", "tmy-2022"]))
    dataset_desc: str = "fake_tmy_api"
    resource_type: str = "fake_tmy"
    valid_intervals: list[int] = field(factory=lambda: [60])


class FakeResource(ResourceBaseAPIModel):
    config_class = FakeResourceConfig

    def setup(self):
        resource_specs = self.helper_setup_method()
        self.config = self.config_class.from_dict(
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


class FakeTMYResource(FakeResource):
    config_class = FakeTMYResourceConfig

    def setup(self):
        self.requested_resource_years = []
        super().setup()

    def get_data_for_year(
        self, latitude, longitude, resource_year, resource_filename="", forced_download=False
    ):
        self.requested_resource_years.append((resource_year, resource_filename))
        dates = pd.date_range(start="2001-01-01", periods=8760, freq="1h")

        return {
            "year": dates.year.to_numpy().astype(float),
            "month": dates.month.to_numpy().astype(float),
            "day": dates.day.to_numpy().astype(float),
            "hour": dates.hour.to_numpy().astype(float),
            "minute": dates.minute.to_numpy().astype(float),
            "ws": np.arange(len(dates), dtype=float),
            "latitude": latitude,
            "longitude": longitude,
            "filename": resource_filename,
            "forced_download": forced_download,
            "id": 1111,
            "units": {"ws": "m/s"},
        }


def _setup_resource_component(resource_class, input_config):
    prob = om.Problem()
    comp = resource_class(
        plant_config=input_config,
        resource_config=input_config["site"],
        driver_config={},
    )
    prob.model.add_subsystem("resource", comp)
    prob.setup()
    return prob, comp


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
        (2019, 26280, False, "", None, "Not enough future resource years"),
        (2012, 17520, False, "f.csv", None, "A single `resource_filename` (f.csv)"),
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
        "year-bound",
        "sngle_filename-multiyear",
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


@pytest.mark.unit
@pytest.mark.parametrize(
    "resource_year,n_timesteps,include_leap,resource_fname,yr_order,expected_years",
    [
        (2018, 26280, False, "", None, [2018, 2019, 2020]),
        (2019, 17544, True, "", None, [2019, 2020]),
    ],
)
def test_get_resource_years_from_start_year(input_config, expected_years):
    _, comp = _setup_resource_component(FakeResource, input_config)

    assert comp.get_resource_years_from_start_year(comp.config.resource_year) == expected_years


@pytest.mark.unit
@pytest.mark.parametrize(
    "resource_year,n_timesteps,include_leap,resource_fname,yr_order",
    [(2020, 8760, False, "", None)],
)
def test_get_resource_years_from_start_year_insufficient_years(input_config):
    _, comp = _setup_resource_component(FakeResource, input_config)
    comp.n_timesteps = 17520

    with pytest.raises(ValueError, match="Not enough future resource years"):
        comp.get_resource_years_from_start_year(2020)


@pytest.mark.unit
@pytest.mark.parametrize(
    "resource_year,n_timesteps,include_leap,resource_fname,yr_order",
    [("tmy-2020", 17520, False, "", None)],
)
def test_get_resource_years_from_start_year_tmy(input_config):
    _, comp = _setup_resource_component(FakeTMYResource, input_config)

    assert comp.get_resource_years_from_start_year("tmy-2020") == ["tmy-2020", "tmy-2021"]


@pytest.mark.unit
@pytest.mark.parametrize(
    "resource_year,n_timesteps,include_leap,resource_fname,yr_order",
    [(2012, 8760, False, "", None)],
)
def test_check_resource_year(input_config):
    _, comp = _setup_resource_component(FakeResource, input_config)
    comp._check_resource_year(2012)

    with pytest.raises(ValueError, match="between 2010 and 2020"):
        comp._check_resource_year(2009)


@pytest.mark.unit
@pytest.mark.parametrize(
    "resource_year,n_timesteps,include_leap,resource_fname,yr_order",
    [("tmy-2020", 8760, False, "", None)],
)
def test_check_resource_year_tmy(input_config):
    _, comp = _setup_resource_component(FakeTMYResource, input_config)
    comp._check_resource_year("tmy-2021")
    comp._check_resource_year(2022)

    with pytest.raises(ValueError, match="Invalid resource year 'tmy-2019'"):
        comp._check_resource_year("tmy-2019")


@pytest.mark.unit
@pytest.mark.parametrize(
    "resource_year,n_timesteps,include_leap,resource_fname,yr_order",
    [
        (
            "tmy-2020",
            17520,
            False,
            ["site_tmy-2020.csv", "site_tmy-2021.csv"],
            None,
        )
    ],
)
def test_get_data_infers_tmy_years_from_filenames(input_config):
    _, comp = _setup_resource_component(FakeTMYResource, input_config)

    assert comp.inferred_resource_years == ["tmy-2020", "tmy-2021"]

    data = comp.get_data(35.0, -100.0, first_call=False)

    assert comp.requested_resource_years[-2:] == [("tmy-2020", ""), ("tmy-2021", "")]
    assert len(data["year"]) == 17520


@pytest.mark.unit
@pytest.mark.parametrize(
    "resource_year,n_timesteps,include_leap,resource_fname,yr_order",
    [("tmy-2020", 17520, False, ["first.csv", "second.csv"], None)],
)
def test_get_data_tmy_filenames_require_years_for_site_change(input_config):
    _, comp = _setup_resource_component(FakeTMYResource, input_config)

    with pytest.raises(ValueError, match="standard naming convention"):
        comp.get_data(35.0, -100.0, first_call=False)


@pytest.mark.unit
@pytest.mark.parametrize(
    "resource_year,n_timesteps,include_leap,resource_fname,yr_order",
    [(2013, 2, False, "", None)],
)
def test_process_final_resource_data(subtests, input_config):
    _, comp = _setup_resource_component(FakeResource, input_config)
    dates = pd.to_datetime(["2012-02-28", "2012-02-29", "2012-03-01"])
    data = {
        "site_id": 4400,
        "year": dates.year.to_numpy(),
        "month": dates.month.to_numpy(),
        "day": dates.day.to_numpy(),
        "hour": dates.hour.to_numpy(),
        "minute": dates.minute.to_numpy(),
        "ws": np.array([1.0, 2.0, 3.0]),
    }

    result = comp.process_final_resource_data(data)

    with subtests.test("leap day is removed and data is clipped"):
        assert result["site_id"] == 4400
        np.testing.assert_array_equal(result["day"], [28, 1])
        np.testing.assert_array_equal(result["ws"], [1.0, 3.0])
        assert len(result["year"]) == 2

    with subtests.test("start and end times are populated"):
        assert result["start_time"] == "2012/02/28 00:00:00 (+0000)"
        assert result["end_time"] == "2012/03/01 00:00:00 (+0000)"

    with subtests.test("incorrect final length raises"):
        comp.n_timesteps = 3
        with pytest.raises(ValueError, match="Resource data is not the same length"):
            comp.process_final_resource_data(data)


@pytest.mark.unit
@pytest.mark.parametrize(
    "resource_year,n_timesteps,include_leap,resource_fname,yr_order",
    [(2012, 8760, False, "", None)],
)
def test_get_data_for_year_loads_and_forces_download(input_config, monkeypatch, tmp_path):
    _, comp = _setup_resource_component(FakeResource, input_config)
    resource_file = tmp_path / "existing.csv"
    resource_file.touch()
    monkeypatch.setattr(
        resource_baseclass,
        "check_resource_dir",
        lambda data_dir=None, data_subdir=None: tmp_path,
    )
    loaded_data = {"ws": np.array([1.0])}
    loaded_files = []
    download_calls = []
    monkeypatch.setattr(comp, "load_data", lambda fpath: loaded_files.append(fpath) or loaded_data)
    monkeypatch.setattr(comp, "create_url", lambda latitude, longitude, year: "fake-url")
    monkeypatch.setattr(
        comp,
        "download_data",
        lambda url, fpath: download_calls.append((url, fpath)) or True,
    )

    result = ResourceBaseAPIModel.get_data_for_year(
        comp, 40.0, -95.0, 2012, resource_filename="existing.csv"
    )
    assert result is loaded_data
    assert loaded_files == [resource_file]
    assert download_calls == []

    result = ResourceBaseAPIModel.get_data_for_year(
        comp, 40.0, -95.0, 2012, resource_filename="existing.csv", forced_download=True
    )
    assert result is loaded_data
    assert download_calls == [("fake-url", resource_file)]
    assert loaded_files == [resource_file, resource_file]


@pytest.mark.unit
@pytest.mark.parametrize(
    "resource_year,n_timesteps,include_leap,resource_fname,yr_order",
    [(2012, 8760, False, "", None)],
)
def test_get_data_for_year_warns_and_raises_on_download_failure(
    input_config, monkeypatch, tmp_path
):
    _, comp = _setup_resource_component(FakeResource, input_config)
    monkeypatch.setattr(
        resource_baseclass,
        "check_resource_dir",
        lambda data_dir=None, data_subdir=None: tmp_path,
    )
    monkeypatch.setattr(comp, "create_url", lambda latitude, longitude, year: "fake-url")
    monkeypatch.setattr(comp, "download_data", lambda url, fpath: False)

    with pytest.warns(UserWarning, match="not found"):
        with pytest.raises(ValueError, match="Did not successfully download"):
            ResourceBaseAPIModel.get_data_for_year(
                comp, 40.0, -95.0, 2012, resource_filename="missing.csv"
            )


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
