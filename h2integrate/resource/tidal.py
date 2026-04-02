from pathlib import Path

import pandas as pd
import openmdao.api as om
import PySAM.TidalFileReader as tidalfile
from attrs import field, define

from h2integrate.core.utilities import BaseConfig
from h2integrate.core.file_utils import get_path, find_file


@define(kw_only=True)
class TidalResourceConfig(BaseConfig):
    """
    Args:
        resource_dir (str | Path, optional): Folder to save resource files to or
        load resource files from. Defaults to "".
        resource_filename (str, optional): Filename to save resource data to or load
            resource data from. Defaults to None.
    """

    resource_dir: Path | str | None = field(default=None)
    resource_filename: Path | str = field(default="")


class TidalResource(om.ExplicitComponent):
    """
    A resource component for processing tidal data from a CSV file.

    This component reads a CSV file containing tidal data, processes it,
    and outputs hourly tidal velocity values for a full year (8760 hours). The input
    file is expected to have specific formatting, including metadata and day and time,
    and speed data columns with some error handling for missing or malformed data.

    Notes:
        The tidal resource data should be in the format:
            - Rows 1 and 2: Header rows with location info.
            - Row 3: Column headings for time-series data
                - (`Year`, `Month`, `Day`, `Hour`, `Minute`, `Speed`).
            - Rows 4+: Data values:
            - `Speed` (current speed) in meters/second.


    Methods:
        initialize():
            Declares the options for the component, including the required "filename" option.
        setup():
            Defines the outputs for the component, in this case just the "tidal_velocity" array.
        compute(inputs, outputs):
            Reads, processes, and resamples the data from the input file.
            Outputs the hourly tidal velocity values.

    Raises:
        FileNotFoundError: If the specified file does not exist.
        ValueError: If the file does not contain sufficient data or the required
            speed column is not found.
    """

    def initialize(self):
        self.options.declare("plant_config", types=dict)
        self.options.declare("resource_config", types=dict)
        self.options.declare("driver_config", types=dict)

    def setup(self):
        # Define inputs and outputs
        self.config = TidalResourceConfig.from_dict(
            self.options["resource_config"],
            additional_cls_name=self.__class__.__name__,
        )
        site_config = self.options["plant_config"]["site"]

        self.add_input("latitude", site_config.get("longitude"), units="deg")
        self.add_input("longitude", site_config.get("longitude"), units="deg")
        self.add_output("tidal_velocity", shape=8760, val=0.0, units="m/s")

    def compute(self, inputs, outputs):
        # Read the CSV file
        # Check if the file exists

        resource_dir = get_path(self.config.resource_dir)
        filename = find_file(self.config.resource_filename, resource_dir)

        # filename = resource_dir / self.config.resource_filename

        tidalfile_model = tidalfile.new()
        # Load resource file
        tidalfile_model.WeatherReader.tidal_resource_filename = str(filename)
        tidalfile_model.WeatherReader.tidal_resource_model_choice = 1  # Time-series=1 JPD=0

        # Read in resource file, output time series arrays to pass to wave performance module
        tidalfile_model.execute()
        hours = tidalfile_model.Outputs.hour

        if len(hours) < 8760:
            # code that makes/modifies data_df
            # Set up dataframe for data manipulation
            df = pd.DataFrame()
            df["year"] = tidalfile_model.Outputs.year
            df["month"] = tidalfile_model.Outputs.month
            df["day"] = tidalfile_model.Outputs.day
            df["hour"] = tidalfile_model.Outputs.hour
            df["minute"] = tidalfile_model.Outputs.minute
            df["date_time"] = pd.to_datetime(
                {
                    "year": df.year,
                    "month": df.month,
                    "day": df.day,
                    "hour": df.hour,
                    "minute": df.minute,
                }
            )
            df = df.drop(["year", "month", "day", "hour", "minute"], axis=1)
            df = df.set_index(["date_time"])
            df["tidal_velocity"] = tidalfile_model.Outputs.tidal_velocity

            # Resample data and linearly interpolate to hourly data
            data_df = df.resample("h").mean()
            data_df = data_df.interpolate(method="linear")

            # If data cannot interpolate last hours
            if len(data_df["tidal_velocity"]) < 8760:
                last_hour = data_df.index.max()
                missing_hours = 8760 - len(data_df["tidal_velocity"])

                missing_time = pd.date_range(
                    last_hour + pd.Timedelta(hours=1), periods=missing_hours, freq="h"
                )
                missing_rows = pd.DataFrame(index=missing_time, columns=df.columns)
                data_df = pd.concat([data_df, missing_rows]).sort_index()
                data_df = data_df.ffill()  # forward fill

            data_df = data_df.reset_index()
            outputs["tidal_velocity"] = data_df["tidal_velocity"]
            return

        if len(hours) == 8760:
            outputs["tidal_velocity"] = tidalfile_model.Outputs.tidal_velocity
            return

        raise ValueError("Resource time-series cannot be subhourly.")
