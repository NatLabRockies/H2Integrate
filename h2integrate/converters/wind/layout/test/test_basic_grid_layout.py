import numpy as np
import pytest

from h2integrate.converters.wind.layout.simple_grid_layout import (
    BasicGridLayoutConfig,
    make_basic_grid_turbine_layout,
    find_square_layout_dimensions_by_nturbs,
    find_rectangular_layout_dimensions_by_nturbs,
)


@pytest.mark.unit
def test_rectangular_layout_dimensions(subtests):
    n_turbs_per_row = 10
    n_rows = 5
    aspect_ratio = n_turbs_per_row / n_rows
    n_turbs = n_turbs_per_row * n_rows
    n_turbs_per_row_out, n_rows_out = find_rectangular_layout_dimensions_by_nturbs(
        n_turbs, aspect_ratio
    )
    with subtests.test("number of turbines per row"):
        assert n_turbs_per_row_out == n_turbs_per_row
    with subtests.test("number of rows"):
        assert n_rows_out == n_rows
    with subtests.test("number of turbines"):
        assert int(n_rows_out * n_turbs_per_row_out) == int(n_turbs)


@pytest.mark.unit
def test_square_layout_dimensions(subtests):
    n_turbs = 25
    n_turbs_per_row_out, n_rows_out = find_square_layout_dimensions_by_nturbs(n_turbs)
    with subtests.test("number of turbines per row"):
        assert n_turbs_per_row_out == 5
    with subtests.test("number of rows"):
        assert n_rows_out == 5
    with subtests.test("number of turbines"):
        assert int(n_rows_out * n_turbs_per_row_out) == n_turbs


@pytest.mark.unit
def test_square_layout_dimensions_uneven_nturbs(subtests):
    n_turbs = 50
    n_turbs_per_row_out, n_rows_out = find_square_layout_dimensions_by_nturbs(n_turbs)
    with subtests.test("number of turbines per row"):
        assert n_turbs_per_row_out == 7
    with subtests.test("number of rows"):
        assert n_rows_out == 8
    with subtests.test("number of turbines"):
        assert int(n_rows_out * n_turbs_per_row_out) >= n_turbs


@pytest.mark.unit
def test_simple_square_layout_uneven_nturbs(subtests):
    layout_config_dict = {
        "row_D_spacing": 7.0,
        "turbine_D_spacing": 5.0,
        "rotation_angle_deg": 0.0,
        "row_phase_offset": 0.0,
        "layout_shape": "square",
    }
    layout_config = BasicGridLayoutConfig.from_dict(layout_config_dict)
    rotor_diameter = 10
    n_turbs = 50
    x_coords, y_coords = make_basic_grid_turbine_layout(rotor_diameter, n_turbs, layout_config)

    with subtests.test("expected number of turbines in x coordinates"):
        assert len(x_coords) == n_turbs
    with subtests.test("expected number of turbines in y coordinates"):
        assert len(y_coords) == n_turbs
    x_positions, x_position_counts = np.unique(x_coords, return_counts=True)
    y_positions, y_position_counts = np.unique(y_coords, return_counts=True)

    with subtests.test("number of rows"):
        assert len(y_positions) == 8

    with subtests.test("number of turbines per row"):
        assert len(x_positions) == 7

    with subtests.test("number of unique x positions"):
        assert sum(x_position_counts) == n_turbs

    with subtests.test("number of unique y positions"):
        assert sum(y_position_counts) == n_turbs

    with subtests.test("x_spacing"):
        assert (
            x_positions[1] - x_positions[0]
            == rotor_diameter * layout_config_dict["turbine_D_spacing"]
        )

    with subtests.test("y_spacing"):
        assert (
            y_positions[1] - y_positions[0] == rotor_diameter * layout_config_dict["row_D_spacing"]
        )

    with subtests.test("unique coordinates"):
        coord_list = list(zip(x_coords, y_coords))
        unique_coords = list(set(coord_list))
        assert len(unique_coords) == n_turbs


@pytest.mark.unit
def test_simple_rectangular_layout_uneven_nturbs(subtests):
    layout_config_dict = {
        "row_D_spacing": 7.0,
        "turbine_D_spacing": 5.0,
        "rotation_angle_deg": 0.0,
        "row_phase_offset": 0.0,
        "layout_shape": "rectangle",
        "turbine_aspect_ratio": 2.0,
    }
    layout_config = BasicGridLayoutConfig.from_dict(layout_config_dict)
    rotor_diameter = 10
    n_turbs = 50
    x_coords, y_coords = make_basic_grid_turbine_layout(rotor_diameter, n_turbs, layout_config)

    with subtests.test("expected number of turbines in x coordinates"):
        assert len(x_coords) == n_turbs
    with subtests.test("expected number of turbines in y coordinates"):
        assert len(y_coords) == n_turbs
    x_positions, x_position_counts = np.unique(x_coords, return_counts=True)
    y_positions, y_position_counts = np.unique(y_coords, return_counts=True)

    with subtests.test("number of rows"):
        assert len(y_positions) == 5

    with subtests.test("number of turbines per row"):
        assert len(x_positions) == 10

    with subtests.test("number of unique x positions"):
        assert sum(x_position_counts) == n_turbs

    with subtests.test("number of unique y positions"):
        assert sum(y_position_counts) == n_turbs

    with subtests.test("x_spacing"):
        assert (
            x_positions[1] - x_positions[0]
            == rotor_diameter * layout_config_dict["turbine_D_spacing"]
        )

    with subtests.test("y_spacing"):
        assert (
            y_positions[1] - y_positions[0] == rotor_diameter * layout_config_dict["row_D_spacing"]
        )

    with subtests.test("unique coordinates"):
        coord_list = list(zip(x_coords, y_coords))
        unique_coords = list(set(coord_list))
        assert len(unique_coords) == n_turbs
