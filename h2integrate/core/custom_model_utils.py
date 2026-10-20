import importlib.util

from h2integrate.core.file_utils import find_file


def create_custom_models(
    supported_models, model_config, config_parent_path, model_types, prefix=""
):
    """Load custom models from the specified directory and add them to ``supported_models``.

    Args:
        supported_models (dict): Mapping of model names to model classes. Updated in place.
        model_config (dict): dictionary containing models, such as
            ``technology_config["technologies"]``.
        config_parent_path (Path): parent path of the input file that ``model_config`` comes
            from. Should either be ``plant_config_path.parent`` or
            ``tech_config_path.parent``.
        model_types (list[str]): list of key names to search for in
            ``model_config.values()``. Should be
            ``["performance_model", "cost_model", "financial_model"]`` if ``model_config``
            is ``technology_config["technologies"]``.
        prefix (str, optional): Prefix of ``model_class_name``, ``model_location`` and
            ``model``. Defaults to "". Should be ``"finance_"`` if looking for custom
            system finance models.
    """

    included_custom_models = {}

    for name, config in model_config.items():
        for model_type in model_types:
            if model_type in config:
                model_name = config[model_type].get(f"{prefix}model")

                # Don't create new custom model or raise an error if the current custom model
                # has already been processed. This can happen if there are 2 or more instances
                # of the same custom model. Also check that all instances of the same custom
                # model tech name use the same class definition.
                if model_name in included_custom_models:
                    model_class_name = config[model_type].get(f"{prefix}model")
                    if model_class_name != included_custom_models[model_name]["model_class_name"]:
                        raise (
                            ValueError(
                                "User has specified two custom models using the same model"
                                f"name ({model_name}), but with different model classes. "
                                "Technologies defined with different classes must have "
                                "different technology names."
                            )
                        )
                    else:
                        continue

                if (model_name not in supported_models) and (model_name is not None):
                    model_class_name = config[model_type].get(f"{prefix}model")
                    model_location = config[model_type].get(f"{prefix}model_location")

                    if not model_class_name or not model_location:
                        raise ValueError(
                            f"Custom {model_type} for {name} must specify "
                            f"'{prefix}model_class_name' and '{prefix}model_location'."
                        )

                    # Resolve the full path of the model location
                    if config_parent_path is not None:
                        model_path = find_file(model_location, config_parent_path)
                    else:
                        model_path = find_file(model_location)

                    if not model_path.exists():
                        raise FileNotFoundError(
                            f"Custom model location {model_path} does not exist."
                        )

                    # Dynamically import the custom model class
                    spec = importlib.util.spec_from_file_location(model_class_name, model_path)
                    module = importlib.util.module_from_spec(spec)
                    spec.loader.exec_module(module)
                    custom_model_class = getattr(module, model_class_name)

                    # Add the custom model to the supported models dictionary
                    supported_models[model_name] = custom_model_class

                    # Add the custom model to custom models dictionary
                    included_custom_models[model_name] = {
                        "model_class_name": model_class_name,
                    }

                else:
                    if (
                        config[model_type].get(f"{prefix}model_class_name") is not None
                        or config[model_type].get(f"{prefix}model_location") is not None
                    ):
                        msg = (
                            f"Custom {prefix}model or {prefix}model_location "
                            f"specified for '{model_name}', "
                            f"but '{model_name}' is a built-in H2Integrate "
                            "model. Using built-in model instead is not allowed. "
                            f"If you want to use a custom model, please rename it "
                            "in your configuration."
                        )
                        raise ValueError(msg)


def collect_custom_models(
    supported_models, technology_config, tech_parent_path, plant_config, plant_parent_path
):
    """Collect custom technology, finance, and resource models into ``supported_models``.

    Args:
        supported_models (dict): Mapping of model names to model classes. Updated in place.
        technology_config (dict): Technology config with a ``technologies`` section.
        tech_parent_path (Path | None): Parent directory of the technology config file.
        plant_config (dict): Plant config, which may define system finance and resource models.
        plant_parent_path (Path | None): Parent directory of the plant config file.
    """
    # check for custom technology models
    create_custom_models(
        supported_models,
        technology_config["technologies"],
        tech_parent_path,
        ["performance_model", "cost_model", "finance_model"],
    )

    # check for custom finance models
    if "finance_parameters" in plant_config:
        finance_groups = plant_config["finance_parameters"]["finance_groups"]

        # check for single custom finance models
        if "model_inputs" in finance_groups:
            create_custom_models(
                supported_models,
                plant_config,
                plant_parent_path,
                ["finance_groups"],
                prefix="finance_",
            )

        # check for named finance models
        if any("model_inputs" in v for k, v in finance_groups.items()):
            finance_model_names = [k for k, v in finance_groups.items() if "model_inputs" in v]
            finance_groups_config = {"finance_groups": finance_groups}
            create_custom_models(
                supported_models,
                finance_groups_config,
                plant_parent_path,
                finance_model_names,
                prefix="finance_",
            )

    # check for custom resource models
    if "sites" in plant_config:
        for site_name, site_params in plant_config["sites"].items():
            if "resources" in site_params:
                resource_models_config = {
                    k: v for k, v in site_params["resources"].items() if "resource_parameters" in v
                }

                resource_model_names = [
                    k for k, v in site_params["resources"].items() if "resource_parameters" in v
                ]
                create_custom_models(
                    supported_models,
                    {site_name: resource_models_config},
                    plant_parent_path,
                    resource_model_names,
                    prefix="resource_",
                )
