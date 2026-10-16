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


def check_dispatch_connections(
    technology_config, dispatch_connections, supported_models, technology_graph
):
    """Validate dispatch connections before OpenMDAO setup.

    Args:
        technology_config (dict): Technology declarations from the technology configuration.
        dispatch_connections (list | None): Technology/dispatching-technology name pairs.
        supported_models (dict): Registry of supported model classes.
        technology_graph (networkx.DiGraph): Graph created by
            :func:`create_technology_graph`.

    Returns:
        None: Returns when all dispatch connections are valid.

    Raises:
        ValueError: If a connection is malformed, extraneous, missing, or incorrect.
    """
    from h2integrate.control.control_strategies.pyomo_storage_controller_baseclass import (
        PyomoStorageControllerBaseClass,
    )

    technologies = technology_config.get("technologies", {})
    dispatch_connections = dispatch_connections or []
    invalid_connections = [c for c in dispatch_connections if len(c) != 2]
    if invalid_connections:
        raise ValueError(
            "Invalid tech to dispatching_tech_name connection(s): "
            f"{invalid_connections}. Each connection must contain exactly two technology names."
        )

    def has_pyomo_controller(tech_name):
        model_name = technologies.get(tech_name, {}).get("control_strategy", {}).get("model")
        model_class = supported_models.get(model_name)
        return model_class is not None and issubclass(model_class, PyomoStorageControllerBaseClass)

    def is_dispatch_controlled(tech_name):
        return "dispatch_rule_set" in technologies.get(tech_name, {}) or has_pyomo_controller(
            tech_name
        )

    invalid_dispatching_techs = sorted(
        {c[1] for c in dispatch_connections if not is_dispatch_controlled(c[1])}
    )
    if invalid_dispatching_techs:
        plural = len(invalid_dispatching_techs) > 1
        raise ValueError(
            "`tech_to_dispatch_connections` in the plant config references "
            f"{invalid_dispatching_techs}, but "
            f"{'these technologies do' if plural else 'this technology does'} not declare a "
            "`dispatch_rule_set` or use a `control_strategy` that subclasses "
            "`PyomoStorageControllerBaseClass`. This usually happens after switching a "
            "storage technology to an open-loop controller without removing the corresponding "
            f"entries for {invalid_dispatching_techs} from `tech_to_dispatch_connections`."
        )

    dispatch_rule_techs = sorted(
        name for name, info in technologies.items() if "dispatch_rule_set" in info
    )
    existing_pairs = {(c[0], c[1]) for c in dispatch_connections}
    missing_techs = []
    expected_by_tech = {}
    for tech_name in dispatch_rule_techs:
        if has_pyomo_controller(tech_name):
            required = {(tech_name, tech_name)}
        else:
            successors = (
                technology_graph.successors(tech_name) if tech_name in technology_graph else []
            )
            required = {
                (tech_name, successor)
                for successor in successors
                if is_dispatch_controlled(successor)
            }
        expected_by_tech[tech_name] = required
        if not required or not required.intersection(existing_pairs):
            missing_techs.append(tech_name)
    if missing_techs:
        plural = len(missing_techs) > 1
        expected = sorted(list(pair) for name in missing_techs for pair in expected_by_tech[name])
        raise ValueError(
            f"Technolog{'ies' if plural else 'y'} {missing_techs} declare a `dispatch_rule_set` "
            f"but {'are' if plural else 'is'} missing from (or incorrectly listed in) "
            f"`tech_to_dispatch_connections`. Based on `technology_interconnections`, "
            f"`tech_to_dispatch_connections` should include (at least): {expected}."
        )


def _check_legacy_commodity_connections(technology_interconnections):
    """Reject legacy length-3 commodity output/input connections."""
    for connection in technology_interconnections:
        if len(connection) != 3 or not isinstance(connection[2], list | tuple):
            continue
        if len(connection[2]) != 2 or not all(isinstance(p, str) for p in connection[2]):
            continue
        source_param, dest_param = (p.split("[", 1)[0] for p in connection[2])
        if not source_param.endswith("_out") or not dest_param.endswith("_in"):
            continue
        source_commodity = source_param[: -len("_out")]
        dest_commodity = dest_param[: -len("_in")]
        if source_commodity == dest_commodity:
            raise ValueError(
                f"Connection [{connection[0]!r}, {connection[1]!r}, {connection[2]!r}] passes "
                f"commodity {source_commodity!r} between technologies using a length-3 format. "
                f"Use a length-4 connection instead: [{connection[0]!r}, {connection[1]!r}, "
                f"{source_commodity!r}, '<transport_tech>']."
            )


def _commodity_topology(technology_graph, classifiers):
    in_degrees, inputs, outputs = {}, {}, {}
    for source, destination, commodities in technology_graph.edges(data="commodity"):
        if not commodities:
            continue
        in_degrees[destination] = in_degrees.get(destination, 0) + 1
        for commodity in commodities:
            inputs.setdefault(destination, {})[commodity] = (
                inputs.setdefault(destination, {}).get(commodity, 0) + 1
            )
            if classifiers.get(destination) != "demand":
                outputs.setdefault(source, {})[commodity] = (
                    outputs.setdefault(source, {}).get(commodity, 0) + 1
                )
    return in_degrees, inputs, outputs


def _resolves_to_real_consumer(node, commodity, technology_graph, classifiers, visited):
    """Follow a chain of demand-classified components to see if they lead to a real consumer."""
    if classifiers.get(node) != "demand":
        return True
    if node in visited:
        return False
    visited.add(node)
    for _, destination, commodities in technology_graph.out_edges(node, data="commodity"):
        if commodity in (commodities or []) and _resolves_to_real_consumer(
            destination, commodity, technology_graph, classifiers, visited
        ):
            return True
    return False


def _check_demand_double_count(tech, commodity, count, technology_graph, classifiers):
    """Raise if a source double-counts a commodity via a direct path and a demand chain.

    Demand-classified components are not counted as destinations by
    :func:`_commodity_topology`, but a source that sends a commodity directly to a real
    consumer *and* to a demand component whose chain also resolves to a real consumer is
    effectively sending the commodity to two real consumers.
    """
    demand_destinations = {
        destination
        for _, destination, commodities in technology_graph.out_edges(tech, data="commodity")
        if classifiers.get(destination) == "demand" and commodity in (commodities or [])
    }
    resolved_demand_paths = sum(
        1
        for destination in demand_destinations
        if _resolves_to_real_consumer(destination, commodity, technology_graph, classifiers, {tech})
    )
    if count + resolved_demand_paths > 1:
        raise ValueError(
            f"Technology {tech!r} sends commodity {commodity!r} both directly to a real "
            "consumer and through a demand-classified component whose chain also resolves "
            "to a real consumer, which would double-count the commodity stream. Consider "
            "using a splitter component or removing the redundant connection."
        )


def validate_technology_interconnections(
    technology_interconnections, technology_graph, tech_control_classifiers
):
    """Validate technology topology after OpenMDAO setup.

    Args:
        technology_interconnections (list): Configured technology connections.
        technology_graph (networkx.DiGraph): Graph created by
            :func:`create_technology_graph`.
        tech_control_classifiers (dict): Classifiers created by
            ``H2IntegrateModel.create_technology_models()``.

    Returns:
        None: Returns when all topology rules pass.

    Raises:
        ValueError: If a legacy connection or commodity topology rule is invalid.
    """
    _check_legacy_commodity_connections(technology_interconnections)
    in_degrees, inputs, outputs = _commodity_topology(technology_graph, tech_control_classifiers)
    # Maps a storage-upstream tech to the specific commodities it sends to storage; only
    # those commodities are exempt from the per-tech output-multiplicity check below, so
    # an unrelated commodity sent by the same tech is still validated normally.
    storage_upstream_commodities = {}
    for tech, classifier in tech_control_classifiers.items():
        if classifier != "storage":
            continue
        if in_degrees.get(tech, 0) == 0:
            raise ValueError(
                f"Storage technology {tech!r} has no input connections in the technology graph "
                "but should have at least 1."
            )
        for commodity, count in inputs.get(tech, {}).items():
            if count > 1:
                raise ValueError(
                    f"Storage technology {tech!r} receives commodity {commodity!r} from {count} "
                    "sources in the technology graph but should receive it from at most 1."
                )
        for commodity, count in outputs.get(tech, {}).items():
            if count > 1:
                raise ValueError(
                    f"Storage technology {tech!r} has {count} output connection(s) for commodity "
                    f"{commodity!r} but should have at most 1."
                )
        for upstream in technology_graph.predecessors(tech):
            commodities = technology_graph.edges[upstream, tech].get("commodity")
            if not commodities:
                continue
            for commodity in commodities:
                storage_upstream_commodities.setdefault(upstream, set()).add(commodity)
                count = outputs.get(upstream, {}).get(commodity, 0)
                if count > 2:
                    raise ValueError(
                        f"Technology {upstream!r} feeds storage technology {tech!r} but has "
                        f"{count} output connection(s). It should connect only to {tech!r} and "
                        "a combiner (at most 2 output streams)."
                    )
    for tech in set(inputs) | set(outputs):
        if tech_control_classifiers.get(tech) in ("splitter", "combiner", "storage"):
            continue
        for commodity, count in inputs.get(tech, {}).items():
            if count > 1:
                raise ValueError(
                    f"Technology {tech!r} receives commodity {commodity!r} from {count} sources "
                    "in the technology graph but should receive it from at most 1. Consider "
                    "using a combiner component."
                )
        exempt_commodities = storage_upstream_commodities.get(tech, set())
        for commodity, count in outputs.get(tech, {}).items():
            if commodity in exempt_commodities:
                continue
            if count > 1:
                raise ValueError(
                    f"Technology {tech!r} sends commodity {commodity!r} to {count} destinations "
                    "in the technology graph but should send it to at most 1. Consider using "
                    "a splitter component."
                )
            _check_demand_double_count(
                tech, commodity, count, technology_graph, tech_control_classifiers
            )


def _technology_io_parameters(prob, technology_config, technology_graph):
    """Collect OpenMDAO I/O names for technologies after setup."""
    technology_io = {}
    for tech_name in technology_graph.nodes():
        tech_info = technology_config["technologies"].get(tech_name, {})
        parameters = set()
        for model_type in ("performance_model", "finance_model", "cost_model", "control_strategy"):
            if not tech_info or model_type not in tech_info:
                continue
            model_name = tech_info[model_type]["model"]
            group = getattr(
                prob.model.plant,
                f"{tech_name}_source" if model_name == "FeedstockPerformanceModel" else tech_name,
            )
            if model_name not in ("FeedstockCostModel", "FeedstockPerformanceModel"):
                group = getattr(group, model_name, None)
                if group is None:
                    continue
            parameters.update(key.split(".")[-1] for key in group.get_io_metadata())
        technology_io[tech_name] = parameters
    return technology_io


def check_technology_connections(prob, technology_config, technology_graph, plant_config_path):
    """Check configured commodity endpoints after ``Problem.setup()``.

    Args:
        prob (openmdao.api.Problem): Set-up OpenMDAO problem.
        technology_config (dict): Technology declarations from the technology configuration.
        technology_graph (networkx.DiGraph): Graph created by
            :func:`create_technology_graph`.
        plant_config_path (Path | None): Plant configuration path for error guidance.

    Returns:
        None: Returns when every configured commodity has valid endpoints.

    Raises:
        ValueError: If a source lacks an output or a destination lacks an input.
    """
    io = _technology_io_parameters(prob, technology_config, technology_graph)
    invalid_outputs, invalid_inputs = set(), set()
    for source, destination, commodities in technology_graph.edges(data="commodity"):
        for commodity in commodities or []:
            if f"{commodity}_out" not in io[source] and not any(
                re.fullmatch(rf"{commodity}_out\d", p) for p in io[source]
            ):
                invalid_outputs.add((source, commodity))
            if f"{commodity}_in" not in io[destination] and not any(
                re.fullmatch(rf"{commodity}_in\d", p) for p in io[destination]
            ):
                invalid_inputs.add((destination, commodity))
    if invalid_outputs or invalid_inputs:
        parts = []
        if invalid_outputs:
            parts.append(
                "The following technologies do not output their specified commodity: "
                + ", ".join(f"`{t}` -> `{c}`" for t, c in sorted(invalid_outputs))
                + "."
            )
        if invalid_inputs:
            parts.append(
                "The following technologies do not accept their specified input commodity: "
                + ", ".join(f"`{t}` <- `{c}`" for t, c in sorted(invalid_inputs))
                + "."
            )
        parts.append(f"Update `technology_interconnections` in {plant_config_path}.")
        raise ValueError("\n".join(parts))
