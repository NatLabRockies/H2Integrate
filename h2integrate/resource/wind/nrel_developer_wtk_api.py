import urllib.parse
from pathlib import Path

import pandas as pd
from attrs import field, define

from h2integrate.core.validators import range_val
from h2integrate.resource.resource_base import ResourceBaseAPIConfig
from h2integrate.resource.wind.wind_resource_base import WindResourceBaseAPIModel
from h2integrate.resource.utilities.nrel_developer_api_keys import (
    get_nrel_developer_api_key,
    get_nrel_developer_api_email,
)


@define(kw_only=True)
class WTKNRELDeveloperAPIConfig(ResourceBaseAPIConfig):
    """Configuration class to download wind resource data from
    `Wind Toolkit Data V2 <https://developer.nrel.gov/docs/wind/wind-toolkit/wtk-download/>`_.

    Args:
        resource_year (int): Year to use for resource data.
            Must been between 2007 and 2014 (inclusive).
        resource_data (dict | object, optional): Dictionary of user-input resource data.
            Defaults to an empty dictionary.
        resource_dir (str | Path, optional): Folder to save resource files to or
            load resource files from. Defaults to "".
        resource_filename (str, optional): Filename to save resource data to or load
            resource data from. Defaults to None.

    Attributes:
        dataset_desc (str): description of the dataset, used in file naming.
            For this dataset, the `dataset_desc` is "wtk_v2".
        resource_type (str): type of resource data downloaded, used in folder naming.
            For this dataset, the `resource_type` is "wind".
        valid_intervals (list[int]): time interval(s) in minutes that resource data can be
            downloaded in. For this dataset, `valid_intervals` are 5, 15, 30, and 60 minutes.

    """

    resource_year: int = field(converter=int, validator=range_val(2007, 2014))
    dataset_desc: str = "wtk_v2"
    resource_type: str = "wind"
    valid_intervals: list[int] = field(factory=lambda: [5, 15, 30, 60])
    resource_data: dict | object = field(default={})
    resource_filename: Path | str = field(default="")
    resource_dir: Path | str | None = field(default=None)


class WTKNRELDeveloperAPIWindResource(WindResourceBaseAPIModel):
    def setup(self):
        # create the input dictionary for WTKNRELDeveloperAPIConfig
        resource_specs = self.helper_setup_method()

        # create the resource config
        self.config = WTKNRELDeveloperAPIConfig.from_dict(resource_specs)

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

        # get the data dictionary
        data = self.get_data(self.config.latitude, self.config.longitude)

        self.resource_data = data

        # add resource data dictionary as an output
        self.add_discrete_output("wind_resource_data", val=data, desc="Dict of wind resource data")

    def create_filename(self, latitude, longitude):
        """Create default filename to save downloaded data to. Filename is formatted as
        "{latitude}_{longitude}_{resource_year}_wtk_v2_{interval}min_{tz_desc}_tz.csv"
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
        input_data = {
            "wkt": f"POINT({longitude} {latitude})",
            "names": [str(self.config.resource_year)],  # TODO: update to handle multiple years
            "interval": str(self.interval),
            "utc": str(self.utc).lower(),
            "api_key": get_nrel_developer_api_key(),
            "email": get_nrel_developer_api_email(),
        }
        base_url = "https://developer.nrel.gov/api/wind-toolkit/v2/wind/wtk-download.csv?"
        url = base_url + urllib.parse.urlencode(input_data, True)
        return url

    def load_data(self, fpath):
        """Load data from a file and format as a dictionary that:

        1) follows naming convention described in WindResourceBaseAPIModel.
        2) is converted to standardized units described in WindResourceBaseAPIModel.

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

        data = pd.read_csv(fpath, header=1)
        header = pd.read_csv(fpath, nrows=1, header=None).values[0]
        header_keys = header[0 : len(header) : 2]
        header_vals = header[1 : len(header) : 2]
        header_dict = dict(zip(header_keys, header_vals))
        site_data = {
            "site_id": header_dict["SiteID"],
            "site_tz": header_dict["Site Timezone"],
            "data_tz": header_dict["Data Timezone"],
            "site_lat": header_dict["Latitude"],
            "site_lon": header_dict["Longitude"],
            "filepath": str(fpath),
        }

        data = data.dropna(axis=1, how="all")

        data, data_units = self.format_timeseries_data(data)
        # make units for data in openmdao-compatible units
        data_units = {
            k: v.replace("%", "percent").replace("degrees", "deg").replace("hour", "h")
            for k, v in data_units.items()
        }
        data_units_temp = {k: "degC" for k, v in data_units.items() if v == "C"}
        data_units.update(data_units_temp)
        # convert data to standardized units
        data, data_units = self.compare_units_and_correct(data, data_units)

        # include site data with data
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
        time_cols = ["Year", "Month", "Day", "Hour", "Minute"]
        data_cols_init = [c for c in data.columns.to_list() if c not in time_cols]
        data_rename_mapper = {}
        data_units = {}
        for c in data_cols_init:
            units = c.split("(")[-1].strip(")")
            new_c = c.replace("air", "").replace("at ", "")
            new_c = new_c.replace(f"({units})", "").strip().replace(" ", "_").replace("__", "_")

            if "surface" in c:
                new_c += "_0m"
                new_c = new_c.replace("surface", "").replace("__", "").strip("_")
            data_rename_mapper.update({c: new_c})
            data_units.update({new_c: units})
        data = data.rename(columns=data_rename_mapper)
        data_dict = {c: data[c].astype(float).values for x, c in data_rename_mapper.items()}
        data_time_dict = {c.lower(): data[c].astype(float).values for c in time_cols}
        data_dict.update(data_time_dict)
        return data_dict, data_units
