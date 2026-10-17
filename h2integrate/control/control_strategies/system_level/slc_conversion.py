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


CONVERSION_RATIO_METHODS = ("timestep", "aggregate")


def conversion_ratio(
    consumed: ArrayLike,
    produced: ArrayLike,
    fallback: float | None,
    method: str = "aggregate",
) -> tuple[NDArray[np.float64], NDArray[np.str_]]:
    """Return per-timestep ratios and identify measured versus fallback values.

    With ``method="aggregate"`` (the default), every timestep uses one
    production-weighted ratio, total valid consumption divided by total valid
    production. With ``method="timestep"``, each valid timestep uses its own
    measured ratio, and invalid timesteps use the mean of the valid measured
    ratios. The capacity fallback is used only when no measured ratio is
    available.

    The aggregate ratio acts as a low-pass filter on the measurement feedback.
    A per-timestep ratio reflects the operating point the converter reached in
    the previous solver iteration (part load, start-up, degradation), so it
    feeds hourly plant events back into hourly demand and can keep a
    Gauss-Seidel iteration from settling. The aggregate ratio responds only to
    the converter's overall efficiency, at the cost of part-load detail.

    Args:
        consumed: Measured input consumption by timestep; NaN marks an
            unconnected signal.
        produced: Measured output production by timestep.
        fallback: Capacity-based sizing ratio, or ``None`` when unavailable.
        method: ``"aggregate"`` or ``"timestep"``. Defaults to ``"aggregate"``.

    Returns:
        A pair containing the ratio array and a same-shaped source array whose
        entries are ``"measured"``, ``"aggregate"``, or ``"capacity"``.

    Raises:
        ValueError: If ``method`` is unknown, or if no valid measured ratio or
            fallback is available.

    Examples:
        >>> ratio, source = conversion_ratio([50.0, 70.0, 0.0], [1.0, 1.0, 0.0], None)
        >>> ratio.tolist(), source.tolist()
        ([60.0, 60.0, 60.0], ['aggregate', 'aggregate', 'aggregate'])
    """
    if method not in CONVERSION_RATIO_METHODS:
        raise ValueError(
            f"Unknown conversion ratio method '{method}'. "
            f"Expected one of {CONVERSION_RATIO_METHODS}."
        )
    consumed_array, produced_array = np.broadcast_arrays(
        np.asarray(consumed, dtype=float), np.asarray(produced, dtype=float)
    )
    valid = np.isfinite(consumed_array) & np.isfinite(produced_array) & (produced_array != 0.0)

    if method == "aggregate" and np.any(valid):
        aggregate = float(np.sum(consumed_array[valid]) / np.sum(produced_array[valid]))
        return np.full(consumed_array.shape, aggregate), np.full(consumed_array.shape, "aggregate")

    if np.any(valid):
        fallback = float(np.mean(consumed_array[valid] / produced_array[valid]))
        fallback_source = "measured"
    else:
        if fallback is None or not np.isfinite(fallback):
            raise ValueError("A fallback or at least one valid measured ratio is required.")
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


def demand_ratios(
    bus_demand: Mapping[str, ArrayLike],
    bus_commodities: Mapping[str, str],
    demand_bus: str | None,
) -> dict[str, NDArray[np.float64]]:
    """Return the plant-wide upstream requirement per unit of delivered demand.

    Demand on every non-demand bus is summed by commodity and divided by the demand
    entering the demand bus. Because each bus demand already multiplies the conversion
    ratios along every path, the result is the aggregated conversion ratio of each
    upstream commodity to the demanded commodity, for example electricity per unit of
    ammonia including both the electrolyzer and direct Haber-Bosch loads. Units are the
    upstream commodity rate units divided by the demand rate units. Timesteps without
    positive demand report zero.

    Args:
        bus_demand: Demand entering each dispatched bus.
        bus_commodities: Commodity carried by each bus name.
        demand_bus: Name of the bus that delivers the demand, or ``None``.

    Returns:
        Per-timestep ratios keyed by upstream commodity, sorted by commodity.

    Examples:
        >>> ratios = demand_ratios(
        ...     {
        ...         "ammonia:demand": [100.0],
        ...         "electricity:haber_bosch": [50.0],
        ...         "hydrogen:haber_bosch": [18.0],
        ...         "electricity:electrolyzer": [990.0],
        ...     },
        ...     {
        ...         "ammonia:demand": "ammonia",
        ...         "electricity:haber_bosch": "electricity",
        ...         "hydrogen:haber_bosch": "hydrogen",
        ...         "electricity:electrolyzer": "electricity",
        ...     },
        ...     "ammonia:demand",
        ... )
        >>> {commodity: ratio.tolist() for commodity, ratio in ratios.items()}
        {'electricity': [10.4], 'hydrogen': [0.18]}
    """
    if demand_bus is None or demand_bus not in bus_demand:
        return {}
    demand = np.asarray(bus_demand[demand_bus], dtype=float)

    totals: dict[str, NDArray[np.float64]] = {}
    for bus_name, profile in bus_demand.items():
        if bus_name == demand_bus:
            continue
        commodity = bus_commodities[bus_name]
        totals[commodity] = totals.get(commodity, 0.0) + np.asarray(profile, dtype=float)

    ratios = {}
    for commodity, total in sorted(totals.items()):
        ratio = np.zeros(np.broadcast_shapes(total.shape, demand.shape))
        np.divide(total, demand, out=ratio, where=demand > 0.0)
        ratios[commodity] = ratio
    return ratios
