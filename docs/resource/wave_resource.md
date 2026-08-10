(wave_resource)=
# Wave Resource: Model Overview

The wave resource model reads and processes ocean wave data for use in the H2I framework. It expects a CSV file containing timeseries significant wave height (Hs) and energy period (Te) data, and outputs hourly arrays suitable for the {ref}`wave_performance` model.

The wave resource file format follows the [DOE Water Power Technologies Office (WPTO) US Wave Dataset](https://developer.nrel.gov/docs/wave/wave-hindcast-download-v1/) convention. Wave resource files for US coastal locations can be downloaded via the [MHKiT-Python](https://mhkit-software.github.io/MHKiT/) library or the WPTO Hindcast dataset API.

```{note}
H2I expects the wave resource data to be in a timeseries format (not a joint probability distribution).
If the source file contains data at a coarser-than-hourly resolution (e.g., 3-hourly), H2I will
linearly interpolate the values to produce an 8760-hour annual timeseries.
```

## File Format

The wave resource CSV file should be in the following format:

- Row 1: Column names for metadata fields.
- Row 2: Metadata values (latitude, longitude, water depth, data source, etc.).
- Row 3: Column headings for the timeseries data:
  `Year`, `Month`, `Day`, `Hour`, `Minute`, `Significant Wave Height`, `Energy Period`.
- Rows 4+: Hourly or sub-hourly data values:
  - `Significant Wave Height` in meters [m].
  - `Energy Period` in seconds [s].

## Configuration

The wave resource is declared in `plant_config.yaml` under the site resources:

```yaml
sites:
  site:
    resources:
      wave_resource:
        resource_model: WaveResource
        resource_parameters:
          resource_dir: resource_files/wave/
          resource_filename: wave_lat43.81_lon-124.82__2010.csv
          resource_year: 2010
```

The `resource_year` parameter is used to generate the hourly timestamp arrays (year, month, day, hour, minute) that are passed internally to the PySAM MhkWave model in timeseries mode.

The wave resource outputs are connected to the wave performance model via `resource_to_tech_connections` in `plant_config.yaml`:

```yaml
resource_to_tech_connections:
  - [site.wave_resource, wave, significant_wave_height]
  - [site.wave_resource, wave, energy_period]
```
