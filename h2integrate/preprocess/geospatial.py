"""Geospatial preprocessing tools. Currently geared towards helping with processing of EIA data."""

US_STATE_MAP = {
    "Alabama": "AL",
    "Alaska": "AK",
    "Arizona": "AZ",
    "Arkansas": "AR",
    "California": "CA",
    "Colorado": "CO",
    "Connecticut": "CT",
    "Delaware": "DE",
    "Florida": "FL",
    "Georgia": "GA",
    "Hawaii": "HI",
    "Idaho": "ID",
    "Illinois": "IL",
    "Indiana": "IN",
    "Iowa": "IA",
    "Kansas": "KS",
    "Kentucky": "KY",
    "Louisiana": "LA",
    "Maine": "ME",
    "Maryland": "MD",
    "Massachusetts": "MA",
    "Michigan": "MI",
    "Minnesota": "MN",
    "Mississippi": "MS",
    "Missouri": "MO",
    "Montana": "MT",
    "Nebraska": "NE",
    "Nevada": "NV",
    "New Hampshire": "NH",
    "New Jersey": "NJ",
    "New Mexico": "NM",
    "New York": "NY",
    "North Carolina": "NC",
    "North Dakota": "ND",
    "Ohio": "OH",
    "Oklahoma": "OK",
    "Oregon": "OR",
    "Pennsylvania": "PA",
    "Rhode Island": "RI",
    "South Carolina": "SC",
    "South Dakota": "SD",
    "Tennessee": "TN",
    "Texas": "TX",
    "Utah": "UT",
    "Vermont": "VT",
    "Virginia": "VA",
    "Washington": "WA",
    "West Virginia": "WV",
    "Wisconsin": "WI",
    "Wyoming": "WY",
    "District of Columbia": "DC",
    "United States": "US",
}


def convert_state_value(state: str) -> str:
    """Convert potential two-letter state abbreviations to upper case and all else to title
    casing to align with the ``US_STATE_MAP`` keys and values.

    Args:
        state (str): Either a two-letter state abbreviation or full state name.

    Returns:
        str: Upper case state abbreviation or title case state name.
    """
    if len(state) == 2:
        return state.upper()
    return state.title()


def convert_state_to_code(state: str) -> str:
    """Converts the :py:attr:`state` name to a two-letter abbreviation or returns the input value.
    Currently only supports US state codes.

    Args:
        state (str): Full state name in title casing or two-letter state abbreviation in upper case.

    Returns:
        str: Two-letter state abbreviation.
    """
    return US_STATE_MAP.get(state, state)


def get_state_from_coords(
    *,
    coordinates: tuple[float, float] | list[tuple, float, float] | None = None,
    latitude: float | list[float] | None = None,
    longitude: float | list[float] | None = None,
) -> str | list[str]:
    """Reverse geocodes a :py:attr:`latitude` and :py:attr:`longitude` pair to get the
    state containing the coordinate pair. Use one of :py:attr:`coordinates` or :py:attr:`latitude`
    with :py:attr:`longitude`, not both.

    ``reverse_geocoder`` library required. Directly ``pip install reverse_geocoder`` or use
    ``pip install h2integrate[gis]``

    Args:
        coordinates (tuple[float, float] | list[tuple[float, float]], optional): Either a tuple
            coordinate pair as (latitude, longitude), or a list of coordinate pairs in the same
            format.
        latitude (float | list[float], optional): Site latitude or a list of site latitudes. Use one
            of :py:attr:`coordinates` or :py:attr:`latitude` with :py:attr:`longitude`, not both.
        longitude (float | list[float], optional): Site longitude or a list of site longitudes. Use
            one of :py:attr:`coordinates` or :py:attr:`latitude` with :py:attr:`longitude`, not
            both.

    Returns:
        str | list[str]: 2-letter state code (i.e., "Alabama" -> "AL") for each site that was
        provided.
    """
    try:
        import reverse_geocoder as rg
    except ModuleNotFoundError as e:
        msg = (
            "`reverse_geocoder` library required. Directly `pip install reverse_geocoder` or use"
            " `pip install h2integrate[gis]`."
        )
        raise ModuleNotFoundError(msg) from e

    if coordinates is None:
        if latitude is None or longitude is None:
            msg = (
                "At least one value must be provided for `coordinates` or combination of"
                " `latitude` and `longitude`."
            )
            raise ValueError(msg)
        if isinstance(latitude, float | int):
            latitude = [latitude]
        if isinstance(longitude, float | int):
            longitude = [longitude]
        if (lat_len := len(latitude)) != (lon_len := len(longitude)):
            msg = f"Length of `latitude` ({lat_len}) and `longitude` ({lon_len}) inputs not equal."
            raise ValueError(msg)
        coordinates = list(zip(latitude, longitude))

    result = rg.search(coordinates)
    single = len(result) == 1
    state = [convert_state_to_code(convert_state_value(el["admin1"])) for el in result]
    return state[0] if single else state
