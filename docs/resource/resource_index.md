# Resource data


- [Wind Resource Data](wind_resource:models)
- [Solar Resource Data](solar_resource:models)
- [Tidal Resource Data](tidal_resource:models)


## Setting resource data for a technology

There are two ways to supply resource data to a technology:
1. Set resource for a technology data [using `set_val()`](#resource-data-specified-using-setval)
2. Create a [custom resource model](#custom-resource-models) for the technology



### Resource data specified using `set_val()`

Resource data for a technology can be set using the `set_val()` command. In the [Run of River Example](https://github.com/NatLabRockies/H2Integrate/tree/develop/examples/07_run_of_river_plant/), the technology named `river` needs a resource input called `discharge`. An example of this is shown below:

```python
import pandas as pd
from h2integrate.core.h2integrate_model import H2IntegrateModel
# Create an H2I model
h2i = H2IntegrateModel("07_run_of_river.yaml")

# Suppose we load the resource data from a csv file
resource_df = pd.read_csv("river_resource_data.csv")

# Setup the h2i model
h2i.setup()

# Set the resource data for the river
h2i.set_val("river.discharge", val=resource_df["discharge"].values, units="m**3/s")

# Run the model
h2i.run()
```


### Custom resource models
The benefit of using a custom resource model is that the resource data can be made to vary for different inputs, which can be beneficial if running a design sweep or optimization where the resource location (specified by a latitude and longitude) is a design variable.

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
        resource_model_location: river_resource/river_resource_model.py
        resource_parameters:
          filename: river_data.csv

resource_to_tech_connections:
  # connect the river resource to the run-of-river hydro technology
  - [site.river_resource, river, discharge]
```

The output `discharge` from the custom `river_resource` model is an input to the technology `river`. The custom resource model is a class named `CustomRiverResource` and the filepath for the `CustomRiverResource` is specified as the `resource_model_location`.
