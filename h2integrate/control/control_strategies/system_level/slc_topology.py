"""Pure graph helpers for heterogeneous-commodity system-level control."""

from collections.abc import Mapping, Iterable

import networkx as nx


def find_commodity_suppliers(
    technology_graph: nx.DiGraph,
    tech_name: str,
    commodity: str,
    supplier_techs: Iterable[str] | None = None,
) -> tuple[str, ...]:
    """Find technologies that supply ``commodity`` to ``tech_name``.

    The graph is traversed backwards only across edges carrying the requested
    commodity. Traversal continues through a predecessor only if it also
    receives that commodity, which passes through combiners, splitters, and
    storage while stopping at a converter. If ``supplier_techs`` is provided,
    intermediate technologies outside that set are excluded from the result.

    Args:
        technology_graph: Directed technology graph with commodity lists on
            its edges.
        tech_name: Technology whose upstream suppliers are sought.
        commodity: Commodity to trace upstream.
        supplier_techs: Optional technology names to retain in the result.

    Returns:
        Sorted tuple of upstream technology names that supply ``commodity``.

    Examples:
        >>> graph = nx.DiGraph()
        >>> graph.add_edge("grid", "electrolyzer", commodity=["electricity"])
        >>> find_commodity_suppliers(graph, "electrolyzer", "electricity")
        ('grid',)
    """
    suppliers: set[str] = set()
    visited = {tech_name}

    def _receives_commodity(node: str) -> bool:
        return any(
            commodity in (edge_commodities or [])
            for _, _, edge_commodities in technology_graph.in_edges(node, data="commodity")
        )

    def _trace_back(current_tech: str) -> None:
        for predecessor in sorted(technology_graph.predecessors(current_tech)):
            if predecessor in visited:
                continue

            edge_commodities = technology_graph.edges[predecessor, current_tech].get(
                "commodity", []
            )
            if commodity not in (edge_commodities or []):
                continue

            visited.add(predecessor)
            suppliers.add(predecessor)
            if _receives_commodity(predecessor):
                _trace_back(predecessor)

    _trace_back(tech_name)
    if supplier_techs is not None:
        suppliers.intersection_update(supplier_techs)

    return tuple(sorted(suppliers))


def detect_commodity_converters(
    technology_graph: nx.DiGraph,
    input_techs: Iterable[str],
    produced_by_tech: Mapping[str, Iterable[str]],
) -> set[tuple[str, str, str]]:
    """Detect controller-managed technologies that convert commodities.

    A converter produces a commodity it does not itself consume, for example
    an electrolyzer converting electricity to hydrogen. Input and output
    commodities are taken from direct graph edges and ``produced_by_tech``.

    Args:
        technology_graph: Directed technology graph with commodity lists on
            its edges.
        input_techs: Technologies managed by the controller that may produce
            commodities.
        produced_by_tech: Mapping from technology names to their output
            commodities.

    Returns:
        Set of ``(input_commodity, technology, output_commodity)`` conversions.
    """
    converters = set()
    for tech_name in sorted(input_techs):
        produced_commodities = set(produced_by_tech.get(tech_name, ()))
        if not produced_commodities:
            continue

        consumed_commodities = set()
        for _, _, edge_commodities in technology_graph.in_edges(tech_name, data="commodity"):
            consumed_commodities.update(edge_commodities or [])

        for out_commodity in sorted(produced_commodities - consumed_commodities):
            for in_commodity in sorted(consumed_commodities - produced_commodities):
                converters.add((in_commodity, tech_name, out_commodity))

    return converters
