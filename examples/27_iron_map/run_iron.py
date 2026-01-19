"""Use built in H2I mapping tools to plot a 3-step iron mining, transport, and reduction process.

This example is focused not on the use of the main H2I model tools, but the post-processing mapping
functions. The H2I model has already been run over several locations, with the data saved and
tracked as a .csv in `./ex_27_out`. To run the model yourself, change the boolean `rerun_model` at
the top of the script to `True`.
Warning: this may take some time (up to a few minutes) depending on your PC's processing capability.

"""

from h2integrate import ROOT_DIR, EXAMPLE_DIR
from h2integrate.postprocess.mapping import (
    plot_geospatial_point_heat_map,
    plot_straight_line_shipping_routes,
)
from h2integrate.core.h2integrate_model import H2IntegrateModel


# Create H2Integrate model
# NOTE:
# If this example has already been run and the cases.csv and cases.sql file is saved in ./ex_27_out.
# You may comment out the following two lines to avoid long runtimes
rerun_model = False
if rerun_model:
    model = H2IntegrateModel("iron_map.yaml")
    model.run()

# Define filepaths
ex_27_dir = EXAMPLE_DIR / "27_iron_map"
ex_27_out_dir = EXAMPLE_DIR / "27_iron_map/ex_27_out"
save_plot_filepath = ex_27_out_dir / "example_27_iron_map.png"
save_plot_filepath.unlink(missing_ok=True)
case_results_filepath = ex_27_out_dir / "cases.csv"
ore_prices_filepath = ex_27_dir / "example_ore_prices.csv"
shipping_coords_filepath = ROOT_DIR / "converters/iron/martin_transport/shipping_coords.csv"
shipping_prices_filepath = ex_27_dir / "example_shipping_prices.csv"

# Plot the LCOI results with geopandas and contextily
# NOTE: you can swap './ex_27_out/cases.sql' with './ex_27_out/cases.csv' to read results from csv
fig, ax, lcoi_layer_gdf = plot_geospatial_point_heat_map(
    case_results_fpath=case_results_filepath,
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
    case_results_fpath=ore_prices_filepath,
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
    case_results_fpath=shipping_prices_filepath,
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
    shipping_coords_fpath=shipping_coords_filepath,
    shipping_route=cleveland_route,
    map_preferences={},
    fig=fig,
    ax=ax,
    base_layer_gdf=[lcoi_layer_gdf, ore_cost_layer_gdf, shipping_cost_layer_gdf],
)

# Add buffalo route as layer
fig, ax, transport_layer2_gdf = plot_straight_line_shipping_routes(
    shipping_coords_fpath=shipping_coords_filepath,
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
    shipping_coords_fpath=shipping_coords_filepath,
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
    save_plot_fpath=save_plot_filepath,
)
