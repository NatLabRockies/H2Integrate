(tidal_resource:models)=
# Tidal Resource: Model Overview

The tidal resource model is essentially a file reader that processes the data for use in the OpenMDAO format of H2I. It expects a CSV file to be input with timeseries tidal data and meta data.

The registered model is {py:class}`~h2integrate.resource.tidal.TidalResource`, configured by
{py:class}`~h2integrate.resource.tidal.TidalResourceConfig` with `resource_dir` and
`resource_filename`. The component declares `latitude` and `longitude` inputs, but reads the
specified file rather than using these values to select data. Its `tidal_velocity` output is
an array of 8,760 hourly speeds in m/s.

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

If the reader returns fewer than 8,760 records, the model resamples the timestamps to hourly
means, linearly interpolates gaps, and forward-fills missing hours at the end of the year.
Exactly 8,760 records are passed through; more than 8,760 records raise an error.
