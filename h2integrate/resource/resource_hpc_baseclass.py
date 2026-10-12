import warnings
from pathlib import Path

import numpy as np
import pandas as pd
import openmdao.api as om
from attrs import field, define

from h2integrate.core.utilities import BaseConfig
from h2integrate.core.file_utils import check_resource_dir
from h2integrate.resource.utilities.time_tools import process_leap_day, add_resource_start_end_times


@define(kw_only=True)
class ResourceBaseH5Config(BaseConfig):
    """Base configuration class for resource data loaded from an .h5 file.

    Subclasses should include the following attributes that are not set in this BaseConfig:

        - **resource_year** (*int*): Year to download resource data for.
            Recommended to have a validator for upper and lower limits.

        - **valid_intervals** (*list[int]*): time interval(s) in minutes that resource data can be
            downloaded in.

    Note:
        Attributes should be updated in subclasses and should not be modifiable by the user.
        These should be inherit attributes of the subclass.

    Args:
        latitude (float): latitude to download resource data for.
        longitude (float): longitude to download resource data for.
        timezone (float | int, optional): timezone to output data in.
            May be used to determine whether to download data in UTC or local timezone.
        save_to_csv (bool, optional): If True, save data loaded from the dataset to a csv.
            If this is true,  then data may be loaded from a csv file if it exists
            (even if ``load_from_csv`` is False). Defaults to False.
        load_from_csv (bool, optional): If True, check if a csv file was pre-saved with the
            resource data for a given site and if so, load data from the csv file.
            Defaults to False.
        csv_output_dir (Path | str | None, optional): The directory to save csv files to or
            load csv files from. Only used if ``save_to_csv`` or ``load_from_csv`` is True.
            Defaults to None.
        include_leap_day (bool, optional): Whether to include leap day if the resource year is a
            leap year. If True, please ensure that ``n_timesteps`` reflects this. Defaults to False.
        use_hsds (bool, optional): If True, load data from an HSDS server. Otherwise,
            load data from the NLR HPC. Defaults to False.


    Attributes:
        dataset_desc (str): description of the dataset, used in file naming.
            Should be updated in a subclass.
        resource_type (str): type of resource data downloaded, used in folder naming.
            Should be updated in a subclass.
    """

    latitude: float = field()
    longitude: float = field()

    timezone: int | float = field()

    # Export file info
    save_to_csv: bool = field(default=False, kw_only=True)
    load_from_csv: bool = field(default=False, kw_only=True)
    csv_output_dir: Path | str | None = field(default=None, kw_only=True)

    include_leap_day: bool = field(default=False)
    use_hsds: bool = field(default=False, kw_only=True)

    # Attributes to be populated by parent classes
    dataset_desc: str = field(default="default", init=False)
    resource_type: str = field(default="none", init=False)

    def get_csv_dir(self, provided_dir):
        """Check for a valid folder to save or load csv files from. By default,
        this method prioritizes using sub-folders per resource type if the
        csv output directory is not user provided.

        Args:
            provided_dir (bool): True is ``csv_output_dir`` was user provided.

        Returns:
            Path: folder to load/save csv files from
        """
        # Get valid resource_dir with the function check_resource_dir()
        csv_dir = check_resource_dir(data_dir=self.csv_output_dir)

        # provided csv_directory with resource-specific subfolder included
        if provided_dir and Path(csv_dir).parts[-1] == self.resource_type:
            return csv_dir

        # csv directory has pre-existing resource-specific subfolder
        if (csv_dir / self.resource_type).is_dir():
            return csv_dir / self.resource_type

        n_csv_files = sum(
            1 for f in Path(csv_dir).glob("*.csv") if self.dataset_desc in f.name and f.is_file()
        )
        if n_csv_files > 0:
            # csv files already exist in csv folder, don't use resource-specific subfolders
            return csv_dir

        # By default, use csv directory resource-specific subfolders
        csv_dir = check_resource_dir(data_dir=csv_dir, data_subdir=self.resource_type)
        return csv_dir

    def __attrs_post_init__(self):
        provided_dir = False if self.csv_output_dir is None else True

        csv_usage_enabled = self.save_to_csv or self.load_from_csv

        if csv_usage_enabled:
            csv_dir = self.get_csv_dir(provided_dir)
            self.csv_output_dir = csv_dir

        if csv_usage_enabled and not provided_dir:
            msg = (
                "Resource data can be loaded or saved to a csv file but `csv_dir` was not "
                f"provided. Csv files will be loaded or saved to folder: {csv_dir}"
            )
            warnings.warn(msg, UserWarning, stacklevel=3)

        if int(self.timezone) != 0:
            msg = (
                "Data from HPC datasets is natively in UTC, please set the ``timezone`` "
                f"to 0 for these resource models instead of {self.timezone}"
            )
            raise NotImplementedError(msg)

            # NOTE: below warning can be used in the future when timeseries data is rolled
            # msg = (
            #     "Data from HPC datasets is natively in UTC. Timeseries data will be rolled to "
            #     "local timezone (in standard time), but time data (year, month, etc) will not "
            #     "be rolled to prevent unexpected behavior in performance models."
            # )
            # warnings.warn(msg, UserWarning, stacklevel=3)


class ResourceBaseH5Model(om.ExplicitComponent):
    """Base model for downloading resource data from API calls or loading resource
    data for a single site from a file.

    Attributes:
        resource_data (dict | None): resource data that is created in ``setup()`` method.
        dt (int): timestep in seconds.
        n_timesteps (int): number of timesteps in a simulation
        config (object): configuration class that inherits ResourceBaseH5Config.
        resource_site (list[float]): latitude and longitude of current resource data
        hpc_path (str): folder containing the subclass resource dataset on the HPC
        hsds_path (str): folder containing the subclass resource dataset on an HSDS server
        dt_min (int): minimum dataset timestep in minutes. Set in a subclass
        interval (int): simulation timestep interval in minutes (based on dt_min and dt).
            Set in a subclass.

    Note:
        Attributes `hpc_path`, `hsds_path`, `dt_min`, and `config` should be set in a subclass.

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
        self.lat_lon_fmt = ".3f"  # format for lat/lon formatting in csv filenaming

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

        # default timezone to UTC because 'timezone' was removed from the plant config schema
        resource_specs.setdefault("timezone", sim_config.get("timezone", 0))

        return resource_specs

    def search_for_csv_file_from_lat_lon(self, latitude, longitude):
        """Search the directory specified in `config.csv_output_dir` for a csv
        file that follows the naming convention in ``create_csv_filename()``. Looks for a file
        whose name contains the following string:

        "{latitude}_{longitude}_{resource_year}_{dataset_desc}"

        Args:
            latitude (float): latitude corresponding to location for resource data
            longitude (float): longitude corresponding to location for resource data

        Note:
            latitude and longitude for filenaming are formatted based on the attribute
            ``lat_lon_fmt``

        Raises:
            UserWarning: If multiple files are found that match the location and resource dataset

        Returns:
            Path | None: If a csv file is found with a matching name, returns the entire
            filepath to that file. Returns None is no csv files are found that match the file format
        """
        loc_str = f"{latitude:{self.lat_lon_fmt}}_{longitude:{self.lat_lon_fmt}}"
        filename_desc = f"{loc_str}_{self.config.resource_year}_{self.config.dataset_desc}"
        close_match_files = [
            f for f in Path(self.config.csv_output_dir).glob("*.csv") if filename_desc in f.name
        ]

        if not close_match_files:
            return None
        if len(close_match_files) == 1:
            return close_match_files[0]

        chosen_file = close_match_files[0]
        msg = (
            f"Found {len(close_match_files)} potential csv files for location "
            f"({latitude}, {longitude}) with dataset description of {filename_desc}. "
            f"Files found were: \n{close_match_files} \n. Running resource model "
            f"with file {chosen_file}"
        )
        warnings.warn(msg, UserWarning, stacklevel=3)
        return chosen_file

    def create_csv_filename(self, site_gid, latitude, longitude):
        """Create default filename to save loaded data to. The filename format is:

        "{site_gid}_{latitude}_{longitude}_{resource_year}_{dataset_desc}_{dt_min}min_utc_tz.csv"
        where "utc" refers to the dataset timezone is in UTC.

        Args:
            site_gid (int): dataset specific site identification number
            latitude (float): latitude corresponding to location for resource data
            longitude (float): longitude corresponding to location for resource data

        Note:
            latitude and longitude for filenaming are formatted based on the attribute
            ``lat_lon_fmt``

        Returns:
            str: filename for resource data to be saved to or loaded from.
        """

        end_name = (
            f"{self.config.resource_year}_{self.config.dataset_desc}_{self.dt_min}min_utc_tz.csv"
        )
        loc_str = f"{int(site_gid)}_{latitude:{self.lat_lon_fmt}}_{longitude:{self.lat_lon_fmt}}"
        filename = f"{loc_str}_{end_name}"
        return filename

    def create_dataset_filepath(self):
        # NOTE: if other dataset models are added that dont use
        # the resource year in the filename, we will need to put this
        # method in individual subclasses

        if self.config.use_hsds:
            # Using HSDS server
            dataset_path = self.hsds_path.format(year=self.config.resource_year)
            return Path(dataset_path)

        # Pulling from super computer
        dataset_path = Path(self.hpc_path.format(year=self.config.resource_year))

        if dataset_path.exists():
            return dataset_path

        msg = (
            f"Dataset file {dataset_path} is not a valid filepath. Please ensure you're logged "
            "onto the NLR supercomputer or, if using an hsds setup, set `use_hsds` to True "
            "and provide the `hsds_kwargs` in the input configuration class. If this error "
            "is unexpected, please open an issue on the H2Integrate GitHub repo."
        )
        raise FileNotFoundError(msg)

    def load_data_from_dataset(self, latitude, longitude):
        """Load resource data from an .h5 dataset. This method should do the following:

        1. Create the dataset filepath

        2. Load the dataset with the corresponding resource extraction class

        3. Get the site_gid from the input latitude/longitude

        4. Extract timeseries data, unit information, and meta data from the dataset

        5. If saving to a csv file is enabled, then do the following two things:

            a. Create the filename for the csv by calling ``create_csv_filename()``
            b. Save the data to a csv by calling ``save_to_csv()``.

        6. Update data to use the same naming convention and units as specified in
        the resource-specific baseclass.

        Args:
            latitude (float): latitude corresponding to location for resource data
            longitude (float): longitude corresponding to location for resource data

        Raises:
            NotImplementedError: if this method is not implemented in a subclass

        Returns:
            tuple[dict,dict]: tuple of resource data formatted as [timeseries data, meta data]
        """
        raise NotImplementedError("This method should be implemented in a subclass.")

    def load_data_from_csv(self, fpath):
        """Load resource data from a pre-saved csv file. This method should do the following:

        1. Load the resource data, extracting both units information meta data from the header,
        and timeseries information from the remaining rows.

        2. Extract units information from the meta-data.

        3. Convert numeric meta-data information from strings to floats or integers.

        4. Update timeseries data to use the same naming convention and units as specified in
        the resource-specific baseclass.

        Args:
            fpath (Path | str): Filepath of a pre-saved csv file containing resource data.

        Raises:
            NotImplementedError: if this method is not implemented in a subclass

        Returns:
            tuple[dict,dict]: tuple of resource data formatted as [timeseries data, meta data]
        """
        raise NotImplementedError("This method should be implemented in a subclass.")

    def sample_data_to_interval(self, data):
        """Downsample resource data to ``self.interval``.
        Assumed that this is called before any leap-day processing

        Args:
            data (dict): dictionary of timeseries resource data

        Returns:
            dict: dictionary of timeseries resource data at the
            timestep specified by ``self.interval``
        """
        time_keys = ["year", "month", "day", "hour", "minute", "second"]
        time_dict = {k: data.get(k) for k in time_keys if k in data}
        time_df = pd.to_datetime(time_dict)
        # Assumed that data interval is not less than 1 min, corresponds with
        # assumptions elsewhere in model
        data_n_timesteps = len(time_df)
        dt_minutes = int((time_df.iloc[1] - time_df.iloc[0]).seconds / 60)  # min
        if len(time_df) == self.n_timesteps:
            return data
        if dt_minutes == self.interval:
            return data
        if dt_minutes > self.interval:
            # This should not happen because of the logic of calculating interval
            # But throw an error just in case
            msg = (
                f"Resource data cannot be sampled to an interval of {self.interval} minutes "
                f"when resource data has a timestep of {dt_minutes} minutes"
            )
            raise ValueError(msg)

        # At this point we have to downsample the data
        year = self.config.resource_year
        is_leap = (year % 100 == 0 and year % 400 == 0 and year % 4 == 0) or (
            year % 4 == 0 and year % 100 != 0
        )
        remaining_timesteps = data_n_timesteps % self.n_timesteps != 0
        step = data_n_timesteps // self.n_timesteps
        if is_leap and remaining_timesteps:
            # Remaining timesteps OK if leap year
            i_end = data_n_timesteps // step
        else:
            i_end = self.n_timesteps
        i = 0
        if self.interval == 60:
            # If interval is 60, then use data at the half-hour mark
            if time_df.iloc[0].minute != 30:
                while time_df.iloc[i].minute < 30:
                    i += 1
        # Downsample data to the specified interval
        time_slice = slice(i, data_n_timesteps, step)
        data_sliced = {k: v[time_slice][:i_end] for k, v in data.items()}
        return data_sliced

    def get_data(self, latitude, longitude, first_call=True):
        """Get resource data to handle any of the expected inputs. This method does the following:

        1. If this is not the first resource call of the simulation, check if latitude and longitude
        inputs are different than the previous latitude and longitude values. If resource data
        has not been already loaded for the site, continue to Step 2.

        2. If either saving or loading from a csv file, check if a csv file matching
        either the sitelat/lon exists. If a csv file is found, load data from
        the csv file and continue to Step 4. Otherwise, continue to Step 3.

        3. Load data from the dataset, continue to Step 4.

        4. Finalize and format data: sample the data to the simulation timestep (``interval``),
        remove leap day data if necessary, add simulation start and end times to the
        data dictionary.

        Args:
            latitude (float): latitude corresponding to location for resource data
            longitude (float): longitude corresponding to location for resource data
            first_call (bool): True if called from `setup()` method, False if called from
                ``compute()`` method to prevent unnecessary reloading of data.

        Returns:
            dict: resource data in the format expected by the subclass.
        """

        site_changed = not np.allclose([latitude, longitude], self.resource_site, atol=1e-6, rtol=0)

        # 1) If site hasn't changed and resource data has already been loaded
        # just return the resource data that was loaded in the setup() method
        if (not first_call) and (self.resource_data is not None):
            if not site_changed:
                return self.resource_data

        # Load data from either a pre-saved csv or load it from the dataset
        csv_file = None
        if self.config.load_from_csv or self.config.save_to_csv:
            # 2. Check to see if a csv file exists
            csv_file = self.search_for_csv_file_from_lat_lon(latitude, longitude)
        if csv_file is not None:
            # 2 cont. Found csv file and csv file usage is enabled, load data from the csv
            data, meta_data = self.load_data_from_csv(csv_file)
        else:
            # 3. csv usage is not enabled or csv file was not found for this site
            # load data from the dataset
            data, meta_data = self.load_data_from_dataset(latitude, longitude)

        # 4. Finalize data formatting

        # Sample data to the proper timestep interval
        data = self.sample_data_to_interval(data)
        # Remove leap day (if necessary)
        # data = self.process_leap_day(data)
        data = process_leap_day(data, self.config.include_leap_day, self.n_timesteps)
        # Add start/end times to the resource data
        data = add_resource_start_end_times(data)

        # Return timeseries data and meta-data
        return data | meta_data

    def compute(self, inputs, outputs, discrete_inputs, discrete_outputs):
        # Update the resource data based on the input site information
        data = self.get_data(
            inputs["latitude"][0],
            inputs["longitude"][0],
            first_call=False,
        )

        # Update the stored resource data and site
        self.resource_site = [inputs["latitude"][0], inputs["longitude"][0]]
        self.resource_data = data
        discrete_outputs[f"{self.config.resource_type}_resource_data"] = data
