"""Tools for getting the EIA natural gas data that could be expanded into other EIA API data."""

import os
import json
from pathlib import Path

import pandas as pd
import requests

from h2integrate.preprocess import geospatial
from h2integrate.core.file_utils import get_path


MCF_to_MMBTU = 1 / 0.964
HOURS_PER_YEAR = 8760

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

NG_PROCESS_NAME_MAP = {
    "Industrial Price": "industrial",
    "Imports Price": "imports",
    "City Gate Price": "citygate",
    "Price Delivered to Residential Consumers": "residential",
    "Wellhead Acquisition Price": "wellhead",
    "Price Delivered to Commercial Sectors": "commercial",
    "Exports (Price)": "exports",
    "Electric Power Price": "electrical_power",
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


def convert_to_monthly(df: pd.DataFrame, start_year: int, end_year: int) -> pd.DataFrame:
    """Converts an annual or monthly timeseries to monthly (at start of month) by repeating the one
    value, or returns the input data converted, if already monthly.

    Args:
        df (pd.DataFrame): The annual or monthly pricing data. Must have the index column, or first
            index column if ``MultiIndex``, be named "period" and already be converted to a
            ``DatetimeIndex``.
        start_year (int): Starting year of the data.
        end_year (int): Ending year of the data.

    Returns:
        pd.DataFrame | None: Returns back the monthly data if the original data have either
            1 or 12 data entries, otherwise None is returned.
    """
    years = 1 + end_year - start_year
    is_multi_ix = isinstance(df.index, pd.MultiIndex)
    dt_ix = df.index if not is_multi_ix else df.index.get_level_values("period").unique()
    if is_multi_ix:
        df = df.swaplevel("period", 0)
        ix_names = [el for el in df.index.names if el != "period"]
        ix_levels = list(range(1, len(ix_names) + 1))
        print(df.index.names)
    if dt_ix.size % 12 == 0:
        # use bfill in case of end of the month--won't impact if already start of the month
        if not is_multi_ix:
            return df.resample("MS").bfill()  # ensure it's always the start of the month
        df = (
            df.unstack(level=ix_levels)  # noqa: PD010, PD013 <- melt and pivot create more work
            .resample("MS")
            .bfill()
            .stack(level=ix_levels, future_stack=True)
            .sort_index()
        )
        return df
    if dt_ix.size == years:
        # annual data are assumed to have been converted to format YYYY-01-01 via pd.to_datetime()
        monthly_ix = pd.DatetimeIndex(
            pd.date_range(f"{start_year}-01", f"{end_year}-12", freq="MS"), name="period"
        )
        if not is_multi_ix:
            df = df.reindex(monthly_ix, method="ffill")
            return df
        print(df.index.names)
        df = (
            df.unstack(level=ix_levels)  # noqa: PD010, PD013 <- melt and pivot create more work
            .reindex(monthly_ix, method="ffill")
            .stack(level=ix_levels, future_stack=True)
            .sort_index()
        )
        print(df.index.names)
        return df

    msg = (
        f"Irregular data size passed, expected compatibility with {years} years, annually, or"
        " monthly. Please check your data."
    )
    raise ValueError(msg)


def convert_to_hourly(df: pd.DataFrame) -> pd.DataFrame:
    """Converts the monthly EIA price timeseries to an hourly time series for ``plant_life``
    number of years, removing any leap year data in the process.

    Args:
        df (pd.DataFrame): The monthly EIA price data. Must have the index column, or first index
            column if ``MultiIndex``, be named "period" and already be converted to a
            ``DatetimeIndex``.

    Raises:
        ValueError: Raised if the ending result failed to convert the monthly timeseries to an 8760
            hour per year timeseries.

    Returns:
        pd.DataFrame | None: Returns the data back an hourly timeseries of price data that has been
            forward filled from month-start entries.
    """
    is_multi_ix = isinstance(df.index, pd.MultiIndex)
    if is_multi_ix:
        ix_names = [el for el in df.index.names if el != "period"]
        ix_levels = list(range(1, len(ix_names) + 1))
        df = df.unstack(level=ix_levels)  # noqa: PD010
    last = df.iloc[[-1]].resample("ME").ffill()
    last.index = pd.DatetimeIndex(
        [pd.to_datetime(last.index[0].to_pydatetime().replace(hour=23))], name="period"
    )
    df = pd.concat((df, last)).resample("h").ffill()
    df = df.drop(df.loc[(df.index.month == 2) & (df.index.day == 29)].index)
    if is_multi_ix:
        df = df.stack(level=ix_levels)  # noqa: PD013
    if df.shape[0] % HOURS_PER_YEAR != 0:
        msg = f"An error occurred converting data to hourly to match size ({df.shape[0]}) to 8760"
        raise ValueError(msg)
    return df


def _validate_resource_year(resource_year: int | tuple[int, int]) -> tuple[int, int]:
    """Formats the resource year for a request for either a single year, or tuple of starting
    year and ending year, returning back a tuple of starting and ending years.

    Args:
        resource_year (int | tuple[int, int]): A single resource year, or a length-2 tuple of
            starting and ending years.

    Raises:
        ValueError: Raised if a :py:attr:`resource_year` is a sequence and does not have 2 elements.
        TypeError: Raised if :py:attr:`resource_year` is neither a :py:obj:`tuple` nor
            :py:obj:`int`.

    Returns:
        tuple[int, int]: The starting and ending year for a data query.
    """
    if isinstance(resource_year, tuple | list):
        if len(resource_year) == 1:
            return resource_year * 2
        if len(resource_year) != 2:
            msg = (
                "Either pass a single `resource_year` or length-2 tuple for the starting"
                " and ending years."
            )
            raise ValueError(msg)
        return resource_year

    if isinstance(resource_year, int):
        return resource_year, resource_year

    msg = (
        "Either pass a single `resource_year` or length-2 tuple for the starting and ending years."
    )
    raise TypeError(msg)


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
    invalid = set(states).difference(geospatial.US_STATE_MAP.values())
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


def _validate_file_name(filename: str | Path | None) -> Path | None:
    """Finds and validates the :py:attr:`filename` if one is passed.

    Args:
        filename (str | Path | None): Full file path or None.

    Returns:
        Path | None: A resolved :py:attr:`filename` if one was provided.
    """
    if filename is not None:
        try:
            filename = get_path(filename)
        except FileNotFoundError:
            filename = Path(filename).resolve()
    return filename


def create_eia_ng_api_url(
    resource_year: int | tuple[int, int],
    price_category: str | list[str],
    state: str | list[str],
    api_key_file: str | Path | None = None,
    *,
    monthly: bool = True,
):
    """Create a validated EIA Natural Gas API URL that is ready to be queried. If no
    :py:attr:`api_key_file` is passed, then the API key is assumed to be an environment variable
    called ``EIA_API_KEY``.

    Args:
        resource_year (int | list[int]): The YYYY-formatted year or length-2 tuple of years whose
            data should be retrieved. Should be between 2001 and the current year, inclusive of
            endpoints as that is all that the EIA provides, regardless of what is queried.
        price_category (str | list[str]): One or a combination of "wellhead", "imports", "citygate",
            "residential", "commercial","industrial", "electrical_power", or "exports". Note that
            not all categories will return state-level data.
        state (str | list[str]): Full name(s) of the state or two-letter state abbreviation(s), such
            as "United States" or "US". Only the "US" or one of the 50 US states will produce valid
            results.
        api_key_file (Path, optional): Full file name of the file where the API key is located. If
            no file name is provided, then the environment variable ``EIA_API_KEY`` is used.
            Default is None
        monthly (Path): True, if monthly data is desired, False if annual data is desired.

    Returns:
        str: A queryable EIA natural gas URL.
    """
    if api_key_file is not None:
        api_key_file = get_path(api_key_file)
    api_key = get_eia_api_key(api_key_file)

    start_year, end_year = _validate_resource_year(resource_year)
    state = _validate_state(state)
    price_category = _validate_price_category(price_category)
    series = sorted([EIA_NG_FACET[c].format(s) for c in price_category for s in state])

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


def get_eia_ng_data(
    resource_year: int | tuple[int, int],
    price_category: str | list[str],
    state: str | list[str],
    api_key_file: str | Path | None = None,
    filename: str | Path | None = None,
    *,
    monthly: bool = True,
):
    """Create a validated EIA Natural Gas API URL that is ready to be queried.

    Args:
        resource_year (int | list[int]): The YYYY-formatted year or length-2 tuple of years whose
            data should be retrieved. Should be between 2001 and the current year, inclusive of
            endpoints as that is all that the EIA provides, regardless of what is queried.
        price_category (str | list[str]): One or a combination of "wellhead", "imports", "citygate",
            "residential", "commercial","industrial", "electrical_power", or "exports". Note that
            not all categories will return state-level data.
        state (str | list[str]): Full name(s) of the state or two-letter state abbreviation(s), such
            as "United States" or "US". Only the "US" or one of the 50 US states will produce valid
            results.
        api_key_file (Path, optional): Full file name of the file where the API key is located. If
            no file name is provided, then the environment variable ``EIA_API_KEY`` is used.
        filename (str | Path | None): Full file name where the EIA data can either be loaded from
            or should be saved to. If None, then data will be queried and returned with saving
            left to the user.
        monthly (Path): True, if monthly data is desired, False if annual data is desired.

    Returns:
        pd.DataFrame: A monthly dataframe containing the date, state, price_category, and price
            (MMBTU).
    """

    filename = _validate_file_name(filename)
    state = _validate_state(state)
    price_category = _validate_price_category(price_category)
    resource_year = _validate_resource_year(resource_year)

    start, end = resource_year
    keep_cols = ["price"]
    if len(state) > 1:
        keep_cols = ["state", *keep_cols]
    if len(price_category) > 1:
        keep_cols = ["category", *keep_cols]
    if filename is not None:
        if filename.exists():
            df = pd.read_csv(filename, parse_dates=["period"]).set_index("period")
            df = df.loc[
                (df.index.year >= start)
                & (df.index.year <= end)
                & df.category.isin(price_category)
                & df.state.isin(state),
                keep_cols,
            ]
            df = convert_to_monthly(df, start, end)
            if df is not None:
                return df

    url = create_eia_ng_api_url(
        api_key_file=api_key_file,
        resource_year=resource_year,
        price_category=price_category,
        state=state,
        monthly=monthly,
    )

    r = requests.get(url)
    if r.status_code != 200:
        err = json.loads(r.text)["error"]
        raise requests.exceptions.HTTPError(err)

    df = pd.DataFrame.from_dict(json.loads(r.text)["response"]["data"])
    if df.size == 0:
        raise ValueError(f"No data for combination {state=}, {price_category=}")

    df.period = pd.to_datetime(df.period)  # NOTE: if annual, converts year to Jan 1 timestamp
    df.value = df.value.astype(float)
    df = (
        df.set_index("period")
        .rename(columns={"value": "price", "area-name": "state", "process-name": "category"})
        .loc[:, keep_cols]
        .replace("U.S.", "US")
        .replace(NG_PROCESS_NAME_MAP)
    )
    if "state" in keep_cols:
        df.state = (
            df.state.str.replace("USA-", "")
            .str.title()
            .replace(geospatial.US_STATE_MAP)
            .str.upper()
        )
    df = df.set_index([el for el in keep_cols if el != "price"], append=True)
    df = convert_to_monthly(df, *resource_year)
    df.price *= MCF_to_MMBTU

    if filename is not None:
        df.to_csv(filename, index_label="period")

    return df
