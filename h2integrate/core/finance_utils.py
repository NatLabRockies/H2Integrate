"""Helpers that parse and validate the finance section of the plant config."""

DEFAULT_FINANCE_GROUP_NAME = "default"


def wrap_single_finance_model_as_default_group(finance_groups):
    """Move a lone ``finance_model``/``model_inputs`` pair into a group named ``default``.

    Modifies ``finance_groups`` in place. Does nothing if both keys are not present.

    Args:
        finance_groups (dict): ``plant_config["finance_parameters"]["finance_groups"]``.

    Raises:
        ValueError: If a finance group is already named ``default``.
    """
    if "finance_model" not in finance_groups or "model_inputs" not in finance_groups:
        return

    if DEFAULT_FINANCE_GROUP_NAME in finance_groups:
        # throw an error if the user has an unused finance group named "default".
        msg = (
            "Invalid key `default` in "
            "plant_config['finance_parameters']['finance_groups']. "
            "Please rename the `default` key to something else or remove it. "
            "The name `default` will be used to reference the finance model group."
        )
        raise ValueError(msg)

    finance_groups[DEFAULT_FINANCE_GROUP_NAME] = {
        "finance_model": finance_groups.pop("finance_model"),
        "model_inputs": finance_groups.pop("model_inputs"),
    }


def build_default_finance_subgroups(finance_groups, technology_names):
    """Build a single subgroup containing every technology.

    Args:
        finance_groups (dict): ``plant_config["finance_parameters"]["finance_groups"]``
            after ``wrap_single_finance_model_as_default_group()``.
        technology_names (list[str]): Names of all technologies in the plant.

    Returns:
        dict: Subgroup definitions keyed by the default finance group name.

    Raises:
        ValueError: If ``commodity`` or the default ``finance_model`` is missing.
    """
    commodity = finance_groups.get("commodity")
    finance_model_name = finance_groups.get(DEFAULT_FINANCE_GROUP_NAME, {}).get("finance_model")
    commodity_stream = finance_groups.get("commodity_stream")

    if not commodity or not finance_model_name:
        raise ValueError(
            "plant_config['finance_parameters']['finance_groups'] "
            "must define 'commodity' and 'finance_model' "
            "if no finance_subgroups are provided."
        )

    subgroup = {
        "commodity": commodity,
        "finance_groups": [DEFAULT_FINANCE_GROUP_NAME],
        "technologies": technology_names,
    }
    if commodity_stream is not None:
        subgroup["commodity_stream"] = commodity_stream
    return {DEFAULT_FINANCE_GROUP_NAME: subgroup}


def get_finance_group_names(subgroup_params):
    """Return the finance group names of a subgroup as a list."""
    finance_group_names = subgroup_params.get("finance_groups", [DEFAULT_FINANCE_GROUP_NAME])
    if isinstance(finance_group_names, str):
        finance_group_names = [finance_group_names]
    return finance_group_names


def parse_finance_subgroup(subgroup_name, subgroup_params, technologies):
    """Validate a finance subgroup definition and return its normalized settings.

    Args:
        subgroup_name (str): Name of the finance subgroup.
        subgroup_params (dict): User-provided definition of the subgroup.
        technologies (dict): ``technology_config["technologies"]``.

    Returns:
        dict: Settings used downstream, with keys ``tech_configs``, ``commodity``,
        ``commodity_stream``, ``is_system_finance_model``, ``use_commodity_stream_timeseries``
        and ``commodity_stream_output``.

    Raises:
        ValueError: If ``commodity`` or ``commodity_stream`` is missing.
        KeyError: If the subgroup lists a technology that is not in the technology config.
        UserWarning: If the commodity stream technology has a cost model but is not
            included in the subgroup technologies.
    """
    commodity = subgroup_params.get("commodity", None)
    tech_names = subgroup_params.get("technologies")
    commodity_stream = subgroup_params.get("commodity_stream", None)

    if commodity is None:
        raise ValueError(
            f"Required parameter ``commodity`` not provided in subgroup {subgroup_name}."
        )

    tech_configs = {}
    for tech in tech_names:
        if tech not in technologies:
            raise KeyError(
                f"Technology '{tech}' not found in the technology configuration, "
                f"but is listed in subgroup '{subgroup_name}', "
                "Available "
                f"technologies: {list(technologies.keys())}"
            )
        tech_configs[tech] = technologies[tech]

    if commodity_stream is not None:
        commodity_stream_has_cost = technologies.get(commodity_stream, {}).get("cost_model", False)
        if commodity_stream_has_cost and commodity_stream not in tech_names:
            raise UserWarning(
                f"The technology specific for the commodity_stream '{commodity_stream}' "
                f"is not included in subgroup '{subgroup_name}' technologies list."
                f" Subgroup '{subgroup_name}' includes technologies: {tech_names}."
            )

    # ``commodity_stream`` identifies the technology whose output is used as
    # the commodity-production signal for this subgroup's finance model. It
    # must be supplied explicitly by the user; there is no default mapping
    # from commodity to tech name.
    if commodity_stream is None:
        msg = (
            f"Finance subgroup '{subgroup_name}' (commodity '{commodity}') is "
            "missing the required `commodity_stream` field. Please specify "
            "which technology's output should be used as the commodity stream "
            "for this subgroup."
        )
        raise ValueError(msg)

    return {
        "tech_configs": tech_configs,
        "commodity": commodity,
        "commodity_stream": commodity_stream,
        "is_system_finance_model": True,
        "use_commodity_stream_timeseries": subgroup_params.get(
            "use_commodity_stream_timeseries", False
        ),
        "commodity_stream_output": subgroup_params.get("commodity_stream_output", None),
    }


def filter_plant_config_for_finance_group(plant_config, model_name, model_inputs):
    """Copy the plant config, keeping only one finance group in ``finance_parameters``."""
    filtered_plant_config = {k: v for k, v in plant_config.items() if k != "finance_parameters"}
    filtered_plant_config["finance_parameters"] = {
        "finance_model": model_name,  # unused by the finance model
        "model_inputs": model_inputs,  # inputs for finance model
    }
    return filtered_plant_config


def get_finance_output_description(
    subgroup_name,
    subgroup_params,
    finance_group_name,
    finance_group_names,
    finance_groups,
    n_tech_finances_in_group,
):
    """Return the description that keeps finance model output names unique within a subgroup.

    Args:
        subgroup_name (str): Name of the finance subgroup.
        subgroup_params (dict): User-provided definition of the subgroup.
        finance_group_name (str): Finance group currently being created.
        finance_group_names (list[str]): All finance groups in the subgroup.
        finance_groups (dict): ``plant_config["finance_parameters"]["finance_groups"]``.
        n_tech_finances_in_group (int): Number of tech-specific finance models seen so far.

    Returns:
        str: The subgroup ``commodity_desc``, suffixed with the finance group name when the
        subgroup has several system-level finance models.

    Raises:
        ValueError: If tech-specific and system-level finance models are mixed in one subgroup.
    """
    commodity_output_desc = subgroup_params.get("commodity_desc", "")

    if len(finance_group_names) <= 1:
        return commodity_output_desc

    # check that the finance model groups do not include tech-specific finances
    non_tech_finances = [k for k in finance_group_names if k in finance_groups]
    tech_finances = [k for k in finance_group_names if k not in finance_groups]

    if n_tech_finances_in_group > 0 and non_tech_finances:
        msg = (
            f"Cannot run a tech-specific finance model ({tech_finances}) in the "
            f"same finance subgroup as a system-level finance model "
            f"({non_tech_finances}). Please modify the finance_groups in finance "
            f"subgroup {subgroup_name}."
        )
        raise ValueError(msg)

    # if multiple non-tech specific finance model groups are specified for the
    # subgroup, the outputs of the finance model must have unique names to
    # avoid errors.
    if len(non_tech_finances) > 1:
        commodity_output_desc = commodity_output_desc + f"_{finance_group_name}"

    return commodity_output_desc
