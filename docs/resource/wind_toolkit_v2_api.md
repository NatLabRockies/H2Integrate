(wind_resource:wtk_v2_api)=
# Wind Resource: WTK V2 API

This resource class downloads wind resource data from [Wind Toolkit Data V2](https://developer.nrel.gov/docs/wind/wind-toolkit/wtk-download/)
and requires an NREL API key to use.

This dataset allows for resource data to be downloaded for:
- **resource years** from 2007 to 2014.
- **locations** within the continental United States.
- **resource heights** from 10 to 200 meters.
- **time intervals** of 5, 15, 30, and 60 minutes.

## Available Data

| Resource Data     | Resource Heights (m)  |
| :---------------- | :---------------: |
| `wind_speed`  | 10, 40, 60, 80, 100, 120, 140, 160, 200 |
| `wind_direction`  | 10, 40, 60, 80, 100, 120, 140, 160, 200 |
| `temperature`  | 10, 40, 60, 80, 100, 120, 140, 160, 200 |
| `pressure`  | 0, 100, 200 |
| `relative_humidity`  | 2 |
| `precipitation_rate`  | 0 |

| Additional Data     | Included  |
| :---------------- | :---------------: |
| `site_id`      | X  |
| `site_lat`      | X |
| `site_lon`      | X |
| `elevation`      |  -- |
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
