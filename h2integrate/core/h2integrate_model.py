import importlib.util

import numpy as np
import networkx as nx
import openmdao.api as om
import matplotlib.pyplot as plt

from h2integrate.core.utilities import (
    get_path,
    find_file,
    load_yaml,
    print_results,
    create_xdsm_from_config,
)
from h2integrate.finances.finances import AdjustedCapexOpexComp
from h2integrate.core.resource_summer import ElectricitySumComp
from h2integrate.core.supported_models import supported_models, is_electricity_producer
from h2integrate.core.inputs.validation import load_tech_yaml, load_plant_yaml, load_driver_yaml
from h2integrate.core.pose_optimization import PoseOptimization
from h2integrate.postprocess.sql_to_csv import convert_sql_to_csv_summary


try:
    import pyxdsm
except ImportError:
    pyxdsm = None


class H2IntegrateModel:
    def __init__(self, config_input):
        # read in config file; it's a yaml dict that looks like this:
        self.load_config(config_input)

        # load in supported models
        self.supported_models = supported_models.copy()

        # load custom models
        self.collect_custom_models()

        # Check if create_om_reports is specified in driver config
        create_om_reports = self.driver_config.get("general", {}).get("create_om_reports", True)
        self.prob = om.Problem(reports=create_om_reports)
        self.model = self.prob.model

        # track if setup has been called via boolean
        self.setup_has_been_called = False

        # initialize recorder_path attribute
        self.recorder_path = None

        # create site-level model
        # this is an OpenMDAO group that contains all the site information
        self.create_site_model()

        # create plant-level model
        # this is an OpenMDAO group that contains all the technologies
        # it will need plant_config but not driver or tech config
        self.create_plant_model()

        # create technology models
        # these are OpenMDAO groups that contain all the components for each technology
        # they will need tech_config but not driver or plant config
        self.create_technology_models()

        self.create_finance_model()

        # connect technologies
        # technologies are connected within the `technology_interconnections` section of the
        # plant config
        self.connect_technologies()

        # create driver model
        # might be an analysis or optimization
        self.create_driver_model()

    def _load_component_config(self, config_key, config_value, config_path, validator_func):
        """Helper method to load and validate a component configuration.

        Args:
            config_key (str): Key name for the configuration (e.g., "driver_config")
            config_value (dict | str): Configuration value from main config
            config_path (Path | None): Path to main config file (None if dict)
            validator_func (callable): Validation function to apply

        Returns:
            tuple: (validated_config, config_file_path, parent_path)
                - validated_config: Validated configuration dictionary
                - config_file_path: Path to config file (None if dict)
                - parent_path: Parent directory of config file (None if dict)
        """
        if isinstance(config_value, dict):
            # Config provided as embedded dictionary
            return validator_func(config_value), None, None
        else:
            # Config provided as filepath - resolve location
            if config_path is None:
                file_path = get_path(config_value)
            else:
                file_path = find_file(config_value, config_path.parent)

            # Store parent directory for resolving custom model paths later
            parent_path = file_path.parent
            return validator_func(file_path), file_path, parent_path

    def load_config(self, config_input):
        """Load and validate configuration files for the H2I model.

        This method loads the main configuration and the three component configuration files
        (driver, technology, and plant configurations). Each configuration can be provided
        either as a dictionary object or as a filepath. When filepaths are provided,
        the method resolves them using multiple search strategies.

        Args:
            config_input (dict | str | Path): Main configuration containing references to
                driver, technology, and plant configurations. Can be:
                - A dictionary containing the configuration data directly
                - A string or Path object pointing to a YAML file containing the configuration

        Behavior:
            - If `config_input` is a dict: Uses it directly as the main configuration
            - If `config_input` is a path: Uses `get_path()` to resolve and load the YAML file
              from multiple search locations (absolute path, relative to CWD, relative to
              H2Integrate package)

            For each component config (driver_config, technology_config, plant_config):
            - If the config value is a dict: Validates it directly using the appropriate
              validation function (`load_driver_yaml`, `load_tech_yaml`, `load_plant_yaml`)
            - If the config value is a path string:
                - When main config was loaded from file: Uses `find_file()` to search
                  relative to the main config file's directory first, then falls back
                  to other search locations (CWD, H2Integrate package, glob patterns)
                - When main config was provided as dict: Uses `get_path()` with standard
                  search strategy (absolute, relative to CWD, relative to H2Integrate package)

        Sets:
            self.name (str): Name of the system from main config
            self.system_summary (str): Summary description from main config
            self.driver_config (dict): Validated driver configuration
            self.technology_config (dict): Validated technology configuration
            self.plant_config (dict): Validated plant configuration
            self.driver_config_path (Path | None): Path to driver config file (None if dict)
            self.tech_config_path (Path | None): Path to technology config file (None if dict)
            self.plant_config_path (Path | None): Path to plant config file (None if dict)
            self.tech_parent_path (Path | None): Parent directory of technology config file
            self.plant_parent_path (Path | None): Parent directory of plant config file

        Note:
            The parent path attributes (tech_parent_path, plant_parent_path) are used later
            for resolving relative paths to custom models and other referenced files within
            the technology and plant configurations.

        Example:
            >>> # Using filepaths
            >>> model = H2IntegrateModel("main_config.yaml")

            >>> # Using mixed dict and filepaths
            >>> config = {
            ...     "name": "my_system",
            ...     "driver_config": "driver.yaml",
            ...     "technology_config": {"technologies": {...}},
            ...     "plant_config": "plant.yaml",
            ... }
            >>> model = H2IntegrateModel(config)
        """
        # Load main configuration
        if isinstance(config_input, dict):
            config = config_input
            config_path = None
        else:
            config_path = get_path(config_input)
            config = load_yaml(config_path)

        self.name = config.get("name")
        self.system_summary = config.get("system_summary")

        # Load and validate each component configuration using the helper method
        self.driver_config, self.driver_config_path, _ = self._load_component_config(
            "driver_config", config.get("driver_config"), config_path, load_driver_yaml
        )

        self.technology_config, self.tech_config_path, self.tech_parent_path = (
            self._load_component_config(
                "technology_config", config.get("technology_config"), config_path, load_tech_yaml
            )
        )

        self.plant_config, self.plant_config_path, self.plant_parent_path = (
            self._load_component_config(
                "plant_config", config.get("plant_config"), config_path, load_plant_yaml
            )
        )

    def create_custom_models(self, model_config, config_parent_path, model_types, prefix=""):
        """This method loads custom models from the specified directory and adds them to the
        supported models dictionary.

        Args:
            model_config (dict): dictionary containing models, such as
                `technology_config["technologies"]`
            config_parent_path (Path): parent path of the input file that `model_config` comes from.
                Should either be `plant_config_path.parent` or `tech_config_path.parent`
            model_types (list[str]): list of keynames to search for in `model_config.values()`.
                Should be ["performance_model", "cost_model", "financial_model"] if `model_config`
                is technology_config["technologies"].
            prefix (str, optional): Prefix of "model_class_name", "model_location" and "model".
                Defaults to "". Should be "finance_" if looking for custom general finance models.
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
                        model_class_name = config[model_type].get(f"{prefix}model_class_name")
                        if (
                            model_class_name
                            != included_custom_models[model_name]["model_class_name"]
                        ):
                            raise (
                                ValueError(
                                    "User has specified two custom models using the same model"
                                    "name ({model_name}), but with different model classes. "
                                    "Technologies defined with different classes must have "
                                    "different technology names."
                                )
                            )
                        else:
                            continue

                    if (model_name not in self.supported_models) and (model_name is not None):
                        model_class_name = config[model_type].get(f"{prefix}model_class_name")
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
                        self.supported_models[model_name] = custom_model_class

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
                                f"Custom {prefix}model_class_name or {prefix}model_location "
                                f"specified for '{model_name}', "
                                f"but '{model_name}' is a built-in H2Integrate "
                                "model. Using built-in model instead is not allowed. "
                                f"If you want to use a custom model, please rename it "
                                "in your configuration."
                            )
                            raise ValueError(msg)

    def collect_custom_models(self):
        """Collect custom models from the technology configuration and
        general finance models found in the plant configuration.
        """
        # check for custom technology models
        self.create_custom_models(
            self.technology_config["technologies"],
            self.tech_parent_path,
            ["performance_model", "cost_model", "finance_model"],
        )

        # check for custom finance models
        if "finance_parameters" in self.plant_config:
            finance_groups = self.plant_config["finance_parameters"]["finance_groups"]

            # check for single custom finance models
            if "model_inputs" in finance_groups:
                self.create_custom_models(
                    self.plant_config,
                    self.plant_parent_path,
                    ["finance_groups"],
                    prefix="finance_",
                )

            # check for named finance models
            if any("model_inputs" in v for k, v in finance_groups.items()):
                finance_model_names = [k for k, v in finance_groups.items() if "model_inputs" in v]
                finance_groups_config = {"finance_groups": finance_groups}
                self.create_custom_models(
                    finance_groups_config,
                    self.plant_parent_path,
                    finance_model_names,
                    prefix="finance_",
                )

    def create_site_model(self):
        site_group = om.Group()

        # Create a site-level component
        site_config = self.plant_config.get("site", {})
        site_component = om.IndepVarComp()
        site_component.add_output("latitude", val=site_config.get("latitude", 0.0), units="deg")
        site_component.add_output("longitude", val=site_config.get("longitude", 0.0), units="deg")
        site_component.add_output("elevation_m", val=site_config.get("elevation_m", 0.0), units="m")

        # Add boundaries if they exist
        site_config = self.plant_config.get("site", {})
        boundaries = site_config.get("boundaries", [])
        for i, boundary in enumerate(boundaries):
            site_component.add_output(f"boundary_{i}_x", val=np.array(boundary.get("x", [])))
            site_component.add_output(f"boundary_{i}_y", val=np.array(boundary.get("y", [])))

        site_group.add_subsystem("site_component", site_component, promotes=["*"])

        # Add the site resource components
        if "resources" in site_config:
            for resource_name, resource_config in site_config["resources"].items():
                resource_model = resource_config.get("resource_model")
                resource_inputs = resource_config.get("resource_parameters")
                resource_class = self.supported_models.get(resource_model)
                if resource_class:
                    resource_component = resource_class(
                        plant_config=self.plant_config,
                        resource_config=resource_inputs,
                        driver_config=self.driver_config,
                    )
                    site_group.add_subsystem(
                        resource_name, resource_component, promotes_inputs=["latitude", "longitude"]
                    )

        self.model.add_subsystem("site", site_group)

    def create_plant_model(self):
        """
        Create the plant-level model.

        This method creates an OpenMDAO group that contains all the technologies.
        It uses the plant configuration but not the driver or technology configuration.

        Information at this level might be used by any technology and info stored here is
        the same for each technology. This includes site information, project parameters,
        control strategy, and finance parameters.
        """
        plant_group = om.Group()

        # Create the plant model group and add components
        self.plant = self.model.add_subsystem("plant", plant_group, promotes=["*"])

    def create_technology_models(self):
        # Loop through each technology and instantiate an OpenMDAO object (assume it exists)
        # for each technology

        self.tech_names = []
        self.performance_models = []
        self.control_strategies = []
        self.dispatch_rule_sets = []
        self.cost_models = []
        self.finance_models = []

        combined_performance_and_cost_models = ["hopp", "h2_storage", "wombat", "iron"]

        if any(tech == "site" for tech in self.technology_config["technologies"]):
            msg = (
                "'site' is an invalid technology name and is reserved for top-level "
                "variables. Please change the technology name to something else."
            )
            raise NameError(msg)

        # Create a technology group for each technology
        for tech_name, individual_tech_config in self.technology_config["technologies"].items():
            perf_model = individual_tech_config.get("performance_model", {}).get("model")

            if "control_parameters" in individual_tech_config["model_inputs"]:
                if "tech_name" in individual_tech_config["model_inputs"]["control_parameters"]:
                    provided_tech_name = individual_tech_config["model_inputs"][
                        "control_parameters"
                    ]["tech_name"]
                    if tech_name != provided_tech_name:
                        raise ValueError(
                            f"tech_name in control_parameters ({provided_tech_name}) must match "
                            f"the top-level name of the tech group ({tech_name})"
                        )

            if perf_model is not None and "feedstock" in perf_model:
                comp = self.supported_models[perf_model](
                    driver_config=self.driver_config,
                    plant_config=self.plant_config,
                    tech_config=individual_tech_config,
                )
                self.plant.add_subsystem(f"{tech_name}_source", comp)
            else:
                tech_group = self.plant.add_subsystem(tech_name, om.Group())
                self.tech_names.append(tech_name)

                # Check if performance, cost, and finance models are the same
                # and in combined_performance_and_cost_models
                perf_model = individual_tech_config.get("performance_model", {}).get("model")
                cost_model = individual_tech_config.get("cost_model", {}).get("model")
                individual_tech_config.get("finance_model", {}).get("model")
                if (
                    perf_model
                    and (perf_model == cost_model)
                    and (perf_model in combined_performance_and_cost_models)
                ):
                    # Catch dispatch rules for systems that have the same performance & cost models
                    if "dispatch_rule_set" in individual_tech_config:
                        control_object = self._process_model(
                            "dispatch_rule_set", individual_tech_config, tech_group
                        )
                        self.control_strategies.append(control_object)

                    # Catch control models for systems that have the same performance & cost models
                    if "control_strategy" in individual_tech_config:
                        control_object = self._process_model(
                            "control_strategy", individual_tech_config, tech_group
                        )
                        self.control_strategies.append(control_object)

                    comp = self.supported_models[perf_model](
                        driver_config=self.driver_config,
                        plant_config=self.plant_config,
                        tech_config=individual_tech_config,
                    )
                    om_model_object = tech_group.add_subsystem(tech_name, comp, promotes=["*"])
                    self.performance_models.append(om_model_object)
                    self.cost_models.append(om_model_object)
                    self.finance_models.append(om_model_object)

                    continue

                # Process the models
                # TODO: integrate financial_model into the loop below
                model_types = [
                    "dispatch_rule_set",
                    "control_strategy",
                    "performance_model",
                    "cost_model",
                ]

                for model_type in model_types:
                    if model_type in individual_tech_config:
                        om_model_object = self._process_model(
                            model_type, individual_tech_config, tech_group
                        )
                        if "control_strategy" in model_type:
                            plural_model_type_name = "control_strategies"
                        else:
                            plural_model_type_name = model_type + "s"
                        getattr(self, plural_model_type_name).append(om_model_object)

                # Process the finance models
                if "finance_model" in individual_tech_config:
                    if "model" in individual_tech_config["finance_model"]:
                        finance_name = individual_tech_config["finance_model"]["model"]

                        if finance_name != individual_tech_config.get("cost_model", {}).get(
                            "model", ""
                        ):
                            finance_object = self.supported_models[finance_name]
                            tech_group.add_subsystem(
                                f"{tech_name}_finance",
                                finance_object(
                                    driver_config=self.driver_config,
                                    plant_config=self.plant_config,
                                    tech_config=individual_tech_config,
                                ),
                                promotes=["*"],
                            )
                            self.finance_models.append(finance_object)

        for tech_name, individual_tech_config in self.technology_config["technologies"].items():
            cost_model = individual_tech_config.get("cost_model", {}).get("model")
            if cost_model is not None and "feedstock" in cost_model:
                comp = self.supported_models[cost_model](
                    driver_config=self.driver_config,
                    plant_config=self.plant_config,
                    tech_config=individual_tech_config,
                )
                self.plant.add_subsystem(tech_name, comp)

    def _process_model(self, model_type, individual_tech_config, tech_group):
        # Generalized function to process model definitions
        model_name = individual_tech_config[model_type]["model"]
        model_object = self.supported_models[model_name]
        om_model_object = tech_group.add_subsystem(
            model_name,
            model_object(
                driver_config=self.driver_config,
                plant_config=self.plant_config,
                tech_config=individual_tech_config,
            ),
            promotes=["*"],
        )
        return om_model_object

    def create_finance_model(self):
        """
        Create and configure the finance model(s) for the plant.

        This method initializes finance subsystems for the plant based on the
        configuration provided in ``self.plant_config["finance_parameters"]``. It
        supports both default (single-model) setups and multiple/distinct (subgroup-specific)
        finance models.

        Within this framework, a finance subgroup serves as a flexible grouping mechanism for
        calculating finance metrics across different subsets of technologies.
        These groupings can draw on varying finance inputs or models within the same simulation.
        To support a wide range of use cases, such as evaluating metrics for only part of a larger
        system, finance subgroups may reference multiple finance_groups and may overlap
        partially or fully with the technologies included in other finance subgroups.

        Behavior:
            * If ``finance_parameters`` is not defined in the plant configuration,
            no finance model is created.
            * If no subgroups are defined, all technologies are grouped together
            under a default finance group. ``commodity`` and ``finance_model`` are
            required in this case.
            * If subgroups are provided, each subgroup defines its own set of
            technologies, associated commodity, and finance model(s).
            Each subgroup is nested under a unique name of your choice under
            ["finance_parameters"]["subgroups"] in the plant configuration.
            * Subsystems such as ``ElectricitySumComp``, ``AdjustedCapexOpexComp``,
            ``GenericProductionSummerPerformanceModel``, and the selected finance
            models are added to each subgroup's finance group.
            * If `commodity_stream` is provided for a subgroup, the output of the
            technology specified as the `commodity_stream` must be the same as the
            specified commodity for that subgroup.
            * Supports both global finance models and technology-specific finance
            models. Technology-specific finance models are defined in the technology
            configuration.

        Raises:
            ValueError:
                If ["finance_parameters"]["finance_group"] is incomplete (e.g., missing
                ``commodity`` or ``finance_model``) when no subgroups are defined.
            ValueError:
                If a subgroup has an invalid technology.
            ValueError:
                If a specified finance model is not found in
                ``self.supported_models``.

        Side Effects:
            * Updates ``self.plant_config["finance_parameters"]["finance_group"] if only a single
            finance model is provided (wraps it in a default finance subgroup).
            * Constructs and attaches OpenMDAO finance subsystem groups to the
            plant model under names ``finance_subgroup_<subgroup_name>``.
            * Stores processed subgroup configurations in
            ``self.finance_subgroups``.

        Example:
            Suppose ``plant_config["finance_parameters"]["finance_group"]`` defines a single finance
            model without subgroups:

            >>> self.plant_config["finance_parameters"]["finance_group"] = {
            ...     "commodity": "hydrogen",
            ...     "finance_model": "ProFastComp",
            ...     "model_inputs": {"discount_rate": 0.08},
            ... }
            >>> self.create_finance_model()
            # Creates a default subgroup containing all technologies and
            # attaches a ProFAST finance model component to the plant.

        """
        # if there aren't any finance parameters don't setup a finance model
        if "finance_parameters" not in self.plant_config:
            return

        subgroups = self.plant_config["finance_parameters"].get("finance_subgroups", None)

        if "finance_groups" not in self.plant_config["finance_parameters"]:
            raise ValueError("plant_config['finance_parameters'] must define 'finance_groups'.")

        finance_subgroups = {}

        default_finance_group_name = "default"
        # only one finance model is being used with subgroups
        if (
            "finance_model" in self.plant_config["finance_parameters"]["finance_groups"]
            and "model_inputs" in self.plant_config["finance_parameters"]["finance_groups"]
        ):
            if (
                default_finance_group_name
                in self.plant_config["finance_parameters"]["finance_groups"]
            ):
                # throw an error if the user has an unused finance group named "default".
                msg = (
                    "Invalid key `default` in "
                    "plant_config['finance_parameters']['finance_groups']. "
                    "Please rename the `default` key to something else or remove it. "
                    "The name `default` will be used to reference the finance model group."
                )
                raise ValueError(msg)
            default_model_name = self.plant_config["finance_parameters"]["finance_groups"].pop(
                "finance_model"
            )
            default_model_inputs = self.plant_config["finance_parameters"]["finance_groups"].pop(
                "model_inputs"
            )
            default_model_dict = {
                default_finance_group_name: {
                    "finance_model": default_model_name,
                    "model_inputs": default_model_inputs,
                }
            }
            self.plant_config["finance_parameters"]["finance_groups"].update(default_model_dict)

        if subgroups is None:
            # --- Default behavior ---
            commodity = self.plant_config["finance_parameters"]["finance_groups"].get("commodity")
            finance_model_name = (
                self.plant_config["finance_parameters"]["finance_groups"]
                .get(default_finance_group_name, {})
                .get("finance_model")
            )

            if not commodity or not finance_model_name:
                raise ValueError(
                    "plant_config['finance_parameters']['finance_groups'] "
                    "must define 'commodity' and 'finance_model' "
                    "if no finance_subgroups are provided."
                )

            # Collect all technologies into one subgroup
            all_techs = list(self.technology_config["technologies"].keys())
            subgroup = {
                "commodity": commodity,
                "finance_groups": [default_finance_group_name],
                "technologies": all_techs,
            }
            subgroups = {default_finance_group_name: subgroup}

        # --- Normal subgroup handling ---
        for subgroup_name, subgroup_params in subgroups.items():
            commodity = subgroup_params.get("commodity", None)
            commodity_desc = subgroup_params.get("commodity_desc", "")
            finance_group_names = subgroup_params.get(
                "finance_groups", [default_finance_group_name]
            )
            tech_names = subgroup_params.get("technologies")
            commodity_stream = subgroup_params.get("commodity_stream", None)

            if isinstance(finance_group_names, str):
                finance_group_names = [finance_group_names]

            # check commodity type
            if commodity is None:
                raise ValueError(
                    f"Required parameter ``commodity`` not provided in subgroup {subgroup_name}."
                )

            tech_configs = {}
            for tech in tech_names:
                if tech in self.technology_config["technologies"]:
                    tech_configs[tech] = self.technology_config["technologies"][tech]
                else:
                    raise KeyError(
                        f"Technology '{tech}' not found in the technology configuration, "
                        f"but is listed in subgroup '{subgroup_name}', "
                        "Available "
                        f"technologies: {list(self.technology_config['technologies'].keys())}"
                    )
            if commodity_stream is not None:
                if "combiner" not in commodity_stream and commodity_stream not in tech_names:
                    raise UserWarning(
                        f"The technology specific for the commodity_stream '{commodity_stream}' "
                        f"is not included in subgroup '{subgroup_name}' technologies list."
                        f" Subgroup '{subgroup_name}' includes technologies: {tech_names}."
                    )

            finance_subgroups.update(
                {
                    subgroup_name: {
                        "tech_configs": tech_configs,
                        "commodity": commodity,
                        "commodity_stream": commodity_stream,
                    }
                }
            )
            finance_subgroup = om.Group()

            # if commodity stream is specified, then create use the "summer" model
            # to sum the commodity production profile from the commodity stream
            if commodity_stream is not None:
                # get the generic summer model
                commodity_summer_model = self.supported_models.get("summer")
                if "combiner" in commodity_stream or "splitter" in commodity_stream:
                    # combiners and splitters have the same tech config as the production summer,
                    # so just use their config if the commodity stream is a combiner or splitter
                    commodity_summer_config = self.technology_config["technologies"][
                        commodity_stream
                    ]
                else:
                    # create the input dictionary for the production summer based
                    # on the commodity type
                    commodity_summer_config = {
                        "model_inputs": {
                            "performance_parameters": {
                                "commodity": commodity,
                                "commodity_units": "kW" if commodity == "electricity" else "kg/h",
                            }
                        }
                    }
                # create the commodity production summer model
                commodity_summer = commodity_summer_model(
                    driver_config=self.driver_config,
                    plant_config=self.plant_config,
                    tech_config=commodity_summer_config,
                )
                # add the production summer as a subsystem
                finance_subgroup.add_subsystem(f"{commodity}_sum", commodity_summer)

            if commodity_stream is None and commodity == "electricity":
                finance_subgroup.add_subsystem(
                    "electricity_sum", ElectricitySumComp(tech_configs=tech_configs)
                )

            # Add adjusted capex/opex
            adjusted_capex_opex_comp = AdjustedCapexOpexComp(
                driver_config=self.driver_config,
                tech_configs=tech_configs,
                plant_config=self.plant_config,
            )

            finance_subgroup.add_subsystem(
                "adjusted_capex_opex_comp", adjusted_capex_opex_comp, promotes=["*"]
            )

            for finance_group_name in finance_group_names:
                # check if using tech-specific finance model
                if any(
                    tech_name == finance_group_name
                    for tech_name, tech_params in tech_configs.items()
                ):
                    tech_finance_group_name = (
                        tech_configs.get(finance_group_name).get("finance_model", {}).get("model")
                    )

                    # this is created in create_technologies()
                    if tech_finance_group_name is not None:
                        # tech specific finance models are created in create_technologies()
                        # and do not need to be included in the general finance models
                        continue

                # if not using a tech-specific finance group, get the finance model and inputs for
                # the finance model group specified by finance_group_name
                finance_group_config = self.plant_config["finance_parameters"][
                    "finance_groups"
                ].get(finance_group_name)
                model_name = finance_group_config.get("finance_model")  # finance model
                fin_model_inputs = finance_group_config.get(
                    "model_inputs"
                )  # inputs to finance model

                # get finance model component definition
                fin_model = self.supported_models.get(model_name)

                if fin_model is None:
                    raise ValueError(f"finance model '{model_name}' not found.")

                # filter the plant_config so the finance_parameters only includes data for
                # this finance model group

                # first, grab information from the plant config, except the finance parameters
                filtered_plant_config = {
                    k: v for k, v in self.plant_config.items() if k != "finance_parameters"
                }

                # then, reformat the finance_parameters to only include inputs for the
                # finance group specified by finance_group_name
                filtered_plant_config.update(
                    {
                        "finance_parameters": {
                            "finance_model": model_name,  # unused by the finance model
                            "model_inputs": fin_model_inputs,  # inputs for finance model
                        }
                    }
                )

                commodity_desc = subgroup_params.get("commodity_desc", "")
                commodity_output_desc = subgroup_params.get("commodity_desc", "")

                # check if multiple finance models are specified for the subgroup
                if len(finance_group_names) > 1:
                    # check that the finance model groups do not include tech-specific finances
                    non_tech_finances = [
                        k
                        for k in finance_group_names
                        if k in self.plant_config["finance_parameters"]["finance_groups"]
                    ]

                    # if multiple non-tech specific finance model groups are specified for the
                    # subgroup, the outputs of the finance model must have unique names to
                    # avoid errors.
                    if len(non_tech_finances) > 1:
                        # finance models name their outputs based on the description and commodity
                        # update the description to include the finance model name to ensure
                        # uniquely named outputs
                        commodity_output_desc = commodity_output_desc + f"_{finance_group_name}"

                # create the finance component
                fin_comp = fin_model(
                    driver_config=self.driver_config,
                    tech_config=tech_configs,
                    plant_config=filtered_plant_config,
                    commodity_type=commodity,
                    description=commodity_output_desc,
                )

                # name the finance component based on the commodity and description
                finance_subsystem_name = (
                    f"{commodity}_finance_{finance_group_name}"
                    if commodity_desc == ""
                    else f"{commodity}_{commodity_desc}_finance_{finance_group_name}"
                )

                # add the finance component to the finance group
                finance_subgroup.add_subsystem(finance_subsystem_name, fin_comp, promotes=["*"])

            # add the finance group to the subgroup
            self.plant.add_subsystem(f"finance_subgroup_{subgroup_name}", finance_subgroup)

        self.finance_subgroups = finance_subgroups

    def connect_technologies(self):
        technology_interconnections = self.plant_config.get("technology_interconnections", [])

        combiner_counts = {}
        splitter_counts = {}

        # loop through each linkage and instantiate an OpenMDAO object (assume it exists) for
        # the connection type (e.g. cable, pipeline, etc)
        for connection in technology_interconnections:
            if len(connection) == 4:
                source_tech, dest_tech, transport_item, transport_type = connection

                if transport_type in self.tech_names:
                    # if the transport type is already a technology, skip creating a new component
                    connection_name = f"{transport_type}"
                else:
                    # make the connection_name based on source, dest, item, type
                    connection_name = f"{source_tech}_to_{dest_tech}_{transport_type}"

                # Get the performance model of the source_tech
                source_tech_config = self.technology_config["technologies"].get(source_tech, {})
                perf_model_name = source_tech_config.get("performance_model", {}).get("model")
                cost_model_name = source_tech_config.get("cost_model", {}).get("model")

                # If the source is a feedstock, make sure to connect the amount of
                # feedstock consumed from the technology back to the feedstock cost model
                if cost_model_name is not None and "feedstock" in cost_model_name:
                    self.plant.connect(
                        f"{dest_tech}.{transport_item}_consumed",
                        f"{source_tech}.{transport_item}_consumed",
                    )

                if perf_model_name is not None and "feedstock" in perf_model_name:
                    source_tech = f"{source_tech}_source"

                # Create the transport object
                # allow transport_type to be from self.tech_name
                if transport_type in self.tech_names:
                    # Connect the connection component to the destination technology
                    pass
                else:
                    connection_component = self.supported_models[transport_type](
                        transport_item=transport_item
                    )

                    # Add the connection component to the model
                    self.plant.add_subsystem(connection_name, connection_component)

                # Check if the source technology is a splitter
                if "splitter" in source_tech:
                    # Connect the source technology to the connection component
                    # with specific output names
                    if source_tech not in splitter_counts:
                        splitter_counts[source_tech] = 1
                    else:
                        splitter_counts[source_tech] += 1

                    # Connect the splitter output to the connection component
                    self.plant.connect(
                        f"{source_tech}.{transport_item}_out{splitter_counts[source_tech]}",
                        f"{connection_name}.{transport_item}_in",
                    )

                elif "storage" in source_tech:
                    # Connect the source technology to the connection component
                    self.plant.connect(
                        f"{source_tech}.{transport_item}_out",
                        f"{connection_name}.{transport_item}_in",
                    )
                else:
                    # Connect the source technology to the connection component
                    self.plant.connect(
                        f"{source_tech}.{transport_item}_out",
                        f"{connection_name}.{transport_item}_in",
                    )

                # Check if the transport type is a combiner
                if "combiner" in dest_tech:
                    # Connect the source technology to the connection component
                    # with specific input names
                    if dest_tech not in combiner_counts:
                        combiner_counts[dest_tech] = 1
                    else:
                        combiner_counts[dest_tech] += 1

                    # Connect the connection component to the destination technology
                    self.plant.connect(
                        f"{connection_name}.{transport_item}_out",
                        f"{dest_tech}.{transport_item}_in{combiner_counts[dest_tech]}",
                    )

                elif "storage" in dest_tech:
                    # Connect the connection component to the destination technology
                    self.plant.connect(
                        f"{connection_name}.{transport_item}_out",
                        f"{dest_tech}.{transport_item}_in",
                    )

                else:
                    # Connect the connection component to the destination technology
                    self.plant.connect(
                        f"{connection_name}.{transport_item}_out",
                        f"{dest_tech}.{transport_item}_in",
                    )

            elif len(connection) == 3:
                # connect directly from source to dest
                source_tech, dest_tech, connected_parameter = connection
                if isinstance(connected_parameter, (tuple, list)):
                    source_parameter, dest_parameter = connected_parameter
                    self.plant.connect(
                        f"{source_tech}.{source_parameter}", f"{dest_tech}.{dest_parameter}"
                    )
                else:
                    self.plant.connect(
                        f"{source_tech}.{connected_parameter}", f"{dest_tech}.{connected_parameter}"
                    )

            else:
                err_msg = f"Invalid connection: {connection}"
                raise ValueError(err_msg)

        resource_to_tech_connections = self.plant_config.get("resource_to_tech_connections", [])

        resource_models = self.plant_config.get("site", {}).get("resources", {})
        resource_source_connections = [c[0] for c in resource_to_tech_connections]
        # Check if there is a missing resource to tech connection or missing resource model
        if len(resource_models) != len(resource_source_connections):
            if len(resource_models) > len(resource_source_connections):
                # more resource models than resources connected to technologies
                non_connected_resource = [
                    k for k in resource_models if k not in resource_source_connections
                ]
                # check if theres a resource model that isn't connected to a technology
                if len(non_connected_resource) > 0:
                    msg = (
                        "Some resources are not connected to a technology. Resource models "
                        f"{non_connected_resource} are not included in "
                        "`resource_to_tech_connections`. Please connect these resources "
                        "to their technologies under `resource_to_tech_connections` in "
                        "the plant config file."
                    )
                    raise ValueError(msg)
            if len(resource_source_connections) > len(resource_models):
                # more resources connected than resource models
                missing_resource = [
                    k for k in resource_source_connections if k not in resource_models
                ]
                # check if theres a resource model that isn't connected to a technology
                if len(missing_resource) > 0:
                    msg = (
                        "Missing resource(s) are not defined but are connected to a technology. "
                        f"Missing resource(s) are {missing_resource}. "
                        "Please check ``resource_to_tech_connections`` in the plant config file "
                        "or add the missing resources"
                        " to plant_config['site']['resources']."
                    )
                    raise ValueError(msg)

        for connection in resource_to_tech_connections:
            if len(connection) != 3:
                err_msg = f"Invalid resource to tech connection: {connection}"
                raise ValueError(err_msg)

            resource_name, tech_name, variable = connection

            # Connect the resource output to the technology input
            self.model.connect(f"site.{resource_name}.{variable}", f"{tech_name}.{variable}")

        # connect outputs of the technology models to the cost and finance models of the
        # same name if the cost and finance models are not None
        if "finance_parameters" in self.plant_config:
            # Connect the outputs of the technology models to the appropriate finance groups
            for group_id, group_configs in self.finance_subgroups.items():
                tech_configs = group_configs.get("tech_configs")
                primary_commodity_type = group_configs.get("commodity")
                commodity_stream = group_configs.get("commodity_stream")

                if commodity_stream is not None:
                    # connect commodity stream output to summer input
                    self.plant.connect(
                        f"{commodity_stream}.{primary_commodity_type}_out",
                        f"finance_subgroup_{group_id}.{primary_commodity_type}_sum.{primary_commodity_type}_in",
                    )
                    # NOTE: this wont be compatible with co2 in the finance models
                    # because its expected to have a different name
                    # connect summer output to finance model
                    self.plant.connect(
                        f"finance_subgroup_{group_id}.{primary_commodity_type}_sum.total_{primary_commodity_type}_produced",
                        f"finance_subgroup_{group_id}.total_{primary_commodity_type}_produced",
                    )

                # if commodity stream was not specified, follow existing logic
                else:
                    plant_producing_electricity = False

                    # Loop through technologies and connect electricity outputs to the ExecComp
                    # Only connect if the technology is included in at least one commodity's stackup
                    # and in this finance group
                    for tech_name in tech_configs.keys():
                        if (
                            is_electricity_producer(tech_name)
                            and primary_commodity_type == "electricity"
                        ):
                            self.plant.connect(
                                f"{tech_name}.electricity_out",
                                f"finance_subgroup_{group_id}.electricity_sum.electricity_{tech_name}",
                            )
                            plant_producing_electricity = True

                    if plant_producing_electricity and primary_commodity_type == "electricity":
                        # Connect total electricity produced to the finance group
                        self.plant.connect(
                            f"finance_subgroup_{group_id}.electricity_sum.total_electricity_produced",
                            f"finance_subgroup_{group_id}.total_electricity_produced",
                        )

                # Only connect technologies that are included in the finance stackup
                for tech_name in tech_configs.keys():
                    # For now, assume splitters and combiners do not add any costs
                    if "splitter" in tech_name or "combiner" in tech_name:
                        continue

                    self.plant.connect(
                        f"{tech_name}.CapEx",
                        f"finance_subgroup_{group_id}.capex_{tech_name}",
                    )
                    self.plant.connect(
                        f"{tech_name}.OpEx", f"finance_subgroup_{group_id}.opex_{tech_name}"
                    )
                    self.plant.connect(
                        f"{tech_name}.VarOpEx", f"finance_subgroup_{group_id}.varopex_{tech_name}"
                    )
                    self.plant.connect(
                        f"{tech_name}.cost_year",
                        f"finance_subgroup_{group_id}.cost_year_{tech_name}",
                    )

                    if "electrolyzer" in tech_name:
                        self.plant.connect(
                            f"{tech_name}.time_until_replacement",
                            f"finance_subgroup_{group_id}.{tech_name}_time_until_replacement",
                        )

                    if commodity_stream is None:
                        if "electrolyzer" in tech_name:
                            if primary_commodity_type == "hydrogen":
                                self.plant.connect(
                                    f"{tech_name}.total_hydrogen_produced",
                                    f"finance_subgroup_{group_id}.total_hydrogen_produced",
                                )

                        if "geoh2" in tech_name:
                            if primary_commodity_type == "hydrogen":
                                self.plant.connect(
                                    f"{tech_name}.total_hydrogen_produced",
                                    f"finance_subgroup_{group_id}.total_hydrogen_produced",
                                )

                        if "ammonia" in tech_name and primary_commodity_type == "ammonia":
                            self.plant.connect(
                                f"{tech_name}.total_ammonia_produced",
                                f"finance_subgroup_{group_id}.total_ammonia_produced",
                            )

                        if (
                            "doc" in tech_name or "oae" in tech_name
                        ) and primary_commodity_type == "co2":
                            self.plant.connect(
                                f"{tech_name}.co2_capture_mtpy",
                                f"finance_subgroup_{group_id}.co2_capture_kgpy",
                            )

                    if "methanol" in tech_name and primary_commodity_type == "methanol":
                        self.plant.connect(
                            f"{tech_name}.total_methanol_produced",
                            f"finance_subgroup_{group_id}.total_methanol_produced",
                        )

                    if "air_separator" in tech_name and primary_commodity_type == "nitrogen":
                        self.plant.connect(
                            f"{tech_name}.total_nitrogen_produced",
                            f"finance_subgroup_{group_id}.total_nitrogen_produced",
                        )

        self.plant.options["auto_order"] = True

        # Check if there are any loops in the technology interconnections
        # If loops are present, add solvers to resolve the coupling
        # Create a directed graph from the technology interconnections
        G = nx.DiGraph()
        for connection in technology_interconnections:
            source = connection[0]
            destination = connection[1]
            G.add_edge(source, destination)

        # Check if there are any cycles (loops) in the graph
        if list(nx.simple_cycles(G)):
            # If cycles are found, set solvers for the plant to resolve the coupling
            self.plant.nonlinear_solver = om.NonlinearBlockGS()
            self.plant.linear_solver = om.DirectSolver()

        # initialize dispatch rules connection list
        tech_to_dispatch_connections = self.plant_config.get("tech_to_dispatch_connections", [])

        for connection in tech_to_dispatch_connections:
            if len(connection) != 2:
                err_msg = f"Invalid tech to dispatching_tech_name connection: {connection}"
                raise ValueError(err_msg)

            tech_name, dispatching_tech_name = connection

            if tech_name == dispatching_tech_name:
                continue
            else:
                # Connect the dispatch rules output to the dispatching_tech_name input
                self.model.connect(
                    f"{tech_name}.dispatch_block_rule_function",
                    f"{dispatching_tech_name}.dispatch_block_rule_function_{tech_name}",
                )

        if (pyxdsm is not None) and (len(technology_interconnections) > 0):
            try:
                create_xdsm_from_config(self.plant_config)
            except FileNotFoundError as e:
                print(f"Unable to create system XDSM diagram. Error: {e}")

    def create_driver_model(self):
        """
        Add the driver to the OpenMDAO model and add recorder.
        """

        myopt = PoseOptimization(self.driver_config)
        if "driver" in self.driver_config:
            myopt.set_driver(self.prob)
            myopt.set_objective(self.prob)
            myopt.set_design_variables(self.prob)
            myopt.set_constraints(self.prob)
        # Add a recorder if specified in the driver config
        if "recorder" in self.driver_config:
            self.recorder_path = myopt.set_recorders(self.prob)

    def setup(self):
        """
        Extremely light wrapper to setup the OpenMDAO problem and track setup status.
        """
        self.setup_has_been_called = True
        self.prob.setup()

    def run(self):
        # do model setup based on the driver config
        # might add a recorder, driver, set solver tolerances, etc
        if not self.setup_has_been_called:
            self.prob.setup()
            self.setup_has_been_called = True

        self.prob.run_driver()

    def post_process(self, summarize_sql=False, show_plots=False):
        """
        Post-process the results of the OpenMDAO model.

        Right now, this means printing the inputs and outputs to all systems in the model.
        We currently exclude any variables with "resource_data" in the name, since those
        are large dictionary variables that are not correctly formatted when printing.

        If `summarize_sql` is set to True and a recorder file was written, the results
        in the recorder file will be summarized and saved as a .csv file.

        Also, if `show_plots` is set to True, then any performance models with post-processing
        plots available will be run and shown.
        """
        # Use custom summary printer instead of OpenMDAO's built-in printing so we can
        # suppress internal value printing and display only mean values.
        print_results(self.prob.model, excludes=["*resource_data"])

        if summarize_sql and self.recorder_path is not None:
            convert_sql_to_csv_summary(self.recorder_path, save_to_file=True)

        for model in self.performance_models:
            if hasattr(model, "post_process") and callable(model.post_process):
                model.post_process(show_plots=show_plots)
                if show_plots:
                    plt.show()
