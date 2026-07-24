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
            input_techs = self.input_techs.copy()

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
