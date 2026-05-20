def check_plant_config_and_profast_params(
    plant_config_dict: dict, pf_param_dict: dict, plant_config_key: str, pf_config_key: str
):
    """
    Checks for consistency between values in the plant configuration dictionary and the
    ProFAST parameters dictionary.

    This function compares the value associated with `plant_config_key` in `plant_config_dict`
    to the value associated with `pf_config_key` in `pf_param_dict`. If `pf_config_key` is not
    present in `pf_param_dict`, the value from `plant_config_dict` is used as the default.
    If the values are inconsistent, a ValueError is raised with a descriptive message.

    Args:
        plant_config_dict (dict): Dictionary containing plant configuration parameters.
        pf_param_dict (dict): Dictionary containing ProFAST parameter values.
        plant_config_key (str): Key to look up in `plant_config_dict`.
        pf_config_key (str): Key to look up in `pf_param_dict`.

    Raises:
        ValueError: If the values for the specified keys in the two dictionaries are inconsistent.
    """

    if (
        pf_param_dict.get(pf_config_key, plant_config_dict[plant_config_key])
        != plant_config_dict[plant_config_key]
    ):
        msg = (
            f"Inconsistent values provided for {pf_config_key} and {plant_config_key}, "
            f"{pf_config_key} is {pf_param_dict.get(pf_config_key)} but "
            f"{plant_config_key} is {plant_config_dict[plant_config_key]}."
            f"Please check that {pf_config_key} is the same as {plant_config_key} or remove "
            f"{pf_config_key} from pf_params input."
        )
        raise ValueError(msg)
