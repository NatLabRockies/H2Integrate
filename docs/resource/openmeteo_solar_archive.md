(solar_resource:openmeteo_historical)=
# Solar Resource: Open-Meteo Historical Solar Data

This resource class downloads solar resource data from the [OpenMeteo Archive API](https://open-meteo.com/en/docs/historical-weather-api)

This dataset allows for solar resource data to be downloaded for:
- **resource years** from 1940 to year before the current calendar year.
- **locations** across the globe.
- **time intervals** of 60 minutes.

## Available Data

| Resource Data     | Included  |
| :---------------- | :---------------: |
| `wind_direction`      | X  |
| `wind_speed`      | X |
| `temperature`      | X |
| `pressure`      |  X |
| `relative_humidity`      | X |
| `ghi`      | X |
| `dhi`      | X |
| `dni`      | X |
| `clearsky_ghi`      |  |
| `clearsky_dhi`      |   |
| `clearsky_dni`      |   |
| `dew_point`      | X |
| `surface_albedo`      | X |
| `solar_zenith_angle`      |   |
| `snow_depth`      | X |
| `precipitable_water`      | X |

| Additional Data     | Included  |
| :---------------- | :---------------: |
| `site_id`      |    |
| `site_lat`      | X |
| `site_lon`      | X |
| `elevation`      |  X |
| `site_tz`      |   |
| `data_tz`      | X |
| `filepath`      | X |
| `year`      | X |
| `month`      | X |
| `day`      | X |
| `hour`      | X |
| `minute`      | X |
| `start_time`| X |
| `end_time`| X |
| `dt`| X |
