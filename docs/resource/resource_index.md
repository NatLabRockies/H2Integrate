---
jupytext:
  text_representation:
    extension: .md
    format_name: myst
    format_version: 0.13
    jupytext_version: 1.18.1
kernelspec:
  display_name: Python 3
  language: python
  name: python3
---

# Resource data


- [Wind Resource Data](wind_resource:models)
- [Solar Resource Data](solar_resource:models)
- [Tidal Resource Data](tidal_resource:models)
- [Resource Datasets](h5_dataset:overview)

## Common Resource Datasets and Considerations

Both wind and solar resource data can be obtained from resource models that use the [OpenMeteo Archive API](https://open-meteo.com/en/docs/historical-weather-api) or resource models that use the resource models available in the [NLR Developer Network](https://developer.nlr.gov).

Resource models that use the [NLR Developer Network](https://developer.nlr.gov) require an API key (which can be obtained for free from [here](https://developer.nlr.gov/signup/)). Resource models that use the OpenMeteo Archive API do not require an API key.

Another key difference is that the NLR resource datasets are constrained to specific geographic regions, meaning you have to choose the resource model that corresponds to your site location. OpenMeteo resource data is available globally, for all onshore sites.

```{note}
OpenMeteo data can be downloaded directly from the web instead of using the models in H2I. If OpenMeteo resource data is downloaded directly from the web and in the local timezone of the site, the data is downloaded with a UTC offset in *daylight time* whereas data downloaded with the H2I resource models will use a UTC offset in *standard time*. Resource data downloaded from the NLR Developer developer network in local time also use a UTC offset in *standard time*.
```


## Specifying multiple resource years for API resource models

If running a simulation that is longer than 1 year, then there are a few options for specifying the resource years to use during the simulation. These options depend on the user inputs and are explained below:

1. Use `resource_year` as the starting year. This option is enabled when `resource_filename` and `resource_year_order` are not provided. With this option, the first year of resource data is for `resource_year` and following years are calculated based on the number of years resource data is needed for the simulation.
2. Use resource data from a list of filenames. This option is enabled when `resource_filename` is a list. The list must be the same length as the number of years needed for the simulation. The filenames provided as `resource_filename` are **not used if the site changes from the site defined in the configuration file**. This can be used with `resource_year_order`, where `resource_year_order` is used if the site changes. If `resource_year_order` is not specified, the year order is inferred from the data in the provided files under the 'year' column (unless using a TMY dataset, in which case the year order is inferred from the filename). Supplying `resource_year_order` alongside `resource_filename` avoids inferring the years and makes the replacement years explicit. The inferred or provided `resource_year_order` is used instead of `resource_year`.
3. Use a specified order of resource years. This option is enabled when `resource_year_order` is a list of resource years and `resource_filename` is an empty string (or not provided). The list must be the same length as the number of years needed for the simulation. The `resource_year_order` is used instead of `resource_year`. As mentioned above, this can be used with the `resource_filename` option.

## Resampling resource data

API resource data may have a different native timestep from the simulation you would like to run. H2I does not resample resource data by default, but you can set explicit parameters in the input file to either upsample the data, downsample the data, or perform both upsampling and downsampling if you have nonuniform data time steps to obtain data for your desired timestep.
The options available are those enabled in the pandas interpolation method for upsampling ([`pandas.DataFrame.interpolate`](https://pandas.pydata.org/docs/reference/api/pandas.DataFrame.interpolate.html)) or a pandas aggregation method for downsampling ([`pandas.DataFrame.agg`](https://pandas.pydata.org/docs/reference/api/pandas.DataFrame.agg.html)) in the resource's `resource_parameters`.

Set `upsample_method` or `downsample_method` in `resource_parameters` to explicitly select the pandas operation. If the data timestep and simulation timestep already match, neither setting is needed. When resampling is requested, H2I emits a warning naming the source timestep, target timestep, direction, and method. If a mismatch requires resampling but no corresponding method is set, H2I raises an error. See {py:func}`h2integrate.resource.utilities.time_tools.resample_resource_data_to_dt` for method details.

### Non-uniform timestep resampling

Resource data with non-uniform time steps (e.g., higher frequency during certain hours
or varying intervals across years) is supported. The following example demonstrates
resampling a dataset containing both 15-minute and 2-hour intervals to a uniform 1-hour
simulation time step, applying downsampling and upsampling in the same run:

```{code-cell} ipython3
:tags: [remove-input]

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from h2integrate.resource.utilities.time_tools import resample_resource_data_to_dt

# Mixed-resolution series: 15-min intervals followed by 2-hour intervals
idx1 = pd.date_range("2020-01-01 00:00", "2020-01-01 03:00", freq="15min")
idx2 = pd.date_range("2020-01-01 05:00", "2020-01-01 11:00", freq="2h")
idx = idx1.append(idx2)

t_hours = (idx - idx[0]).total_seconds() / 3600.0
vals = 8.0 + 4.0 * np.sin(t_hours * np.pi / 6.0)

data = {
    "year": idx.year.to_numpy().astype(float),
    "month": idx.month.to_numpy().astype(float),
    "day": idx.day.to_numpy().astype(float),
    "hour": idx.hour.to_numpy().astype(float),
    "minute": idx.minute.to_numpy().astype(float),
    "wind_speed": vals,
}

# Resample to 1 hour (3600 s): downsamples 15-min region, upsamples 2-hr region
res = resample_resource_data_to_dt(
    data,
    3600,
    upsample_method="time",
    downsample_method="mean",
)

orig_dt = pd.to_datetime({
    "year": data["year"],
    "month": data["month"],
    "day": data["day"],
    "hour": data["hour"],
    "minute": data["minute"],
})
res_dt = pd.to_datetime({
    "year": res["year"],
    "month": res["month"],
    "day": res["day"],
    "hour": res["hour"],
    "minute": res["minute"],
})

fig, ax = plt.subplots(figsize=(9, 4.5))
ax.plot(
    orig_dt,
    data["wind_speed"],
    "o",
    label="Original (non-uniform: 15-min & 2-hr dt)",
    color="tab:blue",
    markersize=7,
    zorder=2,
)
ax.plot(
    res_dt,
    res["wind_speed"],
    "x--",
    label="Resampled (uniform 1-hr dt)",
    color="tab:orange",
    linewidth=1.5,
    markersize=7,
    zorder=3,
)
ax.axvspan(
    orig_dt.iloc[0],
    pd.Timestamp("2020-01-01 03:00"),
    color="tab:green",
    alpha=0.1,
    label="Downsampled region (15 min -> 1 hr)",
)
ax.axvspan(
    pd.Timestamp("2020-01-01 03:00"),
    res_dt.iloc[-1],
    color="tab:purple",
    alpha=0.1,
    label="Upsampled region (2 hr -> 1 hr)",
)
ax.set_xlabel("Time")
ax.set_ylabel("Wind Speed (m/s)")
ax.set_title("Resampling Non-Uniform Data with Both Downsampling and Upsampling")
ax.legend(loc="best")
ax.grid(True, linestyle="--", alpha=0.5)
fig.tight_layout()
plt.show()
```

The resampled line does not pass through every original point, by design:

- **Downsampling (15 min to 1 hr):** each original sample is treated as covering the interval
  that starts at its timestamp. Each hourly value is the `downsample_method` aggregate (here,
  the mean) of all original samples in the hour starting at that hourly timestamp. For
  example, the 00:00 value is the mean of the 00:00, 00:15, 00:30, and 00:45 samples
  (about 8.8 m/s), not the 00:00 sample itself (8.0 m/s). While the data is rising, this mean
  is higher than the original value at the start of the hour, and while it is falling it is
  lower. This preserves the average of the data, which is not the case if values are simply
  picked from the original series.
- **Upsampling (2 hr to 1 hr):** the resampled values are interpolated between original
  samples using `upsample_method`, so the line passes through the original points and adds
  new points in between.
- **End of the data:** the final original sample is assumed to cover one more time step of its
  own length, so the resampled series extends past the last original timestamp (here, to
  12:00) and holds the last value.

## Setting resource data for a technology

There are two ways to supply resource data to a technology:
1. Set resource for a technology data [using `set_val()`](#resource-data-specified-using-setval)
2. Create a [custom resource model](#custom-resource-models) for the technology



(resource-data-specified-using-setval)=
### Resource data specified using `set_val()`

Resource data for a technology can be set using the `set_val()` command. In the [Run of River Example](https://github.com/NatLabRockies/H2Integrate/tree/develop/examples/07_run_of_river_plant/), the technology named `river` needs a resource input called `discharge`. An example of this is shown below:

```python
import pandas as pd
from h2integrate import H2IntegrateModel
# Create an H2I model
h2i = H2IntegrateModel("07_run_of_river.yaml")

# Suppose we load the resource data from a csv file
resource_df = pd.read_csv("river_resource_data.csv")

# Setup the h2i model
h2i.setup()

# Set the resource data for the river
h2i.set_val("river.discharge", val=resource_df["discharge"].values, units="m**3/s")

# Run the model
h2i.run()
```


(custom-resource-models)=
### Custom resource models
The benefit of using a custom resource model is that the resource data can be made to vary for different inputs, which can be beneficial if running a design sweep or optimization where the resource location (specified by a latitude and longitude) is a design variable.

A general resource model can be defined similarly to a custom technology model. A custom resource model should be defined in the plant configuration file within a site section under `sites`.

```{note}
Note that all custom resource models must have inputs of `latitude` and `longitude`. The outputs of your custom resource model should match the expected input to whatever model its connected to.
```

Below shows an example, similar to the [Run of River Example](https://github.com/NatLabRockies/H2Integrate/tree/develop/examples/07_run_of_river_plant/) of how to define a custom resource model within the `plant_config.yaml` file:

```yaml
sites:
  site:
    latitude: 32.34
    longitude: -98.27
    resources:
      river_resource:
        resource_model: CustomRiverResource
        resource_model_location: river_resource/river_resource_model.py
        resource_parameters:
          filename: river_data.csv

site_to_tech_connections:
  # connect the river resource to the run-of-river hydro technology
  - [site.river_resource, river, discharge]
```

The output `discharge` from the custom `river_resource` model is an input to the technology `river`. The custom resource model is a class named `CustomRiverResource` and the filepath for the `CustomRiverResource` is specified as the `resource_model_location`.
