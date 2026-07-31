import warnings
import itertools

import numpy as np
import networkx as nx
import openmdao.api as om


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
        self.add_input(
            self.demand_input_name,
            val=10.0,
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

        self._post_setup_multi_commodity()

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
            upstream_techs = self.get_upstream_techs_for_commodity(storage_tech, commodity)
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
          via ``prob.set_val()``.
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

                self.add_input(
                    f"{tech_name}_buy_price",
                    val=default_price,
                    shape=input_shape,
                    units=f"USD/({self.commodity_rate_units}*h)",
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

    def _new_post_setup_multi_commodity(self):
        if not self.multi_commodity_system:
            return
        # converter upstreams now has values of lists intead of sets
        converters, converter_upstreams = self._find_converter_techs_new()
        grouped_techs = {f"{k[0][0]}-{i}": k[1] for i, k in enumerate(converter_upstreams.items())}
        alt_grouped_techs = {
            (f"{k[0][0]}", f"{i}"): k[1] for i, k in enumerate(converter_upstreams.items())
        }
        {k[1] for k in converters}

        demand_group_techs = self.get_successors_for_tech_with_input_cmod(
            self.demand_tech, self.commodity
        )

        # converter_info.add((self.commodity, self.demand_tech, self.commodity))
        # conversion fator recipes requires simple_graph, converters, demand_tech, grouped_techs
        grouped_techs[f"{self.commodity}-{len(converter_upstreams)+1}"] = demand_group_techs
        alt_grouped_techs[(self.commodity, f"{len(converter_upstreams)+1}")] = demand_group_techs

        # last_converter = [k for k in demand_group_techs if k in converter_techs]
        reversed_grouped_techs = {}
        for k, v in grouped_techs.items():
            for vv in list(v):
                if vv in reversed_grouped_techs:
                    if isinstance(reversed_grouped_techs[vv], str):
                        reversed_grouped_techs[vv] = [reversed_grouped_techs[vv], k]
                    else:
                        reversed_grouped_techs[vv] = reversed_grouped_techs[vv] + [k]
                else:
                    reversed_grouped_techs[vv] = k

        def get_group_for_tech(tech_name):
            groups = {k for k, v in grouped_techs.items() if tech_name in v}
            return list(groups)

        def get_group_for_tech_commodity(tech_name, output_cmod):
            possible_converter_grp = [k for k in converter_upstreams if k[0] == output_cmod]
            if not possible_converter_grp and output_cmod == self.commodity:
                groups = get_group_for_tech(tech_name)
                return groups
            if possible_converter_grp:
                possible_groups = []
                for grp in possible_converter_grp:
                    if tech_name in converter_upstreams[grp]:
                        possible_groups += [
                            f"{k[0]}-{k[1]}"
                            for k, v in alt_grouped_techs.items()
                            if k[0] == output_cmod and tech_name in v
                        ]

                return possible_groups
            warnings.warn("Whats up", UserWarning, stacklevel=3)

        simple_graph = nx.DiGraph()
        for e in list(self.technology_graph.edges(data="commodity")):
            s0, d0, c = e

            s = reversed_grouped_techs.get(s0, s0)
            d = reversed_grouped_techs.get(d0, d0)

            if isinstance(s, str) and isinstance(d, str) and isinstance(c, str):
                if s != d:
                    simple_graph.add_edge(s, d, commodity=c)
            elif isinstance(s, str) and isinstance(d, list) and isinstance(c, str):
                for di in d:
                    if s != di:
                        simple_graph.add_edge(s, di, commodity=c)
            elif isinstance(s, list) and isinstance(d, str) and isinstance(c, str):
                for si in s:
                    if si != d:
                        simple_graph.add_edge(si, d, commodity=c)
            elif isinstance(s, list) and isinstance(d, str) and isinstance(c, list):
                for ci in c:
                    group_name = get_group_for_tech_commodity(s0, ci)
                    simple_graph.add_edge(group_name[0], d, commodity=ci)
                    # TODO: add error if group_name is greater than 0
            else:
                raise ValueError("have not accounted for this design yet")

        self.converters = converters
        self.grouped_techs = grouped_techs
        self.simple_graph = simple_graph
        conversion_recipes = self._make_conversion_factor_recipes()
        self.conversion_recipes = conversion_recipes

    def _post_setup_multi_commodity(self):
        if not self.multi_commodity_system:
            return
        converters, converter_upstreams = self._find_converter_techs(include_feedstock_sources=True)
        # Group together technologies that are connected to a converter
        # I.e., group together an electrolyzer an hydrogen storage,
        # name this group as the shared commodity with a unique number
        grouped_techs = {f"{k[0][0]}-{i}": k[1] for i, k in enumerate(converter_upstreams.items())}

        # 3. Add in a conversion factor of 1 for all non-converter technologies
        converter_tech_names = {v[1] for v in list(converters)}

        conversion_factor_keys = [
            (tc[1], tc[0], tc[1])
            for tc in self.techs_to_commodities
            if tc[0] not in converter_tech_names
        ]
        # missing_input_techs = set(self.input_techs) - set(reversed_grouped_techs.keys())

        # NOTE: maybe only run below if theres a missing_input_tech
        non_converter_input_techs_in_group, demand_group = self._find_demand_tech_group(
            converters, converter_upstreams
        )
        grouped_techs.update(demand_group)

        conversion_factor_keys += [
            (self.commodity, k, self.commodity) for k in non_converter_input_techs_in_group
        ]

        # Add demand component to converter_upstreams
        demand_group_techs = list(demand_group.values())[0]
        converter_upstreams[(self.commodity, self.demand_tech)] = (
            set(demand_group_techs) & self.input_techs
        )

        # 2. Make a dictionary for future-use that has keys of the technology names and
        # the group they belong to
        reversed_grouped_techs = {}
        for k, v in grouped_techs.items():
            for vv in list(v):
                reversed_grouped_techs[vv] = k

        # 4. Track the technologies that are non_input_techs so we know
        # they don't have a converison factor. Also add these technologies
        # to the reversed_group_techs

        # Get the nodes of the technology graph that aren't a controllable technology
        # Also add these technologies to the reversed_group_techs

        non_input_techs_conversion_factor_keys, techs_to_groups = (
            self._find_group_for_non_input_techs(grouped_techs)
        )
        # Add conversion factors of 1 for the technologies that are non_input_techs
        conversion_factor_keys += non_input_techs_conversion_factor_keys
        reversed_grouped_techs.update(
            techs_to_groups
        )  # unsure why we're not updating grouped_techs

        # 5. Make the edges of the grouped technologies
        simple_graph = nx.DiGraph()
        for e in list(self.technology_graph.edges(data="commodity")):
            s0, d0, c = e

            s = reversed_grouped_techs.get(s0, s0)
            d = reversed_grouped_techs.get(d0, d0)

            if s != d:
                simple_graph.add_edge(s, d, commodity=c)

        self.simple_graph = simple_graph
        self.non_converter_conversion_factor_keys = conversion_factor_keys
        self.grouped_techs = grouped_techs
        self.converters = converters
        self.converter_upstreams = converter_upstreams
        self.converter_tech_names = converter_tech_names

        conversion_recipes = self._make_conversion_factor_recipes()

        self.conversion_recipes = conversion_recipes

    def get_upstream_techs_for_commodity(
        self, tech_name: str, commodity: str, include_feedstock_sources=True
    ):
        """Find controlled technologies upstream of ``tech_name`` that output ``commodity``.

        Walks the technology graph backwards from ``tech_name``, finds all ancestor
        nodes that have an outgoing edge carrying ``commodity``, then filters to only
        those managed by the controller.

        Args:
            tech_name (str): Technology whose upstream suppliers are sought.
            commodity (str): Commodity of interest (e.g. ``"electricity"``).
            include_feedstock_sources (bool, optional): If True, feedstock techs are
                included in the set of controller-managed technologies. Defaults to True.

        Returns:
            list[str]: Controller-managed technologies upstream of ``tech_name``
                that produce ``commodity``.
        """
        # Build the set of techs the controller can see
        if include_feedstock_sources:
            input_techs = self.input_techs | set(self.feedstock_comps)
        else:
            input_techs = set(self.input_techs)

        # All graph ancestors of tech_name (any depth)
        ancestors = nx.ancestors(self.technology_graph, tech_name)

        # Keep only ancestors that have an outgoing edge carrying the target commodity.
        # Edges are (source, dest, commodity) tuples
        ancestors_with_commodity = {
            src
            for src, _, comm in self.technology_graph.edges(data="commodity")
            if src in ancestors and comm == commodity
        }

        # Intersect with controller-managed techs
        return list(ancestors_with_commodity & input_techs)

    def get_successors_for_tech_with_input_cmod(self, tech, input_commodity):
        in_flows = dict(self.technology_graph.in_degree)
        if in_flows[tech] < 1:
            # Tech does not have any input commodiites
            return []

        successor_techs_with_commod = set()
        upstream_techs = set(self.technology_graph.predecessors(tech))
        for upstream_tech in upstream_techs:
            produces_cmod = False
            if (
                commod := self.technology_graph.edges[upstream_tech, tech].get("commodity")
            ) is not None:
                if isinstance(commod, str) and commod == input_commodity:
                    successor_techs_with_commod.add(upstream_tech)
                    produces_cmod = True
                if isinstance(commod, list) and input_commodity in commod:
                    successor_techs_with_commod.add(upstream_tech)
                    produces_cmod = True
            if in_flows[upstream_tech] > 1 and produces_cmod:
                new_techs = self.get_successors_for_tech_with_input_cmod(
                    upstream_tech, input_commodity
                )
                if new_techs:
                    successor_techs_with_commod |= set(new_techs)

        return list(successor_techs_with_commod)

    def _find_converter_techs_new(self):
        in_flows = dict(self.technology_graph.in_degree)
        out_flows = dict(self.technology_graph.out_degree)

        non_converter_techs = [
            k for k in list(self.technology_graph.nodes) if in_flows[k] < 1 or out_flows[k] < 1
        ]
        likely_converter_techs = (
            set(self.technology_graph.nodes) - set(non_converter_techs) - set(self.storage_techs)
        ) & set(self.input_techs)

        converter_info = set()
        converter_upstreams = {}
        for converter in list(likely_converter_techs):
            # predecessors are upstream and directly connected to the converter
            predecessor_techs = set(self.technology_graph.predecessors(converter))
            # succesor techs are directly downstream of the converter
            successor_techs = set(self.technology_graph.successors(converter))

            input_commods = set()
            for upstream_tech in predecessor_techs:
                if (
                    cmod := self.technology_graph.edges[upstream_tech, converter].get("commodity")
                ) is not None:
                    if isinstance(cmod, str):
                        input_commods.add(cmod)
                    else:
                        input_commods |= set(cmod)

            output_commods = set()
            for downstream_tech in list(successor_techs):
                if (
                    cmod := self.technology_graph.edges[converter, downstream_tech].get("commodity")
                ) is not None:
                    if isinstance(cmod, str):
                        output_commods.add(cmod)
                    else:
                        output_commods |= set(cmod)

            consumed = input_commods - output_commods
            produced = output_commods - input_commods
            if consumed and produced:
                for input_commod in input_commods:
                    upstream_techs_with_commod = self.get_successors_for_tech_with_input_cmod(
                        converter, input_commod
                    )
                    converter_upstreams[(input_commod, converter)] = upstream_techs_with_commod
                    for output_commod in output_commods:
                        converter_info.add((input_commod, converter, output_commod))

        return converter_info, converter_upstreams

    def _find_converter_techs(self, include_feedstock_sources=True):
        """Identify technologies that transform one commodity into another.

        A "converter" is a tech whose output commodities differ from the commodities
        produced by its upstream ancestors (e.g. an electrolyzer: electricity → hydrogen).

        Args:
            include_feedstock_sources (bool, optional): If True, include feedstock techs
                in the set of candidate technologies. Defaults to True.

        Returns:
            2-element tuple containing:

            - **converters** (tuple[str, str, str]): Set of tuples formatted as
                ``(input_commodity, tech_name, output_commodity)`` tuples.
            - **upstreams** (dict[tuple[str,str], set[str]]): Keys are set of
                ``(input_commodity, tech_name)`` and the values are a set of
                upstream technologies that output the `input_commodity` to `tech_name`.
        """
        # TODO: add an input thats `include_demand_component`

        if include_feedstock_sources:
            input_techs = self.input_techs | set(self.feedstock_comps)
        else:
            input_techs = self.input_techs.copy()

        # Single-commodity systems have no special handling by definition
        if not self.multi_commodity_system:
            return

        # ``converter_techs`` is a set of ``(input_commodity, tech_name, output_commodity)``
        # tuples for each detected conversion
        converter_techs = set()
        # ``converter_order`` is a dictionary defining the directional order of the converters
        # the keys are integers, lower numbers mean it comes first.
        # Values are the format of entries in ``converter_techs``
        converter_order = {}
        # ``converter_ancestors`` is a dictionary with the same keys as ``converter_order``
        # and the values as upstream technologies that produce ``input_commodity`` and are
        # connected to the converter tech (does not include converters in upstream technologies)
        converter_ancestors = {}
        node_order = list(self.technology_graph.nodes())
        edges = list(self.technology_graph.edges(data="commodity"))
        ii = 0

        # NOTE: using tracked_ancestors would make this code very senstive to the order of
        # tech connections
        # I.e., would get different results if feedstocks connected to haber_bosch first
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
            if consumed and produced and (source_tech not in self.storage_techs):
                for in_comm in consumed:
                    for out_comm in produced:
                        # if in_comm != out_comm:
                        converter_techs.add((in_comm, source_tech, out_comm))
                        converter_order[ii] = (in_comm, source_tech, out_comm)
                        converter_ancestors[ii] = [
                            e[0]
                            for e in self.techs_to_commodities
                            if e[1] == in_comm and e[0] in connected_ancestors
                        ]

                        ii += 1
                last_converter = source_tech

        if len(converter_techs) < len(converter_order):
            # remove duplicate converter orders
            rev_converter_order = {v: k for k, v in converter_order.items()}
            # re-reverse it
            converter_order = {v: k for k, v in rev_converter_order.items()}
            # remove duplicate converter orders
            # re-reverse it
            converter_ancestors = {k: converter_ancestors[k] for k in list(converter_order.keys())}

        # Make sure we iterate through the converters in the right order
        converter_cnt = list(converter_order.keys())
        converter_cnt.sort()
        previous_converters = set()  # track previous converters
        # ``upstreams`` is similar to ``converter_ancestors`` but has keys as a tuple formatted as
        # ``(input_commodity, tech_name)``. The values are a set of the technologies upstream of
        # ``tech_name`` that output ``input_commodity`` that is input to ``tech_name``.
        # Key difference from ``converter_ancestors`` is that this includes upstream converter techs
        upstreams = {}  # upstreams is similar to
        # NOTE: unsure how the below logic will work with splitters
        for converter_ii in converter_cnt:
            input_cmod, tech, output_cmod = converter_order[converter_ii]
            if input_cmod == output_cmod:
                continue
            # Get all the upstream technologies that produce a specific commodity
            upstream1 = self.get_upstream_techs_for_commodity(
                tech, input_cmod, include_feedstock_sources=True
            )
            # Combined the upstream techs with all the previous converters
            upstream_converter = set(upstream1) & previous_converters
            # Remove any of the previous converters that arent connected to this converter
            upstreams[(input_cmod, tech)] = set(upstream1) & (
                upstream_converter | set(converter_ancestors[converter_ii])
            )
            previous_converters.add(tech)
        # return converter_techs, converter_order, converter_ancestors, upstreams
        # return converter_order, upstreams
        return converter_techs, upstreams

    def get_converter_capacity_conversion_ratio(
        self, inputs, in_cmod, out_cmod, converter_tech, tech_ancestors
    ):
        """Get capacity ratio of ``in_cmod/out_cmod`` for technology ``converter_tech``

        Args:
            inputs (dict): OpenMDAO inputs
            in_cmod (str): commodity input to the ``converter_tech``
            out_cmod (str): commodity output from the ``converter_tech``
            converter_tech (str): name of the converter technologies
            tech_ancestors (list[str] | set[str] | tuple[str]): upstream technologies
                that produce ``in_cmod`` to the ``converter_tech``

        Returns:
            float | np.ndarray: capacity ratio of `in_cmod/out_cmod`.
        """
        rated_name_fmt = "{tech}_rated_{commod}_production"
        feedstock_name_fmt = "{tech}_{commod}_out"
        in_names = [rated_name_fmt.format(tech=t, commod=in_cmod) for t in list(tech_ancestors)]
        in_feedstock_names = [
            feedstock_name_fmt.format(tech=t, commod=in_cmod)
            for t in list(tech_ancestors)
            if t in self.feedstock_comps
        ]

        total_in_cmod_capac = [inputs[n] for n in in_names if n in inputs]
        avg_feedstock_capac = [inputs[n].mean() for n in in_feedstock_names if n in inputs]

        total_input_capac = np.array(total_in_cmod_capac).sum()
        total_feedstock_capac = np.array(avg_feedstock_capac).sum()

        total_commodity_in_capacity = total_input_capac + total_feedstock_capac

        total_output_capac = inputs[rated_name_fmt.format(tech=converter_tech, commod=out_cmod)]
        return total_commodity_in_capacity / total_output_capac[0]

    def get_converter_conversion_ratio(
        self, inputs, in_cmod, out_cmod, converter_tech, tech_ancestors
    ):
        """Get conversion ratio of ``in_cmod/out_cmod`` for technology ``converter_tech``

        Args:
            inputs (dict): OpenMDAO inputs
            in_cmod (str): commodity input to the ``converter_tech``
            out_cmod (str): commodity output from the ``converter_tech``
            converter_tech (str): name of the converter technologies
            tech_ancestors (list[str] | set[str] | tuple[str]): upstream technologies
                that produce ``in_cmod`` to the ``converter_tech``

        Returns:
            np.ndarray: conversion ratio of `in_cmod/out_cmod`.
        """
        input_name_fmt = "{tech}_{commod}_out"
        in_names = [input_name_fmt.format(tech=t, commod=in_cmod) for t in list(tech_ancestors)]
        total_in_cmod = [inputs[n] for n in in_names if n in inputs]
        total_input = np.array(total_in_cmod).sum(axis=0)
        total_output = inputs[input_name_fmt.format(tech=converter_tech, commod=out_cmod)]

        conversion_factor = total_input / np.abs(total_output)
        return conversion_factor

    def dict_values_to_flat_list(self, dictionary):
        """Aggregate all the values in a dictionary to a flattened list

        Args:
            dictionary (dict): dictionary with values as either a list or set

        Returns:
            list: flattened list of all the values in ``dictionary``
        """
        flat_list = []
        for v in dictionary.values():
            if isinstance(v, set):
                v = list(v)

            flat_list.extend(v)
        return flat_list

    def _check_demand_tech_group_connections(self, converter_tech_names, missing_input_techs):
        # NOTE: sometimes these warnings happen because of the dependency on the
        # tech connection order
        successful = True
        commodities_for_missing_techs = {
            tech: self._get_commodity_for_tech(tech) for tech in list(missing_input_techs)
        }
        commodities_out = self.dict_values_to_flat_list(commodities_for_missing_techs)

        if self.commodity not in list(commodities_out):
            warnings.warn(
                "none of the demand commodities are made by missing techs",
                UserWarning,
                stacklevel=3,
            )
            successful = False

        missing_tech_downstreams = [
            list(nx.descendants(self.technology_graph, tech)) for tech in missing_input_techs
        ]
        missing_tech_downstreams_shared = {self.demand_tech}
        other_converters = converter_tech_names - missing_input_techs

        for downstream in missing_tech_downstreams:
            missing_tech_downstreams_shared = missing_tech_downstreams_shared & set(downstream)
            # TODO: check that no other converters are inbetween
            if set(downstream) & other_converters:
                warnings.warn(
                    "theres an extra converter between the missing techs and the demand",
                    UserWarning,
                    stacklevel=3,
                )
                successful = False
        if not missing_tech_downstreams_shared or len(missing_tech_downstreams_shared) > 1:
            warnings.warn("something unexpected happened", UserWarning, stacklevel=3)
            successful = False

        missing_converter_tech = missing_input_techs & converter_tech_names
        if len(missing_converter_tech) > 1:
            warnings.warn(
                "unsure how code will work with multiple converters connected to demand",
                UserWarning,
                stacklevel=3,
            )
            successful = False
        if not missing_converter_tech:
            warnings.warn("should have a converter before demand ...", UserWarning, stacklevel=3)
            successful = False

        for m0 in list(missing_converter_tech):
            for m1 in list(missing_input_techs - missing_converter_tech):
                m0_upstream = nx.has_path(self.technology_graph, m0, m1)
                m1_upstream = nx.has_path(self.technology_graph, m1, m0)
                if not m0_upstream or m1_upstream:
                    warnings.warn(
                        f"The technologies {m0} and {m1} aren't connected",
                        UserWarning,
                        stacklevel=3,
                    )
                    successful = False
        return successful

    def _find_demand_tech_group(self, converters, converter_upstreams):
        """Find the technologies that are connected to the demand converter
        and the demand technology that produce the demanded commodity

        Args:
            converters (tuple[str, str, str]): Set of tuples formatted as
                ``(input_commodity, tech_name, output_commodity)`` tuples.
            converter_upstreams (dict[tuple[str,str], set[str]]): Keys are set of
                ``(input_commodity, tech_name)`` and the values are a set of
                upstream technologies that output the `input_commodity` to `tech_name`.

        Returns:
            2-element tuple containing:

            - **non_converter_input_techs_in_group** (list[str]): List of
                non-converter technologies that are connected to the demand technology
                and produce the demanded commodity. Only includes technologies in
                `self.input_techs`
            - **demand_group** (dict[str, set[str]]): Key is the name of the demand group
                and values are a set of all the technologies that are connected to the
                demand technology and produce the demanded commodity.
        """
        found_input_techs = self.dict_values_to_flat_list(converter_upstreams)
        missing_input_techs = set(self.input_techs) - set(found_input_techs)

        converter_tech_names = {v[1] for v in list(converters)}

        successful = self._check_demand_tech_group_connections(
            converter_tech_names, missing_input_techs
        )
        if not successful:
            msg = "A bug may exist. Please refer to earlier warnings"
            warnings.warn(msg, UserWarning, stacklevel=3)

        input_comps = {self.demand_tech} - missing_input_techs
        missing_techs_to_downstreams = {
            tech: list(nx.descendants(self.technology_graph, tech)) for tech in missing_input_techs
        }
        missing_tech_downstreams = self.dict_values_to_flat_list(missing_techs_to_downstreams)
        non_input_components = set(missing_tech_downstreams) - input_comps

        unique_number = int(len(converter_upstreams) + 1)
        group_name = f"{self.commodity}-{int(unique_number)}"

        missing_converter_tech = missing_input_techs & converter_tech_names

        # all techs in group, include non-controllable ones (like combiners)
        all_techs_in_group = list(non_input_components | missing_input_techs)
        # input techs in group except for the converter
        non_converter_input_techs_in_group = list(missing_input_techs - missing_converter_tech)
        demand_group = {group_name: set(all_techs_in_group)}

        return non_converter_input_techs_in_group, demand_group

    def _find_group_for_non_input_techs(self, grouped_techs):
        # Get the nodes of the technology graph that aren't a controllable technology
        def get_group_for_tech(tech_name):
            group = [grp for grp, techs in grouped_techs.items() if tech_name in techs]
            if len(group) == 0:
                return None
                # msg = f"Cannot find simplified group for technology {tech_name}"
                # raise ValueError(msg)
            return group[0]

        techs_to_groups = {}
        conversion_factor_keys = []

        non_input_techs = (
            set(self.technology_graph.nodes) - set(self.input_techs) - {self.demand_tech}
        )
        # Also add these technologies to the reversed_group_techs

        for non_t in list(non_input_techs):
            up_techs = set(self.technology_graph.predecessors(non_t)) - non_input_techs
            down_techs = set(self.technology_graph.successors(non_t)) - non_input_techs

            tech_group = get_group_for_tech(non_t)
            commod = None
            if up_techs and (tech_group is None):
                for t in list(up_techs):
                    commod = self.technology_graph.edges[t, non_t].get("commodity", None)
                    if commod is not None:
                        # Add these technologies to the reversed_group_techs
                        techs_to_groups[non_t] = get_group_for_tech(t)
                        break

            if down_techs and (commod is None) and (tech_group is None):
                for t in list(down_techs):
                    commod = self.technology_graph.edges[non_t, t].get("commodity", None)
                    if commod is not None:
                        # Add these technologies to the reversed_group_techs
                        techs_to_groups[non_t] = get_group_for_tech(t)
                        # techs_to_groups[t] = get_group_for_tech(t)
                        break
            # Add conversion factors of 1 for the technologies that are non_input_techs
            if tech_group is None:
                conversion_factor_keys.append((commod, non_t, commod))
        return conversion_factor_keys, techs_to_groups

    def _make_conversion_factor_recipes(self):
        """Make recipes to for compounding conversion factor calculations.

        Returns:
            dict[tuple(str,str,str), list[list[tuple]]]: recipes to calculate the
            conversion ratio from the demand commodity to all upstream subsystems.
            Keys are the recipe name, formatted as tuples of
            `(output_commodity, input_commodity, converter_tech_group)`.
            Values are embedded lists. Each list defines the technologies in a
            step of the conversion. Each element of a list is a tuple formatted as
            `(input_commodity, technology, output_commodity)`
        """
        if not self.multi_commodity_system:
            return {}

        converter_tech_names = {v[1] for v in list(self.converters)}

        # 6. Get the compounding conversion factors
        in_degs = dict(self.simple_graph.in_degree)
        starting_techs = {k for k, v in in_degs.items() if v == 0}

        compounding_conversion_factor_recipes = {}

        for starting_tech in list(starting_techs):
            paths = list(nx.all_simple_paths(self.simple_graph, starting_tech, self.demand_tech))

            if len(paths) > 1:
                warnings.warn("There should only be one path", UserWarning, stacklevel=3)
            path = paths[0]
            reverse_path = path[::-1]
            commodity_conversions = [
                self.simple_graph.edges[p0, p1].get("commodity", None)
                for p0, p1 in zip(reverse_path[1:], reverse_path[:-1])
            ]
            commodity_nodes = list(itertools.pairwise(commodity_conversions))
            techs = reverse_path[1:]

            commodity_graph = nx.DiGraph()  # nodes are commodities
            for i, commod_node in enumerate(commodity_nodes):
                # ammonia, hydrogen
                down_cmod, up_cmod = commod_node
                commodity_graph.add_edge(down_cmod, up_cmod, tech=techs[i])

            commodity_edges = commodity_graph.edges(data="tech")

            path_recipe = []

            for edge in commodity_edges:
                # in_cmod is demand of next tech
                out_cmod, in_cmod, tech = edge
                if tech in self.grouped_techs:
                    techs_in_group = list(self.grouped_techs[tech])

                    recipe = []
                    for t in techs_in_group:
                        if t in converter_tech_names:
                            recipe.append((in_cmod, t, out_cmod))
                        else:
                            recipe.append((out_cmod, t, out_cmod))
                    # TODO: add check if any other non-converter techs have a non-1 conversion factor
                else:
                    recipe = [(in_cmod, tech, out_cmod)]

                path_recipe.append(recipe)
                compounding_conversion_factor_recipes[(out_cmod, in_cmod, tech)] = (
                    path_recipe.copy()
                )

        return compounding_conversion_factor_recipes

    def _get_techs_for_conversion(self, input_cmod, tech):
        # TODO: remove this - I think its unused
        tech_to_demand = [
            s
            for s in list(self.simple_graph.predecessors(tech))
            if self.simple_graph.edges[s, tech].get("commodity", "") == input_cmod
        ]
        if len(tech_to_demand) != 1:
            raise ValueError("Unexpected situation!")
        if tech_to_demand[0] in self.grouped_techs:
            return list(self.grouped_techs[tech_to_demand[0]])
        return tech_to_demand[0]

    def _get_techs_to_demand_from_recipe(self, recipe_name):
        _, input_cmod, tech_group = recipe_name
        techs_to_demand = [
            s
            for s in list(self.simple_graph.predecessors(tech_group))
            if self.simple_graph.edges[s, tech_group].get("commodity", "") == input_cmod
        ]
        if len(techs_to_demand) != 1:
            raise ValueError("Unexpected situation!")
        if techs_to_demand[0] in self.grouped_techs:
            techs_in_group = list(self.grouped_techs[techs_to_demand[0]])
        else:
            techs_in_group = techs_to_demand[0]
        return techs_in_group

    def _get_conversion_from_recipe(self, conversion_factors, recipe):
        # Get comp
        path_conversion = 1.0

        for path in recipe:
            for tech_conversion in path:
                path_conversion *= conversion_factors.get(tech_conversion, 1.0)

        return path_conversion
