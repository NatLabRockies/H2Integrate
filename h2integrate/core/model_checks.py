"""Checks that validate individual model declarations."""


def check_model_time_step(model_name, model_object, time_step):
    """Check that a model supports the configured simulation time step.

    Args:
        model_name (str): Name used to identify the model in error messages.
        model_object: Model class or instance defining ``_time_step_bounds``.
        time_step (int | float): Configured simulation time step in seconds.

    Returns:
        None: Returns when the configured time step is supported.

    Raises:
        ValueError: If the time step falls outside the model's supported bounds.
    """
    time_step = int(time_step)
    minimum_time_step, maximum_time_step = model_object._time_step_bounds
    if minimum_time_step <= time_step <= maximum_time_step:
        return
    raise ValueError(
        f"Model {model_name} is compatible with time steps "
        f"between {minimum_time_step} (s) and {maximum_time_step} (s), but a time step of "
        f"{time_step} (s) was specified. Please set "
        "plant_config['plant']['simulation']['dt'] to a"
        f" value within the range [{minimum_time_step}, {maximum_time_step}]."
    )


def check_model_control_classifier(model_name, model_object, system_level_control_enabled):
    """Check that a model declares a classifier when system-level control is enabled.

    Args:
        model_name (str): Name used to identify the model in error messages.
        model_object: Model class or instance that should declare ``_control_classifier``.
        system_level_control_enabled (bool): Whether the classifier is required.

    Returns:
        None: Returns when no classifier is required or one is present.

    Raises:
        ValueError: If system-level control requires a missing classifier.
    """
    if system_level_control_enabled and not hasattr(model_object, "_control_classifier"):
        raise ValueError(f"Model {model_name} is missing a control classifier")


def check_technology_names(technology_names):
    """Check that no technology uses a reserved name.

    Args:
        technology_names (Iterable[str]): Names of the technologies in the technology config.

    Raises:
        NameError: If a technology is named ``site`` or uses a name reserved for internal
            H2Integrate transport models.
    """
    technology_names = set(technology_names)

    if "site" in technology_names:
        msg = (
            "'site' is an invalid technology name and is reserved for top-level "
            "variables. Please change the technology name to something else."
        )
        raise NameError(msg)

    reserved_techs = {"pipe", "cable"}
    # Use set intersection to find any reserved names present in the config
    invalid_techs = sorted(technology_names.intersection(reserved_techs))

    if invalid_techs:
        if len(invalid_techs) == 1:
            invalid_tech_msg = f"'{invalid_techs[0]}' is an invalid technology name and is"
        else:
            names_str = ", ".join(f"'{tech}'" for tech in invalid_techs)
            invalid_tech_msg = f"{names_str} are invalid technology names and are"

        msg = (
            f"{invalid_tech_msg} reserved for internal H2I transport models. "
            "Please change the technology name to something else."
        )
        raise NameError(msg)


def check_technologies_are_connected(technology_config, plant_config, tech_control_classifiers):
    """Check that multiple technologies come with technology interconnections.

    Args:
        technology_config (dict): Technology config with a ``technologies`` section.
        plant_config (dict): Plant config, optionally with ``technology_interconnections``.
        tech_control_classifiers (dict[str, str]): Control classifier of each technology.

    Raises:
        ValueError: If several non-transport technologies are defined without interconnections.
    """
    n_technologies = len(technology_config["technologies"])
    n_non_transport_techs = sum(1 for v in tech_control_classifiers.values() if v != "transport")
    if (
        n_technologies > 1
        and len(plant_config.get("technology_interconnections", [])) == 0
        and n_non_transport_techs > 1
    ):
        msg = (
            f"{n_technologies} technologies have been defined "
            "in the technology config but are not connected. Please add or populate "
            "`technology_interconnections` in the plant configuration."
        )
        raise ValueError(msg)
