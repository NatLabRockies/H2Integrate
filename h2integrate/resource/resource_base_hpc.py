import warnings
from pathlib import Path
from datetime import timezone, timedelta

import numpy as np
import pandas as pd
import openmdao.api as om
from attrs import field, define, validators

from h2integrate.core.utilities import BaseConfig
from h2integrate.core.file_utils import check_resource_dir


@define(kw_only=True)
class ResourceBaseH5Config(BaseConfig):
    """Base configuration class for resource data loaded from an .h5 file.

    Subclasses should include the following attributes that are not set in this BaseConfig:

        - **resource_year** (*int*): Year to download resource data for.
            Recommended to have a validator for upper and lower limits.
        - **resource_data** (*dict*, optional): Dictionary of user-provided resource data.
            Defaults to {}.
        - **resource_dir** (*str | Path*, optional): Folder to save resource files to or
            load resource files from. Defaults to "".
        - **resource_filename** (*str*, optional): Filename to save resource data to or load
            resource data from. Defaults to None.
        - **valid_intervals** (*list[int]*): time interval(s) in minutes that resource data can be
            downloaded in.

    Note:
        Attributes should be updated in subclasses and should not be modifiable by the user.
        These should be inherit attributes of the subclass.

    Args:
        latitude (float): latitude to download resource data for.
        longitude (float): longitude to download resource data for.
        timezone (float | int): timezone to output data in. May be used to determine whether
            to download data in UTC or local timezone. This should be populated by the value
            in sim_config['timezone']
        use_fixed_resource_location (bool, optional): Whether to update resource data in the
            `compute()` method. Set to False if the site location is being swept, set to
            True if the resource data should not be updated to the location
            (plant_config['site']['latitude'], plant_config['site']['longitude']). Set to True
            to reduce computation time during optimizations or design sweeps if site location is
            not being swept. Defaults to False.

    Attributes:
        dataset_desc (str): description of the dataset, used in file naming.
            Should be updated in a subclass.
        resource_type (str): type of resource data downloaded, used in folder naming.
            Should be updated in a subclass.
    """

    latitude: float = field()
    longitude: float = field()

    timezone: int | float = field()
    site_gid: int = field(default=-1)

    location_input: str = field(default="lat/lon", validator=validators.in_(["lat/lon", "gid"]))
    # TODO: add site_gid as input?
    # use_fixed_resource_location: bool = field(default=False, kw_only=True)
    # resource_data: dict | object = field(default={}, kw_only=True)

    # H5 file info
    # dataset_filename: Path | str = field(default="", kw_only=True)
    # dataset_path: Path | str | None = field(default=None, kw_only=True)

    # Export file info
    save_to_csv: bool = field(default=False, kw_only=True)
    load_from_csv: bool = field(default=False, kw_only=True)
    csv_output_dir: Path | str | None = field(default=None, kw_only=True)
    # csv_filename: str = field(default="")
    with_hsds: bool = field(default=False, kw_only=True)
    hsds_kwargs: dict = field(default={}, kw_only=True)

    # Attributes to be populated by parent classes
    dataset_desc: str = field(default="default", init=False)
    resource_type: str = field(default="none", init=False)

    def __attrs_post_init__(self):
        # provided_filename = False if self.csv_filename == "" else True
        provided_dir = False if self.csv_output_dir is None else True

        # Get valid resource_dir with the function check_resource_dir()
        csv_dir = check_resource_dir(data_dir=self.csv_output_dir)

        csv_usage_enabled = self.save_to_csv or self.load_from_csv

        if self.csv_output_dir is None:
            if provided_dir and Path(self.csv_output_dir).parts[-1] == self.csv_output_dir:
                csv_dir = check_resource_dir(data_dir=self.csv_output_dir)
            else:
                csv_dir = check_resource_dir(
                    data_dir=self.csv_output_dir, data_subdir=self.resource_type
                )

            self.csv_output_dir = csv_dir

        if csv_usage_enabled and not provided_dir:
            msg = (
                "Resource data can be loaded or saved to a csv file but `csv_dir` was not "
                f"provided. Csv files will be loaded or saved to folder: {csv_dir}"
            )
            warnings.warn(msg, UserWarning, stacklevel=3)

        if bool(self.hsds_kwargs) and not self.with_hsds:
            msg = (
                "Provided `hsds_kwargs` but `with_hsds` if False. Please set `with_hsds` "
                "to True to run this resource model with hsds enabled. If running on an "
                "NLR super-computer, remove `hsds_kwargs` from the inputs. "
            )

            raise AttributeError(msg)

        if int(self.timezone) != 0:
            msg = (
                "Data from HPC datasets is natively in UTC. Timeseries data will be rolled to "
                "local timezone (in standard time), but time data (year, month, etc) will not "
                "be rolled to prevent unexpected behavior in performance models."
            )
            warnings.warn(msg, UserWarning, stacklevel=3)

        if self.location_input == "gid" and self.site_gid == -1:
            msg = (
                "`site_gid` is required when `location_input` is `gid`. "
                "Please provide the `site_gid` or change `location_input` to `lat/lon`."
            )
            raise AttributeError(msg)


class ResourceBaseH5Model(om.ExplicitComponent):
    """Base model for downloading resource data from API calls or loading resource
    data for a single site from a file.

    Attributes
        resource_data (dict | None): resource data that is created in setup() method.
        dt (int): timestep in seconds.
        config (object): configuration class that inherits ResourceBaseAPIConfig.

    Inputs:
        latitude (float): latitude corresponding to location for resource data
        longitude (float): longitude corresponding to location for resource data

    Outputs:
        dict: dictionary of resource data.
    """

    def initialize(self):
        self.options.declare("plant_config", types=dict)
        self.options.declare("resource_config", types=dict)
        self.options.declare("driver_config", types=dict)

    def setup(self):
        # create attributes that will be commonly used for resource classes.
        self.resource_data = None
        self.resource_site = [self.config.latitude, self.config.longitude]
        self.resource_id = self.config.site_gid
        self.dt = self.options["plant_config"]["plant"]["simulation"]["dt"]
        self.n_timesteps = self.options["plant_config"]["plant"]["simulation"]["n_timesteps"]
        self.add_input("latitude", self.config.latitude, units="deg")
        self.add_input("longitude", self.config.longitude, units="deg")

        if self.config.location_input == "gid":
            self.add_input(
                f"{self.config.resource_type}_site_gid", self.config.site_gid, units="unitless"
            )

    def helper_setup_method(self):
        """
        Prepares and configures resource specifications for the resource API based on plant
        and site configuration options.

        This method extracts relevant configuration details from the `self.options` dictionary,
        pulls values for latitude, longitude, resource directory and timezone from the
        ``site`` section of ``plant_config`` if these parameters are not specified in the
        ``resource_config`` and returns the updated resource specifications dictionary.

        Returns:
            dict: The resource specifications dictionary with defaults set for latitude,
            longitude, resource_dir, and timezone.
        """
        site_config = self.options["plant_config"]["site"]
        sim_config = self.options["plant_config"]["plant"]["simulation"]
        self.dt = sim_config["dt"]

        # create the input dictionary for the resource API config
        resource_specs = self.options["resource_config"]
        # set the default latitude, longitude, and resource_year from the site_config
        resource_specs.setdefault("latitude", site_config["latitude"])
        resource_specs.setdefault("longitude", site_config["longitude"])
        # set the default resource_dir from a directory that can be
        # specified in site_config['resources']['resource_dir']
        resource_specs.setdefault(
            "resource_dir", site_config.get("resources", {}).get("resource_dir", None)
        )

        # default timezone to UTC because 'timezone' was removed from the plant config schema
        resource_specs.setdefault("timezone", sim_config.get("timezone", 0))

        return resource_specs

    def add_resource_start_end_times(self, data: dict):
        """Add resource data start time, end time, and timestep to the resource data dictionary.

        The start and end time are represented as strings formatted as "yyyy/mm/dd hh:mm:ss (tz)"
        and the timestep is represented in seconds.

        Args:
            data (dict): dictionary of resource data

        Returns:
            data (dict): resource data dictionary with added time strings, modified in place
        """

        time_keys = ["year", "month", "day", "hour", "minute", "second"]
        time_dict = {k: data.get(k) for k in time_keys if k in data}

        # If no time information is in the resource data, return the dictionary unchanged
        if not bool(time_dict):
            return data

        df = pd.to_datetime(time_dict)

        # If theres not enough time information, return the dictionary unchanged
        if len(df) <= 1:
            return data

        start_date = df.iloc[0].strftime("%Y/%m/%d %H:%M:%S")
        end_date = df.iloc[-1].strftime("%Y/%m/%d %H:%M:%S")

        # Get resource time interval
        dt = df.iloc[1] - df.iloc[0]

        # Get timezone string
        tz_utc_offset = timedelta(hours=data.get("data_tz", 0))
        tz = timezone(offset=tz_utc_offset)
        tz_str = str(tz).replace("UTC", "").replace(":", "")
        if tz_str == "":
            tz_str = "+0000"

        # Create dictionary of time information with dt in seconds
        time_start_end_info = {
            "start_time": f"{start_date} ({tz_str})",
            "end_time": f"{end_date} ({tz_str})",
            "dt": dt.seconds,
        }

        # Update resource data with time information
        data.update(time_start_end_info)

        return data

    def process_leap_day(self, data: dict):
        """Process leap day data by optionally removing it and validating data length.

        Checks whether the provided resource data contains a leap day (February 29th).
        If ``include_leap_day`` is set to False in the config and the data contains a
        leap day, the leap day entries are removed. After processing, validates that
        the length of the data matches the expected number of timesteps.

        Args:
            data (dict): DataFrame-like dictionary of resource data containing
                "Month" and "Day" columns.
        Returns:
            dict: Processed resource data with leap day handled according to configuration.

        Raises:
            ValueError: If the length of the data does not match ``self.n_timesteps``
                after leap day processing.
        """

        # Check if data includes leap day
        data_has_leap_day = int(data[data["Month"] == 2]["Day"].max()) == 29

        # Remove leap day if needed
        if not self.config.include_leap_day and data_has_leap_day:
            # Get index of dataframe that includes leap day
            leap_day_index = (
                data.reset_index(drop=False)
                .set_index(keys=["Month", "Day"], drop=True)
                .loc[(2, 29)]["index"]
                .to_list()
            )
            # Drop the leap day data from the dataframe
            data = data.drop(index=leap_day_index)

        # Check if data is the same length as the number of timesteps
        if len(data) != self.n_timesteps:
            leap_day_msg = ""
            if data_has_leap_day and len(data) > self.n_timesteps:
                # Add extra detail to error message if error may be due to leap day
                leap_day_msg = (
                    "This may be because the resource data includes a leap day. ",
                    "To remove data from a leap day from resource data, please set "
                    "`include_leap_day` to False.",
                )

            msg = (
                f"{self.__class__.__name__}: Resource data is not the same length as n_timesteps. "
                f"Resource data has length {len(data)}, n_timesteps is {self.n_timesteps}. "
                f"{leap_day_msg}"
            )
            raise ValueError(msg)

        return data

    def search_for_csv_file_from_gid(self, site_gid: int):
        filename_desc = f"{self.config.resource_year}_{self.config.dataset_desc}"
        existing_files = [
            f for f in Path(self.config.csv_output_dir).glob(f"{site_gid}_*") if f.suffix == ".csv"
        ]
        close_match_files = [f for f in existing_files if filename_desc in f.name]
        if not close_match_files:
            return None
        if len(close_match_files) == 1:
            return close_match_files[0]
        # multiple files match. Perhaps because similar sites have the same site GID
        chosen_file = close_match_files[0]
        msg = (
            f"Found {len(close_match_files)} potential csv files for site_gid {site_gid} "
            f"with dataset description of {filename_desc}. Files found were: \n"
            f"{close_match_files} \n. Running resource model with file {chosen_file}"
        )
        warnings.warn(msg, UserWarning, stacklevel=3)
        return chosen_file

    def search_for_csv_file_from_lat_lon(self, latitude, longitude):
        filename_desc = (
            f"{latitude}_{longitude}_{self.config.resource_year}_{self.config.dataset_desc}"
        )
        close_match_files = [
            f for f in Path(self.config.csv_output_dir).glob("*.csv") if filename_desc in f.name
        ]

        if not close_match_files:
            return None
        if len(close_match_files) == 1:
            return close_match_files[0]
        # multiple files match. This would be a bit unexpected.
        chosen_file = close_match_files[0]
        msg = (
            f"Found {len(close_match_files)} potential csv files for location "
            f"({latitude}, {longitude}) with dataset description of {filename_desc}. "
            f"Files found were: \n{close_match_files} \n. Running resource model "
            f"with file {chosen_file}"
        )
        warnings.warn(msg, UserWarning, stacklevel=3)
        return chosen_file

    # def create_filename(self, latitude, longitude):
    def create_csv_filename(self, site_gid, latitude, longitude):
        """Create default filename to save downloaded data to. Suggested filename formatting is:

        "{latitude}_{longitude}_{resource_year}_{dataset_desc}_{interval}min_{tz_desc}_tz.csv"
        where "tz_desc" is "utc" if the timezone is zero, or "local" otherwise.

        Args:
            latitude (float): latitude corresponding to location for resource data
            longitude (float): longitude corresponding to location for resource data

        Returns:
            str: filename for resource data to be saved to or loaded from.
        """
        end_name = (
            f"{self.config.resource_year}_{self.config.dataset_desc}_{self.dt_min}min_utc_tz.csv"
        )
        filename = f"{int(site_gid)}_{latitude}_{longitude}_{end_name}"
        return filename
        # raise NotImplementedError("This method should be implemented in a subclass.")

    #     Args:
    #         latitude (float): latitude corresponding to location for resource data
    #         longitude (float): longitude corresponding to location for resource data

    def get_data(self, site_gid, latitude, longitude, first_call=True):
        """Get resource data to handle any of the expected inputs. This method does the following:

        0) If this is not the first resource call of the simulation, check if latitude and longitude
            inputs are different than the previous latitude and longitude values. If resource data
            has not been already loaded for the, continue to Step 1.
        1) If either saving or loading from a csv file, check if a csv file matching
            either the site GID or lat/lon exists. If a csv file is found, load data from
            the csv file. Otherwise, continue to step 3
        2)

        Args:
            latitude (float): latitude corresponding to location for resource data
            longitude (float): longitude corresponding to location for resource data
            first_call (bool): True if called from `setup()` method, False if called from
                `compute()` method to prevent unnecessary reloading of data.

        Raises:
            ValueError: If data was not successfully downloaded from the API
            ValueError: An unexpected case was encountered in handling data

        Returns:
            Any: resource data in the format expected by the subclass.
        """
        # site_changed = False

        site_loc_changed = not np.allclose(
            [latitude, longitude], self.resource_site, atol=1e-6, rtol=0
        )
        site_id_changed = site_gid != self.resource_id
        # both_changed = site_loc_changed and site_id_changed
        # neither_changed = (not site_loc_changed) and (not site_id_changed)

        if site_id_changed and self.config.location_input == "lat/lon" and not site_loc_changed:
            msg = (
                f"For location ({latitude},{longitude}), the `site_gid` changed from "
                f"{self.resource_id} to {site_gid}, but the latitude and longitude are unchanged. "
                f"`site_gid` should not change unless the latitude and longitude change when "
                "`location_input` is `lat/lon`. Resource data will be output for "
                f"original `site_gid` of {self.resource_id}"
            )
            warnings.warn(msg, UserWarning, stacklevel=2)
        if site_loc_changed and self.config.location_input == "gid" and not site_id_changed:
            msg = (
                f"For location with `site_gid` of {site_gid}, the location changed from "
                f"{tuple(self.resource_site)} to ({latitude},{longitude}), but the `site_gid` is "
                f"unchanged. The latitude and longitude should not change unless the `site_gid` "
                "changes when `location_input` is `gid`. Resource data will be output for "
                f"original location of {tuple(self.resource_site)}"
            )
            warnings.warn(msg, UserWarning, stacklevel=2)

        # 0) If site hasn't changed and resource data has already been loaded
        # just return the resource data that was loaded in the setup() method
        if (not first_call) and (self.resource_data is not None):
            if self.config.location_input == "lat/lon" and not site_loc_changed:
                return self.resource_data
            if self.config.location_input == "gid" and not site_id_changed:
                return self.resource_data

        # if neither_changed and not first_call:

        # if self.config.load_from_csv:
        #     if self.config.location_input == "gid"
        #     self.search_for_csv_file_from_lat_lon
        # # 0) If site hasn't changed and resource data has already been loaded
        # # just return the resource data that was loaded in the setup() method
        # if not site_changed and not first_call:
        #     if self.resource_data is not None:
        #         return self.resource_data

        # # Check if the filename was provided by the user and the site hasn't changed
        # if provided_filename and not site_changed:
        #     # If the user-provided filename wasn't found, throw a warning
        #     if not filepath.is_file():
        #         msg = (
        #             f"User provided resource filename {self.config.resource_filename} "
        #             f"not found in {resource_dir}. Data will be downloaded for this site."
        #         )
        #         warnings.warn(msg, UserWarning)

        # # 4) If the resulting resource_dir and filename from Steps 2 and 3 make a valid
        # # filepath, load data using `load_data()`
        # if filepath.is_file():
        #     self.filepath = filepath
        #     data = self.load_data(filepath)
        #     data = self.add_resource_start_end_times(data)
        #     return data

        # # If the filepath (resource_dir/filename) does not exist, download data
        # self.filepath = filepath
        # # 5) Create the url to download data using `create_url()` and continue to Step 6.
        # url = self.create_url(latitude, longitude)
        # # 6) Download data from the url created in Step 5 and save to a filepath created from
        # # the resulting resource_dir and filename from Steps 2 and 3.
        # success = self.download_data(url, filepath)
        # if success:
        #     # 7) Load data from the file created in Step 6 using `load_data()`
        #     data = self.load_data(filepath)
        #     data = self.add_resource_start_end_times(data)
        #     return data

    def compute(self, inputs, outputs, discrete_inputs, discrete_outputs):
        if not self.config.use_fixed_resource_location:
            # update the resource data based on the input latitude and longitude
            data = self.get_data(inputs["latitude"][0], inputs["longitude"][0], first_call=False)
            # update the stored resource data and site
            self.resource_site = [inputs["latitude"][0], inputs["longitude"][0]]
            self.resource_data = data
            discrete_outputs[f"{self.config.resource_type}_resource_data"] = data
