"""Utilities for constructing OpenMDAO connections."""

import re

import networkx as nx
import openmdao.api as om


def create_technology_graph(technology_interconnections):
    """Create a directed graph from technology interconnection definitions.

    Args:
        technology_interconnections (list | set): Technology connection definitions.

    Returns:
        networkx.DiGraph: Directed graph with commodities stored on length-4 edges.
    """
    technology_graph = nx.DiGraph()

    def _as_commodity_list(commodity):
        if commodity is None:
            return []
        if isinstance(commodity, str):
            return [commodity]
        return list(commodity)

    for connection in technology_interconnections:
        source = connection[0]
        destination = connection[1]
        if len(connection) == 4:
            new_commodities = _as_commodity_list(connection[2])
            if technology_graph.has_edge(source, destination):
                connected_commodities = technology_graph.edges[source, destination].get("commodity")
                existing_commodities = _as_commodity_list(connected_commodities)
                technology_graph.add_edge(
                    source,
                    destination,
                    commodity=list(set(existing_commodities + new_commodities)),
                )
            else:
                technology_graph.add_edge(
                    source,
                    destination,
                    commodity=new_commodities,
                )
        else:
            technology_graph.add_edge(source, destination)

    return technology_graph


def split_indices_from_connected_parameter_definition(connected_parameter):
    """Parse parameter slices and create OpenMDAO source indices.

    Args:
        connected_parameter (list[str]): Source and destination parameter names, optionally
            containing slice specifications such as ``[0:8760]``.

    Returns:
        tuple: Parameter names with slice specifications removed and the corresponding
        OpenMDAO source indices, or ``None`` when no source indexing is needed.

    Raises:
        ValueError: If the destination slice starts at a nonzero index.
    """
    source_parameter, destination_parameter = connected_parameter

    def _extract_slice(parameter):
        match = re.search(r"\[(.*)\]", parameter)
        return None if match is None else match.group(1)

    def _to_indices(specification):
        if ":" in specification:
            return slice(
                *(int(part) if part.strip() else None for part in specification.split(":"))
            )
        return [int(part) for part in specification.split(",")]

    source_slice = _extract_slice(source_parameter)
    destination_slice = _extract_slice(destination_parameter)

    if source_slice == destination_slice:
        source_indices = None
    elif destination_slice is not None and source_slice is not None:
        if destination_slice.split(":")[0] not in ("", "0"):
            raise ValueError(
                "A non-zero start was provided for the slice for destination "
                f"parameter <{destination_parameter}>"
            )
        destination_length = int(destination_slice.split(":")[-1])
        parsed_source_indices = _to_indices(source_slice)
        if isinstance(parsed_source_indices, slice):
            parsed_source_indices = list(
                range(
                    parsed_source_indices.start or 0,
                    parsed_source_indices.stop,
                    parsed_source_indices.step or 1,
                )
            )

        repeats = -(-destination_length // len(parsed_source_indices))
        source_indices = om.slicer[(parsed_source_indices * repeats)[:destination_length]]
    else:
        source_indices = None if source_slice is None else om.slicer[_to_indices(source_slice)]

    parameter_names = [
        source_parameter.split("[")[0],
        destination_parameter.split("[")[0],
    ]
    return parameter_names, source_indices
