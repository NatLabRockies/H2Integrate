"""
This module contains validator functions for use with `attrs` class definitions.
"""


def gt_zero(instance, attribute, value):
    """Validates that an attribute's value is greater than zero."""
    if value <= 0:
        raise ValueError(f"{attribute} must be greater than zero")


def gte_zero(instance, attribute, value):
    """Validates that an attribute's value is greater than or equal to zero."""
    if value < 0:
        raise ValueError(f"{attribute} must be greater than or equal to zero")


def range_val(min_val, max_val):
    """Validates that an attribute's value is between two values, inclusive ([min_val, max_val])."""

    def validator(instance, attribute, value):
        if value < min_val or value > max_val:
            raise ValueError(f"{attribute} must be in range [{min_val}, {max_val}]")

    return validator


def range_val_or_none(min_val, max_val):
    """Validates that an attribute's value is between two values, inclusive ([min_val, max_val]).
    Ignores None type values."""

    def validator(instance, attribute, value):
        if value is not None:
            if value < min_val or value > max_val:
                raise ValueError(f"{attribute} must be in range [{min_val}, {max_val}]")

    return validator


def contains(items):
    """Validates that an item is part of a given list."""

    def validator(instance, attribute, value):
        if value not in items:
            raise ValueError(f"Item {value} not found in list for {attribute}: {items}")

    return validator


def has_required_keys(required_keys):
    """Validates that a value is a dict containing all required keys.

    Args:
        required_keys (list[str] | tuple[str, ...]): Keys that must be present
            in the input dictionary.
    """

    required_keys = tuple(required_keys)

    def validator(instance, attribute, value):
        if not isinstance(value, dict):
            raise ValueError(
                f"{attribute.name} must be a dict containing keys {required_keys}, "
                f"got {type(value).__name__}."
            )

        missing_keys = [key for key in required_keys if key not in value]
        if missing_keys:
            raise ValueError(
                f"{attribute.name} is missing required key(s): {missing_keys}. "
                f"Expected keys include: {required_keys}."
            )

    return validator


def must_equal(required_value):
    """Validates that an item equals a specific value"""

    def validator(instance, attribute, value):
        if value != required_value:
            msg = (
                f"{attribute.name} cannot be {value}, {attribute.name} "
                f"must have value of {required_value}"
            )
            raise ValueError(msg)

    return validator
