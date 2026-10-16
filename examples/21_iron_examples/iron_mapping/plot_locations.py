from pathlib import Path

from h2integrate.postprocess.mapping import plot_geospatial_point_heat_map


# Define directories
ROOT_DIR = Path(__file__).resolve().parent

files = [
    "mine_sites.csv",
    "dock_sites_labeled.csv",
    "iron_plant_sites_labeled.csv",
]

metrics = [
    "iron_mine.mine",
    "site.name",
    "site.name",
]

markers = [
    "o",
    "d",
    "s",
]

colors = [
    "g",
    "k",
    "y",
]

legend_labels = [
    "Mine",
    "Ore Dock",
    "Iron Plant",
]

horzontal_alignments = [
    [
        "left",
        "center",
        "right",
    ],
    ["right", "left"],
    ["center", "left", "left", "right", "left"],
]

vertical_alignments = [
    [
        "bottom",
        "top",
        "bottom",
    ],
    ["bottom", "bottom"],
    ["top", "top", "top", "top", "top"],
]

x_offset = [
    [
        3,
        0,
        -3,
    ],
    [-3, -6],
    [-9, 3, 3, -6, 6],
]

y_offset = [
    [
        3,
        -3,
        3,
    ],
    [3, 6],
    [-6, -3, -3, -3, -3],
]

fig = None
ax = None
leg_texts = []
gdf_layers = []

for idx, file in enumerate(files):
    fig, ax, leg_texts, gdf_layer = plot_geospatial_point_heat_map(
        case_results_fpath=ROOT_DIR / file,
        metric_to_plot=metrics[idx],
        map_preferences={
            "figsize": (5, 4),
            "colorbar_label": "Plant Type",
            "colorbar_limits": (0, 1),
            "basemap_leftpad": 0.16,
            "basemap_rightpad": 0.33,
            "basemap_upperpad": 0.15,
            "basemap_lowerpad": 0.15,
            "basemap_zoom": 4,
            "marker": markers[idx],
            "markerfacecolor": colors[idx],
            "label_format_string": "s",
            "legend_label": legend_labels[idx],
            "colorbar_bbox_to_anchor": (0.58, 0.25, 0.3, 0.1),
            "figure_title": "Selected Iron Locations",
            "horz_alignment": horzontal_alignments[idx],
            "vert_alignment": vertical_alignments[idx],
            "label_offset_x": x_offset[idx],
            "label_offset_y": y_offset[idx],
        },
        save_sql_file_to_csv=True,
        latitude_var_name="iron_transport.destination_latitude",
        longitude_var_name="iron_transport.destination_longitude",
        show_plot=False if idx < len(files) - 1 else True,
        fig=fig,
        ax=ax,
        leg_texts=leg_texts,
        base_layer_gdf=None if idx == 0 else gdf_layers,
    )
    gdf_layers.append(gdf_layer)
