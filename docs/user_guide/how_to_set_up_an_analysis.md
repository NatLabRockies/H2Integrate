---
jupytext:
  text_representation:
    extension: .md
    format_name: myst
    format_version: 0.13
    jupytext_version: 1.18.1
kernelspec:
  display_name: Python 3.11.13 ('h2i_env')
  language: python
  name: python3
---

# How to set up an analysis

H2Integrate is designed so that you can run a basic analysis or design problem without extensive Python experience.
The key inputs for the analysis are the configuration files, which are in YAML format.
This doc page will walk you through the steps to set up a basic analysis, focusing on the different types of configuration files and how use them.

## Top-level config file

The top-level config file is the main entry point for H2Integrate.
Its main purpose is to define the analysis type and the configuration files for the different components of the analysis.
Here is an example of a top-level config file:

```{literalinclude} ../../examples/08_wind_electrolyzer/wind_plant_electrolyzer.yaml
:language: yaml
:linenos: true
```

The top-level config file contains the following keys:
- `name`: (optional) A name for the analysis. This is used to identify the analysis in the output files.
- `system_summary`: (optional) A summary of the analysis. This helpful for quickly describing the analysis for documentation purposes.

- `driver_config`: The path to the driver config file. This file defines the analysis type and the optimization settings.
- `technology_config`: The path to the technology config file. This file defines the technologies included in the analysis, their modeling parameters, and the performance, cost, and financial models used for each technology.
- `plant_config`: The path to the plant config file. This file defines the system configuration and how the technologies are connected together.

The goal of the organization of the top-level config file is that it is easy to swap out different configurations for the analysis without having to change the code.
For example, if you had different optimization problems, you could have different driver config files for each optimization problem and just change the `driver_config` key in the top-level config file to point to the new file.
This allows you to quickly test different configurations and see how they affect the results.

```{note}
The filepaths for the `plant_config`, `tech_config`, and `driver_config` files specified in the top-level config file can be specified as either:
1. Filepaths relative to the top-level config file; this is done in most examples
2. Filepaths relative to the current working directory; this is also done in most examples, which are intended to be run from the folder they're in.
3. Filepaths relative to the H2Integrate root directory; this works best for unique filenames.
4. Absolute filepaths.

More information about file handling in H2I can be found [here](https://h2integrate.readthedocs.io/en/latest/misc_resources/defining_filepaths.html)
```

## Driver config file

The driver config file defines the analysis type and the optimization settings.
If you are running a basic analysis and not an optimization, the driver config file is quite straightforward and might look like this:

```{literalinclude} ../../examples/08_wind_electrolyzer/driver_config.yaml
:language: yaml
:linenos: true
```

If you are running an optimization, the driver config file will contain additional keys to define the optimization settings, including design variables, constraints, and objective functions.
Further details of more complex instances of the driver config file can be found in more advanced examples as they are developed.

## Technology config file

The technology config file defines the technologies included in the analysis, their modeling parameters, and the performance, cost, and financial models used for each technology.
The yaml file is organized into sections for each technology included in the analysis under the `technologies` heading.
Here is an example of a technology config that is defining an energy system with wind and electrolyzer technologies:

```{literalinclude} ../../examples/08_wind_electrolyzer/tech_config.yaml
:language: yaml
:linenos: true
```

Here, we have defined a wind plant using the `pysam_wind_plant_performance` and `atb_wind_cost` models, and an electrolyzer using the `eco_pem_electrolyzer_performance` and `singlitico_electrolyzer_cost` models.
The `performance_model` and `cost_model` keys define the models used for the performance and cost calculations, respectively.
The `model_inputs` key contains the inputs for the models, which are organized into sections for shared parameters, performance parameters, cost parameters, and financial parameters.

The `shared_parameters` section contains parameters that are common to all models, such as the rating and location of the technology.
These values are defined once in the `shared_parameters` section and are used by all models that reference them.
The `performance_parameters` section contains parameters that are specific to the performance model, such as the sizing and efficiency of the technology.
The `cost_parameters` section contains parameters that are specific to the cost model, such as the capital costs and replacement costs.
The `financial_parameters` section contains parameters that are specific to the financial model, such as the replacement costs and financing terms.

```{note}
There are no default values for the parameters in the technology config file.
You must define all the parameters for the models you are using in the analysis.
```

Based on which models you choose to use, the inputs will vary.
Each model has its own set of inputs, which are defined in the source code for the model.
Because there are no default values for the parameters, we suggest you look at an existing example that uses the model you are interested in to see what inputs are required or look at the source code for the model.
The different models are defined in the `supported_models.py` file in the `h2integrate` package.

## Plant config file

The plant config file defines the system configuration, any parameters that might be shared across technologies, and how the technologies are connected together.

Here is an example plant config file:

```{literalinclude} ../../examples/08_wind_electrolyzer/plant_config.yaml
:language: yaml
:linenos: true
```

The `sites` section contains the site parameters, such as the latitude and longitude, and defines the resources available at each site (e.g., wind or solar resource data).
The `plant` section contains the plant parameters, such as the plant life.
The `finance_parameters` section contains the financial parameters used across the plant, such as the inflation rates, financing terms, and other financial parameters.

The `technology_interconnections` section contains the interconnections between the technologies in the system.
The interconnections are defined as a list of lists, where each sub-list defines a connection between two technologies.
The first entry in the list is the technology that is providing the input to the next technology in the list.
If the list is length 4, then the third entry in the list is what's being passed via a transporter of the type defined in the fourth entry.
If the list is length 3, then the third entry in the list is what is connected directly between the technologies.

The `resource_to_tech_connections` section defines how resources (like wind or solar data) are connected to the technologies that use them.

```{note}
For more information on how to define and interpret technology interconnections, see the {ref}`connecting_technologies` page.
```

## Visualizing the model structure
There are two basic methods for visualizing the model structure of your H2Integrate system model.
You can generate a simplified [XDSM diagram](https://openmdao.github.io/PracticalMDO/Notebooks/ModelConstruction/understanding_xdsm_diagrams.html) showing the technologies and connections specified in your config file, or you can generate an interactive [N2 diagram](https://openmdao.org/newdocs/versions/latest/features/model_visualization/n2_details/n2_details.html) of the full OpenMDAO model.
The XDSM diagram is primarily useful for publications and presentations.
The N2 diagram is primarily useful for debugging. Details for generating XDSM and N2 diagrams of your H2Integrate model are given below.

### XDSM diagram (static and simplified)

Use the built-in `create_xdsm()` method to generate a static system diagram from the
`technology_interconnections` section of your plant config.

```python
from h2integrate.core.h2integrate_model import H2IntegrateModel
import os


# Change to an example directory
os.chdir("../../examples/08_wind_electrolyzer/")

# Build the model from the top-level config file
h2i_model = H2IntegrateModel("wind_plant_electrolyzer.yaml")

# Write XDSM output to connections_xdsm.pdf
h2i_model.create_xdsm(outfile="connections_xdsm")
```

This creates a PDF named `connections_xdsm.pdf` in your current working directory.

```{figure} figures/example_08_xdsm.png
:width: 70%
:align: center
```
*Figure: XDSM diagram generated from the technology interconnections.*

### N2 diagram (interactive and complete)

Use OpenMDAO's `n2` utility to generate an interactive HTML diagram of the full model.

```{code-cell} ipython3
from h2integrate.core.h2integrate_model import H2IntegrateModel
import openmdao.api as om
import os


# Change to an example directory
os.chdir("../../examples/08_wind_electrolyzer/")

# Build and set up the model
h2i_model = H2IntegrateModel("wind_plant_electrolyzer.yaml")
h2i_model.setup()

# Write interactive N2 HTML diagram
om.n2(
    h2i_model.prob,
    outfile="h2i_n2.html",
    display_in_notebook=False, # set to True to display in-line in a notebook
    show_browser=False, # set to True to open in a browser at run time
)
```

Open `h2i_n2.html` in a browser to explore model groups, components, and variable connections.

```{code-cell} ipython3
:tags: [remove-input]
import html
from pathlib import Path
from IPython.display import HTML, display

n2_html = "h2i_n2.html"
n2_srcdoc = html.escape(Path(n2_html).read_text(encoding="utf-8"))
display(
    HTML(
        f'<div style="width:100%; height:600px; overflow:auto; margin:0; padding:0; border:0;">'
        f'<iframe srcdoc="{n2_srcdoc}" '
        'style="display:block; width:200%; height:600px; border:0; margin:0; padding:0; background:transparent;" '
        'loading="lazy"></iframe>'
        '</div>'
    )
)
```
*Figure: Interactive OpenMDAO N2 diagram showing the full model structure and variable connections.*



## Running the analysis

Once you have the config files defined, you can run the analysis using a simple Python script that inputs the top-level config yaml.
Here, we will show a script that runs one of the example analyses included in the H2Integrate package.

```{code-cell} ipython3
from h2integrate.core.h2integrate_model import H2IntegrateModel
import os


# Change the current working directory
os.chdir("../../examples/08_wind_electrolyzer/")

# Create a H2Integrate model
h2i_model = H2IntegrateModel("wind_plant_electrolyzer.yaml")

# Run the model
h2i_model.run()

# h2i_model.post_process()

# Print the average annual hydrogen produced by the electrolyzer in kg/year
annual_hydrogen = h2i_model.model.get_val("electrolyzer.annual_hydrogen_produced", units="kg/year").mean()
print(f"Total hydrogen produced by the electrolyzer: {annual_hydrogen:.2f} kg/year")
```

This will run the analysis defined in the config files and generate the output files in the through the `post_process` method.

## Modifying and rerunning the analysis

Once the configs are loaded into H2I and the model is instantiated, you can directly modify the underlying OpenMDAO variables within H2I.
This is an advanced approach that isn't necessarily recommended for basic users, but showcases the level of flexibility possible with H2I.

```{note}
The same behavior shown here with a manual for-loop can be achieved by using the [design of experiments capability](design_of_experiments_in_h2i.md).
```

```{code-cell} ipython3
# Access the configuration dictionaries
tech_config = h2i_model.technology_config

# Modify a parameter in the technology config
tech_config["technologies"]["electrolyzer"]["model_inputs"]["performance_parameters"][
    "n_clusters"
] = 15

# Rerun the model with the updated configurations
h2i_model.run()

# Post-process the results
# h2i_model.post_process()

# Print the average annual hydrogen produced by the electrolyzer in kg/year
annual_hydrogen = h2i_model.model.get_val("electrolyzer.annual_hydrogen_produced", units="kg/year").mean()
print(f"Total hydrogen produced by the electrolyzer: {annual_hydrogen:.2f} kg/year")
```

This is especially useful when you want to run an H2I model as a script and modify parameters dynamically without changing the original YAML configuration file.
If you want to do a simple parameter sweep, you can wrap this in a loop and modify the parameters as needed.

In the example below, we modify the electrolyzer `n_clusters` and plot the impact on the LCOH.

```{code-cell} ipython3
import numpy as np
import matplotlib.pyplot as plt

# Get the electrolyzer cluster rated capacity
cluster_size_mw = int(
    tech_config["technologies"]["electrolyzer"]["model_inputs"]["performance_parameters"][
        "cluster_rating_MW"
    ]
)

# Define the range for electrolyzer rating
ratings = np.arange(320, 840, cluster_size_mw)

# Initialize arrays to store results
lcoh_results = []

for rating in ratings:
    # Calculate the number of clusters from the rating
    n_clusters = int(rating / cluster_size_mw)

    # Set the n_clusters value directly
    h2i_model.model.set_val("electrolyzer.n_clusters", n_clusters)

    # Rerun the model with the updated configurations
    h2i_model.run()

    # Get the LCOH value
    lcoh = h2i_model.model.get_val("finance_subgroup_hydrogen.LCOH_produced_custom_model", units="USD/kg")[0]

    # Store the results
    lcoh_results.append(lcoh)

# Create a scatter plot
plt.scatter(ratings, lcoh_results)
plt.xlabel("Electrolyzer Rating (kW)")
plt.ylabel("LCOH ($/kg)")
plt.title("LCOH vs Electrolyzer Rating")
plt.grid(True)
plt.show()
```
