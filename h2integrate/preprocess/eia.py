import os
from pathlib import Path

import pandas as pd

from h2integrate.preprocess import geospatial
from h2integrate.core.file_utils import get_path


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


def _validate_resource_year(resource_year: int | tuple[int, int]) -> tuple[int, int]:
    """Formats the resource year for a request for either a single year, or tuple of starting
    year and ending year, returning back a tuple of starting and ending years.

    Args:
        resource_year (int | tuple[int, int]): A single resource year, or a length-2 tuple of
            starting and ending years.

    Raises:
        ValueError: Raised if a :py:attr:`resource_year` is a sequence and does not have 2 elements.
        TypeError: Raised if :py:attr:`resource_year` is neither a :py:obj:`tuple` nor :py:obj:`int`.

    Returns:
        tuple[int, int]: The starting and ending year for a data query.
    """
    if isinstance(resource_year, tuple | list):
        if len(resource_year) != 2:
            msg = (
                "Either pass a single `resource_year` or length-2 tuple for the starting"
                " and ending years."
            )
            raise ValueError(msg)
        return resource_year

    if isinstance(resource_year, int):
        msg = (
            "Either pass a single `resource_year` or length-2 tuple for the starting"
            " and ending years."
        )
        raise TypeError(msg)

    return resource_year, resource_year


def _validate_state(state: str | list[str]) -> list[str]:
    """Validates all :py:attr:`state` input(s) to be an all caps 2-letter state code.

    Args:
        state (str | list[str]): Either a state name or 2-letter state code.

    Raises:
        ValueError: Raised if an input to :py:attr:`state` has not been converted to valid 2-letter
            state code.

    Returns:
        list[str]: A list of all inputs to :py:attr:`state` as a list of 2-letter state codes.
    """
    if isinstance(state, str):
        state = [state]

    states = [geospatial.convert_state_to_code(geospatial.convert_state_value(el)) for el in state]
    invalid = set(states).difference(geospatial.STATE_MAP.values())
    if invalid:
        raise ValueError(f"{', '.join(invalid)} could not be converted to a 2-letter state code.")
    return states


def _validate_price_category(price_category: str | list[str]) -> list[str]:
    """Validates all :py:attr:`price_category` input(s) are matched to an :py:attr:`EIA_NG_FACET`.

    Args:
        state (str | list[str]): Either a state name or 2-letter state code.

    Raises:
        ValueError: Raised if an input to :py:attr:`price_category` is not defined in
            :py:attr:`EIA_NG_FACET`.

    Returns:
        list[str]: A verified list of all inputs to :py:attr:`price_category`.
    """
    if isinstance(price_category, str):
        price_category = [price_category]
    price_category = [el.lower() for el in price_category]

    invalid = set(price_category).difference([*EIA_NG_FACET])
    if invalid:
        msg = f"Invalid category: {', '.join(invalid)}. Use one of {', '.join([*EIA_NG_FACET])}"
        raise ValueError(msg)
    return price_category


def create_eia_ng_api_url(
    api_key_file: str | Path | None,
    resource_year: int | tuple[int, int],
    price_category: str | list[str],
    state: str | list[str],
    *,
    monthly: bool = True,
):
    """Create a validated EIA Natural Gas API URL that is ready to be queried.

    Args:
        api_key_file (Path, optional): Full file name of the file where the API key is located. If
            no file name is provided, then the environment variable ``EIA_API_KEY`` is used.
        resource_year (int | list[int]): The YYYY-formatted year or length-2 tuple of years whose
            data should be retrieved. Should be between 2001 and the current year, inclusive of
            endpoints as that is all that the EIA provides, regardless of what is queried.
        price_category (str | list[str]): One or a combination of "wellhead", "imports", "citygate",
            "residential", "commercial","industrial", "electrical_power", or "exports". Note that
            not all categories will return state-level data.
        state (str | list[str]): Full name(s) of the state or two-letter state abbreviation(s), such
            as "United States" or "US". Only the "US" or one of the 50 US states will produce valid
            results.
        monthly (Path): True, if monthly data is desired, False if annual data is desired.

    Returns:
        str: A queryable EIA natural gas URL.
    """
    if api_key_file is not None:
        api_key_file = get_path(api_key_file)
    api_key = get_eia_api_key(api_key_file)

    start_year, end_year = _validate_resource_year(resource_year)
    state = _validate_state(state)
    price_category = _validate_price_category
    series = [EIA_NG_FACET[c].format(s) for c in price_category for s in state]

    base_url = "https://api.eia.gov/v2/natural-gas/pri/sum/data/"
    frequency = f"frequency={'monthly' if monthly else 'annual'}"
    data = "data[0]=value"
    facets = "&".join(f"facets[series][]={s}" for s in series)
    start = f"start={start_year}"
    end = f"end={end_year}"
    if monthly:
        start = f"{start}-01"
        end = f"{end}-12"
    sort_col = "sort[0][column]=period"
    sort_dir = "sort[0][direction]=asc"
    api_key = f"api_key={api_key}"

    url_opts = "&".join((frequency, data, facets, start, end, sort_col, sort_dir, api_key))
    url = f"{base_url}?{url_opts}"
    return url
