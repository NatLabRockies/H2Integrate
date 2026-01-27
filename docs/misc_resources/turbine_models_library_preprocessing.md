---
jupytext:
  text_representation:
    extension: .md
    format_name: myst
    format_version: 0.13
    jupytext_version: 1.18.1
kernelspec:
  display_name: h2integrate
  language: python
  name: python3
---

# Turbine Models Library Pre-Processing Tools

The [turbine-models package](https://github.com/NREL/turbine-models/tree/main) hosts wind turbine data for a variety of wind turbines and has tools that can streamline the process to run new turbines with the [PySAM Windpower model](https://nrel-pysam.readthedocs.io/en/main/modules/Windpower.html) or [FLORIS](https://github.com/NREL/floris/tree/main).

The full list of turbine models available in the turbine-models library can be found [here](https://github.com/NREL/turbine-models/blob/main/turbine_models/supported_turbines.py)

H2Integrate has preprocessing tools that leverage the functionality available in the turbine-models library. The function `export_turbine_to_pysam_format()` will save turbine model specifications formatted for the PySAM Windpower model. The PySAM Windpower model is wrapped in H2I and can be utilized with the "pysam_wind_plant_performance" model. Example usage of the `export_turbine_to_pysam_format()` function is demonstrated in the following section using Example 8.


## Turbine Model Pre-Processing with PySAM Windpower Model
Example 8 (`08_wind_electrolyzer`) currently uses an 8.3 MW turbine. In the following sections we will demonstrate how to:

1. Save turbine model specifications for the NREL 5 MW turbine in the PySAM Windpower format using `export_turbine_to_pysam_format()`
2. Load the turbine model specifications for the NREL 5 MW turbine and update performance parameters for the wind technology in the `tech_config` dictionary for the NREL 5 MW turbine.
3. Run H2I with the updated tech_config dictionary, showcasing two different methods to run H2I with the NREL 5 MW turbine:
   - initializing H2I with a dictionary input
   - saving the updated tech_config dictionary to a new file and initializing H2I by specifying the filepath to the top-level config file.


We'll start off by importing the required modules and packages:

```{code-cell} ipython3
import os
import numpy as np


from h2integrate import EXAMPLE_DIR
from h2integrate.core.utilities import load_yaml
from h2integrate.core.inputs.validation import load_tech_yaml
from h2integrate.preprocess.wind_turbine_file_tools import export_turbine_to_pysam_format
from h2integrate.core.h2integrate_model import H2IntegrateModel
```

Load the tech config file that we want to update the turbine model for:

```{code-cell} ipython3
# Load the tech config file
tech_config_path = EXAMPLE_DIR / "08_wind_electrolyzer" / "tech_config.yaml"
tech_config = load_tech_yaml(tech_config_path)
```

This example uses the "pysam_wind_plant_performance" performance model for the wind plant. Currently, the performance model is using an 8.3MW wind turbine with a rotor diameter of 196 meters and a hub-height of 130 meters. This information is defined in the `tech_config` file:

```{literalinclude} ../../examples/08_wind_electrolyzer/tech_config.yaml
:language: yaml
:lineno-start: 4
:linenos: true
:lines: 4-31
```

If we want to replace the 8.3 MW turbine with the NREL 5 MW turbine, we can do so using the `export_turbine_to_pysam_format()` function:

```{code-cell} ipython3
turbine_name = "NREL_5MW"

turbine_model_fpath = export_turbine_to_pysam_format(turbine_name)

print(turbine_model_fpath)
```

```{code-cell} ipython3
# Load the turbine model file formatted for the PySAM Windpower module
pysam_options = load_yaml(turbine_model_fpath)
pysam_options
```

```{code-cell} ipython3
# Create dictionary of updated inputs for the new turbine formatted for
# the "pysam_wind_plant_performance" model
updated_parameters = {
    "turbine_rating_kw": np.max(pysam_options["Turbine"].get("wind_turbine_powercurve_powerout")),
    "rotor_diameter": pysam_options["Turbine"].pop("wind_turbine_rotor_diameter"),
    "hub_height": pysam_options["Turbine"].pop("wind_turbine_hub_ht"),
    "pysam_options": pysam_options,
}

# Update wind performance parameters with model from PySAM
tech_config["technologies"]["wind"]["model_inputs"]["performance_parameters"].update(
    updated_parameters
)

# The technology input for the updated wind turbine model
tech_config["technologies"]["wind"]["model_inputs"]["performance_parameters"]
```

### Option 1: Run H2I with dictionary input

```{code-cell} ipython3
# Create the top-level config input dictionary for H2I
h2i_config = {
    # "name": "H2Integrate Config",
    # "system_summary": f"Updated hybrid plant using {turbine_name} turbine",
    "driver_config": EXAMPLE_DIR / "08_wind_electrolyzer" / "driver_config.yaml",
    "technology_config": tech_config,
    "plant_config": EXAMPLE_DIR / "08_wind_electrolyzer" / "plant_config.yaml",
}

# Create a H2Integrate model with the updated tech config
h2i = H2IntegrateModel(h2i_config)

# Run the model
h2i.run()

# Get LCOE of wind plant
wind_lcoe = h2i.model.get_val("finance_subgroup_electricity_profast.LCOE", units="USD/MW/h")
print(f"Wind LCOE is ${wind_lcoe[0]:.2f}/MWh")

# Get LCOH of wind/electrolyzer plant
lcoh = h2i.model.get_val("finance_subgroup_hydrogen.LCOH_produced_profast_model", units="USD/kg")
print(f"LCOH is ${lcoh[0]:.2f}/kg")
```

### Option 2: Save new tech_config to file and run H2I from file

```{code-cell} ipython3
from h2integrate.core.utilities import write_readable_yaml

# Define a new filepath for the updated tech config
tech_config_path_new = EXAMPLE_DIR / "08_wind_electrolyzer" / f"tech_config_{turbine_name}.yaml"

# Save the updated tech config to the new filepath
write_readable_yaml(tech_config, tech_config_path_new)

# Load in the top-level H2I config file
h2i_config_path = EXAMPLE_DIR / "08_wind_electrolyzer" / "wind_plant_electrolyzer.yaml"
h2i_config_dict = load_yaml(h2i_config_path)

# Define a new filepath for the updated top-level config
h2i_config_path_new = (
    EXAMPLE_DIR / "08_wind_electrolyzer" / f"wind_plant_electrolyzer_{turbine_name}.yaml"
)

# Update the technology config filepath in the top-level config with the updated
# tech config filename
h2i_config_dict["technology_config"] = tech_config_path_new.name

# Save the updated top-level H2I config to the new filepath
write_readable_yaml(h2i_config_dict, h2i_config_path_new)

# Change the CWD to the example folder since filepaths in h2i_config_dict are relative
# to the "08_wind_electrolyzer" folder
os.chdir(EXAMPLE_DIR / "08_wind_electrolyzer")

# Create a H2Integrate model with the updated tech config
h2i = H2IntegrateModel(h2i_config_path_new.name)

# Run the model
h2i.run()

# Get LCOE of wind plant
wind_lcoe = h2i.model.get_val("finance_subgroup_electricity_profast.LCOE", units="USD/MW/h")
print(f"Wind LCOE is ${wind_lcoe[0]:.2f}/MWh")

# Get LCOH of wind/electrolyzer plant
lcoh = h2i.model.get_val("finance_subgroup_hydrogen.LCOH_produced_profast_model", units="USD/kg")
print(f"LCOH is ${lcoh[0]:.2f}/kg")
```

## Turbine Model Pre-Processing with FLORIS

Example 26 (`26_floris`) currently uses an 660 kW turbine. This example uses the "floris_wind_plant_performance" performance model for the wind plant. Currently, the performance model is using an 660 kW wind turbine with a rotor diameter of 47.0 meters and a hub-height of 65 meters. In the following sections we will demonstrate how to:

1. Save turbine model specifications for the Vestas 1.65 MW turbine in the FLORIS format using `export_turbine_to_floris_format()`
2. Load the turbine model specifications for the Vestas 1.65 MW turbine and update performance parameters for the wind technology in the `tech_config` dictionary for the Vestas 1.65 MW turbine.
3. Run H2I with the updated tech_config dictionary for the Vestas 1.65 MW turbine


We'll start off with Step 1 and importing the function `export_turbine_to_floris_format()`, which will save turbine model specifications of the Vestas 1.65 MW turbine formatted for FLORIS.

```{code-cell} ipython3
from h2integrate.preprocess.wind_turbine_file_tools import export_turbine_to_floris_format

turbine_name = "Vestas_1.65MW"

turbine_model_fpath = export_turbine_to_floris_format(turbine_name)

print(turbine_model_fpath)
```

Step 2: Load the turbine model specifications for the Vestas 1.65 MW turbine and update performance parameters for the wind technology in the `tech_config` dictionary for the Vestas 1.65 MW turbine.

```{code-cell} ipython3
# Load the tech config file
tech_config_path = EXAMPLE_DIR / "26_floris" / "tech_config.yaml"
tech_config = load_tech_yaml(tech_config_path)

# Load the turbine model file formatted for FLORIS
floris_options = load_yaml(turbine_model_fpath)

# Create dictionary of updated inputs for the new turbine formatted for
# the "floris_wind_plant_performance" model
updated_parameters = {
    "hub_height": -1,  # -1 indicates to use the hub-height in the floris_turbine_config
    "floris_turbine_config": floris_options,
}

# Update distributed wind+ performance parameters in the tech config
tech_config["technologies"]["distributed_wind_plant"]["model_inputs"]["performance_parameters"].update(
    updated_parameters
)

# The technology input for the updated wind turbine model
tech_config["technologies"]["distributed_wind_plant"]["model_inputs"]["performance_parameters"]
```

Step 3: Run H2I with the updated tech_config dictionary for the Vestas 1.65 MW turbine

```{code-cell} ipython3
# Create the top-level config input dictionary for H2I
h2i_config = {
    "driver_config": EXAMPLE_DIR / "26_floris" / "driver_config.yaml",
    "technology_config": tech_config,
    "plant_config": EXAMPLE_DIR / "26_floris" / "plant_config.yaml",
}

# Create a H2Integrate model with the updated tech config
h2i = H2IntegrateModel(h2i_config)

# Run the model
h2i.run()

# Get LCOE of wind plant
wind_lcoe = h2i.model.get_val("finance_subgroup_distributed.LCOE", units="USD/MW/h")
print(f"Wind LCOE is ${wind_lcoe[0]:.2f}/MWh")
```
