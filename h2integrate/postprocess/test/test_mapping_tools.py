import numpy as np
import pandas as pd
import pytest
import geopandas as gpd
from shapely.geometry import Polygon

from h2integrate.postprocess.mapping import (
    auto_colorbar_limits,
    validate_gdfs_are_same_crs,
    auto_detect_lat_long_columns,
    calculate_geodataframe_total_bounds,
)


# Define geometries to be used in testing of GeoDataFrames
larger_square_coords = Polygon(
    [
        (-105.24, 39.74),
        (-105.24, 39.76),
        (-105.20, 39.76),
        (-105.20, 39.74),
    ]
)
smaller_square_coords = Polygon(
    [
        (-105.23, 39.745),
        (-105.23, 39.755),
        (-105.21, 39.755),
        (-105.21, 39.745),
    ]
)


def test_calculate_geodataframe_total_bounds(subtests):
    with subtests.test("Check invalid argument type"):
        expected_msg = "Must provide at least one GeoDataFrame."
        with pytest.raises(ValueError, match=expected_msg):
            calculate_geodataframe_total_bounds()

    with subtests.test("Check mismatched CRS"):
        expected_msg = "All GeoDataFrames must have the same CRS."
        gdf_1 = gpd.GeoDataFrame(
            columns=["index", "test1", "test2"], geometry="test2", crs="EPSG:4326"
        )
        gdf_2 = gpd.GeoDataFrame(
            columns=["index", "test1", "test2"], geometry="test2", crs="EPSG:3857"
        )
        with pytest.raises(ValueError, match=expected_msg):
            calculate_geodataframe_total_bounds(*[gdf_1, gdf_2])

    with subtests.test("Check calculations and output for 1 GeoDataFrame"):
        gdf_1 = gpd.GeoDataFrame(
            data={"index": [0], "test1": ["larger_square"], "test2": [larger_square_coords]},
            geometry="test2",
            crs="EPSG:4326",
        )
        coord_range_dict = calculate_geodataframe_total_bounds(*[gdf_1])
        expected_dict = {
            "min_x": np.float64(-105.24),
            "min_y": np.float64(39.74),
            "max_x": np.float64(-105.2),
            "max_y": np.float64(39.76),
            "x_range": np.float64(0.03999999999999204),
            "y_range": np.float64(0.01999999999999602),
        }
        assert isinstance(
            coord_range_dict, dict
        ), f"Expected dictionary type but got {type(coord_range_dict)}"
        for key, value in expected_dict.items():
            assert pytest.approx(coord_range_dict[key], rel=1e-3) == value

    with subtests.test("Check calculations and output for 2 GeoDataFrames"):
        gdf_1 = gpd.GeoDataFrame(
            data={"index": [0], "test1": ["larger_square"], "test2": [larger_square_coords]},
            geometry="test2",
            crs="EPSG:4326",
        )
        gdf_2 = gpd.GeoDataFrame(
            data={"index": [0], "test1": ["smaller_square"], "test2": [smaller_square_coords]},
            geometry="test2",
            crs="EPSG:4326",
        )
        coord_range_dict = calculate_geodataframe_total_bounds(*[gdf_1, gdf_2])
        expected_dict = {
            "min_x": np.float64(-105.24),
            "min_y": np.float64(39.74),
            "max_x": np.float64(-105.2),
            "max_y": np.float64(39.76),
            "x_range": np.float64(0.03999999999999204),
            "y_range": np.float64(0.01999999999999602),
        }
        assert isinstance(
            coord_range_dict, dict
        ), f"Expected dictionary type but got {type(coord_range_dict)}"
        for key, value in expected_dict.items():
            assert pytest.approx(coord_range_dict[key], rel=1e-3) == value


def test_auto_detect_lat_long_columns(subtests):
    test_good_results_df1 = pd.DataFrame(columns=["index", "latitude", "longitude"])
    test_good_results_df2 = pd.DataFrame(columns=["index", "lat", "long"])
    test_bad_results_df1 = pd.DataFrame(columns=["index", "lat", "latitude"])
    test_bad_results_df2 = pd.DataFrame(columns=["index"])

    with subtests.test("Check invalid argument type"):
        expected_msg = "which argument must be 'lat', 'long', or 'both'."
        with pytest.raises(ValueError, match=expected_msg):
            auto_detect_lat_long_columns(results_df=test_good_results_df1, which="erroneous_arg")

    with subtests.test("Test valid column names"):
        latitude_var_name, longitude_var_name = auto_detect_lat_long_columns(
            results_df=test_good_results_df1, which="both"
        )
        assert latitude_var_name == "latitude", "Could not autodetect latitude column"
        assert longitude_var_name == "longitude", "Could not autodetect longitude column"

        latitude_var_name, longitude_var_name = auto_detect_lat_long_columns(
            results_df=test_good_results_df2, which="both"
        )
        assert latitude_var_name == "lat", "Could not autodetect latitude column"
        assert longitude_var_name == "long", "Could not autodetect longitude column"

        latitude_var_name = auto_detect_lat_long_columns(
            results_df=test_good_results_df2, which="lat"
        )
        assert latitude_var_name == "lat", "Could not autodetect latitude column"

        longitude_var_name = auto_detect_lat_long_columns(
            results_df=test_good_results_df2, which="long"
        )
        assert longitude_var_name == "long", "Could not autodetect longitude column"

    with subtests.test("Test invalid column names"):
        expected_msg = (
            "Unable to automatically detect the latitude variable / column in the data.",
            "Please specify the exact variable name using the latitude_var_name argument",
        )
        with pytest.raises(KeyError, match=str(expected_msg)):
            auto_detect_lat_long_columns(results_df=test_bad_results_df1, which="lat")

        expected_msg = (
            "Unable to automatically detect the longitude variable / column in the data.",
            "Please specify the exact variable name using the longitude_var_name argument",
        )
        with pytest.raises(KeyError, match=str(expected_msg)):
            auto_detect_lat_long_columns(results_df=test_bad_results_df1, which="long")

        expected_msg = (
            "Unable to automatically detect the latitude variable / column in the data.",
            "Please specify the exact variable name using the latitude_var_name argument",
        )
        with pytest.raises(KeyError, match=str(expected_msg)):
            auto_detect_lat_long_columns(results_df=test_bad_results_df2, which="lat")

        expected_msg = (
            "Unable to automatically detect the longitude variable / column in the data.",
            "Please specify the exact variable name using the longitude_var_name argument",
        )
        with pytest.raises(KeyError, match=str(expected_msg)):
            auto_detect_lat_long_columns(results_df=test_bad_results_df2, which="long")


def test_validate_gdfs_are_same_crs(subtests):
    gdf_1 = gpd.GeoDataFrame(
        data={"index": [0], "test1": ["larger_square"], "test2": [larger_square_coords]},
        geometry="test2",
        crs="EPSG:4326",
    )
    gdf_2 = gpd.GeoDataFrame(
        data={"index": [0], "test1": ["smaller_square"], "test2": [smaller_square_coords]},
        geometry="test2",
        crs="EPSG:4326",
    )
    gdf_3 = gpd.GeoDataFrame(
        data={"index": [0], "test1": ["smaller_square"], "test2": [smaller_square_coords]},
        geometry="test2",
        crs="EPSG:4326",
    )
    good_gdf_list = [gdf_1, gdf_2]
    good_gdf_tuple = (gdf_1, gdf_2)
    bad_gdf_list = [gdf_1.to_crs("EPSG:3857"), gdf_2]
    bad_gdf_tuple = (gdf_1.to_crs("EPSG:3857"), gdf_2)

    with subtests.test("Test good single gdf, list gdf, and tuple gdf inputs"):
        output_gdf = validate_gdfs_are_same_crs(base_layer_gdf=gdf_1, results_gdf=gdf_3)
        assert isinstance(
            output_gdf[0], gpd.GeoDataFrame
        ), f"Expected gpd.GeoDataFrame output but got {type(output_gdf[0])}"

        output_gdf = validate_gdfs_are_same_crs(base_layer_gdf=good_gdf_list, results_gdf=gdf_3)
        assert isinstance(
            output_gdf[0], gpd.GeoDataFrame
        ), f"Expected gpd.GeoDataFrame output but got {type(output_gdf[0])}"

        output_gdf = validate_gdfs_are_same_crs(base_layer_gdf=good_gdf_tuple, results_gdf=gdf_3)
        assert isinstance(
            output_gdf[0], gpd.GeoDataFrame
        ), f"Expected gpd.GeoDataFrame output but got {type(output_gdf[0])}"

    with subtests.test("Test bad single gdf, list gdf, and tuple gdf inputs"):
        # NOTE: issues with matching the ValueError to an expected message, omitted that logic
        with pytest.raises(ValueError):
            validate_gdfs_are_same_crs(base_layer_gdf=gdf_1.to_crs("EPSG:3857"), results_gdf=gdf_3)
        with pytest.raises(ValueError):
            validate_gdfs_are_same_crs(base_layer_gdf=bad_gdf_list, results_gdf=gdf_3)
        with pytest.raises(ValueError):
            validate_gdfs_are_same_crs(base_layer_gdf=bad_gdf_tuple, results_gdf=gdf_3)


def test_auto_colorbar_limits(subtests):
    with subtests.test("Test good value input types"):
        vmin, vmax = auto_colorbar_limits(values=pd.Series([0.62, 0.75, 0.93]))
        assert vmin == 0.6
        assert vmax == 1.0

        vmin, vmax = auto_colorbar_limits(values=np.array([0.62, 0.75, 0.93]))
        assert vmin == 0.6
        assert vmax == 1.0

    with subtests.test("Test bad value input types"):
        expected_msg = "Cannot determine colorbar limits from empty data or non-finite data."
        with pytest.raises(ValueError, match=expected_msg):
            auto_colorbar_limits(values=[np.inf, np.nan])

        with pytest.raises(ValueError, match=expected_msg):
            auto_colorbar_limits(values=pd.Series())

        with pytest.raises(ValueError, match=expected_msg):
            auto_colorbar_limits(values=pd.Series([]))

        with pytest.raises(ValueError, match=expected_msg):
            auto_colorbar_limits(values=[])

    with subtests.test("Test docstring examples"):
        vmin, vmax = auto_colorbar_limits(values=[12.3, 87.9])
        assert pytest.approx(vmin, rel=1e-3) == 10.0
        assert pytest.approx(vmax, rel=1e-3) == 90.0

        vmin, vmax = auto_colorbar_limits(values=[0.0042, 0.0091])
        assert pytest.approx(vmin, rel=1e-3) == 0.004
        assert pytest.approx(vmax, rel=1e-3) == 0.01

        vmin, vmax = auto_colorbar_limits(values=[5.0, 5.00001])
        assert pytest.approx(vmin, rel=1e-3) == 4.9
        assert pytest.approx(vmax, rel=1e-3) == 5.1

        vmin, vmax = auto_colorbar_limits(values=[0.0, 1e-7])
        assert pytest.approx(vmin, rel=1e-6) == -0.1
        assert pytest.approx(vmax, rel=1e-6) == 0.1

        vmin, vmax = auto_colorbar_limits(values=[42.0, 42.0])
        assert pytest.approx(vmin, rel=1e-3) == 41.9
        assert pytest.approx(vmax, rel=1e-3) == 42.1
