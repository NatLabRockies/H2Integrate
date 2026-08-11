"""
This module contains validator functions for use with `attrs` class definitions.
"""


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
