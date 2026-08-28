"""Use built in H2I mapping tools to plot a 3-step iron mining, transport, and reduction process.

This example is focused not on the use of the main H2I model tools, but the post-processing mapping
functions. The H2I model has already been run over several locations, with the data saved and
tracked as a .csv in `./ex_28_out`. To run the model yourself, change the boolean `rerun_model` at
the top of the script to `True`.
Warning: this may take some time (up to a few minutes) depending on your PC's processing capability.

"""

from h2integrate import ROOT_DIR, EXAMPLE_DIR, H2IntegrateModel
from h2integrate.postprocess.mapping import (
    plot_geospatial_point_heat_map,
    plot_straight_line_shipping_routes,
)


# TODO: Pull ore/transport prices from separate runs, not static csvs

# Create H2Integrate model
# NOTE:
# If this example has already been run and the cases.csv or cases.sql file are saved in ./ex_28_out,
# you may leave rerun_model = False to save on run time.
# Otherwise, set rerun_model = True to produce the cases.csv / cases.sql results files
rerun_model = True
if rerun_model:
    model = H2IntegrateModel("iron_map.yaml")
    model.run()

    model.post_process(summarize_sql=True)

# Define filepaths
ex_dir = EXAMPLE_DIR / "21_iron_examples/iron_mapping"
ex_out_dir = EXAMPLE_DIR / "21_iron_examples/iron_mapping/ex_out"
save_plot_filepath = ex_out_dir / "example_iron_map.png"
save_plot_filepath.unlink(missing_ok=True)
case_results_filepath = ex_out_dir / "cases.csv"
ore_prices_filepath = ex_dir / "example_ore_prices.csv"
shipping_coords_filepath = ROOT_DIR / "converters/iron/martin_transport/shipping_coords.csv"
shipping_prices_filepath = ex_dir / "example_shipping_prices.csv"

# Add a layer for example ore cost prices from select mines
fig, ax, ore_cost_layer_gdf = plot_geospatial_point_heat_map(
    case_results_fpath=ore_prices_filepath,
    metric_to_plot="ore_cost_per_kg",
    map_preferences={
        "figsize": (5, 4),
        "colormap": "Greens",
        "marker": "o",
        "colorbar_bbox_to_anchor": (0.1, 0.97, 1, 1),
        "colorbar_label": "Levelized Cost of\nIron Ore Pellets\n[$/kg ore]",
        "colorbar_limits": (0.11, 0.14),
        "colorbar_width": "35%",
        "colorbar_num_ticks": 4,
        "horz_alignment": ["left", "center", "right"],
        "vert_alignment": ["bottom", "top", "bottom"],
        "label_offset_x": [3, 0, -3],
        "label_offset_y": [3, -6, 3],
    },
)

# Add a layer for example waterway shipping cost from select mines to select ports
fig, ax, shipping_cost_layer_gdf = plot_geospatial_point_heat_map(
    case_results_fpath=shipping_prices_filepath,
    metric_to_plot="shipping_cost_per_kg",
    map_preferences={
        "figsize": (5, 4),
        "colormap": "Greys",
        "marker": "d",
        "markersize": 80,
        "colorbar_bbox_to_anchor": (0.6, 0.85, 1, 1),
        "colorbar_label": "Waterway\nShipping Cost\n[$/kg ore]",
        "colorbar_limits": (0.026, 0.03),
        "colorbar_width": "35%",
        "colorbar_num_ticks": 3,
        "horz_alignment": ["right", "left"],
        "label_offset_x": [-3, 3],
    },
    fig=fig,
    ax=ax,
    base_layer_gdf=ore_cost_layer_gdf,
)

# Plot the LCOI results with geopandas and contextily
# NOTE: you can swap './ex_28_out/cases.sql' with './ex_28_out/cases.csv' to read results from csv
fig, ax, lcoi_layer_gdf = plot_geospatial_point_heat_map(
    case_results_fpath=case_results_filepath,
    metric_to_plot="finance_subgroup_sponge_iron.LCOS (USD/t)",
    metric_multiplier=1 / 1000,  # Convert from $/t to $/kg
    map_preferences={
        "figsize": (5, 4),
        "colorbar_label": "Levelized Cost of\nIron [$/kg]",
        "colorbar_limits": (0.3, 0.45),
        "colorbar_width": "35%",
        "colorbar_num_ticks": 4,
        "colorbar_bbox_to_anchor": (0.6, 0.27, 1.0, 1.0),
        "horz_alignment": ["right", "left", "left", "right", "left"],
        "vert_alignment": ["top"],
        "label_offset_x": [3, 3, 3, -3, 3],
        "label_offset_y": [-6, -3, -3, -3, -3],
    },
    save_sql_file_to_csv=True,
    fig=fig,
    ax=ax,
    base_layer_gdf=[ore_cost_layer_gdf, shipping_cost_layer_gdf],
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
    map_preferences={
        "figure_title": "Example H2 DRI Iron Costs",
        "figsize": (5, 4),
        "basemap_upperpad": 0.5,
        "basemap_lowerpad": 0.2,
        "basemap_leftpad": 0.05,
        "basemap_rightpad": 0.45,
        "basemap_zoom": 4,
    },
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
    save_plot_dpi=600,
)
