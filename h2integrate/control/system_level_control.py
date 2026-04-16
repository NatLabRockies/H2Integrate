"""
System-level control configuration parsing and validation.

This module handles parsing the optional ``system_level_control`` section from
``plant_config`` and validating that all referenced technologies exist and have
valid roles.

The system-level controller is a standalone ``om.ExplicitComponent`` that
coordinates dispatch across multiple technologies using simple heuristic logic
to meet demand. It is **not** tied to any specific technology's config or to
the Pyomo optimization framework.
"""

VALID_ROLES = {"fixed", "curtailable", "dispatchable", "flexible", "storage", "demand"}

VALID_PRODUCER_ROLES = {"fixed", "curtailable", "dispatchable"}
VALID_CONSUMER_ROLES = {"flexible"}


def validate_system_level_control(slc_config, technology_config):
    """Validate the ``system_level_control`` config section.

    Checks:
    - Required keys (``commodity_streams``) are present
    - All referenced tech names exist in ``technology_config["technologies"]``
    - All roles are valid
    - At least one storage tech exists

    Args:
        slc_config (dict): The ``system_level_control`` section from plant_config.
        technology_config (dict): The full technology_config dict.

    Raises:
        ValueError: If any validation check fails.
    """
    declared_techs = set(technology_config["technologies"].keys())

    if "commodity_streams" not in slc_config:
        raise ValueError(
            "system_level_control requires a 'commodity_streams' section "
            "defining at least one commodity stream with participating technologies."
        )

    has_storage = False

    for stream_name, stream_cfg in slc_config["commodity_streams"].items():
        # Validate producers
        for entry in stream_cfg.get("producers", []):
            _validate_tech_entry(entry, stream_name, declared_techs, "producer")
            role = entry.get("role")
            if role and role not in VALID_PRODUCER_ROLES:
                raise ValueError(
                    f"system_level_control: producer '{entry['tech']}' in stream "
                    f"'{stream_name}' has invalid role '{role}'. "
                    f"Valid producer roles: {sorted(VALID_PRODUCER_ROLES)}"
                )

        # Validate consumers
        for entry in stream_cfg.get("consumers", []):
            _validate_tech_entry(entry, stream_name, declared_techs, "consumer")
            role = entry.get("role")
            if role and role not in VALID_CONSUMER_ROLES:
                raise ValueError(
                    f"system_level_control: consumer '{entry['tech']}' in stream "
                    f"'{stream_name}' has invalid role '{role}'. "
                    f"Valid consumer roles: {sorted(VALID_CONSUMER_ROLES)}"
                )

        # Validate storage
        for entry in stream_cfg.get("storage", []):
            _validate_tech_entry(entry, stream_name, declared_techs, "storage")
            has_storage = True

        # Validate demands
        for entry in stream_cfg.get("demands", []):
            _validate_tech_entry(entry, stream_name, declared_techs, "demand")

    if not has_storage:
        raise ValueError(
            "system_level_control requires at least one storage technology "
            "across all commodity streams."
        )

    # Check mutual exclusivity with existing tech_to_dispatch_connections
    get_all_slc_tech_names(slc_config)


def _validate_tech_entry(entry, stream_name, declared_techs, category):
    """Validate a single technology entry in a commodity stream.

    Args:
        entry (dict): Single entry like ``{"tech": "wind", "role": "fixed"}``.
        stream_name (str): Name of the parent commodity stream.
        declared_techs (set): Set of valid technology names.
        category (str): One of "producer", "consumer", "storage", "demand".

    Raises:
        ValueError: If the tech name is missing or not declared.
    """
    if "tech" not in entry:
        raise ValueError(
            f"system_level_control: entry in '{category}' list of stream "
            f"'{stream_name}' is missing required 'tech' key."
        )
    tech = entry["tech"]
    if tech not in declared_techs:
        raise ValueError(
            f"system_level_control references tech '{tech}' in stream "
            f"'{stream_name}', but it is not declared in "
            f"tech_config.technologies. Available technologies: "
            f"{sorted(declared_techs)}"
        )


def get_all_slc_tech_names(slc_config):
    """Extract all unique technology names from the system_level_control config.

    Args:
        slc_config (dict): The ``system_level_control`` section from plant_config.

    Returns:
        set: All technology names referenced in any commodity stream.
    """
    techs = set()
    for stream_cfg in slc_config.get("commodity_streams", {}).values():
        for category in ("producers", "consumers", "storage", "demands"):
            for entry in stream_cfg.get(category, []):
                techs.add(entry["tech"])
    return techs


def get_storage_techs(slc_config):
    """Get all storage technology names from the system_level_control config.

    Args:
        slc_config (dict): The ``system_level_control`` section from plant_config.

    Returns:
        list[dict]: Storage entries, each with at least a ``"tech"`` key.
    """
    storage_entries = []
    for stream_cfg in slc_config.get("commodity_streams", {}).values():
        storage_entries.extend(stream_cfg.get("storage", []))
    return storage_entries


def get_fixed_producers(slc_config):
    """Get all fixed-role producer entries from the SLC config.

    Args:
        slc_config (dict): The ``system_level_control`` section from plant_config.

    Returns:
        list[tuple[str, dict]]: List of (stream_name, entry) tuples.
    """
    results = []
    for stream_name, stream_cfg in slc_config.get("commodity_streams", {}).items():
        results.extend(
            (stream_name, entry)
            for entry in stream_cfg.get("producers", [])
            if entry.get("role") == "fixed"
        )
    return results


def prepare_system_level_control(technology_config, plant_config):
    """Validate the ``system_level_control`` config section if present.

    This is called early in ``H2IntegrateModel.__init__()`` before technology
    models are created. It validates the config but does **not** mutate
    ``technology_config`` or ``plant_config``.

    The actual controller component is added separately by
    ``add_system_level_controller()``.

    Args:
        technology_config (dict): The full technology_config dict (read-only).
        plant_config (dict): The full plant_config dict (read-only).

    Returns:
        None
    """
    slc_config = plant_config.get("system_level_control")
    if slc_config is None:
        return

    # Validate
    validate_system_level_control(slc_config, technology_config)

    # Check mutual exclusivity with existing tech_to_dispatch_connections
    existing_dispatch = plant_config.get("tech_to_dispatch_connections", [])
    existing_dispatch_techs = set()
    for conn in existing_dispatch:
        if len(conn) >= 1:
            existing_dispatch_techs.add(conn[0])

    slc_techs = get_all_slc_tech_names(slc_config)
    overlap = slc_techs & existing_dispatch_techs
    if overlap:
        raise ValueError(
            f"Technologies {sorted(overlap)} appear in both 'system_level_control' "
            f"and 'tech_to_dispatch_connections'. A technology can only be under "
            f"one dispatch control mechanism. Remove the duplicates from one section."
        )


def add_system_level_controller(plant_group, plant_config, technology_config):
    """Add the ``SystemLevelController`` component to the plant group and wire it.

    This is called after ``create_technology_models()`` so that all technology
    subsystems already exist and their I/O are declared.

    Args:
        plant_group (om.Group): The plant-level OpenMDAO group.
        plant_config (dict): The full plant_config dict.
        technology_config (dict): The full technology_config dict.

    Returns:
        om.ExplicitComponent or None: The controller component, or None if no
            system_level_control config is present.
    """
    from h2integrate.control.control_strategies.system_level.system_level_controller import (
        SystemLevelController,
    )

    slc_config = plant_config.get("system_level_control")
    if slc_config is None:
        return None

    controller = plant_group.add_subsystem(
        "system_level_controller",
        SystemLevelController(
            plant_config=plant_config,
            technology_config=technology_config,
        ),
    )

    return controller


def connect_system_level_controller(model, plant_config):
    """Create OpenMDAO connections between the controller and technology I/O.

    Wires:
    - Fixed producer ``{commodity}_out`` → controller input
    - Controller storage dispatch output → storage ``{commodity}_set_point``

    Args:
        model (om.Group): The top-level OpenMDAO model (prob.model).
        plant_config (dict): The full plant_config dict.
    """
    slc_config = plant_config.get("system_level_control")
    if slc_config is None:
        return

    for stream_name, stream_cfg in slc_config["commodity_streams"].items():
        # Connect fixed producer outputs → controller inputs
        for entry in stream_cfg.get("producers", []):
            if entry.get("role") == "fixed":
                tech = entry["tech"]
                model.connect(
                    f"{tech}.{stream_name}_out",
                    f"system_level_controller.{tech}_{stream_name}_available",
                )

        # Connect controller storage dispatch → storage set_point
        for entry in stream_cfg.get("storage", []):
            tech = entry["tech"]
            model.connect(
                f"system_level_controller.{tech}_{stream_name}_dispatch",
                f"{tech}.{stream_name}_set_point",
            )
