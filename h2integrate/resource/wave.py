from pathlib import Path

import pandas as pd
import openmdao.api as om
import PySAM.WaveFileReader as WaveFileReader
from attrs import field, define

from h2integrate.core.utilities import BaseConfig
from h2integrate.core.file_utils import get_path, find_file


@define(kw_only=True)
class WaveResourceConfig(BaseConfig):
    """
    Args:
        resource_dir (str | Path, optional): Folder to save resource files to or
            load resource files from. Defaults to "".
        resource_filename (str, optional): Filename to save resource data to or load
            resource data from. Defaults to None.
        resource_year (int, optional): Year of the resource data. Used to generate
            timestamps when interpolating sub-hourly data. Defaults to 2010.
    """

    resource_dir: Path | str | None = field(default=None)
    resource_filename: Path | str = field(default="")
    resource_year: int = field(default=2010, converter=int)


class WaveResource(om.ExplicitComponent):
    """A resource component for processing wave data from a CSV file.

    This component reads a CSV file containing wave data, processes it,
    and outputs hourly significant wave height and energy period values for a full
    year (8760 hours). The input file is expected to follow the DOE WPTO wave dataset
    format, with metadata rows followed by time-series data columns.

    Notes:
        The wave resource data should be in the format:

        - Row 1: Column names for metadata.
        - Row 2: Metadata values (lat, lon, water depth, etc.).
        - Row 3: Column headings for time-series data
          (``Year``, ``Month``, ``Day``, ``Hour``, ``Minute``,
          ``Significant Wave Height``, ``Energy Period``).
        - Rows 4+: Data values:

          - ``Significant Wave Height`` in meters.
          - ``Energy Period`` in seconds.

    Raises:
        FileNotFoundError: If the specified file does not exist.
        ValueError: If the file does not contain sufficient data or the required
            columns are not found.
    """

    def initialize(self):
        self.options.declare("plant_config", types=dict)
        self.options.declare("resource_config", types=dict)
        self.options.declare("driver_config", types=dict)

    def setup(self):
        self.config = WaveResourceConfig.from_dict(
            self.options["resource_config"],
            additional_cls_name=self.__class__.__name__,
        )
        site_config = self.options["plant_config"]["site"]

        self.add_input("latitude", site_config.get("latitude"), units="deg")
        self.add_input("longitude", site_config.get("longitude"), units="deg")
        self.add_output("significant_wave_height", shape=8760, val=0.0, units="m")
        self.add_output("energy_period", shape=8760, val=0.0, units="s")

    def compute(self, inputs, outputs):
        resource_dir = get_path(self.config.resource_dir)
        filename = find_file(self.config.resource_filename, resource_dir)

        wave_reader = WaveFileReader.new()
        wave_reader.WeatherReader.wave_resource_filename_ts = str(filename)
        wave_reader.WeatherReader.wave_resource_model_choice = 1  # time-series
        wave_reader.execute()

        number_records = int(wave_reader.Outputs.number_records)

        if number_records < 8760:
            df = pd.DataFrame(
                {
                    "year": wave_reader.Outputs.year,
                    "month": wave_reader.Outputs.month,
                    "day": wave_reader.Outputs.day,
                    "hour": wave_reader.Outputs.hour,
                    "minute": wave_reader.Outputs.minute,
                    "significant_wave_height": wave_reader.Outputs.significant_wave_height,
                    "energy_period": wave_reader.Outputs.energy_period,
                }
            )
            df["datetime"] = pd.to_datetime(
                {
                    "year": df.year,
                    "month": df.month,
                    "day": df.day,
                    "hour": df.hour,
                    "minute": df.minute,
                }
            )
            df = df.drop(["year", "month", "day", "hour", "minute"], axis=1)
            df = df.set_index("datetime")

            data_df = df.resample("h").mean()
            data_df = data_df.interpolate(method="linear")

            if len(data_df) < 8760:
                last_hour = data_df.index.max()
                missing_hours = 8760 - len(data_df)
                missing_time = pd.date_range(
                    last_hour + pd.Timedelta(hours=1), periods=missing_hours, freq="h"
                )
                missing_rows = pd.DataFrame(
                    index=missing_time,
                    columns=data_df.columns,
                    dtype=float,
                )
                data_df = pd.concat([data_df, missing_rows]).sort_index()
                data_df = data_df.ffill()

            outputs["significant_wave_height"] = data_df["significant_wave_height"].values[:8760]
            outputs["energy_period"] = data_df["energy_period"].values[:8760]
        else:
            outputs["significant_wave_height"] = list(wave_reader.Outputs.significant_wave_height)[
                :8760
            ]
            outputs["energy_period"] = list(wave_reader.Outputs.energy_period)[:8760]
