"""
This module contains validator functions for use with `attrs` class definitions.
"""


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
