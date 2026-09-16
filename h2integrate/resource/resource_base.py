import warnings
from pathlib import Path

import numpy as np
import openmdao.api as om
from attrs import field, define

from h2integrate.core.utilities import BaseConfig
from h2integrate.core.file_utils import check_resource_dir
from h2integrate.resource.utilities.time_tools import (
    concatenate_resource_years,
    add_resource_start_end_times,
    resample_resource_data_to_dt,
    conform_resource_data_to_n_timesteps,
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
        resource_filename (str | Path | list, optional): Filename to save resource data to
            or load resource data from. For multi-year simulations, provide a list of
            filenames (one per consecutive year, in chronological order starting at
            ``resource_year``). Defaults to "".
        upsample_method (str, optional): interpolation method passed to
            ``pandas.DataFrame.interpolate`` when resampling to a finer timestep than the
            data provides. Defaults to "time". The "time" method uses linear interpolation
            but accounting for the actual time step.
        downsample_method (str, optional): aggregation passed to the pandas resampler
            when resampling to a coarser timestep than the data provides. Defaults to
            "mean".

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
    upsample_method: str = field(default="time")
    downsample_method: str = field(default="mean")


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

    def create_filename(self, latitude, longitude):
        """Create default filename to save downloaded data to. Suggested filename formatting is:

        "{latitude}_{longitude}_{resource_year}_{dataset_desc}_{interval}min_{tz_desc}_tz.csv"
        where "tz_desc" is "utc" if the timezone is zero, or "local" otherwise.

        Args:
            latitude (float): latitude corresponding to location for resource data
            longitude (float): longitude corresponding to location for resource data

        Returns:
            str: filename for resource data to be saved to or loaded from.
        """

        raise NotImplementedError("This method should be implemented in a subclass.")

    def create_url(self, latitude, longitude):
        """Create url for data download.

        Args:
            latitude (float): latitude corresponding to location for resource data
            longitude (float): longitude corresponding to location for resource data

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

    def get_data(self, latitude, longitude, first_call=True):
        """Get resource data to handle any of the expected inputs. This method does the following:

        0) If this is not the first resource call of the simulation, check if latitude and longitude
            inputs are different than the previous latitude and longitude values. If resource data
            has not been already loaded for the, continue to Step 1.
        1) Check if resource data was input. If not, continue to Step 2.
        2) Get valid resource_dir with :py:func:`check_resource_dir`
        3) Create a filename if resource_filename was not input or if the site location changed
            with the method `create_filename()`. Otherwise, use resource_filename as the filename.
        4) If the resulting resource_dir and filename from Steps 2 and 3 make a valid filepath,
            load data using `load_data()`. Otherwise, continue to Step 5.
        5) Create the url to download data using `create_url()` and continue to Step 6.
        6) Download data from the url created in Step 5 and save to a filepath created from the
            resulting resource_dir and filename from Steps 2 and 3. Continue to Step 7.
        7) Load data from the file created in Step 6 using `load_data()`

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
        site_changed = not np.allclose([latitude, longitude], self.resource_site, atol=1e-6, rtol=0)

        # 0) If site hasn't changed and resource data has already been loaded
        # just return the resource data that was loaded in the setup() method
        if not site_changed and not first_call:
            if self.resource_data is not None:
                return self.resource_data

        # 1) Get the resource data: either the user-provided data (resampled to the
        # simulation timestep) or enough downloaded/loaded years to cover the horizon.
        if bool(self.config.resource_data):
            data = self._resample_to_sim_dt(self.config.resource_data)
        else:
            data = self._acquire_resource_data(latitude, longitude, site_changed)

        # 2) Slice the data to exactly n_timesteps and add start/end times.
        data = conform_resource_data_to_n_timesteps(data, self.n_timesteps)
        data = add_resource_start_end_times(data)
        return data

    def _resample_to_sim_dt(self, data):
        """Resample resource data from its native timestep to the simulation timestep.

        Uses the up/downsampling strategies configured on the resource model.

        Args:
            data (dict): raw resource data at its native timestep.

        Returns:
            dict: resource data resampled to ``self.dt``.
        """
        return resample_resource_data_to_dt(
            data,
            self.dt,
            getattr(self.config, "upsample_method", "time"),
            getattr(self.config, "downsample_method", "mean"),
        )

    def _load_single_year_data(self, latitude, longitude, site_changed, resource_filename=None):
        """Resolve, load, or download one year of resource data.

        Uses the currently configured ``resource_year`` and returns the raw data
        dictionary. This performs Steps 2-7 described in :py:meth:`get_data` for a
        single year (without slicing to the simulation horizon).

        Args:
            latitude (float): latitude corresponding to location for resource data
            longitude (float): longitude corresponding to location for resource data
            site_changed (bool): whether the site location changed from the last call.
            resource_filename (str | Path | None): specific filename to load this year's
                data from. When None, the default naming convention is used.

        Raises:
            ValueError: If data was not successfully downloaded from the API.

        Returns:
            dict: raw resource data for the configured ``resource_year``.
        """
        # check if user provided directory or filename
        provided_filename = bool(resource_filename)
        provided_dir = False if self.config.resource_dir is None else True

        # 2a) check if file exists directly within resource directory
        # 2) Get valid resource_dir with the function check_resource_dir()
        resource_dir = check_resource_dir(data_dir=self.config.resource_dir)
        # 3a) Create a filename if resource_filename was input
        if provided_filename and not site_changed:
            # If a filename was input, use resource_filename as the filename.
            filepath = resource_dir / resource_filename
        # Otherwise, create a filename with the method `create_filename()`.
        else:
            filename = self.create_filename(latitude, longitude)
            filepath = resource_dir / filename
        # if file doesn't exist, continue to Step 2b
        if not filepath.is_file():
            # 2b) check if file exists directly within a subfolder of the resource directory
            # 2) Get valid resource_dir with the function check_resource_dir()
            if (
                provided_dir
                and Path(self.config.resource_dir).parts[-1] == self.config.resource_type
            ):
                resource_dir = check_resource_dir(data_dir=self.config.resource_dir)
            else:
                resource_dir = check_resource_dir(
                    data_dir=self.config.resource_dir, data_subdir=self.config.resource_type
                )
            # 3) Create a filename if resource_filename was input
            if provided_filename and not site_changed:
                # If a filename was input, use resource_filename as the filename.
                filepath = resource_dir / resource_filename
            # Otherwise, create a filename with the method `create_filename()`.
            else:
                filename = self.create_filename(latitude, longitude)
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

        # 4) If the resulting resource_dir and filename from Steps 2 and 3 make a valid
        # filepath, load data using `load_data()` and resample to desired the dt
        if filepath.is_file():
            self.filepath = filepath
            return self._resample_to_sim_dt(self.load_data(filepath))

        # If the filepath (resource_dir/filename) does not exist, download data
        self.filepath = filepath
        # 5) Create the url to download data using `create_url()` and continue to Step 6.
        url = self.create_url(latitude, longitude)
        # 6) Download data from the url created in Step 5 and save to a filepath created from
        # the resulting resource_dir and filename from Steps 2 and 3.
        success = self.download_data(url, filepath)
        if success:
            # 7) Load data from the file created in Step 6 using `load_data()` and resample
            # to the desired dt
            return self._resample_to_sim_dt(self.load_data(filepath))

        else:
            raise ValueError("Did not successfully download resource data.")

    def _acquire_resource_data(self, latitude, longitude, site_changed):
        """Acquire enough resource data to cover the simulation horizon.

        Loads the configured ``resource_year`` and, if a single year does not provide
        enough timesteps to cover ``n_timesteps`` (after resampling), continues loading
        consecutive years until the horizon is covered. Because this is driven by the
        actual number of timesteps in each loaded year, it naturally handles years of
        different lengths -- for example a leap year when leap days are retained.

        Args:
            latitude (float): latitude corresponding to location for resource data
            longitude (float): longitude corresponding to location for resource data
            site_changed (bool): whether the site location changed from the last call.

        Raises:
            ValueError: if not enough resource data is available to cover the horizon
                (a required year is outside the dataset range, a provided list of files
                is exhausted, or a single provided filename cannot cover multiple years).

        Returns:
            dict: a resource data dictionary spanning enough time to cover the horizon.
        """
        resource_filename = self.config.resource_filename
        filename_list = (
            list(resource_filename) if isinstance(resource_filename, list | tuple) else None
        )
        base_year = self.config.resource_year

        yearly_data = []
        total_timesteps = 0
        offset = 0
        try:
            while total_timesteps < self.n_timesteps:
                # Resolve the filename to use for this year, if any
                if filename_list is not None:
                    if offset >= len(filename_list):
                        msg = (
                            f"{type(self).__name__} was given {len(filename_list)} resource "
                            f"file(s) covering only {total_timesteps} timesteps, fewer than the "
                            f"{self.n_timesteps} timesteps required by the simulation horizon. "
                            "Provide additional resource files or shorten the horizon."
                        )
                        raise ValueError(msg)
                    year_filename = filename_list[offset]
                elif offset == 0:
                    year_filename = resource_filename or None
                else:
                    # A single provided filename cannot supply additional years
                    if resource_filename:
                        msg = (
                            f"{type(self).__name__} cannot satisfy a multi-year simulation "
                            "horizon from a single resource_filename. Provide a list of "
                            "filenames (one per consecutive year), or remove resource_filename "
                            "so the required years can be downloaded."
                        )
                        raise ValueError(msg)
                    year_filename = None

                # Advance the resource year for years after the first
                if offset > 0:
                    if not isinstance(base_year, int):
                        msg = f"Resource year must be an integer, {base_year} was given."
                        raise ValueError(msg)
                    try:
                        # Setting resource_year runs the config validator, which raises
                        # if the year is outside the range supported by this dataset.
                        self.config.resource_year = base_year + offset
                    except (ValueError, TypeError) as e:
                        msg = (
                            f"Not enough resource data available for {type(self).__name__} to "
                            f"cover the requested simulation horizon of {self.n_timesteps} "
                            f"timesteps. Year {base_year + offset} is outside the range "
                            "supported by this dataset."
                        )
                        raise ValueError(msg) from e

                year_data = self._load_single_year_data(
                    latitude, longitude, site_changed, year_filename
                )
                yearly_data.append(year_data)
                total_timesteps += self._resource_length(year_data)
                offset += 1
        finally:
            # Restore the configured resource year, which is advanced above for multi-year loads
            if isinstance(base_year, int):
                self.config.resource_year = base_year

        return concatenate_resource_years(yearly_data)

    @staticmethod
    def _resource_length(data):
        """Return the number of timesteps in a resource data dictionary."""
        for key in ("year", "month", "day", "hour", "minute"):
            if key in data:
                return len(np.asarray(data[key]))
        # Fall back to the first array-like value
        for value in data.values():
            if isinstance(value, np.ndarray | list | tuple) and not isinstance(value, str | bytes):
                return len(value)
        return 0

    def compute(self, inputs, outputs, discrete_inputs, discrete_outputs):
        # update the resource data based on the input latitude and longitude
        data = self.get_data(inputs["latitude"][0], inputs["longitude"][0], first_call=False)
        # update the stored resource data and site
        self.resource_site = [inputs["latitude"][0], inputs["longitude"][0]]
        self.resource_data = data
        discrete_outputs[f"{self.config.resource_type}_resource_data"] = data
