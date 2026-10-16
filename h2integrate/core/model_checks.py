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


def check_model_is_steppable(control_strategies, performance_models):
    """Check that all technology control strategies and performance models have the attribute
    _is_steppable == True. If _is_steppable attribute is missing or evaluates to False, then the
    system is suitable for steppable simulation and an error is raised.

    Args:
        control_strategies (list):
        performance_models (list):

    Returns:
        None: Returns if all models are steppable.

    Raises:
        AttributeError: If control strategies or performance models are not flagged as steppable.
    """

    error_msg_list = []

    non_steppable_control_strategies = [
        cs.__str__() for cs in control_strategies if not getattr(cs, "_is_steppable", False)
    ]
    if non_steppable_control_strategies:
        control_msg = f"Control strategy(ies): {sorted(non_steppable_control_strategies)}"
        error_msg_list.append(control_msg)

    non_steppable_performance_models = [
        pm.__str__() for pm in performance_models if not getattr(pm, "_is_steppable", False)
    ]
    if non_steppable_performance_models:
        performance_msg = f"Performance model(s): {sorted(non_steppable_performance_models)}"
        error_msg_list.append(performance_msg)

    if error_msg_list:
        error_msg = (
            "Attempting to run a steppable simulation with unsupported models:\n\t"
            + "\n\t".join(error_msg_list)
            + "\n\t are not flagged as capable of steppable simulation."
        )
        raise AttributeError(error_msg)
