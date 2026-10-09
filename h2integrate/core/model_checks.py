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


def check_model_simulation_duration(model_name, model_object, n_timesteps, dt):
    """Check that a model supports the configured simulation duration.

    Args:
        model_name (str): Name used to identify the model in error messages.
        model_object: Model class or instance defining ``_simulation_duration_bounds``
            as ``(min, max)`` permitted simulation durations in years. Models that do not
            define the attribute default to supporting a single year only.
        n_timesteps (int | float): Number of timesteps in the simulation.
        dt (int | float): Simulation time step in seconds.

    Returns:
        None: Returns when the configured simulation duration is supported.

    Raises:
        ValueError: If the simulation duration falls outside the model's supported bounds.
    """
    seconds_per_year = 31_536_000  # 8760 h/year * 3600 s/h
    years_simulated = (int(n_timesteps) * int(dt)) / seconds_per_year
    minimum_years, maximum_years = getattr(model_object, "_simulation_duration_bounds", (1.0, 1.0))
    if minimum_years <= years_simulated <= maximum_years:
        return
    raise ValueError(
        f"Model {model_name} is compatible with simulation durations between "
        f"{minimum_years} and {maximum_years} years, but a simulation duration of "
        f"{years_simulated:g} years (n_timesteps={int(n_timesteps)} * dt={int(dt)} s) was "
        "specified. Please set plant_config['plant']['simulation'] so that n_timesteps * dt "
        f"corresponds to a duration within the range [{minimum_years}, {maximum_years}] years."
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
