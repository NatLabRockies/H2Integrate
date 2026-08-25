import re
from pathlib import Path

import numpy as np
import pandas as pd
from rex import WindX
from attrs import field, define, validators

from h2integrate.resource.resource_base_hpc import ResourceBaseH5Config
from h2integrate.resource.wind.wind_resource_base import WindResourceBaseH5Model


# Maybe look at MultiFileNSRDBX and MultiTimeNSRDB and MultiYearNSRDBX


@define(kw_only=True)
class WTKHRRRMETDatasetH5Config(ResourceBaseH5Config):
    # double-check years, redo name, check intervals
    resource_year: int = field(converter=int, validator=(validators.ge(2015), validators.le(2025)))
    dataset_desc: str = "hrrr_met_v1"
    resource_type: str = "wind"

    valid_intervals: list[int] = field(factory=lambda: [60])


class WTKHRRRMETDatasetH5(WindResourceBaseH5Model):
    def setup(self):
        self.units_translation = {
            "C": "degC",
            "m s-1": "m/s",
            "degree from N": "deg",
            "W m-2": "W/m**2",
            "kg kg-1": "unitless",
            "mm hr-1": "mm/h",
        }

        self.columns_translation = {
            "windspeed": "wind_speed",
            "winddirection": "wind_direction",
            # "snow_depth"
            # "total_precipitable_water": "precipitable_water",
        }

        self.hpc_path = "/datasets/WIND/HRRR_MET_Toolkit/v1.0.0/hrrr_nat_f02_conus_{year}.h5"
        self.hsds_path = "/nrel/WIND/HRRR_MET_Toolkit/v1.0.0/hrrr_nat_f02_conus_{year}.h5"

        # Below is normally done in a baseclass
        resource_specs = self.helper_setup_method()

        # create the resource config
        self.config = WTKHRRRMETDatasetH5Config.from_dict(
            resource_specs,
            additional_cls_name=self.__class__.__name__,
        )

        self.dt_min = min(self.config.valid_intervals)

        super().setup()

        # Below is normally done in a subclass

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
        data = self.get_data(self.config.site_gid, self.config.latitude, self.config.longitude)

        self.resource_data = data
        # add resource data dictionary as an out
        self.add_discrete_output("wind_resource_data", val=data, desc="Dict of solar resource data")

    def create_dataset_filepath(self):
        # TODO: move to baseclass?
        if self.config.use_hsds:
            dataset_path = self.hsds_path.format(year=self.config.resource_year)
            return Path(dataset_path)
        # Pulling from Super computer
        dataset_path = Path(self.hpc_path.format(year=self.config.resource_year))

        if dataset_path.exists():
            return dataset_path

        msg = (
            f"Dataset flie {dataset_path} is not a valid filepath. Please ensure you're logged "
            "onto the NLR supercomputer or, if using an hsds setup, set `use_hsds` to True "
            "and provide the `hsds_kwargs` in the input configuration class. If this error "
            "is unexpected, please contact an H2Integrate developer"
        )
        raise FileNotFoundError(msg)

    def save_to_csv(self, data_df, site_data, data_units, csv_filename):
        fpath = self.config.csv_output_dir / csv_filename

        # fill_flag_mapper_csv = {f"{k} Flag": int(v) for k, v in fill_flag_mapper.items()}
        # site_data_str = {k:str(v) for k,v in site_data.items()}
        header_dict = site_data | {f"{k} Units": v for k, v in data_units.items()}
        header_line1 = ",".join(f"{k}" for k, _ in header_dict.items())
        header_line2 = ",".join(f"{v}" for _, v in header_dict.items())
        header = header_line1 + "\n" + header_line2 + "\n"
        with fpath.open(mode="w", encoding="utf-8") as f:
            f.write(header)
        data_df.to_csv(fpath, encoding="utf-8", mode="a")

    def load_data_from_dataset(self, latitude, longitude, site_gid=None):
        # probably in resource-specific baseclass
        # called from overall resource baseclass
        dataset_path = self.create_dataset_filepath()

        with WindX(dataset_path, hsds=self.config.use_hsds) as res:
            if site_gid is None:
                site_gid = res.lat_lon_gid((latitude, longitude))
            # NOTE: if site_gid is input, then should use the lat/lon
            # from the meta data instead for csv filenaming?
            site_meta = res.meta.loc[int(site_gid)].to_dict()
            time_index = res.time_index
            resource_units = res.resource.units

            resource_data = {c: res[c, :, int(site_gid)] for c in res.resource_datasets}
        res.close()  # this should be OK, but test it out

        # Afterwards, we should slice down the resource data based on the interval
        site_data = {
            "id": int(site_gid),
            "site_tz": float(site_meta["timezone"]),
            "data_tz": 0,  # data is in UTC
            "site_lat": float(site_meta["latitude"]),
            "site_lon": float(site_meta["longitude"]),
            "elevation": float(site_meta["elevation"]),
            "filepath": str(dataset_path),
            # Below is extra
            "resource_year": self.config.resource_year,
            "country": site_meta.get("country"),
            "state": site_meta.get("state"),
            "county": site_meta.get("county"),
        }

        # Rename data columns
        # column_rename_mapper = {}
        # for key,val in resource_data.items():
        for oldname, newname in self.columns_translation.items():
            # bool(re.fullmatch(r"windspeed_\d+m", txt))
            key_renames = {
                k: k.replace(oldname, newname) for k in list(resource_data.keys()) if oldname in k
            }

            for old_key, new_key in key_renames.items():
                resource_data[new_key] = resource_data.pop(old_key)
                resource_units[new_key] = resource_units.pop(old_key)

        # Rename units as necessary
        data_units = {
            k: self.units_translation.get(v, v)
            for k, v in resource_units.items()
            if k in resource_data and isinstance(v, str)
        }

        data_df = pd.DataFrame(resource_data, index=time_index)
        # data_df = data_df.rename(columns=self.columns_translation)
        data_df.index.name = "time"

        if self.config.save_to_csv:
            # save before units-correction (idk why I'm doing it this way)
            csv_filename = self.create_csv_filename(site_gid, latitude, longitude)
            # get directory to save to
            self.save_to_csv(data_df, site_data, data_units, csv_filename)

        time_cols = ["year", "month", "day", "hour", "minute"]
        time_dict = {k: getattr(time_index, k).values for k in time_cols}
        data_dict = {
            c: np.array(data_df[c].astype(float).values) for c in data_df.columns.to_list()
        }

        data_dict |= time_dict

        data_dict, data_units = self.compare_units_and_correct(data_dict, data_units)

        # resource_data = data_dict | site_data | {"fill_flag": fill_flag_mapper}
        meta_data = site_data

        # NOTE: should we include data_units in the resource data?
        return data_dict, meta_data

    def load_data_from_csv(self, fpath):
        # probably in resource-specific baseclass
        # called from overall resource baseclass

        data = pd.read_csv(fpath, header=2)
        header = pd.read_csv(fpath, nrows=2, header=None)
        header_keys = header.iloc[0].to_list()
        header_vals = header.iloc[1].to_list()
        header_dict = dict(zip(header_keys, header_vals))

        time_data = pd.DatetimeIndex(data["time"])
        time_cols = ["year", "month", "day", "hour", "minute"]
        time_dict = {k: getattr(time_data, k).values for k in time_cols}

        data_units = {k.replace(" Units", ""): v for k, v in header_dict.items() if " Units" in k}

        site_data = {
            k: v for k, v in header_dict.items() if k.replace(" Units", "") not in data_units
        }

        numeric_site_data = [
            k for k, v in site_data.items() if bool(re.fullmatch(r"[+-]?\d+(\.\d+)?", str(v)))
        ]

        int_numeric_site_data = [
            k
            for k, v in site_data.items()
            if bool(re.fullmatch(r"[+-]?\d+", str(v))) or bool(re.fullmatch(r"[+-]?\d+", v))
        ]

        site_data |= {k: float(v) for k, v in site_data.items() if k in numeric_site_data}
        site_data |= {k: int(v) for k, v in site_data.items() if k in int_numeric_site_data}

        data_dict = {
            c: np.array(data[c].astype(float).values) for c in data.columns.to_list() if c != "time"
        }

        data_dict |= time_dict

        data_dict, data_units = self.compare_units_and_correct(data_dict, data_units)

        site_data["dataset_filepath"] = site_data.pop("filepath")
        site_data["filepath"] = str(fpath)
        # NOTE: should we include data_units in the resource data?
        return data_dict, site_data
