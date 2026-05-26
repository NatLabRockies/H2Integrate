import warnings
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
        latitude (float | None): WGS-84 y-coordinate of the site. Will not be used if
            :py:attr:`state` has been provided.
        longitude (float | None): WGS-84 x-coordinate of the site. Will not be used if
            :py:attr:`state` has been provided.
        site_name (str, optional): Name of the site from a multi-site private configuration. When
            provided, the :py:class:`EIANaturalGasFeedstockCostModel` will populate the
            :py:attr:`latitude` and :py:attr:`longitude` from the plant site configuration.
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
            attrs.validators.in_([*geospatial.US_STATE_MAP, *geospatial.US_STATE_MAP.values()])
        ),
    )
    latitude: float | None = field(
        default=None, validator=attrs.validators.optional(range_val(-90.0, 90.0))
    )
    longitude: float | None = field(
        default=None, validator=attrs.validators.optional(range_val(-180.0, 180.0))
    )
    site_name: str = field(
        default=None, validator=attrs.validators.optional(attrs.validators.instance_of(str))
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

            self.state = geospatial.get_state_from_coords(
                latitude=self.latitude, longitude=self.longitude
            )


class EIANaturalGasFeedstockCostModel(FeedstockCostModel):
    """Feedstock cost model based on the EIA natural gas price API results that uses
    annual or monthly data to model an hourly time step for a single year to model the
    price of natural gas used in the model.

    The model will pull the single site data if it is made available to pass the ``latitude`` and
    ``longitude`` from the site configuration, otherwise the ``state`` will need to be provided
    in the configuration.
    """

    def setup(self):
        """Defines the inputs and outputs of the model and converts the
        :py:attr:`EIANaturalGasFeedstockConfig.price` to an hourly timeseries for the
        ``plant_life``.

        Populates the site latitude and longitude with either the configuration's provided site
        name or the first site in plant configuration's ``sites`` dictionary when a ``state`` is
        not directly provided.
        """
        site_config = {}
        sites = self.options["plant_config"].get("sites", {})
        cost_config = merge_shared_inputs(self.options["tech_config"]["model_inputs"], "cost")

        if cost_config.get("state") is None:
            if (site_name := cost_config.get("site_name")) is not None and sites:
                site_config = sites.get(site_name, {})
            if site_name is None and sites:
                site_config = sites[[*sites][0]]

        self.config = EIANaturalGasFeedstockConfig.from_dict(
            cost_config | site_config, additional_cls_name=self.__class__.__name__, strict=False
        )

        price = eia.get_eia_ng_data(
            api_key_file=self.config.api_key_file,
            resource_year=self.config.resource_year,
            price_category=self.config.price_category,
            state=self.config.state,
            monthly=self.config.monthly,
            filename=self.config.filename,
        )
        price = eia.convert_to_hourly(price)
        self.config.price = price
        super().setup()

    def compute(self, inputs, outputs):
        if not np.isclose(inputs["price"], self.config.price, rtol=1e-6):
            warn_msg = "The NG price has changed from EIA price. This may be intended."
            warnings.warn(warn_msg, UserWarning)
        super().compute(inputs, outputs)
