# Resource data


- [Wind Resource Data](wind_resource:models)
- [Solar Resource Data](solar_resource:models)
- [Tidal Resource Data](tidal_resource:models)



## Custom resource models

A general resource model can be defined similarly to a custom technology model. A custom resource model should be defined in the plant configuration file within a site section under `sites`.

```{note}
Note that all custom resource models must have inputs of `latitude` and `longitude`. The outputs of your custom resource model should match the expected input to whatever model its connected to.
```

Below shows an example, similar to the [Run of River Example](https://github.com/NatLabRockies/H2Integrate/tree/develop/examples/07_run_of_river_plant/) of how to define a custom resource model within the `plant_config.yaml` file:

```yaml
sites:
  site:
    latitude: 32.34
    longitude: -98.27
    resources:
      river_resource:
        resource_model: CustomRiverResource
        resource_model_class_name: CustomRiverResource
        resource_model_location: river_resource/river_resource_model.py
        resource_parameters:
          filename: river_data.csv

resource_to_tech_connections:
  # connect the river resource to the run-of-river hydro technology
  - [site.river_resource, river, discharge]
```

The output `discharge` from the custom `river_resource` model is an input to the technology `river`. The custom resource model is a class named `CustomRiverResource` and the filepath for the `CustomRiverResource` is specified as the `resource_model_location`.
