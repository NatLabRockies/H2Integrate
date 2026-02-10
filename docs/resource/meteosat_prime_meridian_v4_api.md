(solar_resource:msg_v4_api)=
# Solar Resource: Meteosat Prime Meridian PSM v4

There are two datasets that use the [NSRDB Meteosat Prime Meridian PSM v4 API](https://developer.nrel.gov/docs/solar/nsrdb/nsrdb-msg-v1-0-0-download/) calls:
- "MeteosatPrimeMeridianSolarAPI"
- "MeteosatPrimeMeridianTMYSolarAPI"
    - supports solar resource data for typical meteorological year (TMY), typical global horizontal irradiance year (TGY), and typical direct normal irradiance year (TDY)

These datasets allow for resource data to be downloaded for **locations** within Africa and Europe.

| Model      | Temporal resolution | Spatial resolution | Years covered | Regions | Website |
| :--------- | :---------------: | :---------------: | :---------------: | :---------------: | :---------------: |
| `MeteosatPrimeMeridianSolarAPI`  | 15, 30, 60 min  | 4 km | 2005-2022  | Africa and Europe | [Meteosat Prime Meridian](https://developer.nrel.gov/docs/solar/nsrdb/nsrdb-msg-v1-0-0-download/) |
| `MeteosatPrimeMeridianTMYSolarAPI`  | 60 min  | 4 km | 2022 or 2014, for tmy, tdy and tgy  | Africa and Europe |  [Meteosat Prime Meridian TMY](https://developer.nrel.gov/docs/solar/nsrdb/nsrdb-msg-v1-0-0-tmy-download/), [Meteosat Prime Meridian TGY](https://developer.nrel.gov/docs/solar/nsrdb/nsrdb-msg-v1-0-0-tgy-download/), and [Meteosat Prime Meridian TDY](https://developer.nrel.gov/docs/solar/nsrdb/nsrdb-msg-v1-0-0-tdy-download/)  |


```{note}
For the `MeteosatPrimeMeridianTMYSolarAPI` model, the `resource_year` should be specified as a string formatted as `tdy-yyyy` or `tgy-yyy` or `tmy-yyyy` where yyyy is the year is either 2014 or 2022.
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
