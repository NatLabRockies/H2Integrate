import warnings
from collections import defaultdict

import numpy as np
import networkx as nx
import openmdao.api as om

from h2integrate.control.control_strategies.system_level.slc_topology import (
    build_dispatch_topology,
    find_commodity_suppliers,
)
from h2integrate.control.control_strategies.system_level.slc_conversion import (
    capacity_ratio as calculate_capacity_ratio,
    conversion_ratio as calculate_conversion_ratio,
    accumulate_derived_demand,
)


def _get_tech_buy_price_input_name(tech_config, tech_name):
    """Return the variable name of a tech's buy-price input, or ``None`` if absent.

    Used by the ``"buy_price"`` ``cost_per_tech`` mode to figure out which
    OpenMDAO input on the technology cost model carries the per-unit purchase
    price. Currently recognizes:

    - ``"electricity_buy_price"`` (Grid technologies)
    - ``"price"`` (Feedstock technologies)

    Args:
        tech_config (dict): The full ``tech_config`` dictionary.
        tech_name (str): Name of the technology.

    Returns:
        str | None: The input variable name, or ``None`` if the tech has no
        recognized buy-price input in its cost / shared parameters.
    """
    tech_def = tech_config.get("technologies", {}).get(tech_name, {})
    model_inputs = tech_def.get("model_inputs", {})
    cost_params = model_inputs.get("cost_parameters", {})
    shared_params = model_inputs.get("shared_parameters", {})
    all_params = {**shared_params, **cost_params}
    if "electricity_buy_price" in all_params:
        return "electricity_buy_price"
    if "price" in all_params:
        return "price"
    return None


def _get_buy_price_default_and_shape(tech_config, tech_name, n_timesteps, plant_life):
    """Return the default buy-price value and OpenMDAO input shape for a tech.

    Mirrors the shape logic used by the technology cost models themselves so
    the SLC's ``{tech_name}_buy_price`` input can be safely connected
    input-to-input with the tech's own buy-price input:

    - Grid (``electricity_buy_price``): shape is determined by
      ``buy_price_mode`` (``per_timestep`` → ``n_timesteps``, ``per_year`` →
      ``plant_life``, ``constant`` → ``1``).
    - Feedstock (``price``): shape is the length of the configured price
      array, or ``1`` for a scalar.
    - Anything else: falls back to ``n_timesteps`` with a default of ``0.0``.

    Args:
        tech_config (dict): The full ``tech_config`` dictionary.
        tech_name (str): Name of the technology.
        n_timesteps (int): Number of simulation timesteps.
        plant_life (int): Plant life in years.

    Returns:
        tuple[float | list | np.ndarray, int]: ``(default_value, shape)``
        suitable for ``add_input(val=..., shape=...)``.
    """
    tech_def = tech_config.get("technologies", {}).get(tech_name, {})
    model_inputs = tech_def.get("model_inputs", {})
    cost_params = model_inputs.get("cost_parameters", {})
    shared_params = model_inputs.get("shared_parameters", {})
    all_params = {**shared_params, **cost_params}

    if "electricity_buy_price" in all_params:
        default_price = all_params["electricity_buy_price"]
        buy_price_mode = all_params.get("buy_price_mode", "per_timestep")
        if buy_price_mode == "per_year":
            return default_price, plant_life
        if buy_price_mode == "constant":
            return default_price, 1
        return default_price, n_timesteps

    if "price" in all_params:
        default_price = all_params["price"]
        if isinstance(default_price, list | np.ndarray):
            return default_price, len(default_price)
        return default_price, 1

    return 0.0, n_timesteps


class SystemLevelControlBase(om.ExplicitComponent):
    """Base class for system-level controllers.

    Provides common setup logic shared by all system-level control strategies:
    demand input, fixed/flexible/dispatchable/storage/feedstock technology I/O
    creation, and technology classification reading from ``plant_config`` and
    ``slc_topology``.

    Subclasses must implement ``compute()`` with their dispatch strategy.

    Each technology group is expected to contain a controller (either user-defined or an
    auto-injected ``PassthroughController``) that consumes a ``{commodity}_set_point`` input and
    produces the ``{commodity}_command_value`` actually fed to the performance/cost models. The
    system-level controller therefore reasons in terms of *demand* values and emits
    ``{tech_name}_{commodity}_set_point`` outputs for every controlled technology.

    The SLC demand signal is provided by a demand component (for example,
    ``GenericDemandComponent``) connected by ``H2IntegrateModel``. When SLC is
    enabled, only one demand component is currently supported.

    Information passed to the controller from H2IntegrateModel is input in the
    ``slc_topology`` option. This dict is framework-internal state derived from the
    plant and technology configs by ``H2IntegrateModel._classify_slc_technologies()``,
    not something users author directly. It must contain:

    - ``demand_commodity``: the commodity being controlled (e.g. "electricity")
    - ``demand_commodity_rate_units``: units string (or None) of the demand commodity
    - ``demand_tech``: name of the demand technology
    - ``demand_profile``: default demand profile from the demand technology configuration
    - ``storage_techs_to_control``: dictionary with keys of the technology names. The value is True
        if the technology is classified as "storage" and has an attached controller.
        Otherwise the value is False.
    - ``technology_graph``: directional graph object representation of the
        technology_interconnections found in the ``plant_config``
    - ``tech_to_commodity``: set of tuples formatted as (tech_name, tech_output_commodity)
    - ``tech_control_classifiers``: dictionary of technologies with key-value pairs of each
        technology name and its corresponding control classifier (one of
        ``"fixed"``, ``"flexible"``, ``"dispatchable"``, ``"storage"``, or
        ``"feedstock"``).

    It may also contain ``dispatch_topology``, the ``DispatchTopology`` built by
    ``H2IntegrateModel``. When it is absent (for example in standalone unit tests), the
    component builds the topology itself from the keys above.

    Controller-specific configuration parameters may be read from
    ``plant_config["system_level_control"]["control_parameters"]``.

    Cost-aware subclasses (e.g. ``CostMinimizationControl``,
    ``ProfitMaximizationControl``) call ``_setup_marginal_costs()`` to register
    marginal-cost inputs for each dispatchable technology based on the
    ``cost_per_tech`` mapping. Supported values per dispatchable tech are:

    - A numeric value (constant marginal cost in ``$/(commodity_rate_unit*h)``).
    - ``"buy_price"`` — use the technology's own purchase price input.
    - ``"VarOpEx"`` — derive marginal cost from the tech's own ``VarOpEx``
      divided by its annualized total production.
    - ``"feedstock"`` — sum ``VarOpEx`` from all feedstock technologies
      upstream of the tech in ``technology_interconnections`` (graph
      ancestors, so feedstocks behind intermediate components are included)
      and divide by the dispatchable tech's annualized total production.
    """

    def initialize(self):
        self.options.declare("driver_config", types=dict)
        self.options.declare("plant_config", types=dict)
        self.options.declare("tech_config", types=dict)
        self.options.declare("slc_topology", types=dict)

    def setup(self):
        plant_config = self.options["plant_config"]
        slc_topology = self.options["slc_topology"]

        self.n_timesteps = plant_config["plant"]["simulation"]["n_timesteps"]

        # Read pre-computed classification from plant_config
        self.commodity = slc_topology["demand_commodity"]
        self.commodity_rate_units = slc_topology.get("demand_commodity_rate_units", None)
        self.demand_tech = slc_topology["demand_tech"]
        self.storage_techs_to_control = slc_topology.get("storage_techs_to_control", {})
        self.technology_graph = slc_topology["technology_graph"]

        self.fixed_techs = [
            k for k, v in slc_topology["tech_control_classifiers"].items() if v == "fixed"
        ]
        self.flexible_techs = [
            k for k, v in slc_topology["tech_control_classifiers"].items() if v == "flexible"
        ]
        self.dispatchable_techs = [
            k for k, v in slc_topology["tech_control_classifiers"].items() if v == "dispatchable"
        ]
        self.storage_techs = [
            k for k, v in slc_topology["tech_control_classifiers"].items() if v == "storage"
        ]
        self.feedstock_comps = [
            k for k, v in slc_topology["tech_control_classifiers"].items() if v == "feedstock"
        ]

        self.input_techs = set(
            self.fixed_techs + self.flexible_techs + self.dispatchable_techs + self.storage_techs
        )

        # Input: demand profile
        self.demand_input_name = f"{self.commodity}_demand"

        # Demand has to be set to the same value to prevent an error
        demand_val = slc_topology["demand_profile"]
        self.add_input(
            self.demand_input_name,
            val=demand_val,
            shape=self.n_timesteps,
            units=self.commodity_rate_units,
            desc=f"Demand profile of {self.commodity}",
        )

        self.techs_to_commodities = slc_topology["tech_to_commodity"]

        # There are multiple commodities being produced by technologies in the system
        self.multi_commodity_system = (
            True if len({e[-1] for e in self.techs_to_commodities}) > 1 else False
        )

        self.commodities_to_units = {self.commodity: self.commodity_rate_units}
        self.commodities_to_ref_var = {}
        self._setup_fixed_category(self.fixed_techs)
        self._setup_tech_category("flexible", self.flexible_techs)
        self._setup_tech_category("dispatchable", self.dispatchable_techs)
        self._setup_tech_category("storage", self.storage_techs)
        self._setup_feedstock_category(self.feedstock_comps)

        # Get the setup-time dispatch topology: which supply buses exist, in what order
        # demand propagates across them, and which conversions link them.
        self._dispatch_topology = slc_topology.get("dispatch_topology")
        if self._dispatch_topology is None:
            self._dispatch_topology = build_dispatch_topology(
                self.technology_graph,
                slc_topology["tech_control_classifiers"],
                self.techs_to_commodities,
                self.demand_tech,
                self.commodity,
            )
        self._warn_undispatched_tech_commodities()

        # Register the converters' measured-consumption inputs. Conversion ratios are derived
        # automatically (measured first, then a capacity-based seed), enabling backward demand
        # propagation across converter boundaries for heterogeneous-commodity systems.
        self._build_converters()

        # Storage with its own sub-controller is told how much commodity flows into it
        self._storage_suppliers = {
            (storage_tech, commodity): find_commodity_suppliers(
                self.technology_graph,
                storage_tech,
                commodity,
                supplier_techs=self.input_techs | set(self.feedstock_comps),
            )
            for storage_tech in self.storage_techs
            if self.storage_techs_to_control.get(storage_tech, False)
            for commodity in self._get_commodity_for_tech(storage_tech)
        }

        # Register a set-point output for every controller-managed splitter so
        # the controller can drive its per-timestep priority allocation from the
        # backpropagated demand of the consumers behind its first output.
        for splitter in self._dispatch_topology.splitters:
            self.add_output(
                f"{splitter.name}_{splitter.commodity}_set_point",
                val=0.0,
                shape=self.n_timesteps,
                units=self._get_splitter_rate_units(splitter.name),
                desc=(
                    f"Prescribed {splitter.commodity} allocation to the priority "
                    f"consumer of splitter {splitter.name}"
                ),
            )

    def _warn_undispatched_tech_commodities(self):
        """Warn when a controller-managed output is outside the demand-reachable topology."""
        dispatched_producers = {
            (tech_name, self._dispatch_topology.buses[bus_name].commodity)
            for bus_name in self._dispatch_topology.dispatch_order
            for tech_name in self._dispatch_topology.buses[bus_name].producers
        }
        undispatched = sorted(
            (tech_name, commodity)
            for tech_name, commodity in self.techs_to_commodities
            if tech_name in self.input_techs and (tech_name, commodity) not in dispatched_producers
        )
        if not undispatched:
            return

        details = ", ".join(f"{tech_name} ({commodity})" for tech_name, commodity in undispatched)
        warnings.warn(
            "Controller-managed outputs are not producers on any demand-reachable supply bus and "
            f"will not be demand-driven: {details}.",
            UserWarning,
            stacklevel=2,
        )

    def _get_splitter_rate_units(self, splitter_name):
        """Return the ``commodity_rate_units`` of a splitter from the tech config, or ``None``."""
        splitter_config = self.options["tech_config"].get("technologies", {}).get(splitter_name, {})
        performance_parameters = splitter_config.get("model_inputs", {}).get(
            "performance_parameters", {}
        )
        return performance_parameters.get("commodity_rate_units", None)

    def _setup_commodity(
        self,
        tech_name,
        commodity,
        commodity_rate_units=None,
        commodity_reference_var=None,
        add_in_name=True,
        initial_demand=1.0,
    ):
        """Register OpenMDAO inputs and outputs for a single (tech, commodity) pair.

        This method handles unit specification in two mutually exclusive ways:

        1. **Explicit units** - pass ``commodity_rate_units`` (e.g. ``"kW"``).
           Each variable is created with ``units=commodity_rate_units``.
        2. **Copied units** - pass ``commodity_reference_var`` (the name of an
           already-registered input whose units should be reused).
           Each variable is created with ``units=None, copy_units=commodity_reference_var``.

        Exactly one of ``commodity_rate_units`` or ``commodity_reference_var`` must be
        provided.

        The following OpenMDAO variables are created:

        - Input ``"{tech_name}_{commodity}_out"`` - commodity produced by the tech
          (only if ``add_in_name=True``).
        - Input ``"{tech_name}_rated_{commodity}_production"`` - rated production
          capacity of the tech.
        - Output ``"{tech_name}_{commodity}_set_point"`` - set-point signal sent to the
          tech's controller (which translates it into a performance-model command value).

        Args:
            tech_name (str): Name of the technology.
            commodity (str): Commodity produced by ``tech_name``.
            commodity_rate_units (str | None): Explicit unit string for the commodity.
                Mutually exclusive with ``commodity_reference_var``.
            commodity_reference_var (str | None): Name of an existing input
                variable whose units should be copied. Mutually exclusive with
                ``commodity_rate_units``.
            add_in_name (bool, optional): If True, register the
                ``"{tech_name}_{commodity}_out"`` input. Defaults to True.
            initial_demand (float, optional): Initial value for the
                set-point output. Defaults to 1.0.

        Returns:
            tuple[str, str, str]: ``(in_name, set_point_name, rated_name)``
        """
        # --- Determine unit kwargs for add_input / add_output ---------
        # Either explicit units or copy_units from a reference variable.
        if commodity_rate_units is not None:
            unit_kwargs = {"units": commodity_rate_units}
        else:
            unit_kwargs = {"units": None, "copy_units": commodity_reference_var}

        # --- Build variable names -------------------------------------
        in_name = f"{tech_name}_{commodity}_out"
        rated_name = f"{tech_name}_rated_{commodity}_production"
        set_point_name = f"{tech_name}_{commodity}_set_point"

        # --- Register inputs and output -------------------------------
        if add_in_name:
            self.add_input(
                in_name,
                val=0.0,
                shape=self.n_timesteps,
                desc=f"{commodity} output from {tech_name}",
                **unit_kwargs,
            )
        self.add_input(
            rated_name,
            val=0.0,
            desc=f"Rated {commodity} production for {tech_name}",
            **unit_kwargs,
        )
        self.add_output(
            set_point_name,
            val=initial_demand,
            shape=self.n_timesteps,
            desc=f"Set-point sent to {tech_name} for {commodity}",
            **unit_kwargs,
        )

        return in_name, set_point_name, rated_name

    def _setup_tech_category(self, category, tech_list):
        """Create OpenMDAO I/O variables for all technologies in a given category.

        This single method handles flexible, dispatchable, and storage
        technologies. The logic is identical for all three categories —
        iterate over each technology's commodities and register the
        appropriate inputs (production output, rated capacity) and output
        (per-tech demand).

        All initial demand values are ``1.0``; the solver converges from there
        using the connected rated-production inputs at run time.

        After this method returns, four lists are stored on ``self`` under
        names produced by the *category* prefix:

            ``self.{category}_input_names``
            ``self.{category}_set_point_names``
            ``self.{category}_rated_names``
            ``self.{category}_commodity_names``

        These lists are consumed by ``compute()`` and the helper methods
        ``_subtract_flexible`` and ``_dispatch_storage``.

        Args:
            category (str): One of ``"flexible"``, ``"dispatchable"``,
                or ``"storage"``. Used to name the attribute lists.
            tech_list (list[str]): Technology names belonging to this category
                (e.g. ``self.flexible_techs``).
        """
        initial_demand = 1.0

        # --- Initialize the four per-category bookkeeping lists -------
        input_names = []
        set_point_names = []
        rated_names = []
        commodity_names = []

        # --- Register I/O for every (tech, commodity) pair ------------
        for tech_name in tech_list:
            tech_commodities = [e[1] for e in self.techs_to_commodities if e[0] == tech_name]
            for commodity in tech_commodities:
                if commodity in self.commodities_to_units:
                    # Units are already known explicitly
                    in_name, set_point_name, rated_name = self._setup_commodity(
                        tech_name,
                        commodity,
                        commodity_rate_units=self.commodities_to_units[commodity],
                        add_in_name=True,
                        initial_demand=initial_demand,
                    )
                elif commodity in self.commodities_to_ref_var:
                    # Units are inferred from a previously-registered reference variable
                    in_name, set_point_name, rated_name = self._setup_commodity(
                        tech_name,
                        commodity,
                        commodity_reference_var=self.commodities_to_ref_var[commodity],
                        add_in_name=True,
                        initial_demand=initial_demand,
                    )
                else:
                    # Units are unknown; try to discover them from the connection
                    in_name = f"{tech_name}_{commodity}_out"
                    meta_data = self.add_input(
                        in_name,
                        val=0.0,
                        shape=self.n_timesteps,
                        units=None,
                        units_by_conn=True,
                        desc=f"{commodity} output from {tech_name}",
                    )
                    if meta_data["units"] is None:
                        # Still unknown: register in_name as the reference
                        # variable so later techs with this commodity can
                        # copy its units.
                        self.commodities_to_ref_var[commodity] = in_name
                        in_name, set_point_name, rated_name = self._setup_commodity(
                            tech_name,
                            commodity,
                            commodity_reference_var=self.commodities_to_ref_var[commodity],
                            add_in_name=False,
                            initial_demand=initial_demand,
                        )
                    else:
                        # Connection provided units — record them for future use
                        self.commodities_to_units[commodity] = meta_data["units"]
                        in_name, set_point_name, rated_name = self._setup_commodity(
                            tech_name,
                            commodity,
                            commodity_rate_units=self.commodities_to_units[commodity],
                            add_in_name=False,
                            initial_demand=initial_demand,
                        )

                if category == "storage":
                    self.add_input(
                        f"{tech_name}_{commodity}_storage_duration", val=0.0, shape=1, units="h"
                    )

                commodity_names.append(commodity)
                input_names.append(in_name)
                set_point_names.append(set_point_name)
                rated_names.append(rated_name)

        # --- Store lists as self.<category>_<suffix> attributes -------
        setattr(self, f"{category}_input_names", input_names)
        setattr(self, f"{category}_set_point_names", set_point_names)
        setattr(self, f"{category}_rated_names", rated_names)
        setattr(self, f"{category}_commodity_names", commodity_names)

    def _setup_fixed_category(self, fixed_list):
        """Create OpenMDAO input variables for fixed technologies.

        Fixed technologies always produce at their rated capacity and do not
        receive a set-point from the controller. Only commodity output inputs
        are registered so the controller can read their production and subtract
        it from demand.

        This method is separate from the more general ``_setup_tech_category`` because the logic
        for fixed techs is dramatically simpler
        (no demand or rated inputs, only production inputs).

        After this method returns, two lists are stored on ``self``:

            ``self.fixed_input_names``
            ``self.fixed_commodity_names``

        Args:
            fixed_list (list[str]): Technology names classified as ``"fixed"``.
        """
        input_names = []
        commodity_names = []

        for tech_name in fixed_list:
            tech_commodities = [e[1] for e in self.techs_to_commodities if e[0] == tech_name]
            for commodity in tech_commodities:
                in_name = f"{tech_name}_{commodity}_out"

                if commodity in self.commodities_to_units:
                    self.add_input(
                        in_name,
                        val=0.0,
                        shape=self.n_timesteps,
                        units=self.commodities_to_units[commodity],
                        desc=f"{commodity} output from {tech_name}",
                    )
                elif commodity in self.commodities_to_ref_var:
                    self.add_input(
                        in_name,
                        val=0.0,
                        shape=self.n_timesteps,
                        units=None,
                        copy_units=self.commodities_to_ref_var[commodity],
                        desc=f"{commodity} output from {tech_name}",
                    )
                else:
                    meta_data = self.add_input(
                        in_name,
                        val=0.0,
                        shape=self.n_timesteps,
                        units=None,
                        units_by_conn=True,
                        desc=f"{commodity} output from {tech_name}",
                    )
                    if meta_data["units"] is None:
                        self.commodities_to_ref_var[commodity] = in_name
                    else:
                        self.commodities_to_units[commodity] = meta_data["units"]

                input_names.append(in_name)
                commodity_names.append(commodity)

        self.fixed_input_names = input_names
        self.fixed_commodity_names = commodity_names

    def _setup_feedstock_category(self, feedstock_list):
        """Iterate over the feedstocks and add inputs for the available feedstock

        Args:
            feedstock_list (list[str]): name of feedstock techs
        """
        for tech_name in feedstock_list:
            tech_commodities = [e[1] for e in self.techs_to_commodities if e[0] == tech_name]
            for commodity in tech_commodities:
                in_name = f"{tech_name}_{commodity}_out"

                if commodity in self.commodities_to_units:
                    # Units are already known explicitly
                    self.add_input(
                        in_name,
                        val=0.0,
                        shape=self.n_timesteps,
                        units=self.commodities_to_units[commodity],
                        desc=f"{commodity} output from {tech_name}",
                    )
                elif commodity in self.commodities_to_ref_var:
                    # Units are inferred from a previously-registered reference variable
                    self.add_input(
                        in_name,
                        val=0.0,
                        shape=self.n_timesteps,
                        units=None,
                        copy_units=self.commodities_to_ref_var[commodity],
                        desc=f"{commodity} output from {tech_name}",
                    )
                else:
                    # Units are unknown; try to discover them from the connection
                    meta_data = self.add_input(
                        in_name,
                        val=0.0,
                        shape=self.n_timesteps,
                        units=None,
                        units_by_conn=True,
                        desc=f"{commodity} output from {tech_name}",
                    )
                    if meta_data["units"] is None:
                        # Still unknown: register in_name as the reference
                        # variable so later techs with this commodity can
                        # copy its units.
                        self.commodities_to_ref_var[commodity] = in_name
                    else:
                        # Connection provided units — record them for future use
                        self.commodities_to_units[commodity] = meta_data["units"]

    def _subtract_fixed(self, fixed_tech, remaining_demand, commodity, inputs):
        """Apply fixed techs: subtract their output from demand.

        Fixed techs always produce and do not receive a set-point.

        Returns the updated demand array.
        """
        if fixed_tech not in self.fixed_techs:
            return remaining_demand

        in_name = f"{fixed_tech}_{commodity}_out"
        if in_name not in inputs:
            return remaining_demand

        remaining_demand -= inputs[in_name]
        return remaining_demand

    def _subtract_flexible(self, flexible_tech, remaining_demand, commodity, inputs, outputs):
        """Apply flexible techs: demand = rated, subtract output from demand.

        Returns the updated demand array.
        """
        if flexible_tech not in self.flexible_techs:
            return

        if f"{flexible_tech}_rated_{commodity}_production" not in inputs:
            return

        # Set per-tech set-point equal to the rated production of that technology
        outputs[f"{flexible_tech}_{commodity}_set_point"] = inputs[
            f"{flexible_tech}_rated_{commodity}_production"
        ] * np.ones(self.n_timesteps)
        remaining_demand -= inputs[f"{flexible_tech}_{commodity}_out"]

        return remaining_demand

    def _dispatch_storage(self, storage_tech, remaining_demand, commodity, inputs, outputs):
        if storage_tech not in self.storage_techs:
            return

        if f"{storage_tech}_{commodity}_out" not in inputs:
            return

        set_point_name = f"{storage_tech}_{commodity}_set_point"
        if set_point_name not in outputs:
            return

        if self.storage_techs_to_control.get(storage_tech, False):
            # Storage tech has its own sub-controller: emit a combined demand
            # signal (always positive) equal to the commodity flowing into
            # storage from upstream techs plus any remaining demand.
            upstream_techs = self._storage_suppliers[(storage_tech, commodity)]
            commodity_into_storage = np.zeros(self.n_timesteps)
            for tech_name in upstream_techs:
                commodity_into_storage += inputs[f"{tech_name}_{commodity}_out"]

            outputs[set_point_name] = commodity_into_storage + remaining_demand
        else:
            # Storage without a sub-controller: emit a charge/discharge
            # command directly. Charge when remaining demand is negative,
            # discharge when positive.
            outputs[set_point_name] = remaining_demand

        remaining_demand -= inputs[f"{storage_tech}_{commodity}_out"]
        return remaining_demand

    def _get_commodity_for_tech(self, tech_name):
        """Get a list of the commodities produced for a technology.

        Args:
            tech_name (str): name of technology

        Returns:
            list[str]: list of commodities produced by the tech_name
        """
        tech_commodities = [e[1] for e in self.techs_to_commodities if e[0] == tech_name]

        return tech_commodities

    # ------------------------------------------------------------------
    # Heterogeneous-commodity dispatch (backward demand propagation)
    # ------------------------------------------------------------------

    def _build_converters(self):
        """Register the converters' measured-consumption inputs from the dispatch topology.

        A converter is a controller-managed technology that produces a commodity
        it does not itself consume (for example an electrolyzer:
        electricity -> hydrogen, or an ammonia synloop: hydrogen -> ammonia).
        The converters come from the conversion links of ``self._dispatch_topology``,
        which ``H2IntegrateModel`` builds, or which ``setup`` builds when running
        standalone (for example in unit tests).

        Populates the attributes used by ``_run_dispatch`` to translate demand
        on one bus into demand on the bus that supplies the converter's input:

        - ``self._links_by_out_bus``: mapping of an output bus name to the
          conversion links whose demand it feeds. Only links whose input and
          output buses are both dispatched are kept.
        - ``self._converter_upstreams``: mapping of ``(in_commodity, tech_name)``
          to the sorted tuple of controller-managed and feedstock technologies that
          supply ``in_commodity`` to the converter. ``_capacity_ratio`` sums
          their rated capacities to seed the conversion ratio.
        - ``self._converter_consumed_names``: mapping of ``(tech_name,
          in_commodity, out_commodity)`` to the ``{tech}_{in_commodity}_consumed``
          input registered for the dynamic (measured) ratio path.
        - ``self._missing_ratio_warned``: set used to emit the "missing ratio"
          warning at most once per converter.

        Conversion ratios are never authored by the user. They are derived
        automatically, with the precedence resolved in ``_conversion_ratio``:
        a measured per-timestep ratio ``consumed / produced`` when the converter
        reports its consumption via a connected ``{in_commodity}_consumed``
        output (wired by ``H2IntegrateModel``), and a capacity-based ratio
        derived from the connected rated-production inputs as the
        first-iteration and zero-output seed. Converters whose input bus has no
        controller-managed producer (for example a feedstock-supplied nitrogen
        stream) are not dispatched, so they do not require a ratio.
        """
        dispatch_links = self._dispatch_topology.dispatch_links
        self._missing_ratio_warned = set()

        self._links_by_out_bus = defaultdict(list)
        for link in dispatch_links:
            self._links_by_out_bus[link.out_bus].append(link)

        # The upstream producers (and any feedstock sources) of each converter input are
        # summed by ``_capacity_ratio`` to seed the conversion ratio from rated capacities.
        self._converter_upstreams = {
            (link.in_commodity, link.tech): link.suppliers for link in dispatch_links
        }

        # Register a measured-consumption input for every dispatched converter
        # input. H2IntegrateModel wires the converter's ``{in_commodity}_consumed``
        # output to this input so the ratio can be measured per timestep. The NaN
        # default marks the input as unconnected (dynamic ratio unavailable) when
        # running the component standalone
        self._converter_consumed_names = {}
        registered_consumed = set()
        for link in dispatch_links:
            tech_name = link.tech
            in_commodity = link.in_commodity
            out_commodity = link.out_commodity

            consumed_name = f"{tech_name}_{in_commodity}_consumed"
            # A co-product converter (one technology, one input, several
            # outputs) shares a single measured-consumption input across its
            # outputs, so register the input at most once per (tech, input).
            if consumed_name not in registered_consumed:
                if in_commodity in self.commodities_to_units:
                    unit_kwargs = {"units": self.commodities_to_units[in_commodity]}
                elif in_commodity in self.commodities_to_ref_var:
                    unit_kwargs = {
                        "units": None,
                        "copy_units": self.commodities_to_ref_var[in_commodity],
                    }
                else:
                    unit_kwargs = {"units": None}

                self.add_input(
                    consumed_name,
                    val=np.full(self.n_timesteps, np.nan),
                    shape=self.n_timesteps,
                    desc=f"Measured {in_commodity} consumed by converter {tech_name}",
                    **unit_kwargs,
                )
                registered_consumed.add(consumed_name)
            self._converter_consumed_names[(tech_name, in_commodity, out_commodity)] = consumed_name

    def _run_dispatch(self, inputs, outputs):
        """Dispatch every supply bus needed to meet the demand profile.

        Demand starts on the demand bus. Buses are processed in
        ``self._dispatch_topology.dispatch_order``, which is fixed at setup, so all
        contributions to a bus are gathered before it is dispatched. For each bus
        the shared fixed, flexible, storage, and dispatchable steps run on that
        bus's producers only. Then every conversion link that supplies the bus
        translates the converter's committed output set-point into demand on the bus
        the converter draws from (via its conversion ratio, measured when available
        and otherwise seeded from rated capacities).

        Demand is held per supply bus in a single ``derived_demand`` map (bus name ->
        profile), not per commodity. Producers of one commodity that are wired to
        different consumers (for example a grid wired only to a Haber-Bosch loop and
        wind wired only to an electrolyzer) sit on different buses, so a surplus on
        one never offsets a deficit on the other. The map also handles two topologies
        beyond the simple single-input, single-output chain:

        - Splitters / multiple consumers of one bus: when several converters (or
          loads) draw from the same bus, each contributes its translated demand
          into the same ``derived_demand[bus]`` entry, so the upstream producers
          are sized against the summed draw without any special grouping logic.
        - Multi-output converters: each conversion link is handled independently,
          so a converter that produces several commodities propagates demand for
          each output separately. Byproduct outputs that carry no demand are simply
          never dispatched and never generate upstream demand.

        Co-product converters (one technology that produces several demanded
        outputs from the same input commodity) are handled so the shared input
        is not double-counted: contributions from different outputs of the same
        converter are combined by the binding (element-wise maximum) requirement,
        since one physical unit produces its co-products together, while distinct
        converters that draw on the same bus still sum. See
        ``_accumulate_derived_demand``.

        Subclasses implement the strategy-specific dispatchable step by
        overriding ``_dispatch_dispatchables``; the fixed, flexible, and
        storage steps are shared across all strategies.

        After each run, ``self.dispatch_trace`` contains a snapshot of bus
        demands, unmet residuals, conversion ratios and their sources, and
        converter contributions. It is a debugging aid, not a public API.
        """
        # Reset the per-converter contribution tracker used to combine multiple
        # outputs of a single converter that draw on the same input bus.
        self._converter_contributions = {}

        # Flexible techs can only curtail, so they always run at their rated
        # production for every commodity they produce. Commanding them here
        # guarantees they are set even when their commodity is not explicitly
        # dispatched below (commodity-level dispatch may re-issue the value).
        for tech_name in self.flexible_techs:
            for commodity in self._get_commodity_for_tech(tech_name):
                rated_name = f"{tech_name}_rated_{commodity}_production"
                set_point_name = f"{tech_name}_{commodity}_set_point"
                if rated_name in inputs and set_point_name in outputs:
                    outputs[set_point_name] = inputs[rated_name] * np.ones(self.n_timesteps)

        topology = self._dispatch_topology
        derived_demand = {}
        bus_demand = {}
        bus_residual = {}
        ratio_trace = {}
        if topology.demand_bus is not None:
            derived_demand[topology.demand_bus] = inputs[self.demand_input_name].copy()

        for bus_name in topology.dispatch_order:
            demand = derived_demand.get(bus_name)
            if demand is None:
                # Demand never reached this bus because an upstream conversion had no ratio
                continue

            bus = topology.buses[bus_name]
            bus_demand[bus_name] = demand.copy()
            residual = self._dispatch_commodity(
                bus.commodity,
                demand.copy(),
                inputs,
                outputs,
                producers=bus.producers,
                is_demand_bus=bus_name == topology.demand_bus,
            )
            bus_residual[bus_name] = np.asarray(residual, dtype=float).copy()

            # Translate committed converter output into demand on the converters' input buses
            for link in self._links_by_out_bus.get(bus_name, ()):
                derived_demand, self._converter_contributions = self._accumulate_derived_demand(
                    derived_demand, link, inputs, outputs, ratio_trace
                )

        self._set_splitter_setpoints(inputs, outputs)
        self.dispatch_trace = {
            "dispatch_order": tuple(topology.dispatch_order),
            "bus_demand": bus_demand,
            "bus_residual": bus_residual,
            "ratios": ratio_trace,
            "contributions": {
                bus_name: {
                    tech_name: value.copy() for tech_name, value in bus_contributions.items()
                }
                for bus_name, bus_contributions in self._converter_contributions.items()
            },
        }

    def _set_splitter_setpoints(self, inputs, outputs):
        """Set each controller-managed splitter's prescribed priority allocation.

        A ``GenericSplitterPerformanceModel`` in ``prescribed_commodity`` mode
        divides its input commodity so the priority output (out1) receives a
        prescribed per-timestep amount and the second output (out2) receives the
        remainder. For a splitter placed on a controller-managed bus, the correct
        prescribed amount is the backpropagated demand of the consumers behind
        out1, found at setup by tracing forward through combiners, splitters, and
        storage. The dispatch already accumulates each converter's draw on the bus
        as its converter contribution, and the demand technology's draw is the
        demand profile itself. Setting the prescribed amount to the sum of those
        draws makes out2 equal the other consumers' draw whenever the upstream
        producers deliver the summed demand. Every consumer is then served from a
        single physical stream without starving any of them.

        Args:
            inputs: OpenMDAO inputs.
            outputs: OpenMDAO outputs; each splitter's
                ``{name}_{commodity}_set_point`` output is written in place.
        """
        for splitter in self._dispatch_topology.splitters:
            contributions = self._converter_contributions.get(splitter.bus, {})
            priority_demand = np.zeros(self.n_timesteps)
            for consumer in splitter.priority_consumers:
                if consumer == self.demand_tech:
                    priority_demand = priority_demand + inputs[self.demand_input_name]
                elif consumer in contributions:
                    priority_demand = priority_demand + contributions[consumer]
            outputs[f"{splitter.name}_{splitter.commodity}_set_point"] = np.maximum(
                priority_demand, 0.0
            )

    def _dispatch_commodity(
        self, commodity, demand, inputs, outputs, producers=None, is_demand_bus=False
    ):
        """Dispatch the technologies producing ``commodity`` to meet ``demand``.

        Applies the shared four-step priority order (fixed, flexible, storage,
        dispatchable) for a single commodity. Only technologies that produce
        ``commodity`` participate, and when ``producers`` is given, only those that
        are also in it. The dispatchable step is delegated to
        ``_dispatch_dispatchables`` so cost-aware subclasses can override it.

        Args:
            commodity (str): Commodity to dispatch (demand or a derived input).
            demand (np.ndarray): Demand profile for ``commodity`` (may be mutated).
            inputs: OpenMDAO inputs.
            outputs: OpenMDAO outputs.
            producers (Iterable[str] | None, optional): Technologies on the supply bus
                being dispatched. ``None`` allows every technology that produces
                ``commodity``.
            is_demand_bus (bool, optional): True when the bus being dispatched
                delivers the demand technology's commodity. Defaults to False.

        Returns:
            np.ndarray: Remaining unmet demand after dispatchables.
        """

        def _on_bus(tech_names):
            return [
                tech_name
                for tech_name in tech_names
                if commodity in self._get_commodity_for_tech(tech_name)
                and (producers is None or tech_name in producers)
            ]

        # 1. Fixed techs: always produce, subtract from demand
        for fixed_tech in _on_bus(self.fixed_techs):
            demand = self._subtract_fixed(fixed_tech, demand, commodity, inputs)

        # 2. Flexible techs: run at rated production, subtract from demand
        for flexible_tech in _on_bus(self.flexible_techs):
            updated = self._subtract_flexible(flexible_tech, demand, commodity, inputs, outputs)
            if updated is not None:
                demand = updated

        # 3. Storage techs: split residual demand evenly and dispatch
        storage_techs = _on_bus(self.storage_techs)
        for storage_tech in storage_techs:
            updated = self._dispatch_storage(
                storage_tech, demand / len(storage_techs), commodity, inputs, outputs
            )
            if updated is not None:
                demand = updated

        # 4. Dispatchable techs: strategy-specific (subclass hook)
        remaining = np.maximum(demand, 0.0)
        return self._dispatch_dispatchables(
            commodity,
            remaining,
            inputs,
            outputs,
            producers=producers,
            is_demand_bus=is_demand_bus,
        )

    def _dispatch_dispatchables(
        self,
        commodity,
        remaining_demand,
        inputs,
        outputs,
        producers=None,
        is_demand_bus=False,
    ):
        """Split remaining demand evenly across dispatchables producing ``commodity``.

        This is the default (cost-agnostic) dispatchable step used by
        ``DemandFollowingControl``. Cost-aware controllers override this method
        to apply merit-order or profit-aware dispatch.

        Args:
            commodity (str): Commodity being dispatched.
            remaining_demand (np.ndarray): Non-negative demand left after the fixed,
                flexible, and storage steps.
            inputs: OpenMDAO inputs.
            outputs: OpenMDAO outputs.
            producers (Iterable[str] | None, optional): Technologies on the supply bus
                being dispatched. ``None`` allows every technology.
            is_demand_bus (bool, optional): True when the bus delivers the demand
                technology's commodity. Defaults to False.

        Returns:
            np.ndarray: Remaining unmet demand (zeros under the even-split
            assumption that dispatchables absorb their full share).
        """
        dispatchables = [
            t
            for t in self.dispatchable_techs
            if commodity in self._get_commodity_for_tech(t)
            and (producers is None or t in producers)
        ]
        n_dispatchable = len(dispatchables)
        if n_dispatchable == 0:
            return remaining_demand

        for tech_name in dispatchables:
            outputs[f"{tech_name}_{commodity}_set_point"] = remaining_demand / n_dispatchable

        return np.zeros(self.n_timesteps)

    def _merit_order_dispatch(
        self, commodity, remaining_demand, inputs, outputs, sell_price=None, producers=None
    ):
        """Dispatch dispatchables producing ``commodity`` in ascending marginal-cost order.

        Each technology is dispatched up to its rated production until demand
        is met. When ``sell_price`` is provided, a technology is only
        dispatched at timesteps where its marginal cost is below the sell price
        (profit gating); demand may then go unmet. When ``producers`` is given,
        only dispatchables in it take part.

        Marginal costs come from ``_compute_marginal_costs`` and are aligned
        with ``self.dispatchable_techs``. Requires ``_setup_marginal_costs`` to
        have been called in the subclass ``setup``.

        Returns:
            np.ndarray: Remaining unmet demand after dispatch.
        """
        dispatchables = [
            t
            for t in self.dispatchable_techs
            if commodity in self._get_commodity_for_tech(t)
            and (producers is None or t in producers)
        ]

        # Initialize set-points for these dispatchables to zero
        for tech_name in dispatchables:
            outputs[f"{tech_name}_{commodity}_set_point"] = np.zeros(self.n_timesteps)

        if not dispatchables:
            return remaining_demand

        marginal_cost_by_tech = dict(
            zip(self.dispatchable_techs, self._compute_marginal_costs(inputs))
        )

        # Merit order: cheapest mean marginal cost first
        dispatch_order = sorted(dispatchables, key=lambda t: marginal_cost_by_tech[t].mean())

        remaining = np.array(remaining_demand, dtype=float)
        for tech_name in dispatch_order:
            rated = inputs[f"{tech_name}_rated_{commodity}_production"]
            if sell_price is not None:
                profitable = marginal_cost_by_tech[tech_name] < sell_price
                dispatch = np.where(profitable, np.minimum(remaining, rated), 0.0)
            else:
                dispatch = np.minimum(remaining, rated)
            outputs[f"{tech_name}_{commodity}_set_point"] = dispatch
            remaining = remaining - dispatch

        return remaining

    def _accumulate_derived_demand(self, derived_demand, link, inputs, outputs, ratio_trace):
        """Add a converter's induced demand on its input bus to ``derived_demand``.

        The converter's committed output (its ``{tech}_{out}_set_point``) is
        multiplied by the input-per-output conversion ratio to obtain the demand
        it places on the bus that supplies its input commodity. Only links whose
        input bus has a controller-managed producer reach this method, so
        feedstock-supplied streams are never translated.

        Backward propagation is opt-in: if a converter exposes neither a connected
        consumption signal nor nonzero rated capacities to seed a ratio, the
        propagation is skipped (upstream techs keep their default dispatch, the
        legacy behavior) and a one-time warning is emitted so the missing ratio is
        discoverable when heterogeneous-commodity control is intended.

        When one converter produces several demanded outputs from the same input
        commodity (a co-product converter), each output's induced demand is
        combined by the element-wise maximum rather than summed, so the shared
        input is not double-counted. Distinct converters that draw on the same
        bus (a splitter) still sum.

        Args:
            derived_demand (dict[str, np.ndarray]): Current demand per bus name.
            link (ConversionLink): Conversion whose output set-point is translated.
            inputs: OpenMDAO inputs.
            outputs: OpenMDAO outputs.
            ratio_trace (dict): Per-compute conversion-ratio snapshots.

        Returns:
            tuple[dict, dict]: Updated demand and converter contribution mappings.

        Examples:
            In Appendix A, four timesteps each demand 100 kg/h of ammonia. The
            Haber-Bosch set point is 100 kg/h, its measured ratios are 0.5 kW
            electricity and 0.18 kg hydrogen per kg ammonia, and the electrolyzer
            ratio is 55 kW per kg hydrogen. The maps change after each link:

            .. code-block:: python

                from h2integrate.control.control_strategies.system_level.slc_conversion import (
                    accumulate_derived_demand,
                )
                from h2integrate.control.control_strategies.system_level.slc_topology import (
                    ConversionLink,
                )

                derived_demand = {"ammonia:ammonia_demand": np.full(4, 100.0)}
                contributions = {}

                # Before call 1:
                # derived_demand = {"ammonia:ammonia_demand": [100] * 4}
                # contributions = {}
                derived_demand, contributions = accumulate_derived_demand(
                    derived_demand,
                    contributions,
                    ConversionLink(
                        "electricity",
                        "haber_bosch",
                        "ammonia",
                        "electricity:haber_bosch",
                        "ammonia:ammonia_demand",
                    ),
                    np.full(4, 100.0),
                    np.full(4, 0.5),
                )
                # After call 1:
                # derived_demand = {"ammonia:ammonia_demand": [100] * 4,
                #                   "electricity:haber_bosch": [50] * 4}
                # contributions = {"electricity:haber_bosch": {"haber_bosch": [50] * 4}}

                # Before call 2, the maps equal the state shown after call 1.
                derived_demand, contributions = accumulate_derived_demand(
                    derived_demand,
                    contributions,
                    ConversionLink(
                        "hydrogen",
                        "haber_bosch",
                        "ammonia",
                        "hydrogen:haber_bosch",
                        "ammonia:ammonia_demand",
                    ),
                    np.full(4, 100.0),
                    np.full(4, 0.18),
                )
                # After call 2:
                # derived_demand = {"ammonia:ammonia_demand": [100] * 4,
                #                   "electricity:haber_bosch": [50] * 4,
                #                   "hydrogen:haber_bosch": [18] * 4}
                # contributions also contains hydrogen:haber_bosch: {haber_bosch: [18] * 4}.

                # Before call 3, the maps equal the state shown after call 2.
                derived_demand, contributions = accumulate_derived_demand(
                    derived_demand,
                    contributions,
                    ConversionLink(
                        "electricity",
                        "electrolyzer",
                        "hydrogen",
                        "electricity:electrolyzer",
                        "hydrogen:haber_bosch",
                    ),
                    np.full(4, 18.0),
                    np.full(4, 55.0),
                )
                # After call 3, derived_demand also contains
                # "electricity:electrolyzer": [990] * 4, with the matching contribution.
        """
        tech_name = link.tech
        in_commodity = link.in_commodity
        out_commodity = link.out_commodity

        ratio_and_source = self._conversion_ratio(tech_name, in_commodity, out_commodity, inputs)
        if ratio_and_source is None:
            key = (tech_name, in_commodity, out_commodity)
            if key not in self._missing_ratio_warned:
                self._missing_ratio_warned.add(key)
                warnings.warn(
                    f"No conversion ratio available for converter '{tech_name}' "
                    f"('{in_commodity}' -> '{out_commodity}'); system-level control will "
                    f"not translate '{out_commodity}' demand into '{in_commodity}' demand, "
                    f"and upstream '{in_commodity}' technologies keep their default "
                    f"dispatch. Connect the converter's '{in_commodity}_consumed' output "
                    f"for a measured ratio, or provide nonzero rated production for "
                    f"'{tech_name}' and its upstream '{in_commodity}' producers so a "
                    f"capacity-based ratio can seed heterogeneous-commodity control.",
                    stacklevel=2,
                )
            return derived_demand, self._converter_contributions

        ratio, source = ratio_and_source
        ratio_trace[(in_commodity, tech_name, out_commodity)] = {
            "value": ratio.copy(),
            "source": source.copy(),
        }
        set_point = np.asarray(outputs[f"{tech_name}_{out_commodity}_set_point"], dtype=float)
        updated_demand, updated_contributions = accumulate_derived_demand(
            derived_demand,
            self._converter_contributions,
            link,
            set_point,
            ratio,
        )
        return updated_demand, updated_contributions

    def _capacity_ratio(self, tech_name, in_commodity, out_commodity, inputs):
        """Return a scalar input-per-output ratio from rated capacities, or ``None``.

        The ratio is the total rated ``in_commodity`` capacity of the converter's
        upstream producers divided by the converter's rated ``out_commodity``
        production. Controller-managed producers contribute their connected
        ``{tech}_rated_{in_commodity}_production`` input; feedstock sources, which
        have no rated-production input, contribute the mean of their
        ``{tech}_{in_commodity}_out`` supply. This capacity-based ratio seeds the
        conversion ratio on the first solver iteration and at zero-output
        timesteps, so conversion ratios never have to be authored by hand.

        Returns ``None`` when the converter's rated output input is absent or
        zero, or when the total upstream input capacity is zero (no meaningful
        seed is available).
        """
        supplier_rated_capacities = []
        feedstock_supplies = []
        upstreams = self._converter_upstreams.get((in_commodity, tech_name), [])
        for upstream in upstreams:
            rated_name = f"{upstream}_rated_{in_commodity}_production"
            if rated_name in inputs:
                supplier_rated_capacities.append(inputs[rated_name])
            elif upstream in self.feedstock_comps:
                out_name = f"{upstream}_{in_commodity}_out"
                if out_name in inputs:
                    feedstock_supplies.append(inputs[out_name])

        rated_out_name = f"{tech_name}_rated_{out_commodity}_production"
        if rated_out_name not in inputs:
            return None
        return calculate_capacity_ratio(
            supplier_rated_capacities, feedstock_supplies, inputs[rated_out_name]
        )

    def _conversion_ratio(self, tech_name, in_commodity, out_commodity, inputs):
        """Return per-timestep conversion ratios and their sources, or ``None``.

        Ratio precedence (conversion ratios are derived automatically; the user
        never authors them):

        1. Dynamic (measured): where the converter reports its consumption via a
           connected ``{tech}_{in_commodity}_consumed`` input, the ratio is
           ``consumed / produced`` at every timestep with nonzero production.
           This is the general, nonlinear-aware path; the plant solver resolves
           the resulting feedback without an analytic Jacobian.
        2. Capacity (seed / fallback): the scalar ratio of the upstream rated
           input capacity to the converter's rated output capacity (see
           ``_capacity_ratio``), used at zero-output timesteps and on the first
           iteration before any consumption has been measured. When no
           consumption is measured at all, the capacity ratio is used at every
           timestep.

        Returns ``None`` when neither a capacity ratio nor a connected
        consumption signal is available, signalling the caller to skip
        propagation. Otherwise returns ``(ratio, source)`` arrays, where source
        is ``"measured"`` for valid measurements and ``"capacity"`` for the
        capacity-based seed or fallback.
        """
        key = (tech_name, in_commodity, out_commodity)
        capacity = self._capacity_ratio(tech_name, in_commodity, out_commodity, inputs)

        consumed = None
        consumed_name = self._converter_consumed_names.get(key)
        if consumed_name is not None:
            measured = np.asarray(inputs[consumed_name], dtype=float)
            # A registered but unconnected input keeps its NaN sentinel; treat it
            # as "no measurement" so the capacity ratio (or the warning) applies
            if np.any(np.isfinite(measured)):
                consumed = measured

        produced = np.asarray(inputs[f"{tech_name}_{out_commodity}_out"], dtype=float)
        if consumed is None:
            if capacity is None:
                return None
            consumed = np.full(produced.shape, np.nan)

        valid = np.isfinite(consumed) & np.isfinite(produced) & (produced != 0.0)
        if capacity is None and not np.any(valid):
            return None

        return calculate_conversion_ratio(consumed, produced, capacity)

    # ------------------------------------------------------------------
    # Marginal-cost helpers for cost-aware controllers
    # ------------------------------------------------------------------

    def _setup_marginal_costs(self):
        """Set up marginal cost inputs for dispatchable techs based on ``cost_per_tech``.

        Should be called from ``setup()`` of cost-aware controllers
        (e.g., ``CostMinimizationControl``, ``ProfitMaximizationControl``).

        Reads ``cost_per_tech`` from
        ``plant_config["system_level_control"]["control_parameters"]`` and creates appropriate
        OpenMDAO inputs for each dispatchable technology:

        - Numeric value (e.g. ``0.05``): used directly as a constant
          marginal cost in ``USD/(commodity_rate_unit*h)``. No additional
          inputs or connections are required.
        - ``"buy_price"``: creates a ``{tech_name}_buy_price`` input
          whose default value is read from the technology's cost config
          (``electricity_buy_price`` for Grid, ``price`` for Feedstock).
          Can be scalar or time-varying and may be overridden at runtime
          via ``prob.set_val()``. Grid electricity prices use ``USD/(kW*h)``
          regardless of the SLC demand commodity.
        - ``"VarOpEx"``: creates a ``{tech_name}_VarOpEx`` input
          connected to the cost model's ``VarOpEx`` output. The
          per-unit marginal cost is computed at run time by dividing
          ``VarOpEx`` by the total production.
        - ``"feedstock"``: looks up ``technology_interconnections`` to
          find all feedstock technologies connected upstream of the
          dispatchable tech, sums their ``VarOpEx`` outputs, and
          divides by the tech's total production. Handles the common
          single-feedstock case as well as multiple feedstock streams.
        """

        self.cost_per_tech = (
            self.options["plant_config"]["system_level_control"]
            .get("control_parameters", {})
            .get("cost_per_tech", {})
        )
        self.dt_hours = self.options["plant_config"]["plant"]["simulation"]["dt"] / 3600
        hours_simulated = self.dt_hours * self.n_timesteps
        self.fraction_of_year_simulated = hours_simulated / 8760
        plant_life = int(self.options["plant_config"]["plant"]["plant_life"])

        self.dispatchable_marginal_cost_types = []

        for tech_name in self.dispatchable_techs:
            cost_spec = self.cost_per_tech.get(tech_name, 0.0)

            if isinstance(cost_spec, int | float):
                self.dispatchable_marginal_cost_types.append(("scalar", cost_spec))

            elif cost_spec == "buy_price":
                # Read default buy price from tech config and create an input on
                # the SLC whose shape matches the tech's own buy-price input.
                # That allows ``H2IntegrateModel`` to wire the tech's buy-price
                # input directly to this SLC input (input-to-input connection),
                # so a single ``prob.set_val()`` on the tech propagates here.
                default_price, input_shape = _get_buy_price_default_and_shape(
                    self.options["tech_config"],
                    tech_name,
                    self.n_timesteps,
                    plant_life,
                )
                price_input_name = _get_tech_buy_price_input_name(
                    self.options["tech_config"], tech_name
                )
                # Grid purchase prices are electricity-specific, not demand-commodity prices.
                price_units = (
                    "USD/(kW*h)"
                    if price_input_name == "electricity_buy_price"
                    else f"USD/({self.commodity_rate_units}*h)"
                )

                self.add_input(
                    f"{tech_name}_buy_price",
                    val=default_price,
                    shape=input_shape,
                    units=price_units,
                    desc=f"Buy price for {tech_name}",
                )
                self.dispatchable_marginal_cost_types.append(("buy_price", tech_name))

            elif cost_spec == "VarOpEx":
                self.add_input(
                    f"{tech_name}_VarOpEx",
                    val=0.0,
                    shape=plant_life,
                    units="USD/year",
                    desc=f"Variable operating expenditure from {tech_name}",
                )
                self.dispatchable_marginal_cost_types.append(("VarOpEx", tech_name))

            elif cost_spec == "feedstock":
                # Find feedstock techs connected upstream of this tech
                feedstock_names = self._find_feedstock_techs(tech_name)
                if not feedstock_names:
                    raise ValueError(
                        f"cost_per_tech '{cost_spec}' for '{tech_name}' requires "
                        f"at least one feedstock connected upstream in "
                        f"technology_interconnections, but none were found."
                    )
                for feedstock_name in feedstock_names:
                    self.add_input(
                        f"{feedstock_name}_VarOpEx",
                        val=0.0,
                        shape=plant_life,
                        units="USD/year",
                        desc=f"Variable operating expenditure from feedstock {feedstock_name}",
                    )
                self.dispatchable_marginal_cost_types.append(
                    ("feedstock", (tech_name, feedstock_names))
                )

            else:
                raise ValueError(
                    f"Unknown cost_per_tech value '{cost_spec}' for '{tech_name}'. "
                    f"Must be a numeric value, 'buy_price', 'VarOpEx', or 'feedstock'."
                )

    def _compute_marginal_costs(self, inputs):
        """Compute per-timestep marginal costs for each dispatchable tech.

        Returns:
            list[np.ndarray]: marginal cost arrays, one per dispatchable
            tech, each of shape ``(n_timesteps,)``.
        """
        marginal_costs = []

        for marginal_cost_type, marginal_cost_data in self.dispatchable_marginal_cost_types:
            if marginal_cost_type == "scalar":
                marginal_cost = np.full(self.n_timesteps, marginal_cost_data)
            elif marginal_cost_type == "buy_price":
                marginal_cost = self._buy_price_marginal_cost(inputs, marginal_cost_data)
            elif marginal_cost_type == "VarOpEx":
                marginal_cost = self._varopex_marginal_cost(inputs, marginal_cost_data)
            elif marginal_cost_type == "feedstock":
                marginal_cost = self._feedstock_marginal_cost(inputs, marginal_cost_data)
            else:
                marginal_cost = np.zeros(self.n_timesteps)

            marginal_costs.append(marginal_cost)

        return marginal_costs

    def _buy_price_marginal_cost(self, inputs, tech_name):
        """Compute marginal cost from buy price.

        Returns a per-timestep marginal cost array equal to the
        technology's buy price. The underlying input may be scalar
        (shape ``(1,)``), per-timestep (shape ``(n_timesteps,)``) or
        per-year (shape ``(plant_life,)``); the value is broadcast or
        repeated as needed to span all simulation timesteps.
        """
        buy_price = np.asarray(inputs[f"{tech_name}_buy_price"])

        if buy_price.shape == (self.n_timesteps,) or buy_price.shape == (1,):
            return np.broadcast_to(buy_price, self.n_timesteps).copy()

        if buy_price.shape == (int(self.options["plant_config"]["plant"]["plant_life"]),):
            # Per-year price: use the first year's value as a representative
            # per-timestep marginal cost for dispatch decisions.
            return np.full(self.n_timesteps, buy_price[0])

        return np.broadcast_to(buy_price, self.n_timesteps).copy()

    def _varopex_marginal_cost(self, inputs, tech_name):
        """Compute marginal cost from VarOpEx and commodity output.

        Divides the first-year ``VarOpEx`` (``$/year``) by the
        annualized total production to obtain an average marginal cost
        in ``$/(commodity_amount_unit)``.

        Returns a constant per-timestep array.
        """
        varopex = inputs[f"{tech_name}_VarOpEx"]  # $/year, shape=plant_life

        # Use commodity_out already connected for this dispatchable tech
        tech_commodities = self._get_commodity_for_tech(tech_name)
        commodity = tech_commodities[0] if tech_commodities else self.commodity

        production = inputs[f"{tech_name}_{commodity}_out"]  # rate units, shape=n_timesteps
        total_production = production.sum() * self.dt_hours

        if total_production > 0:
            annual_production = total_production / self.fraction_of_year_simulated
            marginal_cost_scalar = varopex[0] / annual_production
        else:
            marginal_cost_scalar = 0.0

        return np.full(self.n_timesteps, marginal_cost_scalar)

    def _find_feedstock_techs(self, tech_name):
        """Find feedstock technologies upstream of ``tech_name`` at any depth.

        Uses graph ancestors rather than direct interconnections so that
        feedstocks behind intermediate components (e.g. combiners) are found.

        Args:
            tech_name (str): The dispatchable technology name.

        Returns:
            list[str]: Names of upstream feedstock technologies.
        """
        # All ancestors at any depth, filtered to feedstocks
        ancestors = nx.ancestors(self.technology_graph, tech_name)
        return [tech for tech in ancestors if tech in self.feedstock_comps]

    def _feedstock_marginal_cost(self, inputs, marginal_cost_data):
        """Compute marginal cost from upstream feedstock VarOpEx values.

        Sums the first-year ``VarOpEx`` from all feedstock technologies
        connected to the dispatchable tech, then divides by the tech's
        annualized total production.

        Args:
            marginal_cost_data (tuple): ``(tech_name, feedstock_names)`` where
                tech_name is the dispatchable tech and feedstock_names
                is a list of upstream feedstock technology names.

        Returns:
            np.ndarray: constant per-timestep marginal cost array.
        """
        tech_name, feedstock_names = marginal_cost_data

        # Sum VarOpEx from all connected feedstocks (first year)
        total_varopex = sum(inputs[f"{fs}_VarOpEx"][0] for fs in feedstock_names)

        # Get the tech's production
        tech_commodities = self._get_commodity_for_tech(tech_name)
        commodity = tech_commodities[0] if tech_commodities else self.commodity

        production = inputs[f"{tech_name}_{commodity}_out"]
        total_production = production.sum() * self.dt_hours

        if total_production > 0:
            annual_production = total_production / self.fraction_of_year_simulated
            marginal_cost_scalar = total_varopex / annual_production
        else:
            marginal_cost_scalar = 0.0

        return np.full(self.n_timesteps, marginal_cost_scalar)

    def find_converter_techs(self, include_feedstock_sources=True):
        """Identify technologies that transform one commodity into another.

        A "converter" is a tech whose output commodities differ from the commodities
        produced by its upstream ancestors (e.g. an electrolyzer: electricity → hydrogen).

        Args:
            include_feedstock_sources (bool, optional): If True, include feedstock techs
                in the set of candidate technologies. Defaults to True.

        Returns:
            set[tuple[str, str, str]]: Set of ``(input_commodity, tech_name, output_commodity)``
                tuples for each detected conversion. Returns ``None`` for single-commodity systems.
        """
        if include_feedstock_sources:
            input_techs = self.input_techs | set(self.feedstock_comps)
        else:
            input_techs = self.input_techs.copy()

        # Single-commodity systems have no special handling by definition
        if not self.multi_commodity_system:
            return

        converter_techs = set()
        node_order = list(self.technology_graph.nodes())
        edges = list(self.technology_graph.edges(data="commodity"))

        # Track the most recently discovered converter so we can scope
        # upstream searches for chained converters (A→B→C where B and C
        # both convert). Without this, C would see A's commodity as upstream
        # input even though B already consumed it.
        last_converter = None

        for source_tech, _, _ in edges:
            if source_tech not in input_techs:
                continue

            # Get the commodities produced by this tech (the "output" side of the conversion)
            output_commodities = set(self._get_commodity_for_tech(source_tech))

            # Find controlled ancestors of this tech
            all_ancestors = nx.ancestors(self.technology_graph, source_tech) & input_techs

            if last_converter is not None:
                # Only consider ancestors that appear after the last converter
                # in topological order, preventing double-counting across
                # chained converters.
                converter_idx = node_order.index(last_converter)
                nodes_after_converter = set(node_order[converter_idx + 1 :])
                ancestors = all_ancestors & nodes_after_converter
            else:
                ancestors = all_ancestors

            # Keep only ancestors actually connected (reachable) to this tech
            connected_ancestors = [
                t for t in ancestors if nx.has_path(self.technology_graph, t, source_tech)
            ]

            # Gather all commodities produced by connected ancestors
            input_commodities = set()
            for ancestor in connected_ancestors:
                input_commodities.update(self._get_commodity_for_tech(ancestor))

            # A converter has commodities that appear only on one side:
            # upstream-only commodities are consumed, output-only are produced.
            consumed = input_commodities - output_commodities
            produced = output_commodities - input_commodities

            # If both sides have unique commodities, this tech is a converter
            if consumed and produced:
                for in_comm in consumed:
                    for out_comm in produced:
                        converter_techs.add((in_comm, source_tech, out_comm))
                last_converter = source_tech

        return converter_techs
