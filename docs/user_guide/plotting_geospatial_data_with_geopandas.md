# Plotting geospatial data with GeoPandas and Contextily

When running H2Integrate simulations across a range of site locations, GeoPandas can be leveraged to plot results and create maps with multiple layers. Contextily is leveraged to add visually pleasing open source basemaps.

Currently all GIS and GeoPandas mapping functionality lives in `/H2Integrate/h2integrate/postprocess/mapping.py`

Note: to leverage this functionality users must install H2Integrate with the `gis` or `examples` modifier. ie: `pip install ".[examples]"` or `pip install ".[develop,gis]"`.

## Create a multi-layer geospatial point heat map with simple straight line transport routes

An example use case, mirroring the simulation and workflow in /examples/28_iron_map/run_iron.py, we can use GeoPandas and Contextily to create a multi-layer point heat map which displays the level costs of iron ore pellets from select mines, simplified waterway shipping routes and associated costs to transport the iron ore pellets, and the final levelized cost of iron production via Hydrogen DRI across a range of site locations.

In this example the configuration .yaml files are set such that a design of experiments is run across multiple site locations (latitude,longitude) read in from the "ned_reduced_sitelist.csv" which contains precomputed levelized cost of electricity (LCOE) and levelized cost of hydrogen (LCOH) at each location. This information is then used to calculate the levelized cost of iron production via hydrogen DRI at these locations. Upon running the model, results are saved to a "cases.sql" file.

```python
from h2integrate.postprocess.mapping import (
    plot_geospatial_point_heat_map,
    plot_straight_line_shipping_routes,
)
from h2integrate.core.h2integrate_model import H2IntegrateModel

model = H2IntegrateModel("iron_map.yaml")
model.run()
```

Here is an example of how we can then uses the results in cases.sql to plot a multi-layer point heat map and straight line shipping routes in one figure.

```python
# Plot the LCOI results with geopandas and contextily
# NOTE: you can swap './ex_28_out/cases.sql' with './ex_28_out/cases.csv' to read results from csv
fig, ax, lcoi_layer_gdf = plot_geospatial_point_heat_map(
    case_results_fpath="./ex_28_out/cases.sql",
    metric_to_plot="iron.LCOI (USD/kg)",
    map_preferences={
        "figsize": (10, 8),
        "colorbar_label": "Levelized Cost of\nIron [$/kg]",
        "colorbar_limits": (0.6, 1.0),
    },
    save_sql_file_to_csv=True,
)

# Add a layer for example ore cost prices from select mines
fig, ax, ore_cost_layer_gdf = plot_geospatial_point_heat_map(
    case_results_fpath="./example_ore_prices.csv",
    metric_to_plot="ore_cost_per_kg",
    map_preferences={
        "colormap": "Greens",
        "marker": "o",
        "colorbar_bbox_to_anchor": (0.025, 0.97, 1, 1),
        "colorbar_label": "Levelized Cost of\nIron Ore Pellets\n[$/kg ore]",
        "colorbar_limits": (0.11, 0.14),
    },
    fig=fig,
    ax=ax,
    base_layer_gdf=lcoi_layer_gdf,
)

# Add a layer for example waterway shipping cost from select mines to select ports
fig, ax, shipping_cost_layer_gdf = plot_geospatial_point_heat_map(
    case_results_fpath="./example_shipping_prices.csv",
    metric_to_plot="shipping_cost_per_kg",
    map_preferences={
        "colormap": "Greys",
        "marker": "d",
        "markersize": 80,
        "colorbar_bbox_to_anchor": (0.4, 0.97, 1, 1),
        "colorbar_label": "Waterway Shipping Cost\n[$/kg ore]",
        "colorbar_limits": (0.11, 0.14),
    },
    fig=fig,
    ax=ax,
    base_layer_gdf=[lcoi_layer_gdf, ore_cost_layer_gdf],
)

# Define example water way shipping routes for plotting straight line transport
cleveland_route = [
    "Duluth",
    "Keweenaw",
    "Sault St Marie",
    "De Tour",
    "Lake Huron",
    "Port Huron",
    "Erie",
    "Cleveland",
]

buffalo_route = [
    "Duluth",
    "Keweenaw",
    "Sault St Marie",
    "De Tour",
    "Lake Huron",
    "Port Huron",
    "Erie",
    "Cleveland",
    "Buffalo",
]

chicago_route = [
    "Duluth",
    "Keweenaw",
    "Sault St Marie",
    "De Tour",
    "Mackinaw",
    "Manistique",
    "Chicago",
]

# Add cleveland route as layer
fig, ax, transport_layer1_gdf = plot_straight_line_shipping_routes(
    shipping_coords_fpath="./example_shipping_coords.csv",
    shipping_route=cleveland_route,
    map_preferences={},
    fig=fig,
    ax=ax,
    base_layer_gdf=[lcoi_layer_gdf, ore_cost_layer_gdf, shipping_cost_layer_gdf],
)

# Add buffalo route as layer
fig, ax, transport_layer2_gdf = plot_straight_line_shipping_routes(
    shipping_coords_fpath="./example_shipping_coords.csv",
    shipping_route=buffalo_route,
    map_preferences={},
    fig=fig,
    ax=ax,
    base_layer_gdf=[
        lcoi_layer_gdf,
        ore_cost_layer_gdf,
        shipping_cost_layer_gdf,
        transport_layer1_gdf,
    ],
)

# Add chicago route as layer
fig, ax, transport_layer3_gdf = plot_straight_line_shipping_routes(
    shipping_coords_fpath="./example_shipping_coords.csv",
    shipping_route=chicago_route,
    map_preferences={"figure_title": "Example H2 DRI Iron Costs"},
    fig=fig,
    ax=ax,
    base_layer_gdf=[
        lcoi_layer_gdf,
        ore_cost_layer_gdf,
        shipping_cost_layer_gdf,
        transport_layer1_gdf,
        transport_layer2_gdf,
    ],
    show_plot=True,
    save_plot_fpath="./ex_28_out/example_28_iron_map.png",
)
```

After running the above code, a display window will show the image and the image will be saved to the specified `save_plot_fpath`.

![example_28_iron_map.png](./figures/example_28_iron_map.png)
