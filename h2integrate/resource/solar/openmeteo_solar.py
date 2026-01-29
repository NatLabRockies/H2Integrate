from pathlib import Path
from datetime import datetime

import numpy as np
import pandas as pd
import requests_cache
import openmeteo_requests
from attrs import field, define
from retry_requests import retry

from h2integrate.core.validators import range_val
from h2integrate.resource.resource_base import ResourceBaseAPIConfig
from h2integrate.resource.solar.solar_resource_base import SolarResourceBaseAPIModel


@define(kw_only=True)
class OpenMeteoHistoricalSolarAPIConfig(ResourceBaseAPIConfig):
    """Configuration class to download solar resource data from
    `Open-Meteo Weather API <https://open-meteo.com/en/docs/historical-weather-api>`_.

    Args:
        resource_year (int): Year to use for resource data.
            Must been between 1940 the year before the current calendar year. (inclusive).
        resource_data (dict | object, optional): Dictionary of user-input resource data.
            Defaults to an empty dictionary.
        resource_dir (str | Path, optional): Folder to save resource files to or
            load resource files from. Defaults to "".
        resource_filename (str, optional): Filename to save resource data to or load
            resource data from. Defaults to None.
        verify_download (bool, optional): Whether to verify the API download from the url.
            If an `openmeteo_requests.Client.OpenMeteoRequestsError` error is thrown,
            try setting to True. Defaults to False.

    Attributes:
        dataset_desc (str): description of the dataset, used in file naming.
            For this dataset, the `dataset_desc` is "openmeteo_archive".
        resource_type (str): type of resource data downloaded, used in folder naming.
            For this dataset, the `resource_type` is "solar".
        valid_intervals (list[int]): time interval(s) in minutes that resource data can be
            downloaded in. For this dataset, `valid_intervals` is 60 minutes.

    """

    resource_year: int = field(converter=int, validator=range_val(1940, datetime.now().year - 1))
    dataset_desc: str = "openmeteo_archive_solar"
    resource_type: str = "solar"
    valid_intervals: list[int] = field(factory=lambda: [60])
    resource_data: dict | object = field(default={})
    resource_filename: Path | str = field(default="")
    resource_dir: Path | str | None = field(default=None)
    verify_download: bool = field(default=False)


class OpenMeteoHistoricalSolarResource(SolarResourceBaseAPIModel):
    def setup(self):
        # create the input dictionary for OpenMeteoHistoricalSolarAPIConfig
        resource_specs = self.helper_setup_method()

        # create the resource config
        self.config = OpenMeteoHistoricalSolarAPIConfig.from_dict(resource_specs)

        # set UTC variable depending on timezone, used for filenaming
        self.utc = False
        if float(self.config.timezone) == 0.0:
            self.utc = True

        # check interval to use for data download/load based on simulation timestep
        interval = self.dt / 60
        if any(float(v) == float(interval) for v in self.config.valid_intervals):
            self.interval = int(interval)
        else:
            if interval > max(self.config.valid_intervals):
                self.interval = int(max(self.config.valid_intervals))
            else:
                self.interval = int(min(self.config.valid_intervals))

        super().setup()

        self.hourly_solar_data_to_units = {
            "wind_speed_10m": "m/s",
            "wind_direction_10m": "deg",
            "temperature_2m": "C",
            "surface_pressure": "hPa",  # TODO check units
            # "precipitation": "mm/h", #TODO: check units
            "relative_humidity_2m": "percent",  # ranges between 0 and 100
            "shortwave_radiation": "W/m**2",  # "ghi": "W/m**2",
            "direct_normal_irradiance": "W/m**2",  # "dni": "W/m**2",
            "diffuse_radiation": "W/m**2",  # "dhi": "W/m**2",
            "dew_point_2m": "C",
            # "surface_albedo": "percent",
            # "solar_zenith_angle": "deg",
            "snow_depth": "m",
            "rain": "mm",  # "precipitable_water": "cm",
            "albedo": "percent",
        }
        # get the data dictionary
        data = self.get_data(self.config.latitude, self.config.longitude)

        self.resource_data = data

        # add resource data dictionary as an out
        self.add_discrete_output(
            "solar_resource_data", val=data, desc="Dict of solar resource data"
        )

    def create_filename(self, latitude, longitude):
        """Create default filename to save downloaded data to. Filename is formatted as
        "{latitude}_{longitude}_{resource_year}_openmeteo_archive_{interval}min_{tz_desc}_tz.csv"
        where "tz_desc" is "utc" if the timezone is zero, or "local" otherwise.

        Args:
            latitude (float): latitude corresponding to location for resource data
            longitude (float): longitude corresponding to location for resource data

        Returns:
            str: filename for resource data to be saved to or loaded from.
        """
        # TODO: update to handle multiple years
        # TODO: update to handle nonstandard time intervals
        if self.utc:
            tz_desc = "utc"
        else:
            tz_desc = "local"
        filename = (
            f"{latitude}_{longitude}_{self.config.resource_year}_"
            f"{self.config.dataset_desc}_{self.interval}min_{tz_desc}_tz.csv"
        )
        return filename

    def create_url(self, latitude, longitude):
        """Create url for data download.

        Args:
            latitude (float): latitude corresponding to location for resource data
            longitude (float): longitude corresponding to location for resource data

        Returns:
            str: url to use for API call.
        """
        start_year = int(self.config.resource_year - 1)
        end_year = int(self.config.resource_year + 1)
        input_data = {
            "latitude": latitude,
            "longitude": longitude,
            "start_date": f"{start_year}-12-31",  # format is "%Y-%m-%d"
            "end_date": f"{end_year}-01-01",  # format is "%Y-%m-%d"
            "hourly": list(self.hourly_solar_data_to_units.keys()),
            "wind_speed_unit": "ms",
            "temperature_unit": "celsius",
            "precipitation_unit": "mm",
            "timezone": "GMT" if self.utc else "auto",
        }

        return input_data

    def download_data(self, url, fpath):
        """Download data from url to a file.

        Args:
            url (dict): input parameters for API call.
            fpath (Path | str): filepath to save data to.

        Returns:
            bool: True if data was downloaded successfully, False if error was encountered.
        """

        base_url = "https://archive-api.open-meteo.com/v1/archive"
        cache_session = requests_cache.CachedSession(".cache", expire_after=3600)
        retry_session = retry(cache_session, retries=5, backoff_factor=0.2)
        openmeteo = openmeteo_requests.Client(session=retry_session)
        responses = openmeteo.weather_api(base_url, params=url, verify=self.config.verify_download)
        response = responses[0]
        hourly_data = response.Hourly()
        ts_data = {}

        # Make data
        for i, varname in enumerate(url["hourly"]):
            vals = hourly_data.Variables(i).ValuesAsNumpy()
            ts_data.update({f"{varname} ({self.hourly_solar_data_to_units[varname]})": vals})

        # Make time column in ISO 8601 format
        time_data = pd.date_range(
            start=pd.to_datetime(hourly_data.Time(), unit="s"),
            end=pd.to_datetime(hourly_data.TimeEnd(), unit="s"),
            freq=pd.Timedelta(seconds=hourly_data.Interval()),
            inclusive="left",
        )

        # Convert timeseries data to a DataFrame
        df = pd.DataFrame(ts_data, index=time_data)
        df.index.name = "time"

        # Convert the timeseries data to a string compatible with
        # csv formatting
        data_str = df.to_csv(None)

        # make header, formatted as if downloading data from OpenMETEO
        header_data = {
            "latitude": response.Latitude(),
            "longitude": response.Longitude(),
            "elevation": response.Elevation(),
            "utc_offset_seconds": response.UtcOffsetSeconds(),
        }

        if response.Timezone() is not None:
            header_data.update({"timezone": response.Timezone().decode("utf-8")})
        else:
            header_data.update({"timezone": url["timezone"]})
        if response.TimezoneAbbreviation() is not None:
            header_data.update(
                {"timezone_abbreviation": response.TimezoneAbbreviation().decode("utf-8")}
            )
        else:
            if response.UtcOffsetSeconds() == 0:
                header_data.update({"timezone_abbreviation": "GMT"})
            else:
                tz = response.UtcOffsetSeconds() / 3600
                header_data.update({"timezone_abbreviation": f"GMT{tz}"})

        header1 = ",".join(k for k in header_data.keys())
        header2 = ",".join(str(v) for v in header_data.values())
        header = f"{header1}\n{header2}\n\n"

        # Combine header plus data arrays
        txt = header + data_str

        # save data
        localfile = Path(fpath).open("w+")
        localfile.write(txt)
        localfile.close()
        if Path(fpath).is_file():
            success = True

        return success

    def load_data(self, fpath):
        """Load data from a file and format as a dictionary that:

        1) follows naming convention described in SolarResourceBaseAPIModel.
        2) is converted to standardized units described in SolarResourceBaseAPIModel.

        This method does the following steps:

        1) load the data, separate out scalar data and timeseries data
        2) remove unused data
        3) Rename the data columns to standardized naming convention and create dictionary of
            OpenMDAO compatible units for the data. Calls `format_timeseries_data()` method.
        4) Convert data to standardized units. Calls `compare_units_and_correct()` method

        Args:
            fpath (str | Path): filepath to file containing the data

        Returns:
            dict: dictionary of data in standardized units and naming convention.
            Time information is found in the 'time' key.
        """

        header = pd.read_csv(fpath, nrows=2, header=None)
        header_dict = dict(zip(header.iloc[0].to_list(), header.iloc[1].to_list()))

        if header_dict["timezone_abbreviation"] == "GMT":
            data_tz = 0
        else:
            data_tz = float(header_dict["timezone_abbreviation"].replace("GMT", ""))

        data_tz = float(header_dict["utc_offset_seconds"]) / 3600
        site_data = {
            "data_tz": data_tz,
            "elevation": float(header_dict["elevation"]),
            "site_lat": float(header_dict["latitude"]),
            "site_lon": float(header_dict["longitude"]),
            "filepath": str(fpath),
        }

        data = pd.read_csv(fpath, header=2)

        # Make time columns
        time = pd.DatetimeIndex(data["time"])
        data["Year"] = time.year
        data["Month"] = time.month
        data["Day"] = time.day
        data["Hour"] = time.hour
        data["Minute"] = time.minute

        data = data[data["Year"] == self.config.resource_year]
        # TODO: throw error if data isn't proper length

        data, data_units = self.format_timeseries_data(data)
        # make units for data in openmdao-compatible units

        # convert data to standardized units
        data, data_units = self.compare_units_and_correct(data, data_units)

        # update solar resource data with site data
        data.update(site_data)

        return data

    def format_timeseries_data(self, data):
        """Convert data to a dictionary with keys that follow the standardized naming convention and
        create a dictionary containing the units for the data.

        Args:
            data (pd.DataFrame): Dataframe of timeseries data.

        Returns:
            2-element tuple containing

            - **data** (*dict*): data dictionary with keys following the standardized naming
                convention.
            - **data_units** (*dict*): dictionary with same keys as `data` and values as the
                data units in OpenMDAO compatible format.
        """
        time_cols = ["Year", "Month", "Day", "Hour", "Minute", "time"]
        data_cols_init = [c for c in data.columns.to_list() if c not in time_cols]
        data_rename_mapper = {}
        data_units = {}
        data_variable_name_mapper = {
            "shortwave_radiation": "ghi",
            "direct_normal_irradiance": "dni",
            "diffuse_radiation": "dhi",
            "rain": "precipitable_water",
            "surface_pressure": "pressure",
            "albedo": "surface_albedo",
            # below aren't downloaded in this API call but may available
            # in a user-provided file
            "diffuse_radiation_instant": "dhi_instant",  #
            "direct_normal_irradiance_instant": "dni_instant",
            "shortwave_radiation_instant": "ghi_instant",
        }
        for c in data_cols_init:
            units = c.split("(")[-1].strip(")").replace("°", "deg").replace("%", "unitless")
            units = (
                units.replace("undefined", "unitless").replace("m²", "m**2").replace("degC", "C")
            )

            new_c = c.split("(")[0].replace("air", "").replace("at ", "")
            new_c = new_c.replace(f"({units})", "").strip().replace(" ", "_").replace("__", "_")
            new_c = new_c.replace("_10m", "").replace("_2m", "")

            old_c = c.split("(")[0].strip()

            # don't include data that isn't relevant for solar data
            if old_c not in self.hourly_solar_data_to_units and "instant" not in old_c:
                continue

            if old_c in data_variable_name_mapper:
                new_c = data_variable_name_mapper[old_c]

            data_rename_mapper.update({c: new_c})
            data_units.update({new_c: units})
        data = data.rename(columns=data_rename_mapper)

        data_dict = {c: data[c].astype(float).values for x, c in data_rename_mapper.items()}
        # only include _instant data if non-instant data isn't provided
        if any("_instant" in c for c in list(data_dict.keys())):
            if "dhi_instant" in data_dict and "dhi" not in data_dict:
                # only have instant dhi data, so use dhi_instant as dhi
                dhi = data_dict.pop("dhi_instant")
                data_dict["dhi"] = dhi
            if "dni_instant" in data_dict and "dni" not in data_dict:
                # only have instant dni data, so use dni_instant as dni
                dni = data_dict.pop("dni_instant")
                data_dict["dni"] = dni
            if "ghi_instant" in data_dict and "ghi" not in data_dict:
                # only have instant ghi data, so use ghi_instant as ghi
                ghi = data_dict.pop("ghi_instant")
                data_dict["ghi"] = ghi
                pass

        # check if albedo is only NaNs and remove if so
        if "surface_albedo" in data_dict:
            if all(c for c in np.isnan(data_dict["surface_albedo"])):
                data_dict.pop("surface_albedo")

        data_time_dict = {c.lower(): data[c].astype(float).values for c in time_cols if c != "time"}
        data_dict.update(data_time_dict)
        return data_dict, data_units
