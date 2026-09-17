"""Configuration and OpenMDAO connection checks used by H2IntegrateModel."""

import re


def check_dispatch_connections(
    technology_config,
    dispatch_connections,
    supported_models,
    technology_graph,
):
    """Validate dispatch connections against technology control declarations.

    Args:
        technology_config (dict): Technology configuration containing the technologies.
        dispatch_connections (list): Pairs of technology and dispatching technology names.
        supported_models (dict): Registry of supported model classes.
        technology_graph (networkx.DiGraph): Directed technology connection graph.

    Raises:
        ValueError: If a connection is malformed, extraneous, missing, or incorrect.
    """
    from h2integrate.control.control_strategies.pyomo_storage_controller_baseclass import (
        PyomoStorageControllerBaseClass,
    )

    technologies = technology_config.get("technologies", {})
    dispatch_connections = dispatch_connections or []
    invalid_connections = [
        connection for connection in dispatch_connections if len(connection) != 2
    ]
    if invalid_connections:
        raise ValueError(
            "Invalid tech to dispatching_tech_name connection(s): "
            f"{invalid_connections}. Each connection must contain exactly two technology names."
        )

    def _has_pyomo_storage_controller(tech_name):
        control_model_name = (
            technologies.get(tech_name, {}).get("control_strategy", {}).get("model")
        )
        if control_model_name is None:
            return False
        control_cls = supported_models.get(control_model_name)
        return control_cls is not None and issubclass(control_cls, PyomoStorageControllerBaseClass)

    def _is_dispatch_controlled(tech_name):
        return "dispatch_rule_set" in technologies.get(
            tech_name, {}
        ) or _has_pyomo_storage_controller(tech_name)

    invalid_dispatching_techs = sorted(
        {
            connection[1]
            for connection in dispatch_connections
            if not _is_dispatch_controlled(connection[1])
        }
    )
    if invalid_dispatching_techs:
        plural = len(invalid_dispatching_techs) > 1
        msg = (
            "`tech_to_dispatch_connections` in the plant config references "
            f"{invalid_dispatching_techs}, but "
            f"{'these technologies do' if plural else 'this technology does'} not "
            "declare a `dispatch_rule_set` or use a `control_strategy` that subclasses "
            "`PyomoStorageControllerBaseClass`. This usually happens after switching a "
            "storage technology to an open-loop controller without removing the "
            f"corresponding entries for {invalid_dispatching_techs} from "
            "`tech_to_dispatch_connections` in the plant config."
        )
        raise ValueError(msg)

    dispatch_rule_techs = sorted(
        tech_name
        for tech_name, tech_info in technologies.items()
        if "dispatch_rule_set" in tech_info
    )
    if not dispatch_rule_techs:
        return

    existing_pairs = {(connection[0], connection[1]) for connection in dispatch_connections}
    missing_techs = []
    required_pairs_by_tech = {}
    for tech_name in dispatch_rule_techs:
        if _has_pyomo_storage_controller(tech_name):
            required_pairs = {(tech_name, tech_name)}
        else:
            successors = (
                technology_graph.successors(tech_name) if tech_name in technology_graph else []
            )
            required_pairs = {
                (tech_name, successor)
                for successor in successors
                if _is_dispatch_controlled(successor)
            }
        required_pairs_by_tech[tech_name] = required_pairs
        if not required_pairs or not required_pairs.intersection(existing_pairs):
            missing_techs.append(tech_name)

    if missing_techs:
        plural = len(missing_techs) > 1
        expected_connections = sorted(
            list(pair) for tech_name in missing_techs for pair in required_pairs_by_tech[tech_name]
        )
        msg = (
            f"Technolog{'ies' if plural else 'y'} {missing_techs} declare a "
            "`dispatch_rule_set` but "
            f"{'are' if plural else 'is'} missing from (or incorrectly listed in) "
            "`tech_to_dispatch_connections` in the plant config. Based on "
            "`technology_interconnections`, `tech_to_dispatch_connections` should include "
            f"(at least): {expected_connections}. If a `dispatch_rule_set` is no longer "
            "needed (e.g. after switching a storage technology to an open-loop controller), "
            "remove it instead of adding a connection."
        )
        raise ValueError(msg)


def _check_legacy_commodity_connections(technology_interconnections):
    """Reject length-3 connections that should use explicit commodity transport."""
    for connection in technology_interconnections:
        if len(connection) != 3:
            continue
        connected_parameter = connection[2]
        if not isinstance(connected_parameter, list | tuple) or len(connected_parameter) != 2:
            continue
        source_param, dest_param = connected_parameter
        if not isinstance(source_param, str) or not isinstance(dest_param, str):
            continue
        source_param_base = source_param.split("[", 1)[0]
        dest_param_base = dest_param.split("[", 1)[0]
        if not source_param_base.endswith("_out") or not dest_param_base.endswith("_in"):
            continue
        commodity_from_source = source_param_base[: -len("_out")]
        commodity_from_dest = dest_param_base[: -len("_in")]
        if commodity_from_source != commodity_from_dest:
            continue
        source_tech, dest_tech = connection[0], connection[1]
        raise ValueError(
            f"Connection [{source_tech!r}, {dest_tech!r}, "
            f"[{source_param!r}, {dest_param!r}]] passes commodity "
            f"{commodity_from_source!r} between technologies using a "
            f"length-3 format. Use a length-4 connection instead: "
            f"[{source_tech!r}, {dest_tech!r}, {commodity_from_source!r}, "
            f"'<transport_tech>']. You can use "
            f"'GenericTransporterPerformanceModel' to transport "
            f"{commodity_from_source!r}."
        )


def _collect_commodity_topology(technology_graph, tech_control_classifiers):
    """Collect edge and per-commodity counts for length-4 connections."""
    in_degrees = {}
    in_commodity_sources = {}
    out_commodity_destinations = {}
    for source, destination, commodities in technology_graph.edges(data="commodity"):
        if not commodities:
            continue
        in_degrees[destination] = in_degrees.get(destination, 0) + 1
        for commodity in commodities:
            inputs = in_commodity_sources.setdefault(destination, {})
            inputs[commodity] = inputs.get(commodity, 0) + 1
            if tech_control_classifiers.get(destination) != "demand":
                outputs = out_commodity_destinations.setdefault(source, {})
                outputs[commodity] = outputs.get(commodity, 0) + 1
    return in_degrees, in_commodity_sources, out_commodity_destinations


def _check_storage_topology(
    technology_graph,
    tech_control_classifiers,
    in_degrees,
    in_commodity_sources,
    out_commodity_destinations,
):
    """Validate storage streams and return their directly upstream technologies."""
    storage_upstream_techs = set()
    storage_techs = [
        tech for tech, classifier in tech_control_classifiers.items() if classifier == "storage"
    ]
    for storage_tech in storage_techs:
        if in_degrees.get(storage_tech, 0) == 0:
            raise ValueError(
                f"Storage technology {storage_tech!r} has no input connections in "
                "the technology graph but should have at least 1."
            )
        for commodity, n_sources in in_commodity_sources.get(storage_tech, {}).items():
            if n_sources > 1:
                raise ValueError(
                    f"Storage technology {storage_tech!r} receives commodity "
                    f"{commodity!r} from {n_sources} sources in the technology graph "
                    "but should receive it from at most 1."
                )
        for commodity, n_outputs in out_commodity_destinations.get(storage_tech, {}).items():
            if n_outputs > 1:
                raise ValueError(
                    f"Storage technology {storage_tech!r} has {n_outputs} output connection(s) "
                    f"for commodity {commodity!r} but should have at most 1."
                )

        upstream_techs = [
            tech
            for tech in technology_graph.predecessors(storage_tech)
            if technology_graph.edges[tech, storage_tech].get("commodity")
        ]
        for upstream_tech in upstream_techs:
            storage_upstream_techs.add(upstream_tech)
            commodities = technology_graph.edges[upstream_tech, storage_tech]["commodity"]
            for commodity in commodities:
                n_outputs = out_commodity_destinations.get(upstream_tech, {}).get(commodity, 0)
                if n_outputs > 2:
                    raise ValueError(
                        f"Technology {upstream_tech!r} feeds storage technology "
                        f"{storage_tech!r} but has {n_outputs} output connection(s). "
                        f"It should connect only to {storage_tech!r} and a combiner "
                        "(at most 2 output streams)."
                    )
    return storage_upstream_techs


def _check_general_commodity_topology(
    tech_control_classifiers,
    in_commodity_sources,
    out_commodity_destinations,
    storage_upstream_techs,
):
    """Validate per-commodity source and destination counts for general technologies."""
    all_techs = set(in_commodity_sources) | set(out_commodity_destinations)
    for tech in all_techs:
        classifier = tech_control_classifiers.get(tech)
        if classifier in ("splitter", "combiner", "storage"):
            continue
        for commodity, n_sources in in_commodity_sources.get(tech, {}).items():
            if n_sources > 1:
                raise ValueError(
                    f"Technology {tech!r} receives commodity {commodity!r} from "
                    f"{n_sources} sources in the technology graph but should receive "
                    "it from at most 1. Consider using a combiner component."
                )
        if tech in storage_upstream_techs:
            continue
        for commodity, n_destinations in out_commodity_destinations.get(tech, {}).items():
            if n_destinations > 1:
                raise ValueError(
                    f"Technology {tech!r} sends commodity {commodity!r} to "
                    f"{n_destinations} destinations in the technology graph but should "
                    "send it to at most 1. Consider using a splitter component."
                )


def _demand_reaches_competing_consumer(
    demand_tech,
    technology_graph,
    tech_control_classifiers,
):
    """Return whether a demand chain reaches a non-storage real consumer."""
    visited = set()
    stack = [demand_tech]
    while stack:
        node = stack.pop()
        if node in visited:
            continue
        visited.add(node)
        for _, destination, commodities in technology_graph.out_edges(node, data="commodity"):
            if not commodities:
                continue
            classifier = tech_control_classifiers.get(destination)
            if classifier == "demand":
                stack.append(destination)
            elif classifier != "storage":
                return True
    return False


def _check_demand_paths(technology_graph, tech_control_classifiers):
    """Prevent commodity double-counting through demand component paths."""
    source_commodity_destinations = {}
    for source, destination, commodities in technology_graph.edges(data="commodity"):
        if not commodities:
            continue
        for commodity in commodities:
            source_commodity_destinations.setdefault((source, commodity), []).append(destination)

    for (source, commodity), destinations in source_commodity_destinations.items():
        direct_real_destinations = [
            destination
            for destination in destinations
            if tech_control_classifiers.get(destination) != "demand"
        ]
        outputting_demand_destinations = [
            destination
            for destination in destinations
            if tech_control_classifiers.get(destination) == "demand"
            and _demand_reaches_competing_consumer(
                destination, technology_graph, tech_control_classifiers
            )
        ]
        if direct_real_destinations and outputting_demand_destinations:
            raise ValueError(
                f"Technology {source!r} sends commodity {commodity!r} both directly "
                f"to {direct_real_destinations} and to demand component(s) "
                f"{outputting_demand_destinations} that re-emit the commodity to real "
                "consumers. This would double-count the commodity flow. Either route "
                f"all {commodity!r} from {source!r} through the demand component, or "
                f"connect the downstream consumers directly to {source!r} instead."
            )


def validate_technology_interconnections(
    technology_interconnections,
    technology_graph,
    tech_control_classifiers,
):
    """Validate technology interconnections and commodity topology.

    Args:
        technology_interconnections (list): Technology connection definitions.
        technology_graph (networkx.DiGraph): Directed technology connection graph.
        tech_control_classifiers (dict): Control classifier for each technology.

    Raises:
        ValueError: If an interconnection violates a topology rule.
    """
    _check_legacy_commodity_connections(technology_interconnections)
    topology = _collect_commodity_topology(technology_graph, tech_control_classifiers)
    storage_upstream_techs = _check_storage_topology(
        technology_graph,
        tech_control_classifiers,
        *topology,
    )
    _check_general_commodity_topology(
        tech_control_classifiers,
        topology[1],
        topology[2],
        storage_upstream_techs,
    )
    _check_demand_paths(technology_graph, tech_control_classifiers)


def _technology_io_parameters(prob, technology_config, technology_graph):
    """Collect OpenMDAO input and output names for technologies in the graph."""
    technology_io = {}
    for tech_name in technology_graph.nodes():
        tech_info = technology_config["technologies"].get(tech_name, {})
        io_parameters = set()
        for model_type in (
            "performance_model",
            "finance_model",
            "cost_model",
            "control_strategy",
        ):
            if not tech_info or model_type not in tech_info:
                continue
            model_name = tech_info[model_type]["model"]
            if model_name == "FeedstockPerformanceModel":
                group = getattr(prob.model.plant, f"{tech_name}_source")
            else:
                group = getattr(prob.model.plant, tech_name)
                if "FeedstockCostModel" not in model_name:
                    group = getattr(group, model_name, None)
                    if group is None:
                        continue
            io_parameters.update(key.split(".")[-1] for key in group.get_io_metadata())
        technology_io[tech_name] = io_parameters
    return technology_io


def _has_commodity_parameter(parameters, commodity, direction):
    """Return whether parameters contain an exact or numbered commodity variable."""
    return f"{commodity}_{direction}" in parameters or any(
        re.fullmatch(rf"{commodity}_{direction}\d", parameter) for parameter in parameters
    )


def check_technology_connections(
    prob,
    technology_config,
    technology_graph,
    plant_config_path,
):
    """Check that connected commodity streams exist in the OpenMDAO model.

    Args:
        prob (openmdao.api.Problem): Set-up OpenMDAO problem.
        technology_config (dict): Technology configuration containing model declarations.
        technology_graph (networkx.DiGraph): Directed technology connection graph.
        plant_config_path (Path | None): Plant configuration path used in error guidance.

    Raises:
        ValueError: If a source lacks an output or a destination lacks an input.
    """
    technology_io = _technology_io_parameters(prob, technology_config, technology_graph)
    invalid_outputs = set()
    invalid_inputs = set()
    for source, destination, commodities in technology_graph.edges(data="commodity"):
        if commodities is None:
            continue
        for commodity in commodities:
            if not _has_commodity_parameter(technology_io[source], commodity, "out"):
                invalid_outputs.add((source, commodity))
            if not _has_commodity_parameter(technology_io[destination], commodity, "in"):
                invalid_inputs.add((destination, commodity))

    if not invalid_outputs and not invalid_inputs:
        return
    parts = []
    if invalid_outputs:
        items = ", ".join(
            f"`{tech}` -> `{commodity}`" for tech, commodity in sorted(invalid_outputs)
        )
        parts.append(
            "The following technologies do not output their specified commodity: " f"{items}."
        )
    if invalid_inputs:
        items = ", ".join(
            f"`{tech}` <- `{commodity}`" for tech, commodity in sorted(invalid_inputs)
        )
        parts.append(
            "The following technologies do not accept " f"their specified input commodity: {items}."
        )
    parts.append(f"Update `technology_interconnections` in {plant_config_path}.")
    raise ValueError("\n".join(parts))
