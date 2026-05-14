import os
from pathlib import Path

import pandas as pd


MCF_to_MMBTU = 1 / 0.964

EIA_NG_FACET = {
    "wellhead": "N9190{}3",
    "imports": "N9100{}3",
    "citygate": "N3050{}3",
    "residential": "N3010{}3",
    "commercial": "N3020{}3",
    "industrial": "N3035{}3",
    "electrical_power": "N3045{}3",
    "exports": "N9130{}3",
}


def get_eia_api_key(api_key_file: Path | None) -> str:
    """Retrieves the EIA API key from a file, and returns the key following "EIA_API_KEY:".

    Args:
        api_key_file (Path, optional): Full file path and name of where the EIA API key is located.
            If none is provided, then the API key is retrieved from the environment variables. Must
            be encoded as "EIA_API_KEY: xxxxxx"

    Raises:
        ValueError: Raised either if no file is provided and an environment variable has not be
            defined, or if a filename is provided but "EIA_API_KEY" is not found.

    Returns:
        str: The EIA API key.
    """
    if api_key_file is None:
        key = os.environ.get("EIA_API_KEY")
        if key is None:
            msg = (
                "No `api_key_file` provided for the EIA API, and 'EIA_API_KEY' is not defined as an"
                " environment variable."
            )
            raise ValueError(msg)
        return key

    with api_key_file.open() as f:
        for line in f.readlines():
            if ":" in line:
                name, val = line.strip().split(":")
                if name == "EIA_API_KEY":
                    return val.strip()
    raise ValueError(f"No 'EIA_API_KEY' defined in {api_key_file=}")


def convert_to_monthly(df: pd.DataFrame) -> pd.DataFrame | None:
    """Converts an annual timeseries to monthly by repeating the one value, or returns
    the data passed, if already monthly.

    Args:
        df (pd.DataFrame): The annual or monthly natural gas pricing data.

    Returns:
        pd.DataFrame | None: Returns back the monthly data if the original data have either
            1 or 12 data entries, otherwise None is returned.
    """
    match df.shape[0]:
        case 12:
            return df.resample("MS").bfill()  # ensure it's start of the month
        case 1:
            year = df.index.year[0]
            ix = pd.date_range(f"{year}-01", f"{year}-12", freq="MS")
            df = df.reindex(ix, method="nearest")
            return df
        case _:
            pass
