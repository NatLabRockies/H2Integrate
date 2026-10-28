(feedstocks:intro)=
# Feedstock Models

Feedstock models in H2Integrate represent any resource input that is consumed by technologies in your plant that comes from outside your designed system boundary (and not generated internally), such as natural gas, water, electricity from the grid, or any other material input.
The feedstock modeling approach provides a flexible way to track resource consumption and calculate associated costs for any type of input material or energy source.
Please see the example `16_natural_gas` in the `examples` directory for a complete setup using natural gas as a feedstock.

## How Feedstock Models Work

### Two-Component Architecture

Each feedstock type requires two model components:

1. **Performance Model** ({py:class}`~h2integrate.feedstocks.feedstocks.FeedstockPerformanceModel`,
   configured by {py:class}`~h2integrate.feedstocks.feedstocks.FeedstockPerformanceConfig`):
   - Generates the feedstock supply profile
   - Outputs `{commodity}_out` variable
   - Located at the beginning of the technology chain

2. **Cost Model** ({py:class}`~h2integrate.feedstocks.feedstocks.FeedstockCostModel`,
   configured by {py:class}`~h2integrate.feedstocks.feedstocks.FeedstockCostConfig`):
   - Calculates consumption costs based on actual usage
   - Takes `{commodity}_consumed` and `{commodity}_out` as inputs
   - Located after all consuming technologies in the chain
   - Calculates the capacity factor of the consumed feedstock

The performance model takes a scalar `{commodity}_capacity` input, defaulting to `rated_capacity`,
and outputs a constant supply profile at that rate. Both models support one-hour time steps.

### Technology Interconnections

Feedstocks connect to consuming technologies through the `technology_interconnections` in your plant configuration. The connection pattern is:

```yaml
technology_interconnections: [
    ["name_of_feedstock_source", "consuming_technology", "commodity", "connection_type"],
]
```

Where:

- `name_of_feedstock_source`: Name of your feedstock source
- `consuming_technology`: Technology that uses the feedstock
- `commodity`: Type identifier (e.g., "natural_gas", "water", "electricity")
- `connection_type`: Name for the connection (e.g., "pipe", "cable")

## Configuration

To use the feedstock performance and cost models, add an entry to your `tech_config.yaml` like this:

```yaml
ng_feedstock:
    performance_model:
        model: "FeedstockPerformanceModel"
    cost_model:
        model: "FeedstockCostModel"
    model_inputs:
        shared_parameters:
            commodity: "natural_gas"
            commodity_rate_units: "MMBtu/h"
        performance_parameters:
            rated_capacity: 100.
        cost_parameters:
            commodity_amount_units: "MMBtu" # optional, if not specified defaults to `commodity_rate_units*h`
            cost_year: 2023
            price: 4.2 # cost in USD/commodity_amount_units
            annual_cost: 0. #cost in USD/year
            start_up_cost: 100000. #cost in USD
```

### Model configuration references

The performance and cost configurations must use the same commodity and rate units.

```{eval-rst}
.. autoclass:: h2integrate.feedstocks.feedstocks.FeedstockPerformanceConfig
   :members:
   :no-index:

.. autoclass:: h2integrate.feedstocks.feedstocks.FeedstockCostConfig
   :members:
   :no-index:
```

```{tip}
The `price` parameter is flexible - you can specify constant pricing with a single value, time-varying pricing with an array of length `n_timesteps`, or per-year pricing with an array of length `plant_life`. When `n_timesteps == plant_life`, the per-year interpretation is used.
```

### Consumed Feedstock Outputs

The feedstock model outputs cost and performance information about the consumed feedstock. The most notable outputs are:
- `VarOpEx`: cost of the feedstock consumed (in `USD/yr`)
- `total_{commodity}_consumed`: total feedstock consumed over simulation (in `commodity_amount_units`)
- `annual_{commodity}_consumed`: annual feedstock consumed (in `commodity_amount_units/yr`)
- `rated_{commodity}_production`: this is equal to the the `rated_capacity` of the feedstock model (in `commodity_rate_units`)
- `capacity_factor`: ratio of the feedstock consumed to the maximum feedstock available

For partial-year simulations, annual consumption is annualized, but `VarOpEx` is based on
the simulated-period consumption without annualization. `CapEx` and `OpEx` are the configured
startup and annual fixed costs.

(feedstocks:eia_ng_price)=
## EIA Natural Gas Pricing

A special case of the feedstock cost model
{py:class}`~h2integrate.feedstocks.eia_ng_price.EIANaturalGasFeedstockCostModel`, configured by
{py:class}`~h2integrate.feedstocks.eia_ng_price.EIANaturalGasFeedstockConfig`, enables users
to download data from the EIA API's natural gas price
portal for a single site (see
[the relevant API docs](https://h2integrate.readthedocs.io/en/latest/_autosummary/h2integrate.feedstocks.eia_ng_price.html)
for complete details). Access to the wellhead, import, citygate, residential, commercial,
industrial, electrical power, and exports price facets are supported for the US
as a whole, though it is best to see which data are
[available online in the EIA API documentation](https://www.eia.gov/opendata/browser/natural-gas/pri/sum)
prior to using in an analysis.

Users are expected to get an EIA API key from the
[EIA Open Data portal](https://www.eia.gov/opendata/), or to download the data as as CSV file for
the model to load.

At present, the EIA natural gas cost model uses only a single year of price data (annual or monthly)
and extrapolates it to an hourly timeseries automatically. For users that wish to download a large
batch of data from the EIA, please see the EIA preprocessing tools in
{py:mod}`h2integrate.preprocess.eia`.
In particular, use the `get_eia_ng_data` function once an API has been created and saved to your
environment variables or to a file.

### Configuring the EIA Cost Model

The EIA cost model uses the configuration below instead of the standard feedstock cost
configuration. If the API key is stored in a file, define it on its own line as
`EIA_API_KEY: xxxx`; alternatively set the `EIA_API_KEY` environment variable.

```{eval-rst}
.. autoclass:: h2integrate.feedstocks.eia_ng_price.EIANaturalGasFeedstockConfig
   :members:
   :no-index:
```

:::{important}
If relying on site coordinate data (`latitude` and `longitude`), then the `reverse_geocoder` package
is required, which can be pip installed directly or through the `gis` library extras.
:::
