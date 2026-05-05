import os
import json
from pathlib import Path
from datetime import datetime

import attrs
import numpy as np
import pandas as pd
import requests
import openmdao.api as om
from attrs import field, define

from h2integrate.core.utilities import merge_shared_inputs
from h2integrate.core.file_utils import get_path
from h2integrate.core.model_baseclasses import BaseConfig, CostModelBaseClass


HOURS_PER_YEAR = 8760
SECONDS_PER_HOUR = 3600
MCF_to_MMBTU = 1 / 0.964
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
CURRENT_YEAR = datetime.now().year

EIA_FACET = {
    "wellhead": "N9190{}3",
    "imports": "N9100{}3",
    "citygate": "N3050{}3",
    "residential": "N3010{}3",
    "commercial": "N3020{}3",
    "industrial": "N3035{}3",
    "electrical_power": "N3045{}3",
    "exports": "N9130{}3",
}


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

    result = rg.search((latitude, longitude))
    return convert_state_to_code(convert_state_value(result["admin1"]))


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


@define(kw_only=True)
class EIANaturalGasFeedstockPerformanceConfig(BaseConfig):
    """Configuration class for the EIA natural gas price feedstock, which uses base units of MMBtu.

    Attributes:
        rated_capacity (float):  The rated capacity of the feedstock in `commodity_rate_units`.
            This is used to size the feedstock supply to meet the plant's needs.
    """

    rated_capacity: float = field()
    commodity: str = field(default="natural_gas", init=False)
    commodity_rate_units: str = field(default="MMBtu/h", init=False)


class EIANaturalGasFeedstockPerformanceModel(om.ExplicitComponent):
    """Feedstock performance model compatible with the hard-coded units and commodity inputs
    from the :py:class:`EIANaturalGasFeedstockCostModel` and
    :py:class:`EIANaturalGasFeedstockConfig`.
    """

    _time_step_bounds = (3600, 3600)  # (min, max) time step lengths (seconds) allowed

    def initialize(self):
        self.options.declare("driver_config", types=dict)
        self.options.declare("plant_config", types=dict)
        self.options.declare("tech_config", types=dict)

    def setup(self):
        self.config = EIANaturalGasFeedstockPerformanceConfig.from_dict(
            merge_shared_inputs(self.options["tech_config"]["model_inputs"], "performance"),
            additional_cls_name=self.__class__.__name__,
        )
        self.n_timesteps = self.options["plant_config"]["plant"]["simulation"]["n_timesteps"]
        self.add_input(
            f"{self.config.commodity}_capacity",
            val=self.config.rated_capacity,
            units=self.config.commodity_rate_units,
        )

        self.add_output(
            f"{self.config.commodity}_out",
            shape=self.n_timesteps,
            units=self.config.commodity_rate_units,
        )

    def compute(self, inputs, outputs):
        """Generates the feedstock array operating at full capacity for a full year."""
        outputs[f"{self.config.commodity}_out"] = np.full(
            self.n_timesteps, inputs[f"{self.config.commodity}_capacity"][0]
        )


@define
class EIANaturalGasFeedstockConfig(BaseConfig):
    """EIA Industrial Natural Gas Pricing API configuration and downloader for the US and all 50 US
    states, in $/MCF, converted to $/MMBtu. Please see
    https://www.eia.gov/opendata/browser/natural-gas/pri/sum for further details about data
    availability.

    Args:
        state (str): Full name of the state or two-letter state abbreviation, such as
            "United States" or "US". Only the "US" or all 50 states will produce valid results.
        resource_year (int): The YYYY-format year whose data should be retrieved. Must be between
            2001 and the current year, inclusive of endpoints.
        cost_year (int): dollar-year for costs. Defaults to the current year.
        monthly (Path): True, if monthly data is desired, False if annual data is desired.
        price_category (str): One of "wellhead", "imports", "citygate", "residential", "commercial",
            "industrial", "electrical_power", or "exports". Note that not all categories will return
            state-level data.
        api_key_file (Path, optional): Full file name of the file where the API key is located. If
            no file name is provided, then the environment variables ``EIA_API_KEY`` is used.
        filename (str, optional): Filename for where to save the data or where the data may
            already be located. If the file exists, the columns "period", "state", and "price" must
            exist, otherwise the file will not be used. "period" should be of the form YYYY or
            YYYY-MM, and state should be either the full state name or the two-letter abbreviation.
        annual_cost (float, optional): fixed cost associated with the feedstock in USD/year.
            Defaults to 0.0.
        start_up_cost (float, optional): one-time capital cost associated with the feedstock in USD.
            Defaults to 0.0.
    """

    resource_year: int = field(validator=attrs.validators.in_(range(2001, CURRENT_YEAR + 1)))
    monthly: bool = field(validator=attrs.validators.instance_of(bool))
    price_category: str = field(converter=str.lower, validator=attrs.validators.in_(EIA_FACET))
    url: str = field(default=None, init=False)
    series: str = field(init=False)
    price: pd.DataFrame = field(init=False, validator=attrs.validators.instance_of(pd.DataFrame))
    api_key_file: str | None = field(default=None, converter=attrs.converters.optional(get_path))
    state: str = field(
        default=None,
        converter=attrs.converters.optional(
            attrs.converters.pipe(convert_state_value, convert_state_to_code)
        ),
        validator=attrs.validators.optional(
            attrs.validators.in_([*STATE_MAP, *STATE_MAP.values()])
        ),
    )
    latitude: float = field(default=999.9, validator=attrs.validators.instance_of(float))
    longitude: float = field(default=999.9, validator=attrs.validators.instance_of(float))
    cost_year: int = field(default=CURRENT_YEAR)
    annual_cost: float = field(default=0.0, converter=float)
    start_up_cost: float = field(default=0.0, converter=float)
    commodity: str = field(default="natural_gas", init=False)
    commodity_rate_units: str = field(default="MMBtu/h", init=False)
    commodity_amount_units: str = field(default="MMBtu", init=False)
    filename: str = field(default=None)

    def __attrs_post_init__(self):
        """Creates the EIA natural gas facet series code based on validated user inputs, sets the
        :py:attr:`commodity_amount_units` if not given a value, and fetches the EIA natural gas
        price.
        """
        try:
            self.filename = get_path(self.filename)
        except FileNotFoundError:
            self.filename = Path(self.filename).resolve()

        if self.state is None:
            if self.latitude == 999.9 or self.longitude == 999.9:
                msg = (
                    "The EIA natural gas feedstock model require one of `state` or"
                    " `latitude` and `longitude`."
                )
                raise ValueError(msg)

            self.state = get_state_from_coords(self.latitude, self.longitude)

        self.series = EIA_FACET[self.price_category].format(self.state)
        if self.commodity_amount_units is None:
            self.commodity_amount_units = f"({self.commodity_rate_units})*h"
        if self.api_key_file is not None:
            self.url = self.create_eia_api_url()
        self.price = self.get_data()

    def create_eia_api_url(self):
        year = self.resource_year
        base_url = "https://api.eia.gov/v2/natural-gas/pri/sum/data/"
        frequency = f"frequency={'monthly' if self.monthly else 'annual'}"
        data = "data[0]=value"
        facet = f"facets[series][]={self.series}"
        start = f"start={year}"
        end = f"end={year}"
        if self.monthly:
            start = f"{start}-01"
            end = f"{end}-12"
        sort_col = "sort[0][column]=period"
        sort_dir = "sort[0][direction]=asc"
        api_key = f"api_key={get_eia_api_key(self.api_key_file)}"

        url_opts = "&".join((frequency, data, facet, start, end, sort_col, sort_dir, api_key))
        url = f"{base_url}?{url_opts}"
        return url

    def get_data(self, filename: Path | None = None) -> pd.DataFrame:
        """Loads the previously saved data from :py:attr:`filename` if ``resource_year``
        is available as either annual or monthly data, otherwise data is retrieved from the EIA API.

        Args:
            filename (Path | None, optional): The full filename where the natural gas pricing data
                should be saved to or loaded from, if available. Must have columns "period" and
                "price". Defaults to None.

        Raises:
            requests.exceptions.HTTPError: Raised if an unsuccessful API query result is returned.

        Returns:
            pandas.DataFrame: DataFrame with index "period" and column "value" with natural gas
                pricing in $/MMBtu (converted from the EIA's USD per thousands of cubic feet) as
                either the monthly value or extrapolated annual values to a monthly resolution.
        """
        if filename is None:
            filename = self.filename

        if filename is not None:
            filename = Path(filename).resolve()
            if filename.exists():
                df = pd.read_csv(filename, parse_dates=["period"]).set_index("period")
                df = df.loc[
                    (df.index.year == self.resource_year) & df.state.eq(self.state), ["price"]
                ]
                df = convert_to_monthly(df)
                if df is not None:
                    return df

        if self.url is None:
            msg = (
                "One of `api_key_file` or `filename` with existing data provided to use the"
                " `EIANaturalGasFeedstock` cost and performance models."
            )
            raise ValueError(msg)

        r = requests.get(self.url)
        if r.status_code != 200:
            err = json.loads(r.text)["error"]
            raise requests.exceptions.HTTPError(err)

        df = pd.DataFrame.from_dict(json.loads(r.text)["response"]["data"])
        if df.size == 0:
            raise ValueError(f"No data for combination {self.state=}, {self.price_category=}")

        df.period = pd.to_datetime(df.period)
        df.value = df.value.astype(float)
        df = (
            df.set_index("period")
            .rename(columns={"value": "price", "area-name": "state"})
            .replace("U.S.", "US")
        )[["state", "price"]]
        df = convert_to_monthly(df)
        df.price *= MCF_to_MMBTU

        if filename is not None:
            df.to_csv(filename, index_label="period")
        return df[["price"]]


class EIANaturalGasFeedstockCostModel(CostModelBaseClass):
    """Feedstock cost model based on the EIA natural gas price API results that uses
    annual or monthly data to model an hourly time step for a single year to model the
    price of natural gas used in the model.
    """

    _time_step_bounds = (3600, 3600)  # (min, max) time step lengths (seconds) allowed

    def _extrapolate_price_to_hourly(self) -> pd.DataFrame:
        """Converts the monthly EIA price timeseries to an hourly time series for ``plant_life``
        number of years.
        """
        price = self.config.price.copy()

        last = price.iloc[[-1]].resample("ME").ffill()
        last.index = [pd.to_datetime(last.index[0].to_pydatetime().replace(hour=23))]
        price = (
            pd.concat((price, last))
            .resample("h")
            .ffill()
            .drop(price.loc[(price.index.month == 2) & (price.index.day == 29)].index)
        )
        if price.shape[0] != self.n_timesteps:
            msg = (
                "An error occurred converting EIA data to hourly to match size:"
                f" {price.shape[0]} to simulation {self.n_timesteps=}"
            )
            raise ValueError(msg)
        return price

    def setup(self):
        """Defines the inputs and outputs of the model and converts the
        :py:attr:`EIANaturalGasFeedstockConfig.price` to an hourly timeseries for the
        ``plant_life``.
        """
        # TODO: figure out mult-site or single site usage for coordinates input
        # if (site_config := self.options["plant_config"].get("site")) is None:
        #     raise ValueError("Single-site definition is missing from the plant configuration.")
        self.config = EIANaturalGasFeedstockConfig.from_dict(
            merge_shared_inputs(self.options["tech_config"]["model_inputs"], "cost"),
            # merge_shared_inputs(self.options["tech_config"]["model_inputs"], "cost") | site_config,  # noqa: E501
            additional_cls_name=self.__class__.__name__,
            strict=False,
        )
        self.n_timesteps = int(self.options["plant_config"]["plant"]["simulation"]["n_timesteps"])

        super().setup()

        self.dt = self.options["plant_config"]["plant"]["simulation"]["dt"]
        self.plant_life = int(self.options["plant_config"]["plant"]["plant_life"])
        self.fraction_of_year_simulated = (
            self.dt / SECONDS_PER_HOUR * self.n_timesteps / HOURS_PER_YEAR
        )
        price = self._extrapolate_price_to_hourly()

        self.add_input(
            f"{self.config.commodity}_consumed",
            val=0.0,
            shape=self.n_timesteps,
            units=self.config.commodity_rate_units,
            desc=f"Consumption profile of {self.config.commodity}",
        )
        self.add_input(
            f"{self.config.commodity}_out",
            val=0,
            shape=self.n_timesteps,
            units=self.config.commodity_rate_units,
        )
        self.add_input(
            "price",
            val=price.price.to_numpy(),
            units=f"USD/({self.config.commodity_amount_units})",
            desc=f"Price profile of {self.config.commodity}",
        )

        self.add_output(
            f"total_{self.config.commodity}_consumed",
            val=0.0,
            units=self.config.commodity_amount_units,
        )
        self.add_output(
            f"annual_{self.config.commodity}_consumed",
            val=0.0,
            shape=self.plant_life,
            units=f"({self.config.commodity_amount_units})/year",
        )
        self.add_output(
            "capacity_factor",
            val=0.0,
            shape=self.plant_life,
            units="unitless",
            desc="Capacity factor",
        )
        self.add_output(
            "replacement_schedule",
            val=0.0,
            shape=self.plant_life,
            units="unitless",
            desc="Lifetime estimate of item replacements as a fraction of capacity",
        )

        # TODO: Update to the commodity_capacity input of the FeedstockPerformanceModel
        # NOTE: Should I set this to rated_capacity if it's available?
        self.add_output(
            f"rated_{self.config.commodity}_production",
            val=0,
            units=self.config.commodity_rate_units,
        )

    def compute(self, inputs, outputs, discrete_inputs, discrete_outputs):
        """Calculates the following outputs:

        - ``capacity_factor``: commodity_consumed / commodity_out
        - ``total_commodity_consumed``: sum of commodity_consumed divided by number
          of hours simulated.
        - ``annual_commodity_consumed``: :py:attr:`total_commodity_consumed` * (1 / years simulated)
        - ``rated_commodity_production``: maximum input ``commodity_out``.
        - ``CapEx``: :py:attr:`FeedstockCostConfig.start_up_cost`.
        - ``OpEx``: :py:attr:`FeedstockCostConfig.annual_cost`.
        - ``VarOpEx``: sum of (:py:attr:`FeedstockCostConfig.price` * input ``commodity_consumed``).
        """
        outputs["capacity_factor"] = (
            inputs[f"{self.config.commodity}_consumed"].sum()
            / inputs[f"{self.config.commodity}_out"].sum()
        )
        outputs[f"total_{self.config.commodity}_consumed"] = inputs[
            f"{self.config.commodity}_consumed"
        ].sum() * (self.dt / 3600)

        # TODO: update to handle varying consumption levels when feedstock consumption is available
        outputs[f"annual_{self.config.commodity}_consumed"] = outputs[
            f"total_{self.config.commodity}_consumed"
        ] * (1 / self.fraction_of_year_simulated)

        outputs[f"rated_{self.config.commodity}_production"] = inputs[
            f"{self.config.commodity}_out"
        ].max()

        # TODO: Calculate costs
        price = inputs["price"]
        hourly_consumption = inputs[f"{self.config.commodity}_consumed"]
        cost_per_year = sum(price * hourly_consumption)

        outputs["CapEx"] = self.config.start_up_cost
        outputs["OpEx"] = self.config.annual_cost
        outputs["VarOpEx"] = cost_per_year
