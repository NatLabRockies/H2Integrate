import numpy as np
from numpy.typing import ArrayLike


SECONDS_IN_YEAR = 8760 * 60 * 60


def update_dimensions(n_components: int, *args: np.ndarray):
    """Update the dimensionality of a series of arrays and the value of :py:attr:`n_components`
    to match. If the size of an array passed :py:attr:`args` is 1 and :py:attr:`n_components`
    is greater than 1, all arrays passed to :py:attr:`args` will be broadcast to an array shaped
    (:py:attr:`n_components`, 1). If the arrays are already larger than 1, then
    :py:attr:`n_components will be updated to the size of the arrays.

    Args:
        n_components (int): Number of components in the model
        args (np.ndarray): NumPy array of attribute values used to create a model.

    Returns:
        n_components: The value as passed or updated to match the size of arrays in :py:attr:`args`.
        args: The arrays as passed or the arrays reshaped to shape (:py:attr:`n_components`, 1).
    """
    if args[0].size == 1 and n_components > 1:
        shape = (n_components, 1)
        for arg in args:
            arg = np.broadcast_to(arg, shape)
    n_components = args[0].size
    return n_components, *args


def float_array_converter(val: int | float | ArrayLike):
    return np.array(val).astype(float).reshape(-1, 1)


def int_array_converter(val: int | float | ArrayLike):
    return np.array(val).astype(int).reshape(-1, 1)


def calculate_simulation_years(value, self_) -> float:
    """Calculates the length of the simulation period, in years from the :py:attr:`self_.dt` and
    :py:attr:`self_.n_timesteps` provided from a configuration.
    """
    return self_.dt * self_.n_timesteps / SECONDS_IN_YEAR


def calculate_annual_timesteps(value, self_) -> float:
    """Calculates the number of timesteps in a year from the :py:attr:`self_.dt`, rounded up."""
    return int(np.ceil(SECONDS_IN_YEAR / self_.dt))


def array_ge(val):
    """Validates that all values of an array are greater than or equal to :py:attr:`val`."""

    def validator(instance, attribute, value):
        if any(value < val):
            raise ValueError(f"'{attribute.name}' must have all values of at least {val}.")

    return validator


def array_gt(val):
    """Validates that all values of an array are greater than or equal to :py:attr:`val`."""

    def validator(instance, attribute, value):
        if any(value <= val):
            raise ValueError(f"'{attribute.name}' must have all values greater than {val}.")

    return validator


def match_shape(other):
    """Validates the shape of an array matches the shape of :py:attr:`other`."""

    def validator(instance, attribute, value):
        other_arr = getattr(instance, other, None)
        if other_arr is None:
            raise ValueError(f"'{other}' does not exist.")
        if other_arr.shape != value.shape:
            msg = (
                f"Shape of '{attribute.name}' {value.shape} does not match"
                f" '{other}' {other_arr.shape}."
            )
            raise ValueError(msg)

    return validator
