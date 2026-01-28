import urllib.parse

import pandas as pd

from h2integrate.resource.solar.solar_resource_base import SolarResourceBaseAPIModel
from h2integrate.resource.utilities.nrel_developer_api_keys import (
    get_nrel_developer_api_key,
    get_nrel_developer_api_email,
)


class NRELDeveloperAPISolarResourceBase(SolarResourceBaseAPIModel):
    def setup(self):
        super().setup()

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

        # get the data dictionary
        data = self.get_data(self.config.latitude, self.config.longitude)

        self.resource_data = data
        # add resource data dictionary as an out
        self.add_discrete_output(
            "solar_resource_data", val=data, desc="Dict of solar resource data"
        )

    def create_filename(self, latitude, longitude):
        """Create default filename to save downloaded data to. Filename is formatted as
        "{latitude}_{longitude}_{resource_year}_{config.dataset_desc}_{interval}min_{tz_desc}_tz.csv"
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
        url = self.base_url + urllib.parse.urlencode(input_data, True)
        return url

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
        """
        data = pd.read_csv(fpath, header=2)
        header = pd.read_csv(fpath, nrows=2, header=None)
        header_keys = header.iloc[0].to_list()
        header_vals = header.iloc[1].to_list()
        header_dict = dict(zip(header_keys, header_vals))

        time_cols = ["Year", "Month", "Day", "Hour", "Minute"]
        data_cols = [c for c in data.columns.to_list() if c not in time_cols]
        colnames_to_units = {
            c: header_dict[f"{c} Units"] for c in data_cols if f"{c} Units" in header_dict
        }
        # data_missing_units = [c for c in data_cols if f"{c} Units" not in header_dict]

        colname_mapper = {c: f"{c} ({v})" for c, v in colnames_to_units.items()}

        site_data = {
            "id": int(header_dict["Location ID"]),
            "site_tz": float(header_dict["Local Time Zone"]),
            "data_tz": float(header_dict["Time Zone"]),
            "site_lat": float(header_dict["Latitude"]),
            "site_lon": float(header_dict["Longitude"]),
            "elevation": float(header_dict["Elevation"]),
            "filepath": str(fpath),
        }

        data = data.dropna(axis=1, how="all")
        data = data.rename(columns=colname_mapper)  # add units to colnames

        # dont include data that doesn't have units
        data_main_cols = time_cols + list(colname_mapper.values())
        # make units for data in openMDAO-compatible units
        data, data_units = self.format_timeseries_data(data[data_main_cols])
        # convert units to standard units
        data, data_units = self.compare_units_and_correct(data, data_units)

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
            new_c = (
                new_c.replace(f"({units})", "").strip().replace(" ", "_").replace("__", "_").lower()
            )

            if units == "c":
                units = units.upper()
            if units == "w/m2":
                units = "W/m**2"
            if units == "nan" or units == "%":
                units = "percent"
            if units == "Degree" or units == "Degrees":
                units = "deg"

            data_rename_mapper.update({c: new_c})
            data_units.update({new_c: units})
        data = data.rename(columns=data_rename_mapper)
        data_dict = {c: data[c].astype(float).values for x, c in data_rename_mapper.items()}
        data_time_dict = {c.lower(): data[c].astype(float).values for c in time_cols}
        data_dict.update(data_time_dict)
        return data_dict, data_units
