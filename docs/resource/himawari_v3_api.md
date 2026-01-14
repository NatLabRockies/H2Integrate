(solar_resource:himawari_v3_api)=
# Solar Resource: Himawari PSM v3

There are three datasets that use the [NSRDB Himawari PSM v3 API](https://developer.nrel.gov/docs/solar/nsrdb/himawari7-download/) calls:
- "himawari7_solar_v3_api"
- "himawari8_solar_v3_api"
- "himawari_tmy_solar_v3_api"
    - supports solar resource data for typical meteorological year (TMY), typical global horizontal irradiance year (TGY), and typical direct normal irradiance year (TDY)

These datasets allow for resource data to be downloaded for **locations** within Asia, Australia, and the Pacific.

| Model      | Temporal resolution | Spatial resolution | Years covered | Regions | Website |
| :--------- | :---------------: | :---------------: | :---------------: | :---------------: | :---------------: |
| `himawari7_solar_v3_api`  | 30, 60 min  | 4 km | 2011-2015  | Asia, Australia & Pacific | [Himawari 2011-15](https://developer.nrel.gov/docs/solar/nsrdb/himawari7-download/) |
| `himawari8_solar_v3_api`  | 10, 30, 60 min  | 2 km | 2016-2020  | Asia, Australia & Pacific | [Himawari 2016-2020](https://developer.nrel.gov/docs/solar/nsrdb/himawari-download/) |
| `himawari_tmy_solar_v3_api`  | 60 min  | 4 km | 2020, for tmy, tdy and tgy  | Asia, Australia & Pacific |  [Himawari TMY](https://developer.nrel.gov/docs/solar/nsrdb/himawari-tmy-download/) |


```{note}
For the himawari_tmy_solar_v3_api model, the resource_year should be specified as a string formatted as `tdy-2020` or `tgy-2020` or `tmy-2020`.
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
