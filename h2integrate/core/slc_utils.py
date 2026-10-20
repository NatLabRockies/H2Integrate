import networkx as nx

from h2integrate.core.connection_utils import create_technology_graph


def classify_slc_technologies(
    technology_config, plant_config, technology_graph, tech_control_classifiers
):
    """Classify technologies for system-level control.

    Uses ``tech_control_classifiers`` (populated by
    ``H2IntegrateModel.create_technology_models()``) to partition technologies into fixed,
    flexible, dispatchable, and storage lists. Also identifies the single demand technology
    and its commodity.

    SLC demand is supplied by a demand component (for example,
    ``GenericDemandComponent``). When SLC is enabled, only one demand
    component is currently supported.

    Args:
        technology_config (dict): Technology config with a ``technologies`` section.
        plant_config (dict): Plant config with ``system_level_control`` and
            ``technology_interconnections`` sections.
        technology_graph (nx.DiGraph): Directed graph of the technology interconnections.
        tech_control_classifiers (dict[str, str]): Control classifier of each technology.

    Returns:
        dict: Classification dictionary (``slc_topology``) with keys:

            - ``"demand_tech"`` (str): Name of the demand technology (the tech whose
              performance model is a ``DemandComponent``).
            - ``"demand_commodity"`` (str): Commodity the demand technology consumes
              (e.g. ``"electricity"``, ``"hydrogen"``).
            - ``"demand_commodity_rate_units"`` (str | None): Units string for the
              demand commodity rate (e.g. ``"kW"``, ``"kg/h"``), or ``None`` if not
              specified in the demand tech config.
            - ``"demand_profile"`` (int | float | list): Default demand profile from
                the demand technology configuration.
            - ``"tech_to_commodity"`` (set[tuple[str, str]]): Set of
              ``(tech_name, commodity)`` pairs for every technology that the SLC
              controls or reads from. Built from outgoing edges of the technology
              graph and filtered to fixed, flexible, dispatchable, storage, and
              feedstock classifiers.
            - ``"technology_graph"`` (nx.DiGraph): Directed graph of technology
              interconnections, with edge attribute ``commodity`` indicating the
              commodity carried on each edge. Used by cost-aware controllers to
              trace upstream feedstocks.
            - ``"tech_control_classifiers"`` (dict[str, str]): Mapping of tech name
              to its ``_control_classifier`` (one of ``"fixed"``, ``"flexible"``,
              ``"dispatchable"``, ``"storage"``, ``"feedstock"``). Determines how
              the SLC interacts with each tech.
            - ``"storage_techs_to_control"`` (dict[str, bool]): Whether each storage tech
              has its own sub-controller.

    Raises:
        ValueError: If the demand technology is missing, undefined, unsupported, or not
            connected in the technology interconnections.
    """
    slc_topology = {}
    technologies = technology_config.get("technologies", {})

    if not (demand_tech := plant_config["system_level_control"].get("demand_component", False)):
        msg = (
            "Please specify the technology name for the demand component in "
            "the plant configuration file under ``system_level_control['demand_component']``"
        )
        raise ValueError(msg)
    if demand_tech not in technologies:
        msg = (
            f"Demand technology specified for system level controller, ``{demand_tech}``,"
            "not defined in the tech configuration file."
        )
        raise ValueError(msg)
    model_name = technologies[demand_tech].get("performance_model", {}).get("model", "")
    if "DemandComponent" not in model_name:
        msg = (
            f"Demand component ``{model_name}`` is not a supported model for the system level "
            "control demand technology. Supported demand component performance models include "
            "``DemandComponent`` in the class name."
        )
        raise ValueError(msg)

    model_inputs = technologies[demand_tech].get("model_inputs", {})
    perf_params = model_inputs.get("performance_parameters", {})
    shared_params = model_inputs.get("shared_parameters", {})
    all_params = {**shared_params, **perf_params}

    # Check that the demand tech is in the technology_interconnections
    tech_interconnections = plant_config["technology_interconnections"]
    demand_is_source_connection = [
        tech_connection
        for tech_connection in tech_interconnections
        if tech_connection[0] == demand_tech
    ]
    demand_is_destination_connection = [
        tech_connection
        for tech_connection in tech_interconnections
        if tech_connection[1] == demand_tech
    ]
    if len(demand_is_source_connection) == 0 and len(demand_is_destination_connection) == 0:
        # Raise error if demand technology is not connected
        msg = (
            "No demand commodity was found in the technology interconnections. "
            f"Please ensure that the demand technology ``{demand_tech}`` "
            "is connected in the technology_interconnections"
        )
        raise ValueError(msg)

    # Classify technologies based on their output commodity (or commodities)
    # Use a set to remove duplicates (in case one tech produces multiple commodities)
    # get list of technologies upstream of the demand technology
    upstream_techs = nx.ancestors(technology_graph, demand_tech)
    # only connect the technologies that are connected to the demand tech
    upstream_controllable_techs = {
        tech for tech in upstream_techs if nx.has_path(technology_graph, tech, demand_tech)
    }

    sources_to_commodities = set()
    for source, _, commodities in technology_graph.edges(data="commodity"):
        if source not in upstream_controllable_techs or commodities is None:
            continue

        sources_to_commodities.update((source, commodity) for commodity in commodities)

    # re-make technology interconnections using only technologies
    # upstream of the demand component
    upstream_interconnections = [
        connection
        for connection in tech_interconnections
        if connection[0] in upstream_controllable_techs
    ]

    upstream_tech_graph = create_technology_graph(upstream_interconnections)
    slc_topology["technology_graph"] = upstream_tech_graph

    # downselect the technology control classifiers to only include those upstream
    # of the demand
    upstream_tech_control_classifiers = {
        k: v for k, v in tech_control_classifiers.items() if k in upstream_controllable_techs
    }

    # Check if storage models have a controller
    storage_tech_to_control = {}
    for tech, classifier in upstream_tech_control_classifiers.items():
        if classifier == "storage":
            control_model = (
                technology_config["technologies"][tech]
                .get("control_strategy", {})
                .get("model", None)
            )
            if control_model is None:
                storage_tech_to_control[tech] = False
            else:
                # storage model does use a controller
                storage_tech_to_control[tech] = True
    slc_topology["storage_techs_to_control"] = storage_tech_to_control

    # Remove feedstocks, combiners, and splitters
    control_classifiers_to_connect = [
        "fixed",
        "flexible",
        "dispatchable",
        "storage",
        "feedstock",
    ]
    tech_to_commodity = {
        (e[0], e[-1])
        for e in sources_to_commodities
        if upstream_tech_control_classifiers.get(e[0]) in control_classifiers_to_connect
    }
    slc_topology["tech_to_commodity"] = tech_to_commodity

    # Store classification results in plant_config for SLC component
    slc_topology["demand_tech"] = demand_tech
    slc_topology["demand_commodity"] = all_params["commodity"]
    slc_topology["demand_commodity_rate_units"] = all_params.get("commodity_rate_units", None)
    slc_topology["demand_profile"] = all_params.get("demand_profile", 10.0)

    slc_topology["tech_control_classifiers"] = upstream_tech_control_classifiers

    return slc_topology
