(tidal_resource:models)=
# Tidal Resource: Model Overview

The tidal resource model is essentially a file reader that processes the data for use in the OpenMDAO format of H2I. It expects a CSV file to be input with timeseries tidal data and meta data.

The tidal resource format is based on the [System Advisor Model (SAM)](https://sam.nlr.gov/). Additional sample tidal resource files can be downloaded via the SAM GUI.

```{note}
H2I expects the resource date to be in a timeseries format rather than a probability distribution.
```

The tidal resource data should be in the format:
    - Rows 1 and 2: Header rows with location info.
    - Row 3: Column headings for time-series data
        - (`Year`, `Month`, `Day`, `Hour`, `Minute`, `Speed`).
    - Rows 4+: Data values:
    - `Speed` (current speed) in meters/second.

If the tidal data is greater than hourly the model will interpolate the values in between the timesteps so that the resulting data is in an hourly format.
