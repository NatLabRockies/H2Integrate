import numpy as np
import openmdao.api as om


class SystemLevelControlBase(om.ExplicitComponent):
    """Base class for system-level controllers.

    Provides common setup logic shared by all system-level control strategies:
    demand input, curtailable/dispatchable/storage technology I/O creation,
    and technology classification reading from ``plant_config``.

    Subclasses must implement ``compute()`` with their dispatch strategy.

    Configuration is read from ``plant_config["system_level_control"]``,
    which must contain:

    - ``commodity``: the commodity being controlled (e.g. "electricity")
    - ``commodity_units``: units string (or None)
    - ``demand_tech``: name of the demand technology
    - ``curtailable_techs``: list of curtailable technology names
    - ``dispatchable_techs``: list of dispatchable technology names
    - ``storage_techs``: list of storage technology names
    """

    def initialize(self):
        self.options.declare("driver_config", types=dict)
        self.options.declare("plant_config", types=dict)
        self.options.declare("tech_config", types=dict)

    def setup(self):
        plant_config = self.options["plant_config"]
        slc_config = plant_config["system_level_control"]

        self.n_timesteps = plant_config["plant"]["simulation"]["n_timesteps"]

        # Read pre-computed classification from plant_config
        self.commodity = slc_config["demand_commodity"]
        self.commodity_units = slc_config.get("demand_commodity_rate_units", None)
        self.demand_tech = slc_config["demand_tech"]
        self.curtailable_techs = list(slc_config.get("curtailable_techs", []))
        self.dispatchable_techs = list(slc_config.get("dispatchable_techs", []))
        self.storage_techs = list(slc_config.get("storage_techs", []))

        # Input: demand profile (default value from config)
        demand_profile = slc_config.get("demand_profile", 0.0)
        self.demand_input_name = f"{self.commodity}_demand"
        self.add_input(
            self.demand_input_name,
            val=demand_profile,
            shape=self.n_timesteps,
            units=self.commodity_units,
            desc=f"Demand profile of {self.commodity}",
        )

        self.techs_to_commodities = slc_config["tech_to_commodity"]

        # There are multiple commodities being produced by technologies in the system
        self.multi_commodity_system = (
            True if len({e[-1] for e in self.techs_to_commodities}) > 1 else False
        )

        self.commodities_to_units = {self.commodity: self.commodity_units}
        self.commodities_to_ref_var = {}
        self._setup_tech_category("curtailable", self.curtailable_techs)
        self._setup_tech_category(
            "dispatchable", self.dispatchable_techs, demand_profile=demand_profile
        )
        self._setup_tech_category("storage", self.storage_techs)

    def _setup_commodity_for_given_units(
        self, tech_name, commodity, commodity_units, add_in_name=True, initial_set_point=0.0
    ):
        """Adds inputs and outputs for a commodity when the units are known.
        The inputs and outputs that are added have the below naming convention:

        - ``f"{tech_name}_{commodity}_out"``: input commodity produced by tech_name
        - ``f"{tech_name}_rated_{commodity}_production"``: input rated commodity production
            capacity of tech_name
        - ``f"{tech_name}_{commodity}_set_point"``: output control setpoint for tech_name

        Args:
            tech_name (str): name of technology
            commodity (str): commodity of the technology described by `tech_name`
            commodity_units (str): units of commodity
            add_in_name (bool, optional): If True, add the input for the in_name variable.
                Defaults to True.
            initial_set_point (float, optional): Add as the initial value for the
                set_point variable. Defaults to 0.0.
        Returns:
            tuple(str, str, str): tuple of in_name, set_point_name, and rated_name
        """
        in_name = f"{tech_name}_{commodity}_out"
        set_point_name = f"{tech_name}_{commodity}_set_point"
        rated_name = f"{tech_name}_rated_{commodity}_production"

        if add_in_name:
            self.add_input(
                in_name,
                val=0.0,
                shape=self.n_timesteps,
                units=commodity_units,
                desc=f"{commodity} output from {tech_name}",
            )
        self.add_input(
            rated_name,
            val=0.0,
            units=commodity_units,
            desc=f"Rated {commodity} production for {tech_name}",
        )
        self.add_output(
            set_point_name,
            val=initial_set_point,
            shape=self.n_timesteps,
            units=commodity_units,
            desc=f"Set point for {tech_name} {commodity} curtailment",
        )

        return in_name, set_point_name, rated_name

    def _setup_commodity_for_copy_units(
        self, tech_name, commodity, commodity_reference_var, add_in_name=True, initial_set_point=0.0
    ):
        """Adds inputs and outputs for a commodity where the units are based on a reference
        input variable. The inputs and outputs that are added have the below
        naming convention:

        - ``f"{tech_name}_{commodity}_out"``: input commodity produced by tech_name
        - ``f"{tech_name}_rated_{commodity}_production"``: input rated commodity production
            capacity of tech_name
        - ``f"{tech_name}_{commodity}_set_point"``: output control setpoint for tech_name

        Args:
            tech_name (str): name of technology
            commodity (str): commodity of the technology described by `tech_name`
            commodity_reference_var (str): name of input to copy units from
            add_in_name (bool, optional): If True, add the input for the in_name variable.
                Defaults to True.
            initial_set_point (float, optional): Add as the initial value for the
                set_point variable. Defaults to 0.0.

        Returns:
            tuple(str, str, str): tuple of in_name, set_point_name, and rated_name
        """
        in_name = f"{tech_name}_{commodity}_out"
        set_point_name = f"{tech_name}_{commodity}_set_point"
        rated_name = f"{tech_name}_rated_{commodity}_production"

        if add_in_name:
            self.add_input(
                in_name,
                val=0.0,
                shape=self.n_timesteps,
                units=None,
                copy_units=commodity_reference_var,
                desc=f"{commodity} output from {tech_name}",
            )
        self.add_input(
            rated_name,
            val=0.0,
            units=None,
            copy_units=commodity_reference_var,
            desc=f"Rated {commodity} production for {tech_name}",
        )
        self.add_output(
            set_point_name,
            val=initial_set_point,
            shape=self.n_timesteps,
            units=None,
            copy_units=commodity_reference_var,
            desc=f"Set point for {tech_name} {commodity} curtailment",
        )

        return in_name, set_point_name, rated_name

    def _setup_tech_category(self, category, tech_list, demand_profile=None):
        """Create OpenMDAO I/O variables for all technologies in a given category.

        This single method handles curtailable, dispatchable, and storage
        technologies. The logic is identical for all three categories —
        iterate over each technology's commodities and register the
        appropriate inputs (production output, rated capacity) and output
        (control set-point) — with one difference:

        * **Curtailable / Storage** (``demand_profile is None``):
          ``initial_set_point`` is ``0.0``. Curtailable techs are later
          assigned set-points equal to their rated production; storage techs
          get set-points computed at run-time in ``_dispatch_storage``.

        * **Dispatchable** (``demand_profile`` is provided):
          ``initial_set_point`` is the demand evenly divided among the
          dispatchable techs that produce the demanded commodity, giving
          the solver a reasonable starting guess.

        After this method returns, four lists are stored on ``self`` under
        names produced by the *category* prefix:

            ``self.{category}_input_names``
            ``self.{category}_set_point_names``
            ``self.{category}_rated_names``
            ``self.{category}_commodity_names``

        These lists are consumed by ``compute()`` and the helper methods
        ``_subtract_curtailable`` and ``_dispatch_storage``.

        Args:
            category (str): One of ``"curtailable"``, ``"dispatchable"``,
                or ``"storage"``. Used to name the attribute lists.
            tech_list (list[str]): Technology names belonging to this category
                (e.g. ``self.curtailable_techs``).
            demand_profile (float | np.ndarray | None, optional):
                Only relevant for **dispatchable** techs. When provided, the
                demand is split equally among dispatchable techs that produce
                the demanded commodity to set a non-zero ``initial_set_point``.
                For curtailable and storage techs, leave as ``None`` (default).
        """
        # --- Compute initial_set_point --------------------------------
        # Dispatchable techs: split demand equally among those that produce
        # the demanded commodity so the solver starts from a feasible guess.
        # Curtailable and storage techs always start at 0.
        if demand_profile is not None:
            n_producing = len(
                [t for t in tech_list if self.commodity in self._get_commodity_for_tech(t)]
            )
            if n_producing > 0:
                if np.isscalar(demand_profile):
                    initial_set_point = demand_profile / n_producing
                else:
                    initial_set_point = np.array(demand_profile) / n_producing
            else:
                initial_set_point = 0.0
        else:
            initial_set_point = 0.0

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
                    in_name, set_point_name, rated_name = self._setup_commodity_for_given_units(
                        tech_name,
                        commodity,
                        self.commodities_to_units[commodity],
                        add_in_name=True,
                        initial_set_point=initial_set_point,
                    )
                elif commodity in self.commodities_to_ref_var:
                    # Units are inferred from a previously-registered reference variable
                    in_name, set_point_name, rated_name = self._setup_commodity_for_copy_units(
                        tech_name,
                        commodity,
                        self.commodities_to_ref_var[commodity],
                        add_in_name=True,
                        initial_set_point=initial_set_point,
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
                        in_name, set_point_name, rated_name = self._setup_commodity_for_copy_units(
                            tech_name,
                            commodity,
                            self.commodities_to_ref_var[commodity],
                            add_in_name=False,
                            initial_set_point=initial_set_point,
                        )
                    else:
                        # Connection provided units — record them for future use
                        self.commodities_to_units[commodity] = meta_data["units"]
                        in_name, set_point_name, rated_name = self._setup_commodity_for_given_units(
                            tech_name,
                            commodity,
                            self.commodities_to_units[commodity],
                            add_in_name=False,
                            initial_set_point=initial_set_point,
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

    def _subtract_curtailable(self, inputs, outputs, demand):
        """Apply curtailable techs: set_point = rated, subtract output from demand.

        Returns the updated demand array.
        """
        for in_name, set_point_name, rated_name, commodity in zip(
            self.curtailable_input_names,
            self.curtailable_set_point_names,
            self.curtailable_rated_names,
            self.curtailable_commodity_names,
        ):
            # Output the set-point as the rated production of that technology
            outputs[set_point_name] = inputs[rated_name] * np.ones(self.n_timesteps)
            if commodity == self.commodity:
                demand -= inputs[in_name]

        return demand

    def _dispatch_storage(self, inputs, outputs, demand):
        """Dispatch storage techs proportionally and subtract actual output from demand.

        Positive set_point = discharge, negative = charge.
        Returns the updated demand array.
        """
        # calculate the number of storage technologies that
        # produce the demanded commodity
        n_storage = len(
            [s for s in self.storage_techs if self.commodity in self._get_commodity_for_tech(s)]
        )
        if n_storage > 0:
            storage_share = demand / n_storage
            for set_point_name, commodity in zip(
                self.storage_set_point_names, self.storage_commodity_names
            ):
                if commodity == self.commodity:
                    outputs[set_point_name] = storage_share

        for tech_name, in_name in zip(self.storage_techs, self.storage_input_names):
            if self.commodity in self._get_commodity_for_tech(tech_name):
                demand -= inputs[in_name]

        return demand

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
        ``plant_config["system_level_control"]`` and creates appropriate
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
        slc_config = self.options["plant_config"]["system_level_control"]
        self.cost_per_tech = slc_config.get("cost_per_tech", {})
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
                # Read default buy price from tech config
                tech_config = self.options["tech_config"]
                tech_def = tech_config.get("technologies", {}).get(tech_name, {})
                model_inputs = tech_def.get("model_inputs", {})
                cost_params = model_inputs.get("cost_parameters", {})
                shared_params = model_inputs.get("shared_parameters", {})
                all_params = {**shared_params, **cost_params}

                default_price = all_params.get(
                    "electricity_buy_price",
                    all_params.get("price", 0.0),
                )

                self.add_input(
                    f"{tech_name}_buy_price",
                    val=default_price,
                    shape=self.n_timesteps,
                    units=f"USD/({self.commodity_units}*h)",
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
        technology's buy price (scalar or time-varying).
        """
        return np.broadcast_to(inputs[f"{tech_name}_buy_price"], self.n_timesteps).copy()

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
        """Find feedstock technologies connected upstream of tech_name.

        Scans ``technology_interconnections`` for connections whose
        destination is tech_name and whose source uses
        ``FeedstockPerformanceModel`` or ``FeedstockCostModel``.

        Args:
            tech_name (str): the dispatchable technology name.

        Returns:
            list[str]: names of upstream feedstock technologies.
        """
        tech_config = self.options["tech_config"]
        technologies = tech_config.get("technologies", {})
        interconnections = self.options["plant_config"].get("technology_interconnections", [])

        # Upstream tech names for this dispatchable tech
        upstream_techs = [conn[0] for conn in interconnections if conn[1] == tech_name]

        feedstock_names = []
        for upstream in upstream_techs:
            tech_def = technologies.get(upstream, {})
            perf_model = tech_def.get("performance_model", {}).get("model", "")
            cost_model = tech_def.get("cost_model", {}).get("model", "")
            if "Feedstock" in perf_model or "Feedstock" in cost_model:
                feedstock_names.append(upstream)

        return feedstock_names

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
