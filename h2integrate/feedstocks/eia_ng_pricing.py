from pathlib import Path
from datetime import datetime

import attrs
import numpy as np
import pandas as pd
from attrs import field, define

from h2integrate.preprocess import eia, geospatial
from h2integrate.core.utilities import merge_shared_inputs
from h2integrate.core.file_utils import get_path
from h2integrate.core.validators import range_val
from h2integrate.feedstocks.feedstocks import FeedstockCostModel
from h2integrate.core.model_baseclasses import BaseConfig


HOURS_PER_YEAR = 8760
SECONDS_PER_HOUR = 3600
CURRENT_YEAR = datetime.now().year

default_price = pd.DataFrame(
    np.zeros(8760, dtype=float).reshape(-1, 1),
    columns=["price"],
    index=pd.date_range("2001-01-01", "2001-12-31 23:00:00", freq="h"),
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
    price_category: str = field(
        converter=str.lower, validator=attrs.validators.in_(eia.EIA_NG_FACET)
    )
    api_key_file: str | None = field(default=None, converter=attrs.converters.optional(get_path))
    state: str = field(
        default=None,
        converter=attrs.converters.optional(
            attrs.converters.pipe(geospatial.convert_state_value, geospatial.convert_state_to_code)
        ),
        validator=attrs.validators.optional(
            attrs.validators.in_([*geospatial.STATE_MAP, *geospatial.STATE_MAP.values()])
        ),
    )
    latitude: float | None = field(
        default=None, validator=attrs.validators.optional(range_val(-90.0, 90.0))
    )
    longitude: float | None = field(
        default=None, validator=attrs.validators.optional(range_val(-180.0, 180.0))
    )
    cost_year: int = field(default=CURRENT_YEAR)
    annual_cost: float = field(default=0.0, converter=float)
    start_up_cost: float = field(default=0.0, converter=float)
    filename: str = field(default=None)

    commodity: str = field(default="natural_gas", init=False)
    commodity_rate_units: str = field(default="MMBtu/h", init=False)
    commodity_amount_units: str = field(default="MMBtu", init=False)
    price: pd.DataFrame = field(
        default=default_price, init=False, validator=attrs.validators.instance_of(pd.DataFrame)
    )

    def __attrs_post_init__(self):
        """Creates the EIA natural gas facet series code based on validated user inputs, sets the
        :py:attr:`commodity_amount_units` if not given a value, and fetches the EIA natural gas
        price.
        """
        if self.filename is not None:
            try:
                self.filename = get_path(self.filename)
            except FileNotFoundError:
                self.filename = Path(self.filename).resolve()

        if self.state is None:
            if self.latitude is None or self.longitude is None:
                msg = (
                    "The EIA natural gas feedstock model require one of `state` or"
                    " `latitude` and `longitude`."
                )
                raise ValueError(msg)

            self.state = geospatial.get_state_from_coords(self.latitude, self.longitude)


class EIANaturalGasFeedstockCostModel(FeedstockCostModel):
    """Feedstock cost model based on the EIA natural gas price API results that uses
    annual or monthly data to model an hourly time step for a single year to model the
    price of natural gas used in the model.
    """

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
        if (site_config := self.options["plant_config"].get("site")) is None:
            raise ValueError("Single-site definition is missing from the plant configuration.")
        self.config = EIANaturalGasFeedstockConfig.from_dict(
            merge_shared_inputs(self.options["tech_config"]["model_inputs"], "cost"),
            # merge_shared_inputs(self.options["tech_config"]["model_inputs"], "cost") | site_config,  # noqa: E501
            additional_cls_name=self.__class__.__name__,
            strict=False,
        )
        price = eia.get_eia_ng_data(
            api_key_file=self.config.api_key_file,
            resource_year=self.config.resource_year,
            price_category=self.config.price_category,
            state=self.config.state,
            monthly=self.config.monthly,
            filename=self.config.filename,
        )
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

        # TODO: once the feedstock consumption has standardized outputs, update this to handle
        # consumption that varies over all years of operations.
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
