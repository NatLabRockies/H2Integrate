import numpy as np
from attrs import field, define

from h2integrate.core.utilities import BaseConfig
from h2integrate.core.validators import contains, gte_zero, range_val


@define(kw_only=True)
class BasicGridLayoutConfig(BaseConfig):
    """Configuration class for 'basicgrid' wind layout.

    Args:
        row_D_spacing (float): rotor diameter multiplier for spacing between rows of
            turbines (y direction).
        turbine_D_spacing (float): rotor diameter multiplier for spacing between
            turbines in a row (x direction).
        rotation_angle_deg (float, Optional): rotation angle of layout in degrees where 0 is North,
            increasing counter-clockwise. 90 degrees is East, 180 degrees is South,
            270 degrees is West. Defaults to 0.0.
        row_phase_offset (float, Optional): offset of turbines along row from one row to the next.
            Value must be between 0 and 1. Defaults to 0.0.
        layout_shape (str, optional): layout shape with respect to the number of turbines.
            Must be either 'square' or 'rectangle'. Defaults to 'square'.
        turbine_aspect_ratio (float, optional): ratio of number turbines per row / number of rows
            if using a 'rectangle' layout_shape. Unused for 'square' layout_shape.
    """

    row_D_spacing: float = field()
    turbine_D_spacing: float = field()
    rotation_angle_deg: float = field(default=0.0)
    row_phase_offset: float = field(default=0.0, validator=range_val(0.0, 1.0))

    layout_shape: str = field(
        default="square",
        converter=(str.lower, str.strip),
        validator=contains(["square", "rectangle"]),
    )
    turbine_aspect_ratio: float = field(default=1.0, validator=gte_zero)

    def __attrs_post_init__(self):
        if self.layout_shape == "square" and self.turbine_aspect_ratio != 1.0:
            raise UserWarning("Turbine aspect ratio is unused for layout_shape 'square'.")


def find_square_layout_dimensions_by_nturbs(n_turbs):
    """Calculate dimensions of the most-square shaped layout for
        a given number of turbines.

    Args:
        n_turbs (int): number of wind turbines.

    Returns:
        2-element tuple containing

        - **n_turbs_per_row** (int): number of turbines per row
        - **n_rows** (int): number of rows in layout (rows are parallel to x-axis)
    """
    n_turbs_per_row = np.floor_divide(n_turbs, np.sqrt(n_turbs))
    n_rows_min = n_turbs // n_turbs_per_row
    remainder_turbs = n_turbs % n_turbs_per_row
    if remainder_turbs > n_turbs_per_row:
        n_extra_rows = np.ceil(remainder_turbs / n_turbs_per_row)
    elif remainder_turbs == 0:
        n_extra_rows = 0
    else:
        n_extra_rows = 1

    n_rows = n_rows_min + n_extra_rows

    return n_turbs_per_row.astype(int), n_rows.astype(int)


def find_rectangular_layout_dimensions_by_nturbs(n_turbs, aspect_ratio):
    """Calculate dimensions of a rectangular shaped layout for
        a given number of turbines and aspect ratio.

    Args:
        n_turbs (int): number of wind turbines.
        aspect_ratio (float, Optional): ratio of width/height or
            number turbines per row / number of rows. (width corresponds
            to x coordinates, height corresponds to y coordinates)

    Returns:
        2-element tuple containing

        - **n_turbs_per_row** (int): number of turbines per row
        - **n_rows** (int): number of rows in layout (rows are parallel to x-axis)
    """

    n_turbs_per_row = np.floor_divide(n_turbs, np.sqrt(n_turbs / aspect_ratio))
    n_rows_min = n_turbs // n_turbs_per_row
    remainder_turbs = n_turbs % n_turbs_per_row
    if remainder_turbs > n_turbs_per_row:
        n_extra_rows = np.ceil(remainder_turbs / n_turbs_per_row)
    elif remainder_turbs == 0:
        n_extra_rows = 0
    else:
        n_extra_rows = 1

    n_rows = n_rows_min + n_extra_rows

    return n_turbs_per_row.astype(int), n_rows.astype(int)


def make_basic_grid_turbine_layout(
    rotor_diameter, n_turbines, layout_config: BasicGridLayoutConfig
):
    """Makes a turbine layout for a basic gridded layout config.

    Args:
        rotor_diameter (float): turbine rotor diameter in meters
        n_turbines (int): number of turbines to generate layout form
        layout_config (BasicGridLayoutConfig): layout configuration.

    Returns:
        2-element tuple containing

        - **x_coords** (array[float]): x coordinates of turbines in layout
        - **y_coords** (array[float]): y coordinates of turbines in layout
    """
    n_turbs = int(n_turbines)

    if layout_config.layout_shape == "square":
        n_turbs_x, n_turbs_y = find_square_layout_dimensions_by_nturbs(n_turbs)
    if layout_config.layout_shape == "rectangle":
        n_turbs_x, n_turbs_y = find_rectangular_layout_dimensions_by_nturbs(
            n_turbs, layout_config.turbine_aspect_ratio
        )

    # distance between rows (y)
    y_spacing = layout_config.row_D_spacing * rotor_diameter

    # distance between turbines in a row (x)
    x_spacing = layout_config.turbine_D_spacing * rotor_diameter

    # row phase offset in meters
    phase_offset = x_spacing * layout_config.row_phase_offset

    x_coords = np.zeros((n_turbs_y, n_turbs_x))
    y_coords = np.zeros((n_turbs_y, n_turbs_x))

    for row_number in range(n_turbs_y):
        # make x0 for each row start
        x0 = (phase_offset * row_number) % x_spacing
        # get turbine x positions
        x_pos_in_row = x0 + np.cumsum(x_spacing * np.ones(n_turbs_x)) - x_spacing
        y_pos = row_number * y_spacing * np.ones(n_turbs_x)
        x_coords[row_number] = x_pos_in_row[:n_turbs_x]
        y_coords[row_number] = y_pos

    # get center points
    xc = x_coords.max() - x_coords.min()
    yc = y_coords.max() - y_coords.min()

    # translate coordinates to have origin at polygon center
    xc_points = x_coords.flatten() - xc
    yc_points = y_coords.flatten() - yc

    # calculate rotation angle
    theta = np.deg2rad(layout_config.rotation_angle_deg)

    # rotate clockwise about the origin
    cos_theta = np.cos(theta)
    sin_theta = np.sin(theta)
    xr_points = (xc_points * cos_theta) + (yc_points * sin_theta)
    yr_points = (-1 * xc_points * sin_theta) + (yc_points * cos_theta)

    # translate points back to original coordinate reference system
    x_rotated = xr_points + xc
    y_rotated = yr_points + yc

    return x_rotated[:n_turbs], y_rotated[:n_turbs]
