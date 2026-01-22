(solar_resource:goes_v4_api)=
# Solar Resource: GOES PSM v4

There are four datasets that use the [NSRDB GOES PSM v4 API](https://developer.nrel.gov/docs/solar/nsrdb/nsrdb-GOES-full-disc-v4-0-0-download/) calls:
- "goes_aggregated_solar_v4_api"
- "goes_conus_solar_v4_api"
- "goes_fulldisc_solar_v4_api"
- "goes_tmy_solar_v4_api"
    - supports solar resource data for typical meteorological year (TMY), typical global horizontal irradiance year (TGY), and typical direct normal irradiance year (TDY)

These datasets allow for resource data to be downloaded for **locations** within the continental United States.

| Model      | Temporal resolution | Spatial resolution | Years covered | Regions | Website |
| :--------- | :---------------: | :---------------: | :---------------: | :---------------: | :---------------: |
| `goes_aggregated_solar_v4_api`  | 30, 60 min  | 4 km | 1998-2024  | North America, South America | [GOES Aggregated](https://developer.nrel.gov/docs/solar/nsrdb/nsrdb-GOES-aggregated-v4-0-0-download/) |
| `goes_conus_solar_v4_api`  | 5, 15, 30, 60 min  | 2 km | 2018-2024  | Continental United States | [GOES Conus](https://developer.nrel.gov/docs/solar/nsrdb/nsrdb-GOES-conus-v4-0-0-download/) |
| `goes_fulldisc_solar_v4_api`  | 10, 30, 60 min  | 2 km | 2018-2024  | North America, South America |  [GOES Full disc](https://developer.nrel.gov/docs/solar/nsrdb/nsrdb-GOES-full-disc-v4-0-0-download/) |
| `goes_tmy_solar_v4_api`  | 60 min  | 4 km | 2022-2024, for tmy, tdy and tgy  | North America, South America |  [GOES TMY](https://developer.nrel.gov/docs/solar/nsrdb/nsrdb-GOES-tmy-v4-0-0-download/) |


```{note}
For the goes_tmy_v4_api model, the resource_year should be specified as a string formatted as `tdy-yyyy` or `tgy-yyy` or `tmy-yyyy` where yyyy is the year between 2022 and 2024.
```


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
| `clearsky_ghi`      | X |
| `clearsky_dhi`      | X |
| `clearsky_dni`      | X |
| `dew_point`      | X |
| `surface_albedo`      | X |
| `solar_zenith_angle`      | X |
| `snow_depth`      | X |
| `precipitable_water`      | X |

| Additional Data     | Included  |
| :---------------- | :---------------: |
| `site_id`      | X  |
| `site_lat`      | X |
| `site_lon`      | X |
| `elevation`      |  X |
| `site_tz`      | X |
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
