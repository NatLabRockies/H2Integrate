import re
import warnings
from copy import deepcopy
from pathlib import Path

import numpy as np
import openmdao.api as om
from attrs import field, define

from h2integrate.core.utilities import BaseConfig
from h2integrate.core.file_utils import check_resource_dir
from h2integrate.resource.utilities.data_tools import (
    append_timeseries_data,
    clip_data_to_n_timesteps,
    estimate_resource_year_from_data,
    separate_timeseries_and_meta_data,
)
from h2integrate.resource.utilities.time_tools import (
    is_leap_year,
    process_leap_day,
    check_data_length,
    contains_leap_day,
    add_resource_start_end_times,
    get_number_of_resource_years_needed,
)
from h2integrate.resource.utilities.download_tools import download_from_api


@define(kw_only=True)
class ResourceBaseAPIConfig(BaseConfig):
    """Base configuration class for resource data downloaded from an API.

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
        resource_data (dict | object, optional): Dictionary of user-input resource data.
            Defaults to an empty dictionary.
        resource_dir (str | Path, optional): Folder to save resource files to or
            load resource files from. Defaults to "".
        resource_filename (str | list, optional): Filename(s) to save resource data to or load
            resource data from. Defaults to "". Can only be a list of filenames if
            running a simulation requiring multiple resource years.
        include_leap_day (bool, optional): If False, remove data from leap day if the
            resource_year is a leap year. Otherwise, leave leap day data in. Defaults to False.
        resource_year_order (list, optional): Only used running a simulation requiring multiple
            resource years. List of resource years in-order, such as [2012, 2011, 2013].
            Defaults to None.

    Attributes:
        dataset_desc (str): description of the dataset, used in file naming.
            Should be updated in a subclass.
        resource_type (str): type of resource data downloaded, used in folder naming.
            Should be updated in a subclass.
    """

    latitude: float = field()
    longitude: float = field()

    timezone: int | float = field()

    dataset_desc: str = field(default="default", init=False)
    resource_type: str = field(default="none", init=False)
    resource_data: dict | object = field(default={})
    resource_filename: Path | str | list = field(default="")
    resource_dir: Path | str | None = field(default=None)
    include_leap_day: bool = field(default=False)
    resource_year_order: list | None = field(default=None)


class ResourceBaseAPIModel(om.ExplicitComponent):
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
        self.dt = self.options["plant_config"]["plant"]["simulation"]["dt"]
        self.n_timesteps = self.options["plant_config"]["plant"]["simulation"]["n_timesteps"]
        self.add_input("latitude", self.config.latitude, units="deg")
        self.add_input("longitude", self.config.longitude, units="deg")

        self.resource_year_setting = self.check_config_inputs()

        if self.resource_year_setting == "filenames":
            self.inferred_resource_years = []
            self.resource_year_filenames_processed = False

    def check_config_inputs(self):
        # Calculate the number of resource years needed to achieve the simulation length
        n_data_years = get_number_of_resource_years_needed(
            self.dt, self.n_timesteps, self.config.include_leap_day
        )

        if n_data_years == 1:
            # If only running 1 year, then resource_year_order must be None
            # and resource_filenames cannot be a list
            if self.config.resource_year_order is not None:
                msg = (
                    f"Received extraneous input `resource_year_order` of "
                    f"{self.config.resource_year_order}`. When running a simulation for <= 1 year, "
                    "`resource_year_order` is an extraneous input. "
                )
                raise ValueError(msg)

            if isinstance(self.config.resource_filename, list):
                msg = (
                    "Received invalid input type for `resource_filename`. "
                    "When running a simulation for <= 1 year, "
                    "`resource_filename` must be a single filename (not a list)."
                )

                raise ValueError(msg)

            return "start_year"

        # Running multiple years
        provided_yr_order = self.config.resource_year_order is not None
        provided_filenames = isinstance(self.config.resource_filename, list)

        if not provided_filenames and not provided_yr_order:
            # Didn't provide either, using resource_year as the start-year
            # Check that enough future-years are available from the start-year
            self.get_resource_years_from_start_year(self.config.resource_year)
            return "start_year"

        if provided_filenames and provided_yr_order:
            # Provided resource_year_order and a list of filenames

            if len(self.config.resource_filename) != len(self.config.resource_year_order):
                # If they aren't the same length, throw an error
                err_msg = (
                    "If providing `resource_year_order` and `resource_filename` as a list, they "
                    f"must be the same length. `resource_year_order` is length "
                    f"{len(self.config.resource_year_order)} and `resource_filename` is length "
                    f"{len(self.config.resource_filename)}. Please ensure these both have length "
                    f"{n_data_years}"
                )
                raise ValueError(err_msg)
            # resource_filename and resource_year_order are the same length,
            # but not the correct length
            if len(self.config.resource_year_order) != n_data_years:
                err_msg = (
                    f"`resource_year_order` and `resource_filename` both contain "
                    f"{len(self.config.resource_year_order)} elements but {n_data_years} "
                    "are required for the simulation. "
                )
                raise ValueError(err_msg)

            return "filenames"

        provided_filename = (
            isinstance(self.config.resource_filename, str) and self.config.resource_filename != ""
        ) or isinstance(self.config.resource_filename, Path)
        if provided_yr_order and provided_filename:
            # Provided year order and provided a filename (not a list of filenames)
            msg = (
                "`resource_filename` cannot be a single value when `resource_year_order` is a "
                "list. Please either provide `resource_filename` as a list of filenames or as "
                "an empty string."
            )
            raise ValueError(msg)

        if provided_yr_order:
            # NOTE: could double check with get_n_timesteps_from_year_list
            # (only if not using TMY dataset)
            if len(self.config.resource_year_order) != n_data_years:
                msg = (
                    f"{n_data_years} resource years are required to "
                    f"but {len(self.config.resource_year_order)} were provided. "
                    f"Please ensure that `resource_year_order` has {n_data_years} years"
                )
                raise ValueError(msg)
            return "year_order"

        if provided_filenames:
            if len(self.config.resource_filename) != n_data_years:
                msg = (
                    f"{n_data_years} resource filenames are required to "
                    f"but {len(self.config.resource_filename)} were provided. "
                    f"Please ensure that `resource_filename` has {n_data_years} filenames"
                )
                raise ValueError(msg)
            return "filenames"

    def _check_resource_year(self, resource_year):
        """Check if the input resource year is valid based on the config validator.

        Args:
            resource_year (str | int): resource year to pull data for.
            If resource_year is a string, it should be formatted as 'tmy-{year}' or similar.

        Raises:
            ValueError: If the resource year in invalid based on the config validator
        """

        # NOTE: this method could be updated to deepcopy the config,
        # and set resource_year attribute of the copied config
        # but unsure whether that is more computationally expensive...
        resource_year_validator = type(self.config.__attrs_attrs__.resource_year.validator).__name__

        # In a list validator
        if resource_year_validator == "_InValidator":
            # this type of validator is used in TMY datasets
            init_resource_year = deepcopy(self.config.resource_year)
            year_options = self.config.__attrs_attrs__.resource_year.validator.options
            if isinstance(resource_year, str):
                # resource_year is already a string, like 'tmy-2020'
                if resource_year not in year_options:
                    msg = f"Invalid resource year '{resource_year}', options are {year_options}"
                    raise ValueError(msg)

            if isinstance(resource_year, int):
                year_str = f"{init_resource_year.split('-')[0]}-{resource_year}"
                if year_str not in year_options:
                    msg = f"Invalid resource year '{year_str}', options are {year_options}"
                    raise ValueError(msg)

            return

        # Bounds validator
        for validator in self.config.__attrs_attrs__.resource_year.validator._validators:
            # this type of validator is used for non-TMY datasets
            if "<" in validator.compare_op:
                last_yr = (
                    validator.bound if validator.compare_op == "<=" else int(validator.bound - 1)
                )
            if ">" in validator.compare_op:
                first_yr = (
                    validator.bound if validator.compare_op == ">=" else int(validator.bound + 1)
                )

        if resource_year < first_yr or resource_year > last_yr:
            msg = (
                f"Invalid resource year of {resource_year}. "
                f"Resource year must be between {first_yr} and {last_yr}"
            )
            raise ValueError(msg)

    def get_resource_years_from_start_year(self, resource_starting_year):
        """Get valid resource years to achieve the simulation period, starting at the
        resource year ``resource_starting_year``.

        Args:
            resource_starting_year (str | int): year

        Raises:
            ValueError: not enough valid years following ``resource_starting_year`` to fill the
            simulation period.

        Returns:
            list: list of resource years starting at ``resource_starting_year``
        """
        resource_year_validator = type(self.config.__attrs_attrs__.resource_year.validator).__name__
        if resource_year_validator == "_InValidator":
            # to accommodate tmy solar resource models
            year_options = self.config.__attrs_attrs__.resource_year.validator.options
            if isinstance(resource_starting_year, str):
                # resource_year is formatted like `tmy-2020`
                resource_year_type, resource_year = resource_starting_year.split("-")
                resource_base_year = int(resource_year)
            else:
                # resource_year is just the year, get the "type" from the config (like tmy or tgy)
                resource_year_type, _ = self.config.resource_year.split("-")
                resource_base_year = int(resource_starting_year)

            future_years = sorted(
                [
                    int(yr.split("-")[-1])
                    for yr in year_options
                    if (f"{resource_year_type}-" in yr)
                    and int(yr.split("-")[-1]) >= resource_base_year
                ]
            )

        else:
            resource_base_year = int(resource_starting_year)
            for validator in self.config.__attrs_attrs__.resource_year.validator._validators:
                if "<" in validator.compare_op:
                    last_available_yr = (
                        validator.bound
                        if validator.compare_op == "<="
                        else int(validator.bound - 1)
                    )

            future_years = (
                np.arange(resource_base_year, last_available_yr + 1, 1).astype(int).tolist()
            )

        if self.config.include_leap_day:
            # could use calendar.leapdays(start_year, end_year)
            hours_per_simulation_year = [8784 if is_leap_year(y) else 8760 for y in future_years]
        else:
            hours_per_simulation_year = [8760] * len(future_years)

        # Get the maximum number of hours available in the resource years
        # following resource_start_year
        future_hours_available = int(sum(hours_per_simulation_year))

        # Get the number of hours in the simulation
        hours_simulated = (self.dt / 3600) * self.n_timesteps

        if future_hours_available < hours_simulated:
            msg = f"Not enough future resource years for simulation of {hours_simulated} hours"
            raise ValueError(msg)

        cumulative_hrs = np.cumsum(hours_per_simulation_year)

        # Get the last resource year needed to get enough resource data for n_timesteps
        last_resource_year = [
            y for y, h in zip(future_years, cumulative_hrs) if h >= hours_simulated
        ][0]

        resource_years = (
            np.arange(resource_base_year, last_resource_year + 1, 1).astype(int).tolist()
        )
        if resource_year_validator == "_InValidator":
            # Using TMY data, turn resource year into strings again
            resource_years = [f"{resource_year_type}-{int(y)}" for y in resource_years]
        return sorted(resource_years)

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

    def create_filename(self, latitude, longitude, resource_year):
        """Create default filename to save downloaded data to. Suggested filename formatting is:

        "{latitude}_{longitude}_{resource_year}_{dataset_desc}_{interval}min_{tz_desc}_tz.csv"
        where "tz_desc" is "utc" if the timezone is zero, or "local" otherwise.

        Args:
            latitude (float): latitude corresponding to location for resource data
            longitude (float): longitude corresponding to location for resource data
            resource_year (str | int): year corresponding to the resource data

        Returns:
            str: filename for resource data to be saved to or loaded from.
        """

        raise NotImplementedError("This method should be implemented in a subclass.")

    def create_url(self, latitude, longitude, resource_year):
        """Create url for data download.

        Args:
            latitude (float): latitude corresponding to location for resource data
            longitude (float): longitude corresponding to location for resource data
            resource_year (str | int): year corresponding to the resource data
        Returns:
            str: url to use for API call.
        """

        raise NotImplementedError("This method should be implemented in a subclass.")

    def download_data(self, url, fpath):
        """Download data from url to a file.

        Args:
            url (str): url to call to access data.
            fpath (Path | str): filepath to save data to.

        Returns:
            bool: True if data was downloaded successfully, False if error was encountered.
        """

        success = download_from_api(url, fpath)
        return success

    def load_data(self, fpath):
        """Loads data from a file, reformats data to follow a standardized naming convention,
        converts data to standardized units, and creates a data time profile.

        Args:
            fpath (str | fpath): filepath to load the data from.

        Raises:
            NotImplementedError: this method should be implemented in a subclass.

        Returns:
            dict: dictionary of data that follows the corresponding standardized
                naming convention and is in standardized units.
                The time profile created should be found in the 'time' key.
        """
        raise NotImplementedError("This method should be implemented in a subclass.")

    def get_data_for_year(
        self, latitude, longitude, resource_year, resource_filename="", forced_download=False
    ):
        """Get resource data for a single resource year to handle any of the expected inputs.
        This method does the following:

        1) Get valid resource_dir with :py:func:`check_resource_dir`
        2) Create a filename if resource_filename was not input or if the site location changed
            with the method `create_filename()`. Otherwise, use resource_filename as the filename.
        3) If the resulting resource_dir and filename from Steps 1 and 2 make a valid filepath,
            load data using `load_data()`. Otherwise, continue to Step 4.
        4) Create the url to download data using `create_url()` and continue to Step 5.
        5) Download data from the url created in Step 5 and save to a filepath created from the
            resulting resource_dir and filename from Steps 2 and 3. Continue to Step 6.
        6) Load data from the file created in Step 5 using `load_data()`

        Args:
            latitude (float): latitude corresponding to location for resource data
            longitude (float): longitude corresponding to location for resource data
            resource_year (str | int): year corresponding to the resource data
            resource_filename (str, optional): name of the resource file


        Raises:
            ValueError: If data was not successfully downloaded from the API
            ValueError: An unexpected case was encountered in handling data

        Returns:
            Any: resource data in the format expected by the subclass.
        """

        site_changed = not np.allclose([latitude, longitude], self.resource_site, atol=1e-6, rtol=0)

        # check if user provided directory or filename
        provided_filename = False if resource_filename == "" else True
        provided_dir = False if self.config.resource_dir is None else True

        # 1a) check if file exists directly within resource directory
        # 1) Get valid resource_dir with the function check_resource_dir()
        resource_dir = check_resource_dir(data_dir=self.config.resource_dir)
        # 2a) Create a filename if resource_filename was input
        if provided_filename and not site_changed:
            # If a filename was input, use resource_filename as the filename.
            filepath = resource_dir / resource_filename
        # Otherwise, create a filename with the method `create_filename()`.
        else:
            filename = self.create_filename(latitude, longitude, resource_year)
            filepath = resource_dir / filename
        # if file doesn't exist, continue to Step 2b
        if not filepath.is_file():
            # 1b) check if file exists directly within a subfolder of the resource directory
            # 1) Get valid resource_dir with the function check_resource_dir()
            if (
                provided_dir
                and Path(self.config.resource_dir).parts[-1] == self.config.resource_type
            ):
                resource_dir = check_resource_dir(data_dir=self.config.resource_dir)
            else:
                resource_dir = check_resource_dir(
                    data_dir=self.config.resource_dir, data_subdir=self.config.resource_type
                )
            # 2) Create a filename if resource_filename was input
            if provided_filename and not site_changed:
                # If a filename was input, use resource_filename as the filename.
                filepath = resource_dir / resource_filename
            # Otherwise, create a filename with the method `create_filename()`.
            else:
                filename = self.create_filename(latitude, longitude, resource_year)
                filepath = resource_dir / filename

        # Check if the filename was provided by the user and the site hasn't changed
        if provided_filename and not site_changed:
            # If the user-provided filename wasn't found, throw a warning
            if not filepath.is_file():
                msg = (
                    f"User provided resource filename {resource_filename} "
                    f"not found in {resource_dir}. Data will be downloaded for this site."
                )
                warnings.warn(msg, UserWarning)

        # 3) If the resulting resource_dir and filename from Steps 1 and 2 make a valid
        # filepath, and a new download isn't forced, then load data using `load_data()`
        if filepath.is_file() and not forced_download:
            data = self.load_data(filepath)
            # NOTE: this where we could up/downsample
            return data

        # If the filepath (resource_dir/filename) does not exist, download data
        # 4) Create the url to download data using `create_url()` and continue to Step 5.
        url = self.create_url(latitude, longitude, resource_year)
        # 5) Download data from the url created in Step 4 and save to a filepath created from
        # the resulting resource_dir and filename from Steps 1 and 2.
        success = self.download_data(url, filepath)
        if success:
            # 6) Load data from the file created in Step 5 using `load_data()`
            data = self.load_data(filepath)
            # NOTE: this where we could up/downsample
            return data

        else:
            raise ValueError("Did not successfully download resource data.")

    def process_final_resource_data(self, resource_data):
        """Final processing of multi-year resource data. This method does the following:

        1. Remove resource data for leap-day if needed
        2. Clip the resource data to the number of timesteps in a simulation
        3. Add start and end-times to the resource data
        4. Check that the length of the timeseries resource data is the same as n_timesteps

        Args:
            resource_data (dict): dictionary of resource data for all resource years

        Returns:
            dict: resource_data after final processing and checks
        """
        # NOTE: we could up/downsample here also
        resource_data = process_leap_day(resource_data, self.config.include_leap_day)
        resource_data = clip_data_to_n_timesteps(resource_data, n_timesteps=self.n_timesteps)
        resource_data = add_resource_start_end_times(resource_data)
        check_data_length(resource_data, self.n_timesteps)
        return resource_data

    def get_data(self, latitude, longitude, first_call=True):
        """Get resource data for varying simulation lengths.

        0) If this is not the first resource call of the simulation, check if latitude and longitude
            inputs are different than the previous latitude and longitude values. If resource data
            has not been already loaded for the, continue to Step 1.
        1) Check if resource data was input. If not, continue to Step 2.
        2) Determine the resource years and resource filenames to loop through based on
            ``config.resource_year_setting``
        3) Loop through the resource years and resource filenames, calling ``get_data()``
            for each iteration

        Args:
            latitude (float): latitude corresponding to location for resource data
            longitude (float): longitude corresponding to location for resource data
            first_call (bool): True if called from `setup()` method, False if called from
                `compute()` method to prevent unnecessary reloading of data.

        Returns:
            dict: resource data in the format expected by the subclass.
        """
        site_changed = not np.allclose([latitude, longitude], self.resource_site, atol=1e-6, rtol=0)

        # 0) If site hasn't changed and resource data has already been loaded
        # just return the resource data that was loaded in the setup() method
        if not site_changed and not first_call:
            if self.resource_data is not None:
                return self.resource_data

        # 1) check if user provided data, add start and end times if so
        # and return the data
        if bool(self.config.resource_data):
            data = add_resource_start_end_times(self.config.resource_data)

            if site_changed:
                # warn user if site changed and the resource data didn't
                msg = (
                    f"Site changed from {tuple(self.resource_site)} to ({latitude},{longitude}). "
                    "Since resource data was user-input as a dictionary, the resource data will"
                    "remain unchanged and still be for the site "
                    f"({self.config.latitude}, {self.config.longitude}) provided in the config"
                )
                warnings.warn(msg, UserWarning, stacklevel=3)

            return data

        infer_years_from_files = False
        # 2) Determine the resource years and resource filenames to loop
        if self.resource_year_setting == "start_year":
            # if running multiple years, resource_filename an empty string (based on earlier checks)
            resource_years = self.get_resource_years_from_start_year(self.config.resource_year)
            resource_filenames = [self.config.resource_filename] * len(resource_years)

        elif self.resource_year_setting == "filenames":
            # NOTE: trusting that the site, timezone, and timestep is consistent across files
            resource_years = [self.config.resource_year] * len(self.config.resource_filename)
            resource_filenames = self.config.resource_filename
            infer_years_from_files = (
                self.config.resource_year_order is None
                and not self.resource_year_filenames_processed
            )
            if self.config.resource_year_order is not None:
                resource_years = self.config.resource_year_order
            if not infer_years_from_files:
                resource_years = self.inferred_resource_years
            if infer_years_from_files:
                # likely when first_call is True
                # if first_call:
                # resource_years are not used on first call since the filename is provided
                resource_years = [self.config.resource_year] * len(self.config.resource_filename)
                # Prepare to handle discrepancies if site changes
                self.inferred_resource_years = []
                self.resource_year_filenames_processed = True
                self.raise_error_if_site_change = False
                self.error_msg_details = ""
                infer_years_from_files = True
            # else:
            #     # not first call, use resource years that were estimated from earlier run
            #     resource_years = self.inferred_resource_years
            #     if site_changed:
            #         resource_filenames = [""] * len(self.config.resource_filename)
            if not first_call and site_changed:
                resource_filenames = [""] * len(self.config.resource_filename)

            if site_changed and self.raise_error_if_site_change:
                msg = (
                    f"Site changed from {tuple(self.resource_site)} to ({latitude},{longitude}). "
                    f"When using `resource_year_setting` of 'filenames' with TMY datasets, "
                    "the filenames must following the standard naming convention. Resource years "
                    f"could not be estimated from the input filenames of {self.error_msg_details}."
                )
                raise ValueError(msg)

        elif self.resource_year_setting == "year_order":
            for year in self.config.resource_year_order:
                self._check_resource_year(year)
            resource_years = self.config.resource_year_order
            # config.resource_filename is an empty string (based on earlier checks)
            resource_filenames = [self.config.resource_filename] * len(resource_years)

        timeseries_data = {}
        meta_data = {}

        # 3) Loop through the resource years
        for year, filename in zip(resource_years, resource_filenames):
            is_leap = False  # leap year is always false for TMY datasets
            if not isinstance(year, str):
                # make sure year is an integer if its not a string
                year = int(year)
                is_leap = is_leap_year(year)

            # Check that the resource year is valid
            self._check_resource_year(year)

            # Get the resource data for this year
            resource_data = self.get_data_for_year(
                latitude, longitude, year, resource_filename=filename
            )

            # Extract the metadata and timeseries data
            md, ts = separate_timeseries_and_meta_data(resource_data)

            # Update the meta-data with the most recent meta-data
            meta_data |= md

            # Very specific handling - if first call and using filenames,
            # then estimate resource year for future loops
            if infer_years_from_files:
                # record the resource year order in case site changes in later calls
                if isinstance(year, str):
                    # using a TMY dataset, infer from filename (only possible way)
                    typical_types = ["tmy", "tgy", "tdy"]
                    successful_match = False
                    for txy in typical_types:
                        # match format like tmy-2022
                        match_pattern = re.findall(txy + r"-[+-]?\d+", filename)
                        if bool(match_pattern):
                            # not going to check if valid resource year here,
                            # will be checked if site changes
                            successful_match = True
                            self.inferred_resource_years.append(match_pattern[0])
                            continue
                    if not successful_match:
                        # Flag to throw an error if the site changes
                        self.raise_error_if_site_change = True
                        self.error_msg_details += f" '{filename}',"
                else:
                    # year can be easily pulled from timeseries data
                    year = estimate_resource_year_from_data(ts)
                    self.inferred_resource_years.append(year)
                    # update whether its a leap year for leap-year checks
                    is_leap = is_leap_year(year)

            # Check if data has leap-day data
            has_leap_day_data = contains_leap_day(ts)

            if self.config.include_leap_day and is_leap and not has_leap_day_data:
                msg = "Resource data is missing leap-day, attempting a forced redownload"
                warnings.warn(msg, UserWarning, stacklevel=3)

                # should have leap day data but doesnt, force redownload data
                resource_data = self.get_data_for_year(
                    latitude, longitude, year, resource_filename=filename, forced_download=True
                )

                # Re-extract the metadata and timeseries data
                md, ts = separate_timeseries_and_meta_data(resource_data)

                # Verify that the data now contains a leap day
                now_has_leap_day_data = contains_leap_day(ts)

                if not now_has_leap_day_data:
                    raise ValueError("Leap day data may not be available for this dataset.")

                # Re-update the meta-data with the most recent meta-data
                meta_data |= md

            # Update the timeseries data
            if not bool(timeseries_data):
                # timeseries_data is empty (first-loop), populate it
                timeseries_data |= ts
            else:
                # append new timeseries data to existing
                timeseries_data = append_timeseries_data(timeseries_data, ts)

        # combine meta-data and timeseries data
        resource_data = meta_data | timeseries_data

        # final clean-up and check of the resource data
        resource_data = self.process_final_resource_data(resource_data)
        return resource_data

    def compute(self, inputs, outputs, discrete_inputs, discrete_outputs):
        # update the resource data based on the input latitude and longitude
        data = self.get_data(inputs["latitude"][0], inputs["longitude"][0], first_call=False)
        # update the stored resource data and site
        self.resource_site = [inputs["latitude"][0], inputs["longitude"][0]]
        self.resource_data = data
        discrete_outputs[f"{self.config.resource_type}_resource_data"] = data
