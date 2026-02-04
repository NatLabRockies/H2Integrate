(wind_resource:models)=
# Wind Resource: Model Overview

- [**"WTKNRELDeveloperAPIWindResource"**](wind_resource:wtk_v2_api): this requires an API key for the NREL developer network
- [**"OpenMeteoHistoricalWindResource"**](wind_resource:openmeteo_archive)


```{note}
Please refer to the `Setting Environment Variables` doc page for information on setting up an NREL API key if you haven't yet.
```

(windresource:overview)=
# Wind Resource: Output Data

Wind resource models may output wind resource data, site information, information about the data source, and time information. This information is outputted as a dictionary. The following sections detail the naming convention for the dictionary keys, standardized units, and descriptions of all the output data that may be output from a wind resource model.

- [Wind Resource Data](#primary-data-wind-resource-timeseries)
- [Site Information](#additional-data-site-information)
- [Data Source Information](#additional-data-data-source)
- [Time Profile Information](#additional-data-time-profile)


```{note}
Not all wind resource models will output all the data keys listed below. Please check the documentation for each wind resource model and wind performance model to ensure compatibility.
```

(primary-data-wind-resource-timeseries)=
## Primary Data: Wind Resource Timeseries
The below variables are outputted as arrays, with a length equal to the simulation duration. In the variables listed below, `<height>` is used to indicate the height (in meters) above the ground for the resource parameter. `<height>` should be 0 for surface level wind resource data. The naming convention and standardized units of wind resource variables are listed below:
- `wind_direction_<height>m`: wind direction in degrees (units are 'deg')
- `wind_speed_<height>m`: wind speed in meters per second (units are 'm/s')
- `temperature_<height>m`: air temperature in Celsius (units are 'C')
- `pressure_<height>m`: air pressure in atm (units are 'atm')
- `precipitation_rate_<height>m`: precipitation rate in millimeters per hour (units are 'mm/h')
- `relative_humidity_<height>`: relative humidity represented as a percentage (units are 'percent')

## Additional Data: Site Information
- `site_id` (int): site id
- `site_tz` (int | float): local timezone for the site
- `site_lat` (float): latitude of the site
- `site_lon` (float): longitude of the site
- `elevation` (float | int): elevation of the site in meters

## Additional Data: Data source
- `data_tz` (int | float): timezone the data is in represented as an hour offset from UTC
- `filepath` (str): filepath where the resource data was loaded from
- `start_time` (str): the start time of resource data formatted as "yyyy/mm/dd hh:mm:ss (tz)", where tz is the timezone represented as the UTC offset
- `end_time` (str): the end time of resource data formatted as "yyyy/mm/dd hh:mm:ss (tz)", where tz is the timezone represented as the UTC offset
- `dt` (int | float): the timestep of resource data in seconds

## Additional Data: Time profile
Time data may be outputted as arrays to represent the time profile of the resource data. These times should be represented in the timezone of `data_tz` (if outputted).
- `year`: year as 4-digit value (i.e., 2019)
- `month`: month of year (1-12)
- `day`: day of month (1-31)
- `hour`: hour of day from a 24-hour clock (0-23)
- `minute`: minute of hour (0-59)
