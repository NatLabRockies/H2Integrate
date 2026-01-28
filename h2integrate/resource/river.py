from pathlib import Path

import pandas as pd
import openmdao.api as om
from attrs import field, define

from h2integrate.core.utilities import BaseConfig


@define(kw_only=True)
class RiverResourceConfig(BaseConfig):
    filename: str | Path = field()


class RiverResource(om.ExplicitComponent):
    """
    A resource component for processing river discharge data from a CSV file.

    This component reads a CSV file containing river discharge data, processes it,
    and outputs hourly discharge values for a full year (8760 hours). The input
    file is expected to have specific formatting, including metadata and discharge
    data columns with some error handling for missing or malformed data.

    CSV files are assumed to have the structure outputted from the USGS Water
    Information System: https://waterdata.usgs.gov/nwis/uv

    Methods:
        initialize():
            Declares the options for the component, including the required "filename" option.
        setup():
            Defines the outputs for the component, in this case just the "discharge" array.
        compute(inputs, outputs):
            Reads, processes, and resamples the discharge data from the input file.
            Outputs the hourly discharge values.

    Raises:
        FileNotFoundError: If the specified file does not exist.
        ValueError: If the file does not contain sufficient data or the required
            discharge column is not found.
    """

    def initialize(self):
        self.options.declare("plant_config", types=dict)
        self.options.declare("resource_config", types=dict)
        self.options.declare("driver_config", types=dict)
        # self.options.declare("filename", types=str)

    def setup(self):
        # Define inputs and outputs
        self.config = RiverResourceConfig.from_dict(self.options["resource_config"])
        site_config = self.options["plant_config"]["site"]

        self.add_input("latitude", site_config.get("latitude", 0.0), units="deg")
        self.add_input("longitude", site_config.get("longitude", 0.0), units="deg")
        self.add_output("discharge", shape=8760, val=0.0, units="ft**3/s")

    def compute(self, inputs, outputs):
        # Read the CSV file
        filename = self.config.filename

        # Check if the file exists
        if not Path(filename).is_file():
            raise FileNotFoundError(f"The file '{filename}' does not exist.")

        df = pd.read_csv(
            filename,
            sep="\t",
            comment="#",  # Ignore comment lines starting with #
            skiprows=13,  # Skip top metadata until actual headers
        )

        # Check if the DataFrame is empty or has insufficient data
        if df.empty or len(df) < 8760:
            raise ValueError("Insufficient data for resampling.")

        # Extract the column name for discharge
        with Path.open(filename) as file:
            for line in file:
                if "Discharge, cubic feet per second" in line:
                    # Extract the numeric identifier before "Discharge"
                    parts = line.split()
                    column_identifier = f"{parts[1]}_{parts[2]}"
                    break
            else:
                raise ValueError("Discharge column not found in the file.")

        # Rename the columns to more meaningful names
        df = df.rename(
            columns={
                column_identifier: "discharge_cfs",
            }
        )

        # Drop the first row if it contains unwanted metadata
        df = df.iloc[1:].reset_index(drop=True)

        df = df[["datetime", "discharge_cfs"]]

        # Convert 'discharge_cfs' to numeric, coercing errors to NaN
        df["discharge_cfs"] = pd.to_numeric(df["discharge_cfs"], errors="coerce")

        # Convert datetime column to datetime format
        df["datetime"] = pd.to_datetime(df["datetime"])

        # Set datetime as index (required for resampling)
        df = df.set_index("datetime")

        # Resample to hourly data using mean
        df_hourly = df.resample("1h").mean()

        # Reset index if to use datetime as a column again
        df_hourly = df_hourly.reset_index()

        # Forward fill NaN values with the last valid observation
        df_hourly = df_hourly.ffill(limit=1)

        # Check if the output length matches 8760
        if len(df_hourly) != 8760:
            raise ValueError(
                f"Resampled data does not have the expected length of 8760 hours."
                f"Actual length: {len(df_hourly)}"
            )

        outputs["discharge"] = df_hourly["discharge_cfs"].values
