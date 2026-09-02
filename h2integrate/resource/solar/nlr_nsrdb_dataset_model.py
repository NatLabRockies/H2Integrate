import re

import numpy as np
import pandas as pd
from rex import NSRDBX
from attrs import field, define, validators

from h2integrate.resource.resource_base_hpc import ResourceBaseH5Model, ResourceBaseH5Config
from h2integrate.resource.solar.solar_resource_base import SolarResourceBase


@define(kw_only=True)
class NSRDBDatasetH5Config(ResourceBaseH5Config):
    """Configuration class to access solar resource data from NLR datasets.
    Resource data is available from 1998-2025.

    Args:
        resource_year (int): Year to use for resource data.
            Must been between 1998 and 2025 (inclusive).

    Attributes:
        dataset_desc (str): description of the dataset, used in file naming.
            For this dataset, the `dataset_desc` is "nsrdb_current".
        resource_type (str): type of resource data downloaded, used in folder naming.
            For this dataset, the `resource_type` is "solar".
        valid_intervals (list[int]): time interval(s) in minutes that resource data can be
            downloaded in. For this dataset, `valid_intervals` are 30 and 60 minutes.
    """

    resource_year: int = field(converter=int, validator=(validators.ge(1998), validators.le(2025)))
    dataset_desc: str = "nsrdb_current"
    resource_type: str = "solar"
    valid_intervals: list[int] = field(factory=lambda: [30, 60])


class NSRDBDatasetH5(SolarResourceBase, ResourceBaseH5Model):
    def setup(self):
        self.units_translation = {
            "Celsius": "degC",
            "W/m2": "W/m**2",
            "degrees": "deg",
            "%": "percent",
            "atm-cm": "cm/atm",  # unsure - unit for Ozone
            "micron": "um",
            "percent of filled timesteps": "percent",
        }

        self.columns_translation = {
            "air_temperature": "temperature",
            "surface_pressure": "pressure",
            "total_precipitable_water": "precipitable_water",
        }

        self.hpc_path = "/datasets/NSRDB/current/nsrdb_{year}.h5"
        self.hsds_path = "/nrel/NSRDB/current/nsrdb_{year}.h5"

        # create the input dictionary for NSRDBDatasetH5Config
        resource_specs = self.helper_setup_method()

        self.config = NSRDBDatasetH5Config.from_dict(
            resource_specs,
            additional_cls_name=self.__class__.__name__,
        )

        self.dt_min = min(self.config.valid_intervals)

        super().setup()

        # The rest of this method is the exact same as whats used in the API resource models

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

        # add resource data dictionary as an output
        self.add_discrete_output(
            "solar_resource_data", val=data, desc="Dict of solar resource data"
        )

    def load_data_from_dataset(self, latitude, longitude):
        """Load resource data from an .h5 dataset.

        Args:
            latitude (float): latitude corresponding to location for resource data
            longitude (float): longitude corresponding to location for resource data

        Returns:
            tuple[dict,dict]: tuple of resource data formatted as [timeseries data, meta data]
        """

        # NOTE: if more solar resource datasets are added,
        # this method could likely be moved into a baseclass

        # Get filepath of the .h5 dataset
        dataset_path = self.create_dataset_filepath()

        # Load the dataset from the .h5 file using the NSRDBX resource extraction tool
        with NSRDBX(dataset_path, hsds=self.config.use_hsds) as res:
            # Get the site_gid from the input latitude/longitude
            site_gid = res.lat_lon_gid((latitude, longitude))
            # Extract timeseries data, unit information, and meta data
            site_meta = res.meta.loc[int(site_gid)].to_dict()
            time_index = res.time_index
            resource_units = res.resource.units

            resource_data = {c: res[c, :, int(site_gid)] for c in res.resource_datasets}
        res.close()

        site_data = {
            "id": int(site_gid),
            "site_tz": float(site_meta["timezone"]),
            "data_tz": 0,  # data is in UTC
            "site_lat": float(site_meta["latitude"]),
            "site_lon": float(site_meta["longitude"]),
            "elevation": float(site_meta["elevation"]),
            "filepath": str(dataset_path),
            # Below is extra data (not available in API calls)
            "resource_year": self.config.resource_year,
            "country": site_meta.get("country"),
            "state": site_meta.get("state"),
            "county": site_meta.get("county"),
        }

        # Rename units as necessary (renaming to OpenMDAO compatible formatting)
        data_units = {
            self.columns_translation.get(k, k): self.units_translation.get(v, v)
            for k, v in resource_units.items()
            if k in resource_data and isinstance(v, str)
        }
        # Rename resource data keys in the resource_data and resource_units dictionaries
        # to align with the resource data naming in the wind resource baseclass
        for old_key, new_key in self.columns_translation.items():
            if old_key in resource_data:
                resource_data[new_key] = resource_data.pop(old_key)
                resource_units[new_key] = resource_units.pop(old_key)

        # Create fill-flag dictionary
        if "cloud_type" in data_units:
            cloud_type_mapper = data_units.pop("cloud_type")
            fill_flag_mapper = {
                cloud_type.split(":")[0].replace("'", "").strip(): int(
                    cloud_type.split(":")[1].strip()
                )
                for cloud_type in cloud_type_mapper.split(",")
            }
        else:
            fill_flag_mapper = resource_units.get("cloud_type", {})

        # Update the time interval based on the data for csv filenaming
        data_dt = res.time_index[1] - res.time_index[0]
        self.dt_min = int(data_dt.seconds / 60)

        if self.config.save_to_csv:
            # convert the timeseries data to a dataframe
            data_df = pd.DataFrame(resource_data, index=time_index)
            data_df.index.name = "time"
            # create the filename for the csv
            csv_filename = self.create_csv_filename(site_gid, latitude, longitude)
            # save before units-correction in case theres a future change in units-correction
            self.save_to_csv(data_df, site_data, data_units, fill_flag_mapper, csv_filename)

        # Convert the time index to a dictionary
        time_cols = ["year", "month", "day", "hour", "minute"]
        time_dict = {k: getattr(time_index, k).values for k in time_cols}

        # Ensure that time-series data are numpy arrays
        data_dict = {k: np.array(v) for k, v in resource_data.items()}

        # Combine the time information and timeseries resource data
        data_dict |= time_dict

        # Update data to the units defined in the baseclass
        data_dict, data_units = self.compare_units_and_correct(data_dict, data_units)

        meta_data = site_data | {"fill_flag_mapper": fill_flag_mapper} | {"units": data_units}

        # Create the meta-data dictionary
        return data_dict, meta_data

    def save_to_csv(self, data_df, site_data, data_units, fill_flag_mapper, csv_filename):
        """Save data extracted from the dataset to a csv file for a given site.

        Args:
            data_df (pd.DataFrame): timeseries resource data
            site_data (dict): dictionary of site metadata
            data_units (dict): dictionary of data columns and the corresponding units
            fill_flag_mapper (dict): dictionary of cloud/sky types and their flag values
            csv_filename (str): filename of the csv file created with ``create_csv_filename()``
        """

        # Create the full filepath for the csv file
        fpath = self.config.csv_output_dir / csv_filename

        # Add "Flag" to the header columns for fill-flag mapping
        fill_flag_mapper_csv = {f"{k} Flag": int(v) for k, v in fill_flag_mapper.items()}
        header_dict = site_data | fill_flag_mapper_csv
        # Add "Units" to the header columns for units
        header_dict |= {f"{k} Units": v for k, v in data_units.items()}
        # Convert unit info, fill flag info, and site metadata to a header string
        header_line1 = ",".join(f"{k}" for k, _ in header_dict.items())
        header_line2 = ",".join(f"{v}" for _, v in header_dict.items())
        header = header_line1 + "\n" + header_line2 + "\n"
        with fpath.open(mode="w", encoding="utf-8") as f:
            # Write the header to a csv file
            f.write(header)

        # Add the timeseries data to the remaining rows of the csv file
        data_df.to_csv(fpath, encoding="utf-8", mode="a")

    def load_data_from_csv(self, fpath):
        """Load resource data that was pulled from an .h5 dataset and saved to a csv file

        Args:
            fpath (Path | str): Filepath of a pre-saved csv file containing resource data.

        Returns:
            tuple[dict,dict]: tuple of resource data formatted as [timeseries data, meta data]
        """

        # NOTE: if more solar resource datasets are added,
        # this method could likely be moved into a baseclass

        # Load the resource time-series information
        data = pd.read_csv(fpath, header=2)

        # Load the resource meta-data (units, site information, etc)
        header = pd.read_csv(fpath, nrows=2, header=None)
        header_keys = header.iloc[0].to_list()
        header_vals = header.iloc[1].to_list()
        header_dict = dict(zip(header_keys, header_vals))

        # Convert the "time" column to a dictionary of time keys
        time_data = pd.DatetimeIndex(data["time"])
        time_cols = ["year", "month", "day", "hour", "minute"]
        time_dict = {k: getattr(time_data, k).values for k in time_cols}

        # Create a dictionary of units for each column of resource data
        data_units = {k.replace(" Units", ""): v for k, v in header_dict.items() if " Units" in k}
        # Create a dictionary of fill flag information
        fill_flag_mapper = {
            k.replace(" Flag", ""): v for k, v in header_dict.items() if " Flag" in k
        }
        # Extract site metadata from the header information
        site_data = {
            k: v
            for k, v in header_dict.items()
            if k.replace(" Units", "") not in data_units
            and k.replace(" Flag", "") not in fill_flag_mapper
        }

        # All the header data is loaded as strings, get the keys numeric meta data
        numeric_site_data = [
            k for k, v in site_data.items() if bool(re.fullmatch(r"[+-]?\d+(\.\d+)?", str(v)))
        ]
        int_numeric_site_data = [
            k
            for k, v in site_data.items()
            if bool(re.fullmatch(r"[+-]?\d+", str(v))) or bool(re.fullmatch(r"[+-]?\d+", v))
        ]

        # Convert the meta-data with numeric values to their corresponding numeric type
        site_data |= {k: float(v) for k, v in site_data.items() if k in numeric_site_data}
        site_data |= {k: int(v) for k, v in site_data.items() if k in int_numeric_site_data}

        # Convert the timeseries data to a dictionary
        data_dict = {
            c: np.array(data[c].astype(float).values) for c in data.columns.to_list() if c != "time"
        }

        # Add the time information to the timeseries data dictionary
        data_dict |= time_dict

        # Convert the data to standardized units defined in the solar resource baseclass
        data_dict, data_units = self.compare_units_and_correct(data_dict, data_units)

        meta_data = site_data | {"fill_flag_mapper": fill_flag_mapper}

        # Update the meta-data to include the filepath of this csv file
        meta_data["dataset_filepath"] = meta_data.pop("filepath")
        meta_data["filepath"] = str(fpath)

        return data_dict, meta_data | {"units": data_units}
