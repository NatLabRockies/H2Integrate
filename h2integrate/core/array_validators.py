import numpy as np
from numpy.typing import ArrayLike, DTypeLike


def to_array(dtype: DTypeLike, shape: tuple[int, ...] | None = None):
    """Converts an array-like object to a NumPy ``NDArray`` with type :py:attr:`dtype` and shape
    :py:attr:`shape`.

    Args:
        dtype (DTypeLike): A NumPy compatible type such as ``float`` or ``int``.
        shape (tuple[int, ...]) | None: The shape the array should take once created, such as
            ``(-1, 1)`` for a single column array, or ``None`` of a standard 1-D dynamic-length
            array. Defaults to ``None``.
    """

    def convert(val: int | float | ArrayLike):
        arr = np.array(val).astype(dtype)
        if shape is not None:
            return arr.reshape(shape)
        return arr

    return convert


def array_ge(val):
    """Validates that all values of an array are greater than or equal to :py:attr:`val`."""

    def validator(instance, attribute, value):
        if (value < val).any():
            msg = f"'{attribute.name}' must have all values greater than or equal to {val}."
            raise ValueError(msg)

    return validator


def array_gt(val):
    """Validates that all values of an array are greater than or equal to :py:attr:`val`."""

    def validator(instance, attribute, value):
        if (value <= val).any():
            raise ValueError(f"'{attribute.name}' must have all values greater than {val}.")

    return validator


def array_le(val):
    """Validates that all values of an array are less than or equal to :py:attr:`val`."""

    def validator(instance, attribute, value):
        if (value > val).any():
            msg = f"'{attribute.name}' must have all values less than or equal to {val}."
            raise ValueError(msg)

    return validator


def array_lt(val):
    """Validates that all values of an array are less than :py:attr:`val`."""

    def validator(instance, attribute, value):
        if (value >= val).any():
            raise ValueError(f"'{attribute.name}' must have all values less than {val}.")

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
