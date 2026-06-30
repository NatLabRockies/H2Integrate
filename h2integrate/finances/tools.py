import re

from openmdao.utils.units import (
    PhysicalUnit,
    _find_unit,
    convert_units,
    is_compatible,
    simplify_unit,
)


def check_plant_config_and_profast_params(
    plant_config_dict: dict, pf_param_dict: dict, plant_config_key: str, pf_config_key: str
):
    """
    Checks for consistency between values in the plant configuration dictionary and the
    ProFAST parameters dictionary.

    This function compares the value associated with `plant_config_key` in `plant_config_dict`
    to the value associated with `pf_config_key` in `pf_param_dict`. If `pf_config_key` is not
    present in `pf_param_dict`, the value from `plant_config_dict` is used as the default.
    If the values are inconsistent, a ValueError is raised with a descriptive message.

    Args:
        plant_config_dict (dict): Dictionary containing plant configuration parameters.
        pf_param_dict (dict): Dictionary containing ProFAST parameter values.
        plant_config_key (str): Key to look up in `plant_config_dict`.
        pf_config_key (str): Key to look up in `pf_param_dict`.

    Raises:
        ValueError: If the values for the specified keys in the two dictionaries are inconsistent.
    """

    if (
        pf_param_dict.get(pf_config_key, plant_config_dict[plant_config_key])
        != plant_config_dict[plant_config_key]
    ):
        msg = (
            f"Inconsistent values provided for {pf_config_key} and {plant_config_key}, "
            f"{pf_config_key} is {pf_param_dict.get(pf_config_key)} but "
            f"{plant_config_key} is {plant_config_dict[plant_config_key]}."
            f"Please check that {pf_config_key} is the same as {plant_config_key} or remove "
            f"{pf_config_key} from pf_params input."
        )
        raise ValueError(msg)


def _compute_price_units(outputs):
    """Derive the OpenMDAO unit for a commodity price from an output dictionary.

    This helper is intended to be passed as the ``compute_units`` callback of
    ``om.ExplicitComponent.add_output``. It inspects the component's already-declared
    outputs to find the unit of the rated commodity production, then constructs the
    matching price unit as ``USD / (rate_unit * h)``.

    The function searches ``outputs`` for the first key matching the regex
    ``rated_\\w+_production`` (e.g. ``rated_hydrogen_production``,
    ``rated_electricity_production``). The unit string of the matched output is
    then used as ``rate_unit``, and the resulting price unit
    ``USD/(rate_unit*h)`` is resolved into an OpenMDAO unit object via
    ``openmdao.utils.units._find_unit``.

    Example:
        If ``outputs`` contains ``rated_hydrogen_production`` declared with units
        ``kg/h``, this function returns the OpenMDAO unit for ``USD/((kg/h)*h)``,
        which simplifies to ``USD/kg``.

    Args:
        outputs (dict): Mapping of output name to OpenMDAO output metadata object
            (typically the ``outputs`` dictionary passed to a ``compute_units``
            callback). Each value must expose a ``name()`` method returning the
            unit string of that output.

    Returns:
        The OpenMDAO unit object corresponding to ``USD/(rate_unit*h)``, suitable
        for use as the unit of a price-valued output.

    Raises:
        ValueError: If no ``rated_*_production`` output is present in ``outputs``
            to derive the rate unit from.
    """
    rate_units = [v.name() for k, v in outputs.items() if re.fullmatch(r"rated_\w+_production", k)]
    if len(rate_units) == 0:
        raise ValueError("Cannot find rate units")
    commodity_amount_units = f"({rate_units[0]})*h"
    price_units = f"USD/({commodity_amount_units})"
    return _find_unit(price_units)


def _compute_rate_units(price_units: str, check_conversion: bool):
    """Estimate rate units from price units.

    Args:
        price_units (str): Price units. Should be defined as USD per some commodity amount.
        check_conversion (bool): Whether to check for a conversion factor of 1.0 from price_units
            to price units re-calculated from the estimated rate_units


    Raises:
        ValueError: if the `rate_units` cannot be easily estimated from the `price_units`

    Returns:
        str: rate units extrapolated from `price_units`.
    """

    # 9 base units that make-up ``_powers`` attribute of a ``PhysicalUnit`` are:
    # [m, kg, s, A, K, mol, cd, rad, str, USD, pax, byte, unitless]
    # All base units have a ``_factor`` attribute of 1.0
    # ``_factor`` is the amount to multiply a number by to convert from the base units
    # to the other units. For example, 'g' has a factor of 0.001

    # 1. convert price units to amount units

    # Create ``PhysicalUnit`` objects for the price units and for units of USD
    price_unit_cls = _find_unit(price_units)
    usd_units = _find_unit("USD")

    # Remove the USD component from the numerator (divide by USD)
    names = price_unit_cls._names - usd_units._names
    factor = usd_units._factor * price_unit_cls._factor
    amount_units_powers = [a - b for a, b in zip(price_unit_cls._powers, usd_units._powers)]
    denom_amount_unit_cls = PhysicalUnit(names, factor, amount_units_powers)
    amount_units = simplify_unit(f"1/({denom_amount_unit_cls.name()})")

    # 2. convert amount units to rate units
    # Create ``PhysicalUnit`` objects for the amount units and for units of h
    amount_unit_cls = _find_unit(amount_units)
    hr_units = _find_unit("h")

    # Add in a time component to the denominator (divide by hours)
    rate_names = amount_unit_cls._names - hr_units._names
    rate_factor = hr_units._factor * amount_unit_cls._factor
    rate_units_powers = [a - b for a, b in zip(amount_unit_cls._powers, hr_units._powers)]
    rate_unit_cls = PhysicalUnit(rate_names, rate_factor, rate_units_powers)
    rate_units = rate_unit_cls.name()

    if not check_conversion:
        return rate_units
    equivalent_price_units = simplify_unit(f"USD/(({rate_units})*h)")

    conversion = convert_units(1, price_units, equivalent_price_units)
    if is_compatible(price_units, equivalent_price_units) and float(conversion) == 1.0:
        return rate_units

    msg = (
        f"Estimated rate units of '{rate_units}' from price units of '{price_units}'."
        f"Try to use price units of '{equivalent_price_units}' instead."
    )
    raise ValueError(msg)
