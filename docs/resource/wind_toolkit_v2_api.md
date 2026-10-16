(wind_resource:wtk_v2_api)=
# Wind Resource: Wind Toolkit V2 API

There are two datasets that use the [Wind Toolkit v2 API](https://developer.nlr.gov/docs/wind/wind-toolkit/) calls:
- ["WTKNLRDeveloperAPIWindResource"](wind_resource:wind_toolkit_data)
- ["HRRRMETToolkitWindAPI"](wind_resource:hrrr_met_data)

```{note}
These datasets require an API key from the [NLR developer network](https://developer.nlr.gov/signup/)
```

These datasets allow for resource data to be downloaded for **locations** within the continental United States.

| Model      | Temporal resolution | Spatial resolution | Years covered | Regions | Website |
| :--------- | :---------------: | :---------------: | :---------------: | :---------------: | :---------------: |
| `WTKNLRDeveloperAPIWindResource`  | 5, 15, 30, 60 min  | 4 km | 2007-2014  | Continental United States | [Wind Toolkit Data](https://developer.nlr.gov/docs/wind/wind-toolkit/wtk-download/) |
| `HRRRMETToolkitWindAPI`  | 60 min  | 2 km | 2015-2025  | Continental United States | [HRRR MET Toolkit](https://developer.nlr.gov/docs/wind/wind-toolkit/wtk-hrrr-met-toolkit-v1-0-0-download/) |

(wind_resource:wind_toolkit_data)=
## WTKNLRDeveloperAPIWindResource
This resource class downloads wind resource data from [Wind Toolkit Data v2](https://developer.nlr.gov/docs/wind/wind-toolkit/wtk-download/).

This dataset allows for resource data to be downloaded for:
- **resource years** from 2007 to 2014.
- **locations** within the continental United States.
- **resource heights** from 10 to 200 meters.
- **time intervals** of 5, 15, 30, and 60 minutes.

### Available Data

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



(wind_resource:hrrr_met_data)=
## HRRRMETToolkitWindAPI
This resource class downloads wind resource data from [HRRR MET Toolkit v2](https://developer.nlr.gov/docs/wind/wind-toolkit/wtk-hrrr-met-toolkit-v1-0-0-download/)

This dataset allows for resource data to be downloaded for:
- **resource years** from 2015 to 2025
- **locations** within the continental United States.
- **resource heights** from 10 to 500 meters.
- **time interval** of 60 minutes.

### Available Data

| Resource Data     | Resource Heights (m)  |
| :---------------- | :---------------: |
| `wind_speed`  | 10, 20, 40, 60, 80, 100, 120, 140, 160, 180, 200, 220, 240, 260, 280, 300, 400, 500 |
| `wind_direction`  | 10, 20, 40, 60, 80, 100, 120, 140, 160, 180, 200, 220, 240, 260, 280, 300, 400, 500 |
| `temperature`  | 0, 2, 10, 20, 40, 60, 80, 100, 120, 140, 160, 180, 200, 220, 240, 260, 280, 300, 400, 500 |
| `pressure`  | 0, 100, 200, 300 |
| `relative_humidity`  | 2 |
| `specifichumidity`  | 2 |
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
