"""
Curve fitting utilities for ASPEN surface processing models.

This module contains all the curve fitting functions, data structures, and utilities
needed to fit cost and performance curves to individual data points produced from
Aspen processing modeling.

The main functions provided are:
- refit_coeffs: Fit curves to ASPEN data and save coefficients
- load_coeffs: Load pre-fitted coefficients from file
- evaluate_performance_curves: Evaluate fitted curves for given inputs
"""

from pathlib import Path
from dataclasses import dataclass

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from scipy.optimize import curve_fit


# Constants
ROOT_DIR = Path(__file__).resolve().parent.parent
CURVE_FIT_TOLERANCE = 0.0001
STEAM_CONSTANT = 0.61  # kt/h - little variance between Aspen results

# Curve fit type constants
CURVE_FIT_TYPE_DOUBLE_EXP = "double_exp"
CURVE_FIT_TYPE_EXP_POWER = "exp_power"
CURVE_FIT_TYPE_NONE = "none"


@dataclass
class CurveCoefficients:
    """Container for curve fitting coefficients and metadata."""

    a1: float
    a2: float
    a3: float
    a4: float
    a5: float
    scale_x: float
    scale_y: float
    scale_z: float
    fit_type: str

    def to_dict(self) -> dict:
        """Convert to dictionary format."""
        return {
            "a1": self.a1,
            "a2": self.a2,
            "a3": self.a3,
            "a4": self.a4,
            "a5": self.a5,
            "scale_x": self.scale_x,
            "scale_y": self.scale_y,
            "scale_z": self.scale_z,
            "fit_type": self.fit_type,
        }


def scale_variables(input_vars: list[np.ndarray] | np.ndarray) -> tuple[np.ndarray, list[float]]:
    """
    Scale variables to the range [0, 1] for better numerical conditioning during curve fitting.

    Args:
        input_vars: List of arrays to scale (must contain positive values).

    Returns:
        Tuple of (scaled_variables, scale_factors) where scale_factors are the max values.
    """

    if isinstance(input_vars, list):
        input_vars = np.array(input_vars)
    scale_factors = input_vars.max(axis=1)
    scaled_inputs = np.transpose(np.transpose(input_vars) / scale_factors)

    return scaled_inputs, list(scale_factors)


def exponential_power_function(
    xy: tuple[np.ndarray, np.ndarray], a1: float, a2: float, a3: float, a4: float, a5: float
) -> np.ndarray:
    """
    Two-variable curve fitting function combining exponential and power terms.

    Function form: f(x, y) = a1 * exp(x * a2) + a3 * y^a4 + a5

    Args:
        xy: Tuple of (x, y) input arrays.
        a1, a2, a3, a4, a5: Curve fitting coefficients.

    Returns:
        Fitted output values.
    """
    x, y = xy
    return a1 * np.exp(x * a2) + a3 * y**a4 + a5


def double_power_function(
    xy: tuple[np.ndarray, np.ndarray], a1: float, a2: float, a3: float, a4: float, a5: float
) -> np.ndarray:
    """
    Two-variable curve fitting function with two power terms (only uses x variable).

    Function form: f(x, y) = a1 * x^a2 + a3 * x^a4 + a5
    Note: y variable is kept for API consistency with exponential_power_function.

    Args:
        xy: Tuple of (x, y) input arrays (y is ignored).
        a1, a2, a3, a4, a5: Curve fitting coefficients.

    Returns:
        Fitted output values.
    """
    x, _ = xy
    return a1 * x**a2 + a3 * x**a4 + a5


def evaluate_curve(xy: tuple[np.ndarray, np.ndarray], coeffs: CurveCoefficients) -> np.ndarray:
    """
    Evaluate a fitted curve using the appropriate function type.

    Args:
        xy: Tuple of (x, y) scaled input arrays.
        coeffs: Curve coefficients including fit type.

    Returns:
        Scaled output values.
    """
    curve_params = [coeffs.a1, coeffs.a2, coeffs.a3, coeffs.a4, coeffs.a5]

    if coeffs.fit_type == CURVE_FIT_TYPE_DOUBLE_EXP:
        return double_power_function(xy, *curve_params)
    elif coeffs.fit_type == CURVE_FIT_TYPE_EXP_POWER:
        return exponential_power_function(xy, *curve_params)
    else:  # NONE type (e.g., steam with constant value)
        return np.zeros_like(xy[0])


def load_aspen_data(input_fn: str) -> tuple[np.ndarray, np.ndarray, pd.DataFrame]:
    """
    Load ASPEN modeling results from CSV file.

    Args:
        input_fn: Filename of ASPEN results CSV in ./inputs directory.

    Returns:
        Tuple of (h2_concentration, flow_rate, dataframe).
    """
    path = ROOT_DIR / "inputs"

    inputs_df = pd.read_csv(path / input_fn, index_col=["Item", "Units"])
    h2_conc = inputs_df.loc["H2 Conc Wellhead"].to_numpy().flatten()
    flow = inputs_df.loc["Mass Flow Wellhead"].to_numpy().flatten()

    return h2_conc, flow, inputs_df


def fit_single_curve(
    output_name: str,
    scaled_output: np.ndarray,
    fit_input_data: np.ndarray,
    input_scale_factors: list[float],
    output_scale_factor: float,
) -> CurveCoefficients:
    """
    Fit a single curve to the scaled data.

    Args:
        output_name: Name of the output variable.
        scaled_output: Scaled output data.
        fit_input_data: Scaled input data.
        input_scale_factors: Scale factors for inputs.
        output_scale_factor: Scale factor for output.

    Returns:
        CurveCoefficients object with fitted parameters.
    """
    # Determine which curve fitting function and how many data points to use
    # Data points 0-4 are from Aspen modeling.
    # Data points 5-6 at H2 conc. = 100% and 0% are empirically correlated.
    if output_name == "H2 Flow Out [kg/hr]":
        fit_type, n_points = CURVE_FIT_TYPE_DOUBLE_EXP, 6
    elif output_name in ["H2 Conc Out [% mol]", "Labor [op/shift]"]:
        fit_type, n_points = CURVE_FIT_TYPE_DOUBLE_EXP, 5
    elif output_name == "Capex [USD]":
        fit_type, n_points = CURVE_FIT_TYPE_EXP_POWER, 7
    elif output_name in ["Electricity [kW]", "Cooling Water [kt/h]"]:
        fit_type, n_points = CURVE_FIT_TYPE_EXP_POWER, 6
    else:  # Steam
        fit_type, n_points = CURVE_FIT_TYPE_NONE, 5

    # Select appropriate fitting function
    if fit_type == CURVE_FIT_TYPE_DOUBLE_EXP:
        fit_func = double_power_function
    elif fit_type == CURVE_FIT_TYPE_EXP_POWER:
        fit_func = exponential_power_function
    else:  # NONE type - use exp_power but won't be used
        fit_func = exponential_power_function

    # Perform curve fitting
    input_subset = fit_input_data[:, :n_points]
    output_subset = scaled_output[:n_points]
    opt_coeffs, _ = curve_fit(fit_func, input_subset, output_subset, ftol=CURVE_FIT_TOLERANCE)

    return CurveCoefficients(
        a1=opt_coeffs[0],
        a2=opt_coeffs[1],
        a3=opt_coeffs[2],
        a4=opt_coeffs[3],
        a5=opt_coeffs[4],
        scale_x=input_scale_factors[0],
        scale_y=input_scale_factors[1],
        scale_z=output_scale_factor,
        fit_type=fit_type,
    )


def plot_curve_fit(
    output_name: str,
    coeffs: CurveCoefficients,
    h2_conc: np.ndarray,
    flow: np.ndarray,
    actual_output: np.ndarray,
    h2_out: np.ndarray,
    h2_out_surf: np.ndarray | None = None,
) -> np.ndarray | None:
    """
    Plot the fitted curve surface and data points for validation.

    Args:
        output_name: Name of the output variable.
        coeffs: Fitted curve coefficients.
        h2_conc: H2 concentration data points.
        flow: Flow rate data points.
        actual_output: Actual output values.
        h2_out: H2 output flow for normalization.
        h2_out_surf: H2 output surface (for non-H2 flow variables).

    Returns:
        Updated h2_out_surf if output_name is "H2 Flow Out [kg/hr]", else None.
    """
    # Create evaluation grid
    x_grid_pts = np.arange(0.01, 1, 0.01)
    y_grid_pts = np.exp(np.linspace(np.log(1000), np.log(100000), 100))
    x_grid, y_grid = np.meshgrid(x_grid_pts, y_grid_pts)

    # Scale the grid
    x_grid_scaled = x_grid / coeffs.scale_x
    y_grid_scaled = y_grid / coeffs.scale_y

    # Evaluate fitted surface
    if coeffs.fit_type == CURVE_FIT_TYPE_DOUBLE_EXP:
        z_surf_scaled = double_power_function(
            (x_grid_scaled, y_grid_scaled), coeffs.a1, coeffs.a2, coeffs.a3, coeffs.a4, coeffs.a5
        )
    else:
        z_surf_scaled = exponential_power_function(
            (x_grid_scaled, y_grid_scaled), coeffs.a1, coeffs.a2, coeffs.a3, coeffs.a4, coeffs.a5
        )

    z_surf = z_surf_scaled * coeffs.scale_z

    # Apply appropriate scaling based on output type
    new_h2_out_surf = None
    if output_name == "H2 Flow Out [kg/hr]":
        new_h2_out_surf = z_surf * y_grid
    elif output_name == "Steam [kt/h]":
        z_surf = STEAM_CONSTANT / h2_out_surf if h2_out_surf is not None else z_surf
    elif output_name not in ["H2 Conc Out [% mol]"]:
        if h2_out_surf is not None:
            z_surf = z_surf * y_grid / h2_out_surf

    # Create contour plot
    cplot = plt.contourf(x_grid_pts, y_grid_pts, z_surf, cmap="turbo", levels=256)

    # Plot actual data points
    cmap_min = np.min(cplot.levels)
    cmap_max = np.max(cplot.levels)

    for i, point_value in enumerate(actual_output[:5]):
        if output_name not in ["H2 Flow Out [kg/hr]", "H2 Conc Out [% mol]"]:
            point_value *= flow[i] / h2_out[i]

        point_color_frac = (point_value - cmap_min) / (cmap_max - cmap_min)
        plt.plot(
            h2_conc[i],
            flow[i],
            "o",
            zorder=1,
            color=cplot.cmap(point_color_frac)[:3],
            markeredgecolor=[1, 1, 1],
        )

    # Format plot labels
    label = output_name
    if "H2 Conc Out" not in output_name and output_name != "H2 Flow Out [kg/hr]":
        label = output_name[:-1] + "/(kg/hr H2 out)]"

    plt.title(label)
    plt.xlabel("Wellhead Hydrogen Concentration [mol %]")
    plt.ylabel("Wellhead Flow Capacity [kg/hr]")
    plt.semilogy()

    cbar = plt.colorbar()
    cbar.set_label(label, loc="center")
    plt.show()

    return new_h2_out_surf


def refit_coeffs(
    input_fn: str, refit_coeff_fn: str, output_names: list[str], plot_flag: bool = False
) -> dict[str, dict]:
    """
    Fit performance and cost coefficients to ASPEN modeling data for surface processing model.

    This fits three-dimensional surfaces with two inputs (H2 concentration and wellhead flow)
    and one output (cycling through variables in output_names).

    Args:
        input_fn (str): Filename of ASPEN results CSV in ./inputs directory.
        refit_coeff_fn (str | None): Filename to save fitted coefficients to in ./inputs directory.
            If None, does not save the file.
        output_names (list[str]): List of output variable names to fit curves for.
        plot_flag (bool): Whether to plot fitted surfaces for visual validation.

    Returns:
        dict: Dictionary mapping output names to their fitted coefficients.
    """
    # Load and prepare data
    h2_conc, flow, inputs_df = load_aspen_data(input_fn)

    # Check for any invalid output names
    invalid_output_names = [
        out_name
        for out_name in output_names
        if out_name not in list(inputs_df.index.get_level_values("Item"))
    ]
    if len(invalid_output_names) > 0:
        msg = (
            f"{invalid_output_names} is not a valid output name, valid options "
            f"include {inputs_df.index.to_list()}"
        )
        raise ValueError(msg)

    # Extract and normalize outputs
    output_names = list({*output_names})
    output_names.insert(0, "H2 Flow Out [kg/hr]")

    outputs = np.zeros((len(output_names), len(h2_conc)))
    for ni, name in enumerate(output_names):
        if "H2 Conc" in name:
            outputs[ni] = inputs_df.loc[name].to_numpy().flatten()
            continue
        outputs[ni] = inputs_df.loc[name].to_numpy().flatten() / flow

    # Scale data for numerical conditioning
    fit_input_data, in_scale_factors = scale_variables([h2_conc, flow])
    scaled_outputs, out_scale_factors = scale_variables(outputs)

    # Fit curves for each output
    col_names = ["a1", "a2", "a3", "a4", "a5", "scale_x", "scale_y", "scale_z", "fit_type"]

    # Generate labels for the outputs
    name_to_label = {
        name: f"{name[:-1]}/(kg/hr H2 in)]" if "H2 Conc Out" not in name else name
        for name in output_names
    }

    fit_coeffs = pd.DataFrame(columns=col_names, index=list(name_to_label.values()))
    h2_out_surf = None  # only used for plotting
    for i, name in enumerate(output_names):
        # Fit the curve
        coeffs = fit_single_curve(
            name, scaled_outputs[i], fit_input_data, in_scale_factors, out_scale_factors[i]
        )

        fit_coeffs.loc[name_to_label[name]] = coeffs.to_dict()

        # Plot if requested
        if plot_flag:
            h2_out = outputs[output_names.index("H2 Flow Out [kg/hr]")] * flow

            actual_output = scaled_outputs[i] * out_scale_factors[i]
            new_surf = plot_curve_fit(
                name, coeffs, h2_conc, flow, actual_output, h2_out, h2_out_surf
            )
            if h2_out_surf is None:
                h2_out_surf = new_surf

    # Save coefficients to CSV
    if refit_coeff_fn is not None:
        fit_coeffs.to_csv(ROOT_DIR / "inputs" / refit_coeff_fn)

    # Return as dictionary
    return fit_coeffs.to_dict("index")


def load_coeffs(coeff_fn: str, output_names: list[str]) -> dict[str, dict]:
    """
    Load pre-fitted curve coefficients from CSV file.

    Args:
        coeff_fn (str): Filename of coefficients CSV in ./inputs directory.
        output_names (list[str]): List of output variable names to load.

    Returns:
        dict: Dictionary mapping output names to their coefficient dictionaries.
    """
    df = pd.read_csv(ROOT_DIR / "inputs" / coeff_fn, index_col="Unnamed: 0")

    invalid_output_names = [
        out_name for out_name in output_names if out_name not in df.index.to_list()
    ]
    if len(invalid_output_names) > 0:
        msg = (
            f"{invalid_output_names} is not a valid output name, valid options include"
            f" {df.index.to_list()}"
        )

        raise ValueError(msg)

    coeff_dict = df.loc[output_names].to_dict("index")

    return coeff_dict


def evaluate_performance_curves(
    h2_conc: float, wellhead_cap: float, coeffs_dict: dict[str, dict], curve_names: list[str]
) -> dict[str, float]:
    """
    Evaluate all performance curves for given inputs.

    Args:
        h2_conc (float): H2 concentration (fraction, not %).
        wellhead_cap (float): Wellhead capacity in kg/hr.
        coeffs_dict (dict): Dictionary of curve coefficients.
        curve_names (list[str]): List of curve names to evaluate.

    Returns:
        dict: Dictionary mapping curve names to evaluated results.
    """
    results = {}

    for curve_name, curve_coeffs in coeffs_dict.items():
        # curve_coeffs = coeffs_dict[curve_name]

        # Scale inputs
        x = h2_conc / curve_coeffs["scale_x"]
        y = wellhead_cap / curve_coeffs["scale_y"]

        # Get coefficients
        params = [curve_coeffs[f"a{i}"] for i in range(1, 6)]

        # Evaluate based on fit type
        fit_type = curve_coeffs["fit_type"]
        if fit_type == CURVE_FIT_TYPE_DOUBLE_EXP:
            z = double_power_function((x, y), *params)
        elif fit_type == CURVE_FIT_TYPE_EXP_POWER:
            z = exponential_power_function((x, y), *params)
        else:  # NONE type (steam constant)
            z = 0.0

        # Unscale output
        results[curve_name] = z * curve_coeffs["scale_z"]

    return results


if __name__ == "__main__":
    """
    This main block is for refitting the curve coefficients directly.
    """
    output_names = [
        "H2 Flow Out [kg/hr]",
        "H2 Conc Out [% mol]",
        "Electricity [kW]",
        "Cooling Water [kt/h]",
        "Steam [kt/h]",
    ]
    coeffs = refit_coeffs("aspen_results.csv", "aspen_perf_coeffs.csv", output_names, True)
    output_names = ["Capex [USD]", "Labor [op/shift]"]
    coeffs = refit_coeffs("aspen_results.csv", "aspen_cost_coeffs.csv", output_names, True)
