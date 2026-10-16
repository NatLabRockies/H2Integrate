"""Pure conversion-ratio calculations for system-level control."""

from collections.abc import Mapping, Iterable

import numpy as np
from numpy.typing import NDArray, ArrayLike

from h2integrate.control.control_strategies.system_level.slc_topology import ConversionLink


def capacity_ratio(
    supplier_rated_capacities: Iterable[ArrayLike],
    feedstock_supplies: Iterable[ArrayLike],
    rated_output: ArrayLike,
) -> float | None:
    """Calculate an input-per-output sizing ratio from rated capacities.

    Controller-managed suppliers contribute the sum of their rated capacities;
    feedstock suppliers contribute their mean supply. This is a seed for the
    conversion ratio, not a measured efficiency.

    Args:
        supplier_rated_capacities: Rated input capacities for controlled
            suppliers.
        feedstock_supplies: Feedstock input supply profiles.
        rated_output: Rated output capacity of the converter.

    Returns:
        The total rated input divided by rated output, or ``None`` when either
        side has no usable capacity.
    """
    total_input_capacity = sum(
        float(np.sum(np.asarray(capacity, dtype=float))) for capacity in supplier_rated_capacities
    )
    for supply in feedstock_supplies:
        supply_array = np.asarray(supply, dtype=float)
        if supply_array.size:
            total_input_capacity += float(np.mean(supply_array))

    rated_output_array = np.asarray(rated_output, dtype=float).reshape(-1)
    if rated_output_array.size == 0:
        return None
    rated_output_value = float(rated_output_array[0])

    if (
        not np.isfinite(total_input_capacity)
        or not np.isfinite(rated_output_value)
        or rated_output_value == 0.0
        or total_input_capacity == 0.0
    ):
        return None
    return total_input_capacity / rated_output_value


def measured_ratio(
    consumed: ArrayLike, produced: ArrayLike, fallback: float
) -> NDArray[np.float64]:
    """Calculate measured input-per-output ratios, filling invalid points.

    A measurement is valid only when both values are finite and production is
    nonzero. Invalid points, including zero-production timesteps, use the
    supplied fallback.

    Args:
        consumed: Measured input consumption by timestep.
        produced: Measured output production by timestep.
        fallback: Ratio used where a measurement cannot be calculated.

    Returns:
        The measured ratio at valid timesteps and ``fallback`` elsewhere.
    """
    consumed_array, produced_array = np.broadcast_arrays(
        np.asarray(consumed, dtype=float), np.asarray(produced, dtype=float)
    )
    valid = np.isfinite(consumed_array) & np.isfinite(produced_array) & (produced_array != 0.0)
    ratio = np.full(consumed_array.shape, float(fallback), dtype=float)
    np.divide(consumed_array, produced_array, out=ratio, where=valid)
    return ratio


def conversion_ratio(
    consumed: ArrayLike,
    produced: ArrayLike,
    fallback: float | None,
) -> tuple[NDArray[np.float64], NDArray[np.str_]]:
    """Return per-timestep ratios and identify measured versus fallback values.

    When no capacity fallback is available but some measurements are valid,
    invalid timesteps use the mean of the valid measured ratios. A caller with
    neither a capacity fallback nor any valid measurements should handle that
    missing-ratio case before calling this function.

    Args:
        consumed: Measured input consumption by timestep; NaN marks an
            unconnected signal.
        produced: Measured output production by timestep.
        fallback: Capacity-based sizing ratio, or ``None`` when unavailable.

    Returns:
        A pair containing the ratio array and a same-shaped source array whose
        entries are ``"measured"`` or ``"capacity"``.

    Raises:
        ValueError: If no valid measured ratio or fallback is available.
    """
    consumed_array, produced_array = np.broadcast_arrays(
        np.asarray(consumed, dtype=float), np.asarray(produced, dtype=float)
    )
    valid = np.isfinite(consumed_array) & np.isfinite(produced_array) & (produced_array != 0.0)

    if fallback is not None and not np.isfinite(fallback):
        fallback = None
    if fallback is None:
        if not np.any(valid):
            raise ValueError("A fallback or at least one valid measured ratio is required.")
        measured_values = np.zeros(consumed_array.shape, dtype=float)
        np.divide(consumed_array, produced_array, out=measured_values, where=valid)
        fallback = float(measured_values[valid].mean())
        fallback_source = "measured"
    else:
        fallback_source = "capacity"

    ratios = measured_ratio(consumed_array, produced_array, float(fallback))
    sources = np.where(valid, "measured", fallback_source)
    return ratios, sources


def accumulate_derived_demand(
    derived_demand: Mapping[str, ArrayLike],
    contributions: Mapping[str, Mapping[str, ArrayLike]],
    link: ConversionLink,
    set_point: ArrayLike,
    ratio: ArrayLike,
) -> tuple[dict[str, NDArray[np.float64]], dict[str, dict[str, NDArray[np.float64]]]]:
    """Return updated demand and contributions without mutating either input.

    Contributions from multiple outputs of the same converter are combined by
    element-wise maximum. Distinct converters on the same input bus still sum
    through the bus's ``derived_demand`` profile.

    Args:
        derived_demand: Current demand profile for each supply bus.
        contributions: Per-bus demand contributions, keyed by converter.
        link: Conversion link whose output demand is being propagated.
        set_point: Converter output set point.
        ratio: Per-timestep input-per-output conversion ratio.

    Returns:
        New ``(derived_demand, contributions)`` dictionaries. Input mappings
        and arrays are left unchanged.
    """
    new_demand = {
        bus_name: np.asarray(demand, dtype=float).copy()
        for bus_name, demand in derived_demand.items()
    }
    new_contributions = {
        bus_name: {
            tech_name: np.asarray(value, dtype=float).copy()
            for tech_name, value in bus_contributions.items()
        }
        for bus_name, bus_contributions in contributions.items()
    }

    contribution = np.maximum(np.asarray(set_point, dtype=float), 0.0) * np.asarray(
        ratio, dtype=float
    )
    by_tech = new_contributions.setdefault(link.in_bus, {})
    previous = by_tech.get(link.tech)
    if previous is None:
        combined = contribution
        delta = contribution
    else:
        combined = np.maximum(previous, contribution)
        delta = combined - previous
    by_tech[link.tech] = combined.copy()

    if link.in_bus in new_demand:
        new_demand[link.in_bus] = new_demand[link.in_bus] + delta
    else:
        new_demand[link.in_bus] = delta.copy()

    return new_demand, new_contributions
