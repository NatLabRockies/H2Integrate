"""Pure graph helpers for heterogeneous-commodity system-level control."""

import warnings
from collections import defaultdict
from collections.abc import Mapping, Iterable

import attrs
import networkx as nx


# Control classifiers whose technologies produce a commodity that the controller dispatches.
CONTROLLED_CLASSIFIERS = frozenset({"fixed", "flexible", "dispatchable", "storage"})
# Classifiers that supply a commodity to the system (controlled technologies and feedstocks).
SUPPLIER_CLASSIFIERS = CONTROLLED_CLASSIFIERS | {"feedstock"}


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


@attrs.frozen
class SupplyBus:
    """A set of producers and consumers that share one physical stream of a commodity.

    A bus is one weakly connected component of the technology graph restricted to the
    edges that carry a single commodity. Combiners, splitters, and storage keep their
    neighbors on the same bus, while two producers of the same commodity that never meet
    (for example a grid wired only to a Haber-Bosch loop and wind wired only to an
    electrolyzer) end up on different buses.

    Attributes:
        name: ``"{commodity}:{consumer1}+{consumer2}"``. Consumers are sorted, so the
            name does not depend on the order of the technology interconnections.
        commodity: Commodity carried by the bus.
        producers: Sorted technologies that produce ``commodity`` onto the bus
            (controlled technologies and feedstocks).
        consumers: Sorted converters that consume ``commodity`` from the bus, plus the
            demand technology when ``commodity`` is the demand commodity.
        members: Sorted names of every technology on the bus, including combiners
            and splitters.
    """

    name: str
    commodity: str
    producers: tuple[str, ...]
    consumers: tuple[str, ...]
    members: tuple[str, ...]


@attrs.frozen(order=True)
class ConversionLink:
    """A converter translating demand on its output bus into demand on its input bus.

    Attributes:
        in_commodity: Commodity the converter consumes.
        tech: Converter technology name.
        out_commodity: Commodity the converter produces.
        in_bus: Name of the bus that supplies ``in_commodity`` to ``tech``.
        out_bus: Name of the bus that ``tech`` supplies with ``out_commodity``.
        suppliers: Sorted controlled and feedstock technologies that supply
            ``in_commodity`` to ``tech`` along edges carrying that commodity.
    """

    in_commodity: str
    tech: str
    out_commodity: str
    in_bus: str
    out_bus: str
    suppliers: tuple[str, ...] = ()


@attrs.frozen
class SplitterNode:
    """A splitter on a dispatched bus whose priority allocation the controller sets.

    Attributes:
        name: Splitter technology name.
        commodity: Commodity the splitter divides.
        bus: Name of the bus the splitter sits on.
        priority_consumers: Sorted consumers on the bus that are reachable from the
            splitter's first output (out1), tracing through combiners, splitters,
            and storage.
    """

    name: str
    commodity: str
    bus: str
    priority_consumers: tuple[str, ...]


@attrs.frozen
class DispatchTopology:
    """Setup-time description of how demand propagates across supply buses.

    Built once by ``build_dispatch_topology`` from the technology graph alone. Whether a
    conversion ratio is known does not change the order, so no graph work is needed while
    the controller computes.

    Attributes:
        demand_bus: Name of the bus that carries the demand technology's commodity, or
            ``None`` when the demand technology has no incoming edge for that commodity.
        buses: Every supply bus, keyed by name.
        links: Sorted conversion links with both buses present.
        dispatch_order: Names of the buses that receive set points, demand bus first.
            A bus is dispatched when demand reaches it and at least one controlled
            technology produces onto it. Buses supplied only by feedstocks never
            receive set points.
        splitters: Splitters on dispatched buses, sorted by name.
    """

    demand_bus: str | None
    buses: dict[str, SupplyBus]
    links: tuple[ConversionLink, ...]
    dispatch_order: tuple[str, ...]
    splitters: tuple[SplitterNode, ...] = ()

    @property
    def dispatch_links(self) -> tuple[ConversionLink, ...]:
        """Links whose input and output buses are both dispatched."""
        dispatched = set(self.dispatch_order)
        return tuple(
            link for link in self.links if link.in_bus in dispatched and link.out_bus in dispatched
        )

    @property
    def consumption_signals(self) -> tuple[tuple[str, str], ...]:
        """Sorted unique ``(converter, input commodity)`` pairs that need a measured draw.

        A converter with several outputs appears once per input commodity.
        """
        return tuple(sorted({(link.tech, link.in_commodity) for link in self.dispatch_links}))

    def describe(self) -> str:
        """Return a readable multi-line summary for debugging, docs, and tests."""
        lines = [f"Demand bus: {self.demand_bus}", "Dispatch order:"]
        for index, bus_name in enumerate(self.dispatch_order, start=1):
            bus = self.buses[bus_name]
            lines.append(
                f"  {index}. {bus_name} (producers: {', '.join(bus.producers)}; "
                f"consumers: {', '.join(bus.consumers)})"
            )

        not_dispatched = sorted(set(self.buses) - set(self.dispatch_order))
        if not_dispatched:
            lines.append(f"Not dispatched: {', '.join(not_dispatched)}")

        if self.dispatch_links:
            lines.append("Conversion links (output bus -> input bus):")
            lines.extend(
                f"  {link.tech}: {link.out_bus} -> {link.in_bus}" for link in self.dispatch_links
            )

        if self.splitters:
            lines.append("Splitters:")
            lines.extend(
                f"  {splitter.name} on {splitter.bus} "
                f"(priority consumers: {', '.join(splitter.priority_consumers)})"
                for splitter in self.splitters
            )

        return "\n".join(lines)


def _commodity_subgraph(technology_graph: nx.DiGraph, commodity: str) -> nx.DiGraph:
    """Return the view of ``technology_graph`` with only the edges carrying ``commodity``."""
    edges = [
        (source, destination)
        for source, destination, edge_commodities in technology_graph.edges(data="commodity")
        if commodity in (edge_commodities or [])
    ]
    return technology_graph.edge_subgraph(edges)


def build_supply_buses(
    technology_graph: nx.DiGraph,
    produced_by_tech: Mapping[str, Iterable[str]],
    converters: Iterable[tuple[str, str, str]],
    demand_tech: str,
    demand_commodity: str,
) -> dict[str, SupplyBus]:
    """Group the technology graph into supply buses, one per commodity and consumer set.

    For each commodity, the graph is restricted to the edges that carry it and each weakly
    connected component becomes a bus. This merges consumers that share a splitter, since
    their demand sums, and separates independent supply paths. Components without a
    consumer are dropped because nothing draws from them.

    Args:
        technology_graph: Directed technology graph with commodity lists on its edges.
        produced_by_tech: Mapping from supplier technology names to the commodities they
            produce.
        converters: ``(input_commodity, technology, output_commodity)`` conversions, as
            returned by ``detect_commodity_converters``.
        demand_tech: Name of the demand technology.
        demand_commodity: Commodity the demand technology consumes.

    Returns:
        Supply buses keyed by name and sorted by name.

    Examples:
        >>> graph = nx.DiGraph()
        >>> graph.add_edge("grid", "haber_bosch", commodity=["electricity"])
        >>> graph.add_edge("wind", "electrolyzer", commodity=["electricity"])
        >>> converters = [
        ...     ("electricity", "electrolyzer", "hydrogen"),
        ...     ("electricity", "haber_bosch", "ammonia"),
        ... ]
        >>> produced_by_tech = {"grid": {"electricity"}, "wind": {"electricity"}}
        >>> sorted(build_supply_buses(graph, produced_by_tech, converters, "demand", "ammonia"))
        ['electricity:electrolyzer', 'electricity:haber_bosch']
    """
    consumers_by_commodity = defaultdict(set)
    for in_commodity, tech_name, _out_commodity in converters:
        consumers_by_commodity[in_commodity].add(tech_name)
    consumers_by_commodity[demand_commodity].add(demand_tech)

    commodities = {
        commodity
        for _, _, edge_commodities in technology_graph.edges(data="commodity")
        for commodity in edge_commodities or []
    }

    buses = {}
    for commodity in sorted(commodities):
        commodity_graph = _commodity_subgraph(technology_graph, commodity)
        for component in nx.weakly_connected_components(commodity_graph):
            consumers = tuple(sorted(component & consumers_by_commodity[commodity]))
            if not consumers:
                continue

            name = f"{commodity}:{'+'.join(consumers)}"
            producers = tuple(
                sorted(tech for tech in component if commodity in produced_by_tech.get(tech, ()))
            )
            buses[name] = SupplyBus(
                name=name,
                commodity=commodity,
                producers=producers,
                consumers=consumers,
                members=tuple(sorted(component)),
            )

    return dict(sorted(buses.items()))


def _warn_if_partial_overlap(
    technology_graph: nx.DiGraph, bus: SupplyBus, controlled_techs: set[str]
) -> None:
    """Warn when a controlled producer cannot reach every consumer on ``bus``."""
    commodity_graph = _commodity_subgraph(technology_graph, bus.commodity)
    unreachable = [
        f"{producer} -> {consumer}"
        for producer in bus.producers
        if producer in controlled_techs
        for consumer in bus.consumers
        if not nx.has_path(commodity_graph, producer, consumer)
    ]
    if unreachable:
        warnings.warn(
            f"Supply bus '{bus.name}' mixes producers that cannot all reach every consumer "
            f"(no {bus.commodity} path for: {', '.join(unreachable)}). System-level control "
            "dispatches the bus as one pool, so a producer may be given demand it cannot "
            "physically serve.",
            UserWarning,
            stacklevel=3,
        )


def _find_splitters(
    technology_graph: nx.DiGraph,
    tech_control_classifiers: Mapping[str, str],
    buses: Mapping[str, SupplyBus],
    bus_of: Mapping[tuple[str, str], str],
    dispatched: set[str],
) -> tuple[SplitterNode, ...]:
    """Find splitters on dispatched buses and the consumers behind their first output."""
    splitters = []
    for tech_name in sorted(technology_graph.nodes):
        if tech_control_classifiers.get(tech_name) != "splitter":
            continue

        # The first connection out of a splitter is its priority output (out1).
        first_output = None
        for destination in technology_graph.successors(tech_name):
            edge_commodities = technology_graph.edges[tech_name, destination].get("commodity")
            if edge_commodities:
                first_output = (destination, edge_commodities[0])
                break
        if first_output is None:
            continue

        first_destination, commodity = first_output
        bus_name = bus_of.get((commodity, tech_name))
        if bus_name not in dispatched:
            continue

        commodity_graph = _commodity_subgraph(technology_graph, commodity)
        reachable = {first_destination} | nx.descendants(commodity_graph, first_destination)
        splitters.append(
            SplitterNode(
                name=tech_name,
                commodity=commodity,
                bus=bus_name,
                priority_consumers=tuple(sorted(reachable & set(buses[bus_name].consumers))),
            )
        )

    return tuple(splitters)


def build_dispatch_topology(
    technology_graph: nx.DiGraph,
    tech_control_classifiers: Mapping[str, str],
    tech_to_commodity: Iterable[tuple[str, str]],
    demand_tech: str,
    demand_commodity: str,
) -> DispatchTopology:
    """Build the setup-time supply buses, conversion links, and dispatch order.

    Demand starts on the demand bus. Each conversion link translates demand on the bus its
    converter supplies into demand on the bus the converter draws from, so the buses are
    ordered topologically from the demand bus outward and every contribution to a bus is
    known before the bus is dispatched. Ties are broken alphabetically, which makes the
    order independent of the order of the technology interconnections.

    Args:
        technology_graph: Directed technology graph with commodity lists on its edges.
        tech_control_classifiers: Mapping from technology name to control classifier.
        tech_to_commodity: ``(technology, commodity)`` pairs for the technologies the
            controller manages or reads (fixed, flexible, dispatchable, storage, feedstock).
        demand_tech: Name of the demand technology.
        demand_commodity: Commodity the demand technology consumes.

    Returns:
        The dispatch topology.

    Raises:
        ValueError: If the conversions that connect to the demand bus form a cycle, for
            example a fuel cell whose electricity returns to its own electrolyzer's bus.

    Warns:
        UserWarning: If a dispatched bus holds a controlled producer that has no path to
            one of the bus's consumers. The bus is still dispatched as one pool.

    Examples:
        >>> graph = nx.DiGraph()
        >>> graph.add_edge("wind", "electrolyzer", commodity=["electricity"])
        >>> graph.add_edge("electrolyzer", "demand", commodity=["hydrogen"])
        >>> topology = build_dispatch_topology(
        ...     graph,
        ...     {"wind": "flexible", "electrolyzer": "dispatchable"},
        ...     {("wind", "electricity"), ("electrolyzer", "hydrogen")},
        ...     "demand",
        ...     "hydrogen",
        ... )
        >>> topology.dispatch_order
        ('hydrogen:demand', 'electricity:electrolyzer')
    """
    controlled_techs = {
        tech
        for tech, classifier in tech_control_classifiers.items()
        if classifier in CONTROLLED_CLASSIFIERS
    }
    supplier_techs = {
        tech
        for tech, classifier in tech_control_classifiers.items()
        if classifier in SUPPLIER_CLASSIFIERS
    }
    produced_by_tech = defaultdict(set)
    for tech_name, commodity in tech_to_commodity:
        if tech_name in supplier_techs:
            produced_by_tech[tech_name].add(commodity)

    converters = sorted(
        detect_commodity_converters(technology_graph, controlled_techs, produced_by_tech)
    )
    buses = build_supply_buses(
        technology_graph, produced_by_tech, converters, demand_tech, demand_commodity
    )
    bus_of = {(bus.commodity, member): bus.name for bus in buses.values() for member in bus.members}

    links = []
    for in_commodity, tech_name, out_commodity in converters:
        in_bus = bus_of.get((in_commodity, tech_name))
        out_bus = bus_of.get((out_commodity, tech_name))
        if in_bus is None or out_bus is None:
            # An output that nothing consumes can never carry demand back to the inputs.
            continue
        links.append(
            ConversionLink(
                in_commodity=in_commodity,
                tech=tech_name,
                out_commodity=out_commodity,
                in_bus=in_bus,
                out_bus=out_bus,
                suppliers=find_commodity_suppliers(
                    technology_graph, tech_name, in_commodity, supplier_techs=supplier_techs
                ),
            )
        )
    links = tuple(sorted(links))

    demand_bus = next(
        (
            bus.name
            for bus in buses.values()
            if bus.commodity == demand_commodity and demand_tech in bus.consumers
        ),
        None,
    )

    dispatch_order: tuple[str, ...] = ()
    if demand_bus is not None:
        bus_graph = nx.DiGraph()
        bus_graph.add_nodes_from(buses)
        bus_graph.add_edges_from((link.out_bus, link.in_bus) for link in links)
        reachable_graph = bus_graph.subgraph({demand_bus} | nx.descendants(bus_graph, demand_bus))
        try:
            bus_order = list(nx.lexicographical_topological_sort(reachable_graph))
        except nx.NetworkXUnfeasible:
            cycle = nx.find_cycle(reachable_graph)
            cycle_buses = " -> ".join([edge[0] for edge in cycle] + [cycle[0][0]])
            cycle_techs = sorted(
                {link.tech for link in links if (link.out_bus, link.in_bus) in set(cycle)}
            )
            msg = (
                "System-level control needs an acyclic conversion topology, but the supply "
                f"buses form a cycle: {cycle_buses}. Technologies converting around the cycle: "
                f"{', '.join(cycle_techs)}."
            )
            raise ValueError(msg) from None

        dispatch_order = tuple(
            bus_name
            for bus_name in bus_order
            if controlled_techs.intersection(buses[bus_name].producers)
        )

    for bus_name in dispatch_order:
        _warn_if_partial_overlap(technology_graph, buses[bus_name], controlled_techs)

    return DispatchTopology(
        demand_bus=demand_bus,
        buses=buses,
        links=links,
        dispatch_order=dispatch_order,
        splitters=_find_splitters(
            technology_graph, tech_control_classifiers, buses, bus_of, set(dispatch_order)
        ),
    )
