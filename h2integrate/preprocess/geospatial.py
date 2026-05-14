try:
    import reverse_geocoder as rg
except ModuleNotFoundError as e:
    msg = (
        "Geospatial tools require the `reverse_geocoder` library to be installed. Directly"
        " `pip install reverse_geocoder` or use `pip install h2integrate[gis]`."
    )
    raise ModuleNotFoundError(msg) from e

STATE_MAP = {
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
    casing to align with the ``STATE_MAP`` keys and values.

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

    Args:
        state (str): Full state name in title casing or two-letter state abbreviation in upper case.

    Returns:
        str: Two-letter state abbreviation.
    """
    return STATE_MAP.get(state, state)


def get_state_from_coords(latitude: float, longitude: float) -> str:
    """Reverse geocodes a :py:attr:`latitude` and :py:attr:`longitude` pair to get the
    state containing the coordinate pair.

    Args:
        latitude (float): Site latitude.
        longitude (float): Site longitude.

    Returns:
        str: 2-letter state code (i.e., "Alabama" -> "AL").
    """
    try:
        import reverse_geocoder as rg
    except ModuleNotFoundError as e:
        msg = (
            "EIA natural gas feedstock coordinate input requires `reverse_geocoder` to be"
            " installed. Directly `pip install reverse_geocoder` or use"
            " `pip install h2integrate[gis]`."
        )
        raise ModuleNotFoundError(msg) from e

    result = rg.search((latitude, longitude))[0]
    return convert_state_to_code(convert_state_value(result["admin1"]))
