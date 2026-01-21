(defining_sites_connect_resource)=
# Defining Sites and Connecting Resources

This guide covers how to define sites, resource models, amd connect resource data to technologies within H2Integrate, focusing on the `sites` configuration and the `resource_to_tech_connections` configuration defined in the plant configuration file.

## Defining Sites and Resources

The `sites` section of the plant configuration file defines the sites included in the analysis, their location parameters (latitude and longitude), and the resource models used for each site.
The yaml file is organized into sections for each site included in the analysis under the `sites` heading.
Here is an example of a site that is defining a wind resource model.

```yaml
sites:
    wind_site: #site name
        latitude: 34.22
        longitude: -102.75
        resources:
            wind_resource: #resource model name
                resource_model: "wind_toolkit_v2_api"
                resource_parameters:
                    resource_year: 2012
                    use_fixed_resource_location: True # this is the default
```

Further information on the available resource models can be found [here](https://h2integrate.readthedocs.io/en/latest/resource/resource_index.html)

## Resource to technology connections overview

The `resource_to_tech_connections` section in your plant configuration file defines how different technologies are connected to sites and the resource data for that site.
The H2I framework establishes the necessary OpenMDAO connections between your sites and technologies based on these specifications.

Resource to technology connections are defined as an array of 3-element arrays in your `plant_config.yaml`:

```yaml
resource_to_tech_connections: [
  [site_name.resource_name, tech_name, variable_name],
  ['wind_site.wind_resource','wind','wind_resource_data'],
]
```

- **site_name**: Name of the site for the resource model. Many examples with one site have a site name of 'site', but this name is defined by the user ('wind_site' is the site name in the above example).
- **resource_name**: Name of the resource model outputting the resource data. This can be any name defined by the user ('wind_resource' is the name of the resource model in the above example).
- **tech_name**: Name of the technology receiving the input resource data. This should be the name of a technology defined in the technology configuration file (the technology is named 'wind' in the above example).
- **variable_name**: The resource variable name to pass from the site to the technology, this entry is not user defined. The variable names for different resource and corresponding technology models are:
    - "wind_resource_data" for wind technology models and wind resource models
    - "solar_resource_data" for solar technology models and solar resource models
    - "discharge" for river resource models and water power technology models


The following sections will go over various examples and use-cases for defining sites and resource models.

### Single site without resource
If none of the technologies in the technology configuration require resource data, then `resource_to_tech_connections` is not included in the plant configuration file and `resources` are not defined for the site defined under `sites`.

An example `sites` configuration may look like:
```yaml
sites:
  site_A: #site name
    latitude: 32.34 #site latitude
    longitude: -98.27 #site longitude
```

Some examples that define a single site without resource data are:
- `examples/03_methanol/smr/plant_config_smr.yaml`
- `examples/11_hybrid_energy_plant/plant_config.yaml`

### Single site with a single resource
If a single technology (named `"wind"` in this example) requires resource data, then the `sites` configuration and `resource_to_tech_connections` may look like:
```yaml
sites:
    wind_site: #site name
        latitude: 34.22
        longitude: -102.75
        resources:
            wind_resource: #resource model name
                resource_model: "wind_toolkit_v2_api"
                resource_parameters:
                    resource_year: 2012
                    use_fixed_resource_location: True
resource_to_tech_connections: [
  # formatted as [site_name.resource_name, tech_name, variable_name],
  ['wind_site.wind_resource','wind','wind_resource_data'],
]
```

Some examples that define a single site with a single resource are:
- `examples/03_methanol/co2_hydrogenation_doc/plant_config_co2h.yaml`
- `examples/07_run_of_river_plant/plant_config.yaml`
- `examples/08_wind_electrolyzer/plant_config.yaml`
- `examples/10_electrolyzer_om/plant_config.yaml`
- `examples/14_wind_hydrogen_dispatch/inputs/plant_config.yaml`
- `examples/22_site_doe/plant_config.yaml`

### Single site with multiple resources
If multiple technologies (named `"wind"` and `"solar"` in this example) require resource data from the same location, then the `sites` configuration and `resource_to_tech_connections` may look like:
```yaml
sites:
    site_A: #site name
        latitude: 34.22
        longitude: -102.75
        resources:
            wind_resource: #resource model name for wind resource
                resource_model: "wind_toolkit_v2_api"
                resource_parameters:
                    resource_year: 2012
                    use_fixed_resource_location: True
            solar_resource: #resource model name for solar resource
                resource_model: "goes_aggregated_solar_v4_api"
                resource_parameters:
                    resource_year: 2012
                    use_fixed_resource_location: True
resource_to_tech_connections: [
  # formatted as [site_name.resource_name, tech_name, variable_name],
  ['site_A.wind_resource','wind','wind_resource_data'],
  ['site_A.solar_resource','solar','solar_resource_data'],
]
```

Some examples that define a single site with multiple resources are:
- `examples/01_onshore_steel_mn/plant_config.yaml`
- `examples/02_texas_ammonia/plant_config.yaml`
- `examples/03_methanol/co2_hydrogenation/plant_config_co2h.yaml`
- `examples/23_solar_wind_ng_demand/plant_config.yaml`

### Multiple sites with resources
If multiple technologies, named `"distributed_wind_plant"` and `"utility_wind_plant"` in this example (examples/26_floris), require resource data from different locations, then the `sites` configuration and `resource_to_tech_connections` may look like:
```yaml
sites:
  distributed_wind_site: #name of distributed site
    latitude: 44.04218
    longitude: -95.19757
    resources:
      wind_resource: #resource model name for distributed_wind_site
        resource_model: "openmeteo_wind_api"
        resource_parameters:
          resource_year: 2023
  utility_wind_site: # name of utility site
    latitude: 35.2018863
    longitude: -101.945027
    resources:
      wind_resource: #resource model name for utility_wind_site
        resource_model: "wind_toolkit_v2_api"
        resource_parameters:
          resource_year: 2012
resource_to_tech_connections: [
  # formatted as [site_name.resource_name, tech_name, variable_name],
  ['distributed_wind_site.wind_resource', 'distributed_wind_plant', 'wind_resource_data'],
  ['utility_wind_site.wind_resource', 'utility_wind_plant', 'wind_resource_data'],
]
```

Some examples that define multiple sites with resources are:
- `examples/15_wind_solar_electrolyzer/plant_config.yaml`
- `examples/26_floris/plant_config.yaml`
- `examples/27_site_doe_diff/plant_config.yaml`
