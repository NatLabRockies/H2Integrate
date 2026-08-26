import re
import importlib.util
from enum import IntEnum

import numpy as np
import networkx as nx
import openmdao.api as om

from h2integrate.core.utilities import create_xdsm_from_config
from h2integrate.core.dict_utils import check_inputs
from h2integrate.core.file_utils import get_path, find_file, load_yaml
from h2integrate.core.supported_models import (
    no_cost_models,
    supported_models,
    no_replacement_schedule_models,
)
from h2integrate.core.commodity_stream_definitions import multivariable_streams
from h2integrate.control.control_strategies.passthrough_controller import PassthroughController
from h2integrate.control.control_strategies.system_level.solver_options import (
    SLCSolverOptionsConfig,
)
from h2integrate.control.control_strategies.system_level.system_level_control_base import (
    _get_tech_buy_price_input_name,
)


class State(IntEnum):
    INITIALIZED = 0
    SETUP = 1
    RUN = 2
    POST_PROCESS = 3


class H2IntegrateModel:
    def __init__(self, config_input):
        # read in config file; it's a yaml dict that looks like this:
        self.load_config(config_input)

        # add bool for whether using system-level control
        self.slc = False
        if "system_level_control" in self.plant_config:
            self.slc = True

        # create technology connection graph based on technology interconnections
        # defined in plant config
        self.technology_graph = self.create_technology_graph(
            self.plant_config.get("technology_interconnections", {})
        )

        # load in supported models
        self.supported_models = supported_models.copy()

        # load custom models
        self.collect_custom_models()

        # Check if create_om_reports is specified in driver config
        create_om_reports = self.driver_config.get("general", {}).get("create_om_reports", True)
        self.prob = om.Problem(reports=create_om_reports)
        self.model = self.prob.model

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

        # add system-level controller if configured
        if self.slc:
            slc_topology = self._classify_slc_technologies()
            self.add_system_level_controller(slc_topology)

        # connect technologies
        # technologies are connected within the `technology_interconnections` section of the
        # plant config
        self.connect_technologies()

        # create driver model
        # might be an analysis or optimization
        self.create_driver_model()

        self.state = State.INITIALIZED

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

        This method loads the main configuration and the component configuration files
        (driver, technology, and plant). Each configuration can be provided either as
        a dictionary or as a file path. When file paths are provided, the method
        resolves them using multiple search strategies.

        Args:
            config_input (dict | str | Path): Main configuration containing references to
                driver, technology, and plant configurations. This can be:

                - A dictionary containing the configuration data directly.
                - A string or Path pointing to a YAML file containing the configuration.

        Behavior:

            - If ``config_input`` is a dict, uses it directly as the main configuration.
            - If ``config_input`` is a path, uses ``get_path()`` to resolve and load the YAML
              file from multiple search locations (absolute path, relative to CWD, relative to
              the H2Integrate package).
            - For component configs provided as dicts, validates them directly using
              ``load_driver_yaml``, ``load_tech_yaml``, and ``load_plant_yaml``.
            - For component configs provided as paths and a file-based main config, uses
              ``find_file()`` to search relative to the main config directory first, then
              falls back to other search locations (CWD, H2Integrate package, glob patterns).
            - For component configs provided as paths and a dict-based main config, uses
              ``get_path()`` with standard search locations (absolute, CWD, H2Integrate package).

        Sets:
            self.name (str): Name of the system from main config.
            self.system_summary (str): Summary description from main config.
            self.driver_config (dict): Validated driver configuration.
            self.technology_config (dict): Validated technology configuration.
            self.plant_config (dict): Validated plant configuration.
            self.driver_config_path (Path | None): Path to driver config file (None if dict).
            self.tech_config_path (Path | None): Path to technology config file (None if dict).
            self.plant_config_path (Path | None): Path to plant config file (None if dict).
            self.tech_parent_path (Path | None): Parent directory of technology config file.
            self.plant_parent_path (Path | None): Parent directory of plant config file.

        Note:
            The parent path attributes (``tech_parent_path``, ``plant_parent_path``) are used
            later to resolve relative paths to custom models and other referenced files within
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
        from h2integrate.core.inputs.validation import (
            load_tech_yaml,
            load_plant_yaml,
            load_driver_yaml,
        )

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

        for name, vals in self.technology_config["technologies"].items():
            if "control_strategy" in vals:
                controller_model_name = vals["control_strategy"]["model"]
                controller_cls = supported_models.get(controller_model_name)
                if controller_cls is not None:
                    from h2integrate.control.control_strategies.pyomo_storage_controller_baseclass import (  # noqa: E501
                        PyomoStorageControllerBaseClass,
                    )

                    if issubclass(controller_cls, PyomoStorageControllerBaseClass):
                        model_inputs = self.technology_config["technologies"][name]["model_inputs"]
                        if (
                            "control_parameters" not in model_inputs
                            or model_inputs["control_parameters"] is None
                        ):
                            model_inputs["control_parameters"] = {"tech_name": name}
                        else:
                            model_inputs["control_parameters"]["tech_name"] = name

    def create_custom_models(self, model_config, config_parent_path, model_types, prefix=""):
        """This method loads custom models from the specified directory and adds them to the
        supported models dictionary.

        Args:
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
                        if (
                            model_class_name
                            != included_custom_models[model_name]["model_class_name"]
                        ):
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

                    if (model_name not in self.supported_models) and (model_name is not None):
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
                                f"Custom {prefix}model or {prefix}model_location "
                                f"specified for '{model_name}', "
                                f"but '{model_name}' is a built-in H2Integrate "
                                "model. Using built-in model instead is not allowed. "
                                f"If you want to use a custom model, please rename it "
                                "in your configuration."
                            )
                            raise ValueError(msg)

    def collect_custom_models(self):
        """Collect custom models from the technology configuration and
        system finance models found in the plant configuration.
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

        # check for custom resource models
        if "sites" in self.plant_config:
            for site_name, site_params in self.plant_config["sites"].items():
                if "resources" in site_params:
                    resource_models_config = {
                        k: v
                        for k, v in site_params["resources"].items()
                        if "resource_parameters" in v
                    }

                    resource_model_names = [
                        k for k, v in site_params["resources"].items() if "resource_parameters" in v
                    ]
                    self.create_custom_models(
                        {site_name: resource_models_config},
                        self.plant_parent_path,
                        resource_model_names,
                        prefix="resource_",
                    )

    def create_site_model(self):
        """
        Create and configure site component(s) for the system.

        This method initializes a site group for each site provided in
        ``self.plant_config["sites"]``.

        This method creates an OpenMDAO Group for each site that contains the location definition
        and resources models (if provided in the configuration) for that site.
        """
        # Loop through each site defined in the plant config
        # If no sites defined in plant_config, nothing to do
        if "sites" not in self.plant_config or not self.plant_config["sites"]:
            return
        for site_name, site_info in self.plant_config["sites"].items():
            # Reorganize the plant config to be formatted as expected by the
            # resource models
            plant_config_reorg = {
                "site": site_info,
                "plant": self.plant_config["plant"],
            }

            # Create the site group and resource models
            site_group = self.create_site_group(plant_config_reorg, site_info)

            # Add the site group to the system model
            self.model.add_subsystem(site_name, site_group)

    def create_site_group(self, plant_config_dict: dict, site_config: dict):
        """
        Create and configure a site Group for the input site configuration.

        Args:
            plant_config_dict (dict): The plant config dictionary formatted for the resource models
            site_config (dict): Information that defines each site, such as latitude,
                longitude, and resource models.

        Returns:
            om.Group: OpenMDAO group for a site
        """

        from h2integrate.core.sites import SiteLocationComponent

        # Initialize the site group
        site_group = om.Group()

        # Create a site location component (defines latitude, longitude, etc)
        site_inputs = {k: v for k, v in site_config.items() if k != "resources"}
        site_component = SiteLocationComponent(site_inputs)

        site_group.add_subsystem("site_component", site_component, promotes=["*"])

        # Add the site resource components
        if "resources" in site_config:
            for resource_name, resource_config in site_config["resources"].items():
                resource_model = resource_config.get("resource_model")
                resource_inputs = resource_config.get("resource_parameters")
                resource_class = self.supported_models.get(resource_model)
                if resource_class:
                    resource_component = resource_class(
                        plant_config=plant_config_dict,
                        resource_config=resource_inputs,
                        driver_config=self.driver_config,
                    )
                    site_group.add_subsystem(
                        resource_name, resource_component, promotes_inputs=["latitude", "longitude"]
                    )
        return site_group

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

    def _classify_slc_technologies(self):
        """Classify technologies for system-level control.

        Uses ``self.tech_control_classifiers`` (populated by ``create_technology_models()``)
        to partition technologies into fixed, flexible, dispatchable, and storage lists.
        Also identifies the single demand technology and its commodity.

        SLC demand is supplied by a demand component (for example,
        ``GenericDemandComponent``). When SLC is enabled, only one demand
        component is currently supported.

        Returns:
            dict: Classification dictionary (``slc_topology``) with keys:

                - ``"demand_tech"`` (str): Name of the demand technology (the tech whose
                  performance model is a ``DemandComponent``).
                - ``"demand_commodity"`` (str): Commodity the demand technology consumes
                  (e.g. ``"electricity"``, ``"hydrogen"``).
                - ``"demand_commodity_rate_units"`` (str | None): Units string for the
                  demand commodity rate (e.g. ``"kW"``, ``"kg/h"``), or ``None`` if not
                  specified in the demand tech config.
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
        """
        slc_topology = {}
        technologies = self.technology_config.get("technologies", {})

        if not (
            demand_tech := self.plant_config["system_level_control"].get("demand_component", False)
        ):
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
        tech_interconnections = self.plant_config["technology_interconnections"]
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
        upstream_techs = nx.ancestors(self.technology_graph, demand_tech)
        # only connect the technologies that are connected to the demand tech
        upstream_controllable_techs = {
            tech for tech in upstream_techs if nx.has_path(self.technology_graph, tech, demand_tech)
        }

        sources_to_commodities = set()
        for source, _, commodities in self.technology_graph.edges(data="commodity"):
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

        upstream_tech_graph = self.create_technology_graph(upstream_interconnections)
        slc_topology["technology_graph"] = upstream_tech_graph

        # downselect the technology control classifiers to only include those upstream
        # of the demand
        upstream_tech_control_classifiers = {
            k: v
            for k, v in self.tech_control_classifiers.items()
            if k in upstream_controllable_techs
        }

        # Check if storage models have a controller
        storage_tech_to_control = {}
        for tech, classifier in upstream_tech_control_classifiers.items():
            if classifier == "storage":
                control_model = (
                    self.technology_config["technologies"][tech]
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

        slc_topology["tech_control_classifiers"] = upstream_tech_control_classifiers

        return slc_topology

    def add_system_level_controller(self, slc_topology):
        """Add a system-level controller component and connect it within the plant.

        Instantiates the controller specified by ``control_strategy`` in the plant configuration,
        adds it as an OpenMDAO subsystem named ``"system_level_controller"``, configures
        solvers on the plant group to resolve the feedback loop, and creates all
        necessary OpenMDAO connections between the controller and the technology models it
        dispatches.

        The method executes in five sequential steps:

        1. **Select and instantiate the controller** - Looks up the class from
           ``supported_models`` using the ``control_strategy`` string (e.g.
           ``"DemandFollowingControl"``, ``"ProfitMaximizationControl"``). Raises ``ValueError``
           if the strategy name is not found. The instantiated component is added to
           ``self.plant`` as ``"system_level_controller"``.

        2. **Configure the plant-level nonlinear solver** - Because the controller creates a
           feedback loop (controller outputs become technology inputs, whose outputs feed back to
           the controller), a nonlinear solver is required. Solver type and options are read from
           ``plant_config["system_level_control"]["solver_options"]`` via
           ``SLCSolverOptionsConfig``. A ``DirectSolver`` is set as the linear solver and
           is largely inconsequential as we're not propagating derivatives at this time.

        3. **Connect technology outputs to controller inputs** - For each ``(tech_name,
           commodity)`` pair in ``slc_topology["tech_to_commodity"]``:

           - **Feedstock techs**: Only the commodity output
             (``{tech_name}_source.{commodity}_out``) is connected to the controller. Feedstocks
             have no demand-input connection.
           - **Fixed techs**: Only the commodity output
             (``{tech_name}.{commodity}_out``) is connected to the controller. Fixed techs
             always produce and receive no demand-input connection.
           - **Flexible / dispatchable / storage techs**: Both the commodity output
             (``{tech_name}.{commodity}_out``) and rated production
             (``{tech_name}.rated_{commodity}_production``) are connected as controller inputs.
             The controller's per-tech ``{tech_name}_{commodity}_set_point`` output is then
             connected to the tech group's ``{commodity}_set_point`` input. Every controlled
             tech group is expected to expose this input — either via a user-defined
             ``control_strategy`` or via the auto-injected ``PassthroughController`` — which
             converts the set-point signal into the appropriate performance-model command value.

        4. **Connect marginal-cost inputs for cost-aware strategies** - Only executed when
           ``control_strategy`` is ``"CostMinimizationControl"`` or
           ``"ProfitMaximizationControl"``. Additional cost-aware control strategies
           would need to be added here. For each dispatchable tech, the ``cost_per_tech``
           specification determines which cost signal is connected:

           - ``"VarOpEx"``: connects the tech's own ``VarOpEx`` output.
           - ``"feedstock"``: uses graph traversal (``nx.ancestors``) on the
             ``technology_graph`` to find all upstream feedstock technologies
             at any depth and connects each feedstock's ``VarOpEx`` output.
             This is consistent with the ``_find_feedstock_techs`` method
             used by the controller component internally.
           - ``"buy_price"``: the controller's ``{tech_name}_buy_price`` input is
             connected input-to-input to the technology's own buy-price input
             (``electricity_buy_price`` for Grid, ``price`` for Feedstock) so a
             single ``prob.set_val()`` on the tech propagates to the SLC. The
             default value still comes from the tech config.
           - Numeric scalar: no connection needed; the value is used directly as a constant
             marginal cost.

        5. **Connect the demand profile** - Connects the demand technology's output
           (``{demand_tech}.{demand_commodity}_demand_out``) to the controller's demand input
           (``system_level_controller.{demand_commodity}_demand``). This relies on the
           current SLC constraint that exactly one demand component is defined.

        Args:
            slc_topology (dict): Pre-computed dictionary produced by
                ``_classify_slc_technologies()``. Expected keys:

                - ``"demand_tech"`` (str): Name of the demand technology.
                - ``"demand_commodity"`` (str): Commodity the demand consumes.
                - ``"tech_to_commodity"`` (set[tuple[str, str]]): Set of ``(tech_name,
                  commodity)`` pairs for all controlled techs.
                - ``"tech_control_classifiers"`` (dict[str, str]): Mapping of tech name to
                  classifier (``"fixed"``, ``"flexible"``, ``"dispatchable"``, ``"storage"``,
                  ``"feedstock"``).
                - ``"storage_techs_to_control"`` (dict[str, bool]): Whether each storage tech
                  has its own sub-controller.
                - ``"technology_graph"`` (nx.DiGraph): Directed graph of technology
                  interconnections.

        Raises:
            ValueError: If ``control_strategy`` is not found in ``self.supported_models``.

        Side Effects:
            - Adds ``"system_level_controller"`` subsystem to ``self.plant``.
            - Sets ``self.plant.nonlinear_solver`` and ``self.plant.linear_solver``.
            - Creates OpenMDAO connections within ``self.plant``.
        """
        plant_slc_config = self.plant_config["system_level_control"]

        # --- Step 1: Select and instantiate the controller class ----------
        strategy_name = plant_slc_config.get("control_strategy")
        slc_cls = self.supported_models.get(strategy_name)
        if slc_cls is None:
            raise ValueError(
                f"Unknown control_strategy '{strategy_name}' in system_level_control. "
                f"Must be a valid model name in supported_models."
            )

        slc_comp = slc_cls(
            driver_config=self.driver_config,
            plant_config=self.plant_config,
            tech_config=self.technology_config,
            slc_topology=slc_topology,
        )
        self.plant.add_subsystem("system_level_controller", slc_comp)

        # --- Step 2: Configure the nonlinear solver on the plant group ----
        # The feedback loop (controller <-> technologies) requires an
        # iterative nonlinear solver to converge.
        solver_config = SLCSolverOptionsConfig.from_dict(plant_slc_config.get("solver_options", {}))
        solver_cls = solver_config.return_nonlinear_solver()
        solver = solver_cls()
        solver_options = solver_config.get_solver_options()
        for k, v in solver_options.items():
            solver.options[k] = v
        self.plant.nonlinear_solver = solver
        self.plant.linear_solver = om.DirectSolver()

        # --- Step 3: Connect technology outputs/inputs to the controller --
        for tech_to_commodity in slc_topology["tech_to_commodity"]:
            tech_name, commodity = tech_to_commodity

            if slc_topology["tech_control_classifiers"][tech_name] == "feedstock":
                # Feedstocks only provide their commodity output to the
                # controller; they receive no set-point back.
                self.plant.connect(
                    f"{tech_name}_source.{commodity}_out",
                    f"system_level_controller.{tech_name}_{commodity}_out",
                )
                continue

            if slc_topology["tech_control_classifiers"][tech_name] == "fixed":
                # Fixed techs only provide their commodity output to the
                # controller; they always produce and receive no set-point.
                self.plant.connect(
                    f"{tech_name}.{commodity}_out",
                    f"system_level_controller.{tech_name}_{commodity}_out",
                )
                continue

            # Flexible, dispatchable, and storage techs: connect their
            # commodity output and rated production as controller inputs.
            self.plant.connect(
                f"{tech_name}.{commodity}_out",
                f"system_level_controller.{tech_name}_{commodity}_out",
            )

            self.plant.connect(
                f"{tech_name}.rated_{commodity}_production",
                f"system_level_controller.{tech_name}_rated_{commodity}_production",
            )

            # Storage tech: connect the storage duration as a controller input
            if slc_topology["tech_control_classifiers"][tech_name] == "storage":
                self.plant.connect(
                    f"{tech_name}.storage_duration",
                    f"system_level_controller.{tech_name}_{commodity}_storage_duration",
                )

            # Every controlled tech group exposes a ``{commodity}_set_point``
            # input (provided by either a user-defined control_strategy or an
            # auto-injected PassthroughController). Route the SLC's per-tech
            # set-point output to that input.
            self.plant.connect(
                f"system_level_controller.{tech_name}_{commodity}_set_point",
                f"{tech_name}.{commodity}_set_point",
            )

        # --- Step 4: Connect marginal-cost inputs (cost-aware strategies) -
        if strategy_name in ("CostMinimizationControl", "ProfitMaximizationControl"):
            cost_per_tech = plant_slc_config.get("control_parameters", {}).get("cost_per_tech", {})
            technology_graph = slc_topology["technology_graph"]
            for tech_name, _ in slc_topology["tech_to_commodity"]:
                if self.tech_control_classifiers[tech_name] == "dispatchable":
                    cost_spec = cost_per_tech.get(tech_name, 0.0)
                    if cost_spec == "VarOpEx":
                        # Tech's own variable operating expenditure
                        self.plant.connect(
                            f"{tech_name}.VarOpEx",
                            f"system_level_controller.{tech_name}_VarOpEx",
                        )
                    elif cost_spec == "feedstock":
                        # Find all upstream feedstock technologies using
                        # graph traversal (matches _find_feedstock_techs
                        # in the SLC component).
                        ancestors = nx.ancestors(technology_graph, tech_name)
                        feedstock_names = [
                            t
                            for t in ancestors
                            if self.tech_control_classifiers.get(t) == "feedstock"
                        ]
                        for feedstock_name in feedstock_names:
                            self.plant.connect(
                                f"{feedstock_name}.VarOpEx",
                                f"system_level_controller.{feedstock_name}_VarOpEx",
                            )
                    elif cost_spec == "buy_price":
                        # Input-to-input connection (OpenMDAO 3.44+): tie the
                        # tech's own buy-price input to the SLC's buy-price
                        # input so a single ``prob.set_val()`` on the tech
                        # updates both the cost model and the controller.
                        #
                        # OpenMDAO 3.44 requires input-to-input connections to
                        # be made on the top-level model (not a subgroup); we
                        # use promoted names from ``self.plant`` since the
                        # plant is added to ``self.model`` with ``promotes=*``.
                        tech_buy_price_input = _get_tech_buy_price_input_name(
                            self.technology_config, tech_name
                        )
                        if tech_buy_price_input is not None:
                            self.model.connect(
                                f"{tech_name}.{tech_buy_price_input}",
                                f"system_level_controller.{tech_name}_buy_price",
                            )
                    # numeric scalar: used directly, no connection needed

        # --- Step 5: Connect the demand profile to the controller ---------
        demand_tech = slc_topology["demand_tech"]
        demand_commodity = slc_topology["demand_commodity"]
        self.plant.connect(
            f"{demand_tech}.{demand_commodity}_demand_out",
            f"system_level_controller.{demand_commodity}_demand",
        )

    def create_technology_models(self):
        # Loop through each technology and instantiate an OpenMDAO object (assume it exists)
        # for each technology

        if (
            len(self.technology_config["technologies"]) > 1
            and len(self.plant_config.get("technology_interconnections", [])) == 0
        ):
            msg = (
                f"{len(self.technology_config['technologies'])} technologies have been defined "
                "in the technology config but are not connected. Please add or populate "
                "`technology_interconnections` in the plant configuration."
            )
            raise ValueError(msg)

        self.tech_names = []
        self.performance_models = []
        self.control_strategies = []
        self.dispatch_rule_sets = []
        self.cost_models = []
        self.finance_models = []
        self.tech_control_classifiers = {}  # for system-level control

        combined_performance_and_cost_models = [
            "WOMBATElectrolyzerModel",
            "IronComponent",
            "ArdWindPlantModel",
        ]

        if any(tech == "site" for tech in self.technology_config["technologies"]):
            msg = (
                "'site' is an invalid technology name and is reserved for top-level "
                "variables. Please change the technology name to something else."
            )
            raise NameError(msg)

        reserved_techs = {"pipe", "cable"}
        # Use set intersection to find any reserved names present in the config
        invalid_techs = sorted(
            set(self.technology_config["technologies"]).intersection(reserved_techs)
        )

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

            if perf_model == "FeedstockPerformanceModel":
                comp = self.supported_models[perf_model](
                    driver_config=self.driver_config,
                    plant_config=self.plant_config,
                    tech_config=individual_tech_config,
                )
                self._check_time_step(perf_model, comp)
                self.tech_control_classifiers.update({tech_name: "feedstock"})
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

                    self._check_control_classifier(perf_model, comp)
                    self.tech_control_classifiers.update({tech_name: comp._control_classifier})
                    self._check_time_step(perf_model, comp)
                    om_model_object = tech_group.add_subsystem(perf_model, comp, promotes=["*"])
                    self.performance_models.append(om_model_object)
                    self.cost_models.append(om_model_object)
                    self.finance_models.append(om_model_object)

                    self._add_passthrough_controller(tech_group, comp, individual_tech_config)

                    continue

                # Process the models
                # TODO: integrate financial_model into the loop below
                model_types = [
                    "dispatch_rule_set",
                    "control_strategy",
                    "performance_model",
                    "cost_model",
                ]

                perf_om_object = None
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

                        if model_type == "performance_model":
                            perf_om_object = om_model_object

                        # Collect control classifier for topology validation and SLC
                        if model_type == "performance_model":
                            perf_cls = self.supported_models.get(perf_model)
                            if perf_cls is not None:
                                classifier = getattr(perf_cls, "_control_classifier", None)
                                if classifier is not None:
                                    self.tech_control_classifiers[tech_name] = classifier

                if perf_om_object is not None:
                    self._add_passthrough_controller(
                        tech_group, perf_om_object, individual_tech_config
                    )

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
            cost_model = individual_tech_config.get("cost_model", {}).get("model", "")

            if "FeedstockCostModel" in cost_model:
                comp = self.supported_models[cost_model](
                    driver_config=self.driver_config,
                    plant_config=self.plant_config,
                    tech_config=individual_tech_config,
                )
                self._check_time_step(tech_name, comp)
                self.plant.add_subsystem(tech_name, comp)

    def _process_model(self, model_type, individual_tech_config, tech_group):
        # Generalized function to process model definitions
        model_name = individual_tech_config[model_type]["model"]
        model_object = self.supported_models[model_name]

        self._check_time_step(model_name, model_object)

        om_model_object = tech_group.add_subsystem(
            model_name,
            model_object(
                driver_config=self.driver_config,
                plant_config=self.plant_config,
                tech_config=individual_tech_config,
            ),
            promotes=["*"],
        )

        # Some controllers read performance-model outputs (e.g.
        # ``rated_<commodity>_production``) as inputs, which creates a
        # controller<->performance data cycle within the technology group. Add a
        # nonlinear solver so this coupling is resolved instead of using stale
        # (default) values on a single execution pass.
        if model_type == "control_strategy" and getattr(
            model_object, "_reads_performance_outputs", False
        ):
            tech_group.nonlinear_solver = om.NonlinearBlockGS()
            tech_group.linear_solver = om.DirectSolver()

        return om_model_object

    def _check_time_step(self, model_name, model_object):
        dt = int(self.plant_config["plant"]["simulation"]["dt"])

        min_ts = model_object._time_step_bounds[0]
        max_ts = model_object._time_step_bounds[1]
        if dt < min_ts or dt > max_ts:
            msg = (
                f"Model {model_name} is compatible with time steps "
                f"between {min_ts} (s) and {max_ts} (s), but a time step of {dt} (s) "
                "was specified. Please set plant_config['plant']['simulation']['dt'] to a"
                f" value within the range [{min_ts}, {max_ts}]."
            )
            raise ValueError(msg)

    def _check_control_classifier(self, model_name, model_object):
        if not self.slc:
            return
        if not hasattr(model_object, "_control_classifier"):
            msg = f"Model {model_name} is missing a control classifier"
            raise ValueError(msg)

    def _add_passthrough_controller(self, tech_group, perf_comp, individual_tech_config):
        """Automatically add a PassthroughController to a tech group if appropriate.

        A controller is auto-inserted only when:

        - the technology has no user-defined ``control_strategy`` in its config,
        - the performance model exposes a ``_control_classifier`` of
          ``"flexible"``, ``"dispatchable"``, or ``"storage"``,
        - the performance model has set ``commodity`` and ``commodity_rate_units``
          attributes (typically set in its ``initialize()``), or those values
          can be read from the individual tech config.

        The controller's ``{commodity}_set_point`` input becomes the tech group's
        external set-point-input promoted at the tech group level, and its
        ``{commodity}_command_value`` output is auto-connected (via promotion) to the
        performance model's ``{commodity}_command_value`` input if one exists.
        """
        # Skip if the user has already specified a control strategy for this tech;
        # their explicit choice takes precedence over the auto-injected passthrough.
        if "control_strategy" in individual_tech_config:
            return

        # Only flexible/dispatchable/storage techs accept an externally
        # provided demand signal. Fixed, feedstock, combiner, and splitter techs are
        # handled elsewhere (fixed/feedstock have no demand input) and must
        # not get a passthrough.
        classifier = getattr(perf_comp, "_control_classifier", None)
        if classifier not in ("flexible", "dispatchable", "storage"):
            return

        # The performance model must declare the commodity it produces and the
        # units of its set-point so the PassthroughController can size its I/O
        # consistently. If they aren't yet set on the component (some models
        # only assign these in ``setup()``), fall back to reading them from the
        # individual tech config's model_inputs.
        commodity = getattr(perf_comp, "commodity", None)
        commodity_rate_units = getattr(perf_comp, "commodity_rate_units", None)
        if commodity is None or commodity_rate_units is None:
            model_inputs = individual_tech_config.get("model_inputs", {})
            shared = model_inputs.get("shared_parameters", {})
            perf_inputs = model_inputs.get("performance", {})
            if commodity is None:
                commodity = perf_inputs.get("commodity", shared.get("commodity"))
            if commodity_rate_units is None:
                commodity_rate_units = perf_inputs.get(
                    "commodity_rate_units", shared.get("commodity_rate_units")
                )
        if commodity is None or commodity_rate_units is None:
            return

        # Build the controller sized to the plant's simulation horizon so its
        # vector I/O matches the performance model's time-series I/O.
        n_timesteps = int(self.plant_config["plant"]["simulation"]["n_timesteps"])
        controller = PassthroughController(
            commodity=commodity,
            n_timesteps=n_timesteps,
            commodity_rate_units=commodity_rate_units,
        )

        # Promote all controller variables so:
        #   - `{commodity}_set_point` becomes the tech group's external input
        #     (this is what the system-level controller connects to), and
        #   - `{commodity}_command_value` is auto-connected by name to the
        #     performance model's matching input via promotion.
        om_controller = tech_group.add_subsystem("controller", controller, promotes=["*"])
        self.control_strategies.append(om_controller)

        # Ensure the controller runs before the performance/cost models that
        # consume its command_value output. Subsystem creation order otherwise
        # places the controller last in the group's execution order, which
        # would delay the command_value by one solver iteration.
        existing_order = list(tech_group._static_subsystems_allprocs.keys())
        if "controller" in existing_order:
            new_order = ["controller"] + [n for n in existing_order if n != "controller"]
            tech_group.set_order(new_order)

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
            * Subsystems such as ``AdjustedCapexOpexComp`` and
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
            * Updates ``self.plant_config["finance_parameters"]["finance_group"]`` if only a
              single finance model is provided (wraps it in a default finance subgroup).
            * Constructs and attaches OpenMDAO finance subsystem groups to the
              plant model under names ``finance_subgroup_<subgroup_name>``.
            * Stores processed subgroup configurations in
              ``self.finance_subgroups``.

        Example:
            Suppose ``plant_config["finance_parameters"]["finance_group"]`` defines a single finance
            model without subgroups:

            >>> self.plant_config["finance_parameters"]["finance_group"] = {
            ...     "commodity": "hydrogen",
            ...     "finance_model": "ProFastLCO",
            ...     "model_inputs": {"discount_rate": 0.08},
            ... }
            >>> self.create_finance_model()
            # Creates a default subgroup containing all technologies and
            # attaches a ProFAST finance model component to the plant.

        """

        from h2integrate.finances.finances import AdjustedCapexOpexComp, AdjustedCapacityFactorComp

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
            commodity_stream = self.plant_config["finance_parameters"]["finance_groups"].get(
                "commodity_stream"
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
            if commodity_stream is not None:
                subgroup["commodity_stream"] = commodity_stream
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
                commodity_stream_has_cost = (
                    self.technology_config["technologies"]
                    .get(commodity_stream, {})
                    .get("cost_model", False)
                )
                if commodity_stream_has_cost and commodity_stream not in tech_names:
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
                        "is_system_finance_model": True,
                        "use_commodity_stream_timeseries": subgroup_params.get(
                            "use_commodity_stream_timeseries", False
                        ),
                        "commodity_stream_output": subgroup_params.get(
                            "commodity_stream_output", None
                        ),
                    }
                }
            )

            finance_subgroup = om.Group()

            # ``commodity_stream`` identifies the technology whose output is used as
            # the commodity-production signal for this subgroup's finance model. It
            # must be supplied explicitly by the user — there is no default mapping
            # from commodity to tech name.
            if commodity_stream is None:
                msg = (
                    f"Finance subgroup '{subgroup_name}' (commodity '{commodity}') is "
                    "missing the required `commodity_stream` field. Please specify "
                    "which technology's output should be used as the commodity stream "
                    "for this subgroup."
                )
                raise ValueError(msg)

            # Add adjusted capex/opex
            adjusted_capex_opex_comp = AdjustedCapexOpexComp(
                driver_config=self.driver_config,
                tech_configs=tech_configs,
                plant_config=self.plant_config,
            )

            finance_subgroup.add_subsystem(
                "adjusted_capex_opex_comp", adjusted_capex_opex_comp, promotes=["*"]
            )

            # Initialize counter to check if invalid combination of finance
            # groups exist within a finance subgroup
            n_tech_finances_in_group = 0
            for finance_group_name in finance_group_names:
                # check if using tech-specific finance model
                if any(
                    tech_name == finance_group_name
                    for tech_name, tech_params in tech_configs.items()
                ):
                    tech_finance_group_name = (
                        tech_configs.get(finance_group_name).get("finance_model", {}).get("model")
                    )

                    # this is created in create_technology_models()
                    if tech_finance_group_name is not None:
                        n_tech_finances_in_group += 1
                        # tech specific finance models are created in create_technology_models()
                        # and do not need to be included in the system finance models.
                        # set commodity_stream to None so that inputs needed for system-level
                        # finance models are not connected to tech-specific finance models.
                        # finance_subgroups[subgroup_name].update({"commodity_stream": None})
                        finance_subgroups[subgroup_name].update({"is_system_finance_model": False})
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
                    finance_groups = self.plant_config["finance_parameters"]["finance_groups"]
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
                        # finance models name their outputs based on the description and commodity
                        # update the description to include the finance model name to ensure
                        # uniquely named outputs
                        commodity_output_desc = commodity_output_desc + f"_{finance_group_name}"

                if finance_subgroups[subgroup_name]["use_commodity_stream_timeseries"]:
                    if (
                        finance_subgroups[subgroup_name].get("commodity_stream_output", None)
                        is None
                    ):
                        msg = (
                            "`commodity_stream_output` is a required input if "
                            f"`use_commodity_stream_timeseries` is True. Please add the "
                            f"`commodity_stream_output` for finance subgroup `{subgroup_name}`"
                        )
                        raise ValueError(msg)

                    adj_cf_comp = AdjustedCapacityFactorComp(
                        plant_config=filtered_plant_config,
                        commodity_type=commodity,
                    )
                    finance_subgroup.add_subsystem("adjusted_cf_comp", adj_cf_comp, promotes=["*"])

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

    def _connect_multivariable_stream(
        self, source_tech, dest_tech, stream_name, combiner_counts, splitter_counts
    ):
        """Connect a multivariable stream between source and destination technologies.

        Handles combiner indexing (numbered inputs), splitter indexing (numbered outputs),
        and direct connections. Updates combiner_counts/splitter_counts dicts in-place.

        Args:
            source_tech (str): Name of the source technology.
            dest_tech (str): Name of the destination technology.
            stream_name (str): Name of the multivariable stream (key in multivariable_streams).
            combiner_counts (dict): Tracks the next input index per combiner technology.
            splitter_counts (dict): Tracks the next output index per splitter technology.
        """
        if "combiner" in dest_tech:
            if dest_tech not in combiner_counts:
                combiner_counts[dest_tech] = 1
            else:
                combiner_counts[dest_tech] += 1
            stream_index = combiner_counts[dest_tech]
            for var_name in multivariable_streams[stream_name]:
                self.plant.connect(
                    f"{source_tech}.{stream_name}:{var_name}_out",
                    f"{dest_tech}.{stream_name}:{var_name}_in{stream_index}",
                )
        elif "splitter" in source_tech:
            if source_tech not in splitter_counts:
                splitter_counts[source_tech] = 1
            else:
                splitter_counts[source_tech] += 1
            stream_index = splitter_counts[source_tech]
            for var_name in multivariable_streams[stream_name]:
                self.plant.connect(
                    f"{source_tech}.{stream_name}:{var_name}_out{stream_index}",
                    f"{dest_tech}.{stream_name}:{var_name}_in",
                )
        else:
            for var_name in multivariable_streams[stream_name]:
                self.plant.connect(
                    f"{source_tech}.{stream_name}:{var_name}_out",
                    f"{dest_tech}.{stream_name}:{var_name}_in",
                )

    def connect_technologies(self):
        technology_interconnections = self.plant_config.get("technology_interconnections", [])

        combiner_counts = {}
        splitter_counts = {}

        # loop through each linkage and instantiate an OpenMDAO object (assume it exists) for
        # the connection type (e.g. cable, pipeline, etc)
        for connection in technology_interconnections:
            if len(connection) == 4:
                source_tech, dest_tech, transport_item, transport_type = connection

                # Check if this is a multivariable stream connection
                # Format: [source, dest, stream_name, transport_type]
                if transport_item in multivariable_streams:
                    self._connect_multivariable_stream(
                        source_tech,
                        dest_tech,
                        transport_item,
                        combiner_counts,
                        splitter_counts,
                    )
                    continue  # Skip the rest of the 4-element handling

                if transport_type in self.tech_names:
                    # if the transport type is already a technology, skip creating a new component
                    connection_name = f"{transport_type}"
                else:
                    # make the connection_name based on source, dest, item, type
                    connection_name = (
                        f"{transport_item}_{source_tech}_to_{dest_tech}_{transport_type}"
                    )

                # Get the performance model of the source_tech
                source_tech_config = self.technology_config["technologies"].get(source_tech, {})
                perf_model_name = source_tech_config.get("performance_model", {}).get("model")
                cost_model_name = source_tech_config.get("cost_model", {}).get("model", "")

                # If the source is a feedstock, make sure to connect the amount of
                # feedstock consumed from the technology back to the feedstock cost model
                if "FeedstockCostModel" in cost_model_name:
                    self.plant.connect(
                        f"{dest_tech}.{transport_item}_consumed",
                        f"{source_tech}.{transport_item}_consumed",
                    )
                    # Connect the feedstock performance model output to the cost model input
                    self.plant.connect(
                        f"{source_tech}_source.{transport_item}_out",
                        f"{source_tech}.{transport_item}_out",
                    )

                if perf_model_name == "FeedstockPerformanceModel":
                    source_tech = f"{source_tech}_source"

                # Create the transport object
                # allow transport_type to be from self.tech_name
                if transport_type in self.tech_names:
                    # Connect the connection component to the destination technology
                    pass
                else:
                    connection_component = self.supported_models[transport_type](
                        transport_item=transport_item, plant_config=self.plant_config
                    )

                    # Add the connection component to the model
                    self._check_time_step(transport_type, connection_component)
                    self.plant.add_subsystem(connection_name, connection_component)

                    # Reorder the subsystems so transporters comes after their source technology
                    # NOTE: the private method must be used because setup() has not been called
                    subsystem_names = list(self.plant._static_subsystems_allprocs)
                    subsystem_names.remove(connection_name)
                    insert_idx = subsystem_names.index(source_tech) + 1
                    subsystem_names.insert(insert_idx, connection_name)
                    self.plant.set_order(subsystem_names)

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
                    # Connect the source tech design and performance info to the combiner
                    self.plant.connect(
                        f"{source_tech}.rated_{transport_item}_production",
                        f"{dest_tech}.rated_{transport_item}_production{combiner_counts[dest_tech]}",
                    )
                    self.plant.connect(
                        f"{source_tech}.capacity_factor",
                        f"{dest_tech}.{transport_item}_capacity_factor{combiner_counts[dest_tech]}",
                    )

                else:
                    # Connect the connection component to the destination technology
                    self.plant.connect(
                        f"{connection_name}.{transport_item}_out",
                        f"{dest_tech}.{transport_item}_in",
                    )

            elif len(connection) == 3:
                source_tech, dest_tech, connected_parameter = connection
                src_indices = None

                # initialize src_indices to allow connections between different shaped variables
                if isinstance(connected_parameter, list):
                    connected_parameter, src_indices = (
                        self._split_indices_from_connected_parameter_definition(connected_parameter)
                    )

                # connect directly from source to dest
                if isinstance(connected_parameter, tuple | list):
                    source_parameter, dest_parameter = connected_parameter
                    # Check if this is a multivariable stream connection
                    if source_parameter in multivariable_streams:
                        self._connect_multivariable_stream(
                            source_tech,
                            dest_tech,
                            source_parameter,
                            combiner_counts,
                            splitter_counts,
                        )
                    else:
                        self.plant.connect(
                            f"{source_tech}.{source_parameter}",
                            f"{dest_tech}.{dest_parameter}",
                            src_indices=src_indices,
                        )
                else:
                    # Check if the connected_parameter is a multivariable stream
                    if connected_parameter in multivariable_streams:
                        self._connect_multivariable_stream(
                            source_tech,
                            dest_tech,
                            connected_parameter,
                            combiner_counts,
                            splitter_counts,
                        )
                    else:
                        self.plant.connect(
                            f"{source_tech}.{connected_parameter}",
                            f"{dest_tech}.{connected_parameter}",
                            src_indices=src_indices,
                        )

            else:
                err_msg = f"Invalid connection: {connection}"
                raise ValueError(err_msg)

        resource_to_tech_connections = self.plant_config.get("resource_to_tech_connections", [])

        if "sites" in self.plant_config:
            resource_models = {}
            for site_grp, site_grp_inputs in self.plant_config["sites"].items():
                for resource_key, resource_params in site_grp_inputs.get("resources", {}).items():
                    resource_models[f"{site_grp}.{resource_key}"] = resource_params

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
                            "Missing resource(s) are not defined but are connected to a"
                            f" technology. Missing resource(s) are {missing_resource}. "
                            "Please check ``resource_to_tech_connections`` in the plant"
                            " config file or add the missing resources"
                            " to plant_config['site']['resources']."
                        )
                        raise ValueError(msg)

            for connection in resource_to_tech_connections:
                if len(connection) != 3:
                    err_msg = f"Invalid resource to tech connection: {connection}"
                    raise ValueError(err_msg)

                resource_name, tech_name, variable = connection

                # Connect the resource output to the technology input
                self.model.connect(f"{resource_name}.{variable}", f"{tech_name}.{variable}")

        # connect outputs of the technology models to the cost and finance models of the
        # same name if the cost and finance models are not None
        if "finance_parameters" in self.plant_config:
            # Connect the outputs of the technology models to the appropriate finance groups
            for group_id, group_configs in self.finance_subgroups.items():
                tech_configs = group_configs.get("tech_configs")
                primary_commodity_type = group_configs.get("commodity")
                commodity_stream = group_configs.get("commodity_stream")
                is_system_finance_model = group_configs.get("is_system_finance_model")

                if is_system_finance_model:
                    if group_configs.get("use_commodity_stream_timeseries", False):
                        # TODO: finish this logic
                        self.plant.connect(
                            f"{commodity_stream}.{group_configs.get('commodity_stream_output')}",
                            f"finance_subgroup_{group_id}.{primary_commodity_type}_produced",
                        )
                    else:
                        # Connect the rated commodity production and capacity factor
                        # for system-level finance models
                        self.plant.connect(
                            f"{commodity_stream}.rated_{primary_commodity_type}_production",
                            f"finance_subgroup_{group_id}.rated_{primary_commodity_type}_production",
                        )

                        self.plant.connect(
                            f"{commodity_stream}.capacity_factor",
                            f"finance_subgroup_{group_id}.capacity_factor",
                        )

                # Only connect technologies that are included in the finance stackup
                for tech_name in tech_configs.keys():
                    # Skip technologies whose models doesn't add costs
                    perf_model = tech_configs[tech_name].get("performance_model").get("model")
                    if perf_model in no_cost_models:
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

                    if is_system_finance_model and perf_model not in no_replacement_schedule_models:
                        # connect replacement schedule to system-level finance models
                        self.plant.connect(
                            f"{tech_name}.replacement_schedule",
                            f"finance_subgroup_{group_id}.replacement_schedule_{tech_name}",
                        )

        self.plant.options["auto_order"] = True

        # Check if there are any loops in the technology interconnections
        # If loops are present, add solvers to resolve the coupling
        # Check if there are any cycles (loops) in the technology graph
        if list(nx.simple_cycles(self.technology_graph)):
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
                # Only connect dispatch rules if they are defined in the tech_config
                tech_dispatch_rule = self.technology_config.get(tech_name, {}).get(
                    "dispatch_rule_set", False
                )
                if tech_dispatch_rule:
                    # Connect the dispatch rules output to the dispatching_tech_name input
                    self.model.connect(
                        f"{tech_name}.dispatch_block_rule_function",
                        f"{dispatching_tech_name}.dispatch_block_rule_function_{tech_name}",
                    )

    def create_driver_model(self):
        """
        Add the driver to the OpenMDAO model and add recorder.
        """

        from h2integrate.core.pose_optimization import PoseOptimization

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
        self.prob.setup()
        self.state = State.SETUP

        for tech, tech_info in self.technology_config["technologies"].items():
            check_inputs(self.prob, tech, tech_info, self.tech_config_path)
        self._validate_technology_interconnections()
        self._check_tech_connections()

    def run(self):
        # do model setup based on the driver config
        # might add a recorder, driver, set solver tolerances, etc
        if self.state < State.SETUP:
            self.setup()

        if self.state < State.RUN:
            # OpenMDAO will skip this step if it encounters an issue leading to silent failures
            # TODO: remove this step when OpenMDAO implements cursor closure
            if self.recorder_path is not None:
                self.recorder_path.unlink(missing_ok=True)

        self.prob.run_driver()
        self.state = State.RUN

    def post_process(self, print_results=True, summarize_sql=False, show_plots=False):
        """Post-process the results of the OpenMDAO model.

        Prints the inputs and outputs to all systems in the model, excluding any
        variables with "resource_data" in the name since those are large dictionary
        variables that are not correctly formatted when printing.

        Args:
            print_results (bool): If True, print a summary of all model inputs
                and outputs. Defaults to True.
            summarize_sql (bool): If True and a recorder file was written,
                convert the SQL recorder file to a CSV summary. Defaults to False.
            show_plots (bool): If True, run post-processing plots for any
                performance models that support them. Defaults to False.
        """
        if self.state < State.RUN:
            raise RuntimeError("`run` not called, so `post_process` cannot be called.")
        if print_results:
            # Use custom summary printer instead of OpenMDAO's built-in printing so we can
            # suppress internal value printing and display only mean values.
            self.print_results(self.prob.model, excludes=["*resource_data"])

        if summarize_sql and self.recorder_path is not None:
            from h2integrate.postprocess.sql_to_csv import convert_sql_to_csv_summary

            convert_sql_to_csv_summary(self.recorder_path, save_to_file=True)

        for model in self.performance_models:
            if hasattr(model, "post_process") and callable(model.post_process):
                model.post_process(show_plots=show_plots)
                if show_plots:
                    import matplotlib.pyplot as plt

                    plt.show()
        self.state = State.POST_PROCESS

    @staticmethod
    def print_results(model, includes=None, excludes=None, show_units=True):
        """Print hierarchical inputs plus explicit/implicit outputs (means only) using Rich.

        Order of rows preserves OpenMDAO's original ordering from list_inputs/list_outputs.
        Group rows are emitted lazily the first time a variable within that path appears.
        """

        def _gather_outputs(explicit=True, implicit=False):
            return model.list_outputs(
                explicit=explicit,
                implicit=implicit,
                val=True,
                prom_name=True,
                units=show_units,
                shape=True,
                includes=includes,
                excludes=excludes,
                out_stream=None,
                return_format="list",
            )

        explicit_meta = _gather_outputs(explicit=True, implicit=False)
        implicit_meta = _gather_outputs(explicit=False, implicit=True)

        # Gather inputs (no explicit/implicit split in OpenMDAO API)
        input_meta = model.list_inputs(
            val=True,
            prom_name=True,
            units=show_units,
            shape=True,
            includes=includes,
            excludes=excludes,
            out_stream=None,
            return_format="list",
        )

        def _mean(val):
            if isinstance(val, np.ndarray):
                return "nan" if val.size == 0 else f"{np.mean(val)}"
            if isinstance(val, int | float | np.number):
                return f"{val}"
            return "n/a"

        from rich import box
        from rich.table import Table
        from rich.console import Console

        console = Console()

        def _emit_section(title, meta_list, kind_label="outputs"):
            if not meta_list:
                return
            console.print(f"\n{len(meta_list)} {title.lower()} {kind_label}:")
            table = Table(show_header=True, header_style="bold", box=box.MINIMAL, pad_edge=False)
            table.add_column("Variable", overflow="fold")
            table.add_column("Mean", justify="right")
            if show_units:
                table.add_column("Units")
            table.add_column("Shape")
            table.add_column("Promoted name", overflow="fold")

            emitted_groups = set()
            for abs_name, meta in meta_list:
                parts = abs_name.split(".")
                # emit group rows
                for depth in range(len(parts) - 1):
                    grp_path = ".".join(parts[: depth + 1])
                    if grp_path not in emitted_groups:
                        emitted_groups.add(grp_path)
                        indent = "  " * depth
                        grp_name = parts[depth]
                        if show_units:
                            table.add_row(f"{indent}{grp_name}", "", "", "", "")
                        else:
                            table.add_row(f"{indent}{grp_name}", "", "", "")
                var = parts[-1]
                indent = "  " * (len(parts) - 1)
                mean_raw = _mean(meta.get("val"))
                try:
                    val = float(mean_raw)
                    units_val_raw = meta.get("units")
                    # Format as integer if units are 'year' or variable name is 'cost_year'
                    if units_val_raw == "year" or var == "cost_year":
                        mean_val = str(int(val))
                    elif abs(val) >= 1e5:
                        formatted = f"{val:,.2f}"
                        mean_val = formatted.rstrip("0")
                        if mean_val.endswith("."):
                            mean_val = mean_val  # Keep e.g. "520." format
                        else:
                            mean_val = mean_val + "." if "." not in mean_val else mean_val
                    else:
                        formatted = f"{val:,.4f}"
                        mean_val = formatted.rstrip("0")
                        # Ensure we end with "." if all decimals were zeros
                        if mean_val.endswith("."):
                            pass  # Keep as e.g. "520." or "0."
                        elif "." not in mean_val:
                            mean_val = mean_val + "."
                except (ValueError, TypeError):
                    mean_val = str(mean_raw)
                units_val = (
                    "n/a"
                    if (var == "cost_year" or meta.get("units") is None)
                    else str(meta.get("units"))
                    if show_units
                    else ""
                )
                shape_meta = meta.get("shape", "")
                if var == "cost_year":
                    shape_str = "n/a"
                elif isinstance(shape_meta, tuple | list) and len(shape_meta) > 0:
                    shape_str = str(shape_meta[0])
                else:
                    shape_str = "" if shape_meta in (None, "", ()) else str(shape_meta)
                promoted = meta.get("prom_name", "")
                if show_units:
                    table.add_row(f"{indent}{var}", mean_val, units_val, shape_str, promoted)
                else:
                    table.add_row(f"{indent}{var}", mean_val, shape_str, promoted)
            console.print(table)

        # Emit sections (inside function scope)
        _emit_section("Explicit", input_meta, kind_label="inputs")
        _emit_section("Explicit", explicit_meta, kind_label="outputs")
        _emit_section("Implicit", implicit_meta, kind_label="outputs")

        # structured return
        def _structured(meta_list):
            return {
                name: {
                    "mean": _mean(meta.get("val")),
                    **(
                        {
                            "units": (
                                "n/a"
                                if name.split(".")[-1] == "cost_year" or meta.get("units") is None
                                else meta.get("units")
                            )
                        }
                        if show_units
                        else {}
                    ),
                    "shape": (
                        "n/a"
                        if name.split(".")[-1] == "cost_year"
                        else meta.get("shape")[0]
                        if isinstance(meta.get("shape"), tuple | list)
                        and len(meta.get("shape")) > 0
                        else ""
                        if meta.get("shape") in (None, "", ())
                        else meta.get("shape")
                    ),
                    "promoted_name": meta.get("prom_name"),
                }
                for name, meta in meta_list
            }

        return {
            "inputs": _structured(input_meta),
            "explicit_outputs": _structured(explicit_meta),
            "implicit_outputs": _structured(implicit_meta),
        }

    def create_xdsm(self, outfile="connections_xdsm"):
        """Create an XDSM diagram from the plant technology interconnections.

        This method reads ``technology_interconnections`` from ``self.plant_config``
        and delegates diagram generation to
        :func:`h2integrate.core.utilities.create_xdsm_from_config`.

        Args:
            outfile (str, optional): Base filename for the generated XDSM output.
                The default is ``"connections_xdsm"``.

        Raises:
            ValueError: If ``technology_interconnections`` is empty or missing from
                the plant configuration.
        """

        technology_interconnections = self.plant_config.get("technology_interconnections", [])

        if len(technology_interconnections) > 0:
            create_xdsm_from_config(self.plant_config, output_file=outfile)
        else:
            raise ValueError(
                "Generating an XDSM diagram requires technology interconnections, "
                "but none were found."
            )

    def create_technology_graph(self, tech_interconnections: list | set):
        """Create a directed graph of the technology interconnections.

        Builds a NetworkX directed graph where nodes represent technologies
        and edges represent connections between them. If a connection includes
        a commodity (length-4 entry), it is stored as an edge attribute.

        Args:
            tech_interconnections (list): list of technology interconnections

        Returns:
            nx.DiGraph: A directed graph with technologies as nodes and
                interconnections as edges.
        """
        technology_graph = nx.DiGraph()

        def _as_commodity_list(commodity):
            """Coerce a commodity definition to a list."""
            if commodity is None:
                return []
            if isinstance(commodity, str):
                return [commodity]
            return list(commodity)

        for connection in tech_interconnections:
            source = connection[0]
            destination = connection[1]
            if len(connection) == 4:
                new_commodities = _as_commodity_list(connection[2])

                # Commodity is defined in connection. Keep edge commodities
                # as a list, even for a single commodity.
                if technology_graph.has_edge(source, destination):
                    connected_cmods = technology_graph.edges[source, destination].get("commodity")
                    existing_commodities = _as_commodity_list(connected_cmods)
                    merged_commodities = list(set(existing_commodities + new_commodities))
                    technology_graph.add_edge(
                        source,
                        destination,
                        commodity=merged_commodities,
                    )
                else:
                    technology_graph.add_edge(
                        source,
                        destination,
                        commodity=new_commodities,
                    )
            else:
                technology_graph.add_edge(source, destination)

        return technology_graph

    def _validate_technology_interconnections(self):
        """Validate technology interconnections for common errors and discouraged patterns.

        Performs the following checks:

        1. Length-3 connections that pass a commodity via a ``[commodity_out, commodity_in]``
           pair should instead use a length-4 connection with an explicit commodity name and
           transport component. An error is raised when source and destination parameter names
           differ only by their ``_out`` / ``_in`` suffix (i.e. the commodity could be inferred).

        2. Storage technology topology: each storage technology must have exactly 1 input
           connection (length-4) and at most 1 output connection (length-4). The technology
           directly upstream of the storage component is allowed at most 2 output connections
           (one to the storage tech and one to a combiner).

        3. For all other technologies connected via length-4 connections (excluding splitters,
           combiners, storage technologies, and direct predecessors of storage technologies),
           each individual commodity may arrive from at most 1 source and be sent to at most
           1 destination. Technologies with multiple inputs or outputs are fine as long as
           each commodity comes from a single source and goes to a single destination
           (e.g. an ammonia plant receiving hydrogen, nitrogen, and electricity from three
           separate technologies is perfectly valid).

        Raises:
            ValueError: If any interconnection violates the topology rules.
        """
        technology_interconnections = self.plant_config.get("technology_interconnections", [])

        # --- Check 1: discouraged length-3 [commodity_out, commodity_in] connections ---
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
            if source_param_base.endswith("_out") and dest_param_base.endswith("_in"):
                commodity_from_source = source_param_base[: -len("_out")]
                commodity_from_dest = dest_param_base[: -len("_in")]
                if commodity_from_source == commodity_from_dest:
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

        # --- Checks 2 and 3: topology checks using the technology graph ---
        # Build edge-count degree maps (L4 only) for the storage topology check,
        # and per-commodity source/destination maps for the general stream check.
        in_degs_l4: dict[str, int] = {}
        out_degs_l4: dict[str, int] = {}
        # in_commodity_sources[tech][commodity] = number of distinct sources
        in_commodity_sources: dict[str, dict[str, int]] = {}
        # out_commodity_dests[tech][commodity] = number of distinct destinations
        out_commodity_dests: dict[str, dict[str, int]] = {}

        for source, dest, commodity in self.technology_graph.edges(data="commodity"):
            if not commodity:
                continue  # length-3 connections carry no commodity; skip them
            out_degs_l4[source] = out_degs_l4.get(source, 0) + 1
            in_degs_l4[dest] = in_degs_l4.get(dest, 0) + 1
            dest_classifier = self.tech_control_classifiers.get(dest)
            for c in commodity:
                in_commodity_sources.setdefault(dest, {}).update(
                    {c: in_commodity_sources.get(dest, {}).get(c, 0) + 1}
                )
                # Demand-classified techs are observers/sinks (they report on a commodity
                # stream but do not consume it in a topology sense). Exclude them from the
                # source's output-destination count so that a source may simultaneously
                # feed a real consumer and a reporting/demand component without triggering
                # the multi-destination error in Check 3.
                if dest_classifier != "demand":
                    current = out_commodity_dests.setdefault(source, {})
                    current[c] = current.get(c, 0) + 1

        # --- Check 2: storage technology topology ---
        storage_techs = [k for k, v in self.tech_control_classifiers.items() if v == "storage"]
        storage_upstream_techs: set[str] = set()
        for storage_tech in storage_techs:
            n_in = in_degs_l4.get(storage_tech, 0)
            if n_in == 0:
                raise ValueError(
                    f"Storage technology {storage_tech!r} has no input connections in "
                    f"the technology graph but should have at least 1."
                )
            # Per-commodity check: each commodity must arrive from exactly 1 source.
            # A storage tech may accept multiple different commodities (e.g. electricity
            # and hydrogen) from different upstream technologies; that is fine as long as
            # no single commodity is supplied by more than one source.
            for commodity, n_sources in in_commodity_sources.get(storage_tech, {}).items():
                if n_sources > 1:
                    raise ValueError(
                        f"Storage technology {storage_tech!r} receives commodity "
                        f"{commodity!r} from {n_sources} sources in the technology graph "
                        f"but should receive it from at most 1."
                    )
            for commodity, n_out in out_commodity_dests.get(storage_tech, {}).items():
                if n_out > 1:
                    raise ValueError(
                        f"Storage technology {storage_tech!r} has {n_out} output connection(s) "
                        f"for commodity {commodity!r} but should have at most 1."
                    )
            # Identify the upstream technology (connected via a length-4 edge)
            upstream_techs_l4 = [
                t
                for t in self.technology_graph.predecessors(storage_tech)
                if self.technology_graph.edges[t, storage_tech].get("commodity")
            ]
            for upstream_tech in upstream_techs_l4:
                storage_upstream_techs.add(upstream_tech)
                for commodity in self.technology_graph.edges[upstream_tech, storage_tech].get(
                    "commodity"
                ):
                    n_out_upstream = out_commodity_dests.get(upstream_tech, {}).get(commodity, 0)
                    if n_out_upstream > 2:
                        raise ValueError(
                            f"Technology {upstream_tech!r} feeds storage technology "
                            f"{storage_tech!r} but has {n_out_upstream} output connection(s). "
                            f"It should connect only to {storage_tech!r} and a combiner "
                            f"(at most 2 output streams)."
                        )

        # --- Check 3: per-commodity max 1 source/destination for general technologies ---
        # A technology may receive multiple different commodities from different sources
        # (e.g. an ammonia plant accepting hydrogen, nitrogen, and electricity is valid),
        # but each individual commodity must arrive from exactly 1 source and be sent to
        # exactly 1 destination (unless the tech is a splitter, combiner, storage, or the
        # direct upstream tech of a storage component, all of which have known exceptions).
        all_techs_in_l4 = set(in_commodity_sources) | set(out_commodity_dests)
        for tech in all_techs_in_l4:
            classifier = self.tech_control_classifiers.get(tech)
            if classifier in ("splitter", "combiner"):
                continue
            if classifier == "storage":
                continue  # already validated in check 2

            for commodity, n_sources in in_commodity_sources.get(tech, {}).items():
                if n_sources > 1:
                    raise ValueError(
                        f"Technology {tech!r} receives commodity {commodity!r} from "
                        f"{n_sources} sources in the technology graph but should receive "
                        f"it from at most 1. Consider using a combiner component."
                    )

            if tech in storage_upstream_techs:
                continue  # out-stream validation for storage upstream handled in check 2

            for commodity, n_dests in out_commodity_dests.get(tech, {}).items():
                if n_dests > 1:
                    raise ValueError(
                        f"Technology {tech!r} sends commodity {commodity!r} to "
                        f"{n_dests} destinations in the technology graph but should "
                        f"send it to at most 1. Consider using a splitter component."
                    )

        # --- Check 4: prevent commodity double-counting via demand components ---
        # A demand component may receive a commodity and pass it on to a real consumer
        # (e.g. acting as a profile regularizer). However, if a source does this it
        # must NOT also send the same commodity directly to another real consumer,
        # because the flow would be counted twice.
        #
        # Valid:   source -> demand_comp -> real_consumer   (single path through demand)
        # Valid:   source -> demand_comp (pure observer)
        #          source -> real_consumer
        # Invalid: source -> real_consumer_A                (competing direct path)
        #          source -> demand_comp -> real_consumer_B (and also via demand)
        #
        # The check is transitive: a demand component "reaches a real consumer" even
        # when the path passes through a chain of other demand components first.

        def _demand_reaches_real_consumer(demand_tech: str) -> bool:
            """Return True if demand_tech can reach a non-demand tech via L4 edges."""
            visited: set[str] = set()
            stack = [demand_tech]
            while stack:
                node = stack.pop()
                if node in visited:
                    continue
                visited.add(node)
                for _, d, c in self.technology_graph.out_edges(node, data="commodity"):
                    if not c:
                        continue
                    if self.tech_control_classifiers.get(d) != "demand":
                        return True
                    stack.append(d)
            return False

        # Build per-(source, commodity) destination lists from L4 edges.
        source_commodity_dests: dict[tuple[str, str], list[str]] = {}
        for source, dest, commodity in self.technology_graph.edges(data="commodity"):
            if not commodity:
                continue
            for c in commodity:
                source_commodity_dests.setdefault((source, c), []).append(dest)

        for (source, commodity), dests in source_commodity_dests.items():
            direct_real_dests = [
                d for d in dests if self.tech_control_classifiers.get(d) != "demand"
            ]
            outputting_demand_dests = [
                d
                for d in dests
                if self.tech_control_classifiers.get(d) == "demand"
                and _demand_reaches_real_consumer(d)
            ]
            if direct_real_dests and outputting_demand_dests:
                raise ValueError(
                    f"Technology {source!r} sends commodity {commodity!r} both directly "
                    f"to {direct_real_dests} and to demand component(s) "
                    f"{outputting_demand_dests} that re-emit the commodity to real "
                    f"consumers. This would double-count the commodity flow. Either route "
                    f"all {commodity!r} from {source!r} through the demand component, or "
                    f"connect the downstream consumers directly to {source!r} instead."
                )

    def _check_tech_connections(self):
        """Check that commodity streams between technologies are valid.

        Validates that each commodity in a length-4 technology interconnection
        is output by the source technology and accepted as input by the
        destination technology. Does not check length-3 connections or
        missing input commodity streams.

        Raises:
            ValueError: If any commodity connection is invalid.
        """
        # Collect IO parameter names for each technology in the graph
        tech_io = {}
        for tech_name in self.technology_graph.nodes():
            tech_info = self.technology_config["technologies"].get(tech_name, {})
            io_params = set()

            for model_type in [
                "performance_model",
                "finance_model",
                "cost_model",
                "control_strategy",
            ]:
                if not tech_info or model_type not in tech_info:
                    continue

                model_name = tech_info[model_type]["model"]

                if model_name == "FeedstockPerformanceModel":
                    group = getattr(self.prob.model.plant, f"{tech_name}_source")
                else:
                    group = getattr(self.prob.model.plant, tech_name)
                    if "FeedstockCostModel" not in model_name:
                        group = getattr(group, model_name, None)
                        if group is None:
                            continue

                io_params.update([key.split(".")[-1] for key in group.get_io_metadata().keys()])

            tech_io[tech_name] = io_params

        def _has_commodity_param(params, commodity, direction):
            """Check if the technology has the commodity parameter, either exact
            or numbered (splitter/combiner)."""
            return f"{commodity}_{direction}" in params or any(
                re.fullmatch(rf"{commodity}_{direction}\d", p) for p in params
            )

        # Validate commodity connections
        invalid_outputs = set()  # (tech, commodity) pairs where source lacks _out param
        invalid_inputs = set()  # (tech, commodity) pairs where dest lacks _in param
        for source, dest, commodities in self.technology_graph.edges(data="commodity"):
            if commodities is None:
                continue  # length-3 connections have no commodity to check

            for commodity in commodities:
                if not _has_commodity_param(tech_io[source], commodity, "out"):
                    invalid_outputs.add((source, commodity))
                if not _has_commodity_param(tech_io[dest], commodity, "in"):
                    invalid_inputs.add((dest, commodity))

        # Build a single error message grouping output and input issues separately
        if invalid_outputs or invalid_inputs:
            parts = []
            if invalid_outputs:
                items = ", ".join(f"`{tech}` -> `{comm}`" for tech, comm in sorted(invalid_outputs))
                parts.append(
                    f"The following technologies do not output their specified commodity: {items}."
                )
            if invalid_inputs:
                items = ", ".join(f"`{tech}` <- `{comm}`" for tech, comm in sorted(invalid_inputs))
                parts.append(
                    f"The following technologies do not accept "
                    f"their specified input commodity: {items}."
                )
            # Point user to the file that needs fixing
            parts.append(f"Update `technology_interconnections` in {self.plant_config_path}.")
            raise ValueError("\n".join(parts))

    @staticmethod
    def _split_indices_from_connected_parameter_definition(connected_parameter):
        """Extract and parse slice indices from connected parameter definitions for OpenMDAO
        connections.

        This function processes parameter names containing slice patterns in square brackets
        (e.g., "power[0:8760]") and generates OpenMDAO-compatible src_indices for connections
        between variables of different shapes.

        Args:
            connected_parameter (list[str]): A two-element list containing:
                - [0] source parameter name, optionally with pattern like "var[slice_spec]"
                - [1] destination parameter name, optionally with pattern like "var[slice_spec]"

                Example: ["power[0:8760]", "demand[:]"]

        Returns:
            tuple: A two-element tuple containing:
                - connected_parameter (list[str]): The parameter names with slices removed
                  (e.g., ["power", "demand"])
                - src_indices: OpenMDAO slicer object for indexing source outputs to match
                  destination input shapes. Returns om.slicer[slice] for indexing.

        Note:
            If the destination has a slice pattern, it must include the length ":N"
            (e.g., "[0:N]"), the function extracts N as the destination length and
            multiplies the source slice by this factor to create properly scaled indices.
            The length is required because the length is not known in the OpenMDAO model
            until prob.setup() has been called.
        """
        source_parameter, dest_parameter = connected_parameter

        def _extract_slice(parameter):
            """Return the contents inside the brackets (e.g. '0:8760'), or None."""
            match = re.search(r"\[(.*)\]", parameter)
            return None if match is None else match.group(1)

        def _to_indices(spec):
            """Convert a bracket spec string into a slice or list of ints."""
            if ":" in spec:
                return slice(*(int(p) if p.strip() else None for p in spec.split(":")))
            return [int(p) for p in spec.split(",")]

        source_slice = _extract_slice(source_parameter)
        dest_slice = _extract_slice(dest_parameter)

        if source_slice == dest_slice:
            src_indices = None
        elif dest_slice is not None and source_slice is not None:
            # Tile the source indices to fill the destination length to handle shape
            # mismatches. Examples:
            #   source="0",   dest_length=8760 -> [0] repeated 8760 times
            #   source="0,1", dest_length=10   -> [0, 1] cycled to fill 10 slots
            if dest_slice.split(":")[0] not in ("", "0"):
                raise ValueError(
                    "A non-zero start was provided for the slice for destination "
                    f"parameter <{dest_parameter}>"
                )
            dest_length = int(dest_slice.split(":")[-1])

            source_indices = _to_indices(source_slice)
            if isinstance(source_indices, slice):
                source_indices = list(
                    range(
                        source_indices.start or 0,
                        source_indices.stop,
                        source_indices.step or 1,
                    )
                )

            # Repeat the source values enough times to cover the destination, then
            # truncate so the result is exactly dest_length long. This cycles through
            # the source values when the source is shorter than the destination.
            n_repeats = -(-dest_length // len(source_indices))  # ceiling division
            src_indices = om.slicer[(source_indices * n_repeats)[:dest_length]]
        else:
            # No destination slice pattern; use source slice pattern directly.
            src_indices = None if source_slice is None else om.slicer[_to_indices(source_slice)]

        # Remove the slice patterns from parameter names to get clean names.
        connected_parameter = [source_parameter.split("[")[0], dest_parameter.split("[")[0]]

        return connected_parameter, src_indices
