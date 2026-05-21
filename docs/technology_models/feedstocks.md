# Feedstock Models

Feedstock models in H2Integrate represent any resource input that is consumed by technologies in your plant that comes from outside your designed system boundary (and not generated internally), such as natural gas, water, electricity from the grid, or any other material input.
The feedstock modeling approach provides a flexible way to track resource consumption and calculate associated costs for any type of input material or energy source.
Please see the example `16_natural_gas` in the `examples` directory for a complete setup using natural gas as a feedstock.

## How Feedstock Models Work

### Two-Component Architecture

Each feedstock type requires two model components:

1. **Performance Model** (`FeedstockPerformanceModel`):
   - Generates the feedstock supply profile
   - Outputs `{commodity}_out` variable
   - Located at the beginning of the technology chain

2. **Cost Model** (`FeedstockCostModel`):
   - Calculates consumption costs based on actual usage
   - Takes `{commodity}_consumed` as input
   - Located after all consuming technologies in the chain
   - Calculates the capacity factor of the consumed feedstock

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

### Performance Model Parameters

- `commodity` (str): Identifier for the feedstock type (e.g., "natural_gas", "water", "electricity")
- `commodity_rate_units` (str): commodity_rate_units for feedstock consumption (e.g., "MMBtu/h", "kg/h", "galUS/h", or "MW")
- `rated_capacity` (float): Maximum feedstock supply rate in `commodity_rate_units`

### Cost Model Parameters

- `commodity` (str): Must match the performance model identifier
- `commodity_rate_units` (str): Must match the performance model commodity_rate_units
- `price` (float, int, or list): Cost per unit in `USD/commodity_amount_units`. Can be:
  - Scalar: Constant price for all timesteps and years
  - List of length `n_timesteps`: Price per timestep, applied uniformly across all years
  - List of length `plant_life`: Price per year of plant operation
- `annual_cost` (float, optional): Fixed cost per year in USD/year. Defaults to 0.0
- `start_up_cost` (float, optional): One-time capital cost in USD. Defaults to 0.0
- `cost_year` (int): Dollar year for cost inputs
- `commodity_amount_units` (str | None, optional): the amount units of the commodity (i.e., "MMBtu", "kg", "galUS" or "kW*h"). If None, will be set as `commodity_rate_units*h`

```{tip}
The `price` parameter is flexible - you can specify constant pricing with a single value, time-varying pricing with an array of length `n_timesteps`, or per-year pricing with an array of length `plant_life`. When `n_timesteps == plant_life`, the per-year interpretation will be used and a warning is issued for clarity.
```

### Consumed Feedstock Outputs

The feedstock model outputs cost and performance information about the consumed feedstock. The most notable outputs are:
- `VarOpEx`: cost of the feedstock consumed (in `USD/yr`)
- `total_{commodity}_consumed`: total feedstock consumed over simulation (in `commodity_amount_units`)
- `annual_{commodity}_consumed`: annual feedstock consumed (in `commodity_amount_units/yr`)
- `rated_{commodity}_production`: this is equal to the the `rated_capacity` of the feedstock model (in `commodity_rate_units`)
- `capacity_factor`: ratio of the feedstock consumed to the maximum feedstock available

## EIA Natural Gas Pricing

A special case of the feedstock cost model `EIANaturalGasFeedstockCostModel` exists to enable users
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
[`h2integrate/preprocess/eia.py`](https://github.com/NatLabRockies/H2Integrate/h2integrate/preprocess/eia.py).
In particular, use the `get_eia_ng_data` function once an API has been created and saved to your
environment variables or to a file.

### Configuring the EIA Cost Model

Similar to the standard feedstock model, the following variables are able to be set by the user

- `cost_year` (int): Dollar year for cost inputs
- `annual_cost` (float, optional): Fixed cost per year in USD/year. Defaults to 0.0
- `start_up_cost` (float, optional): One-time capital cost in USD. Defaults to 0.0

Additionally, there are a few other settings that users will need to provide for the model to work
that differ from the standard cost model.

:::{important}
If relying on site coordinate data (`latitude` and `longitude`), then the `reverse_geocoder` package
is required, which can be pip installed directly or through the `gis` library extras.
:::

- `resource_year` (int): Which year to obtain the data from in the range [2001, 2026].
- `monthly` (bool): If True, the monthly data are retrieved, otherwise the annual price is used.
- location data options 1) use `state` or 2) use `latitude` and `longitude`:
  - `state` (str): Full name of the state or two-letter state abbreviation, such as "United States" or
    "US". Only the "US" or all 50 states will produce valid results. When `state` is provided, the
    site coordinate data will be ignored.
  - `latitude` (float): Latitude of the natural gas plant site. Only used when `state` is not
    provided, and will be filled from the plant configuration's site data if not provided.
  - `longitude` (float): Longitude of the natural gas plant site. Only used when `state` is not
    provided, and will be filled from the plant configuration's site data if not provided.

- `price_category` (str): One of "wellhead", "imports", "citygate", "residential", "commercial",
  "industrial", "electrical_power", or "exports". Note that not all categories will return
  state-level data.
- `api_key_file` (str, optional): The file where the user's API key is stored. If storing in a file,
  define it on its own line using the convention "EIA_API_KEY: xxxx", or have the API key defined as
  an environment variable set as "EIA_API_KEY".
- `filename` (str, optional): Filename where the data should be loaded from if it exists or saved
  to once it is downloaded.

- `commodity`: Set to "natural_gas" internally.
- `commodity_rate_units`: Set to "MMBtu/h" internally.
- `commodity_amount_units`: Set to "MMBtu" internally.
