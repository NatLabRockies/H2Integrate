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
        self.storage_techs_to_control = slc_config.get("storage_techs_to_control", {})
        self.technology_graph = slc_config["technology_graph"]

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

    # def _get_upstream_techs(self, inputs, tech_name):
    #     tech_commodities = self._get_commodity_for_tech(tech_name)

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
        rated_name = f"{tech_name}_rated_{commodity}_production"

        if self.storage_techs_to_control.get(tech_name, False):
            # tech_name is storage and does have an attached controller
            set_point_name = f"{tech_name}_{commodity}_demand"
        else:
            # if tech_name is not in storage_techs_to_control
            # or storage tech does not have an attached controller
            set_point_name = f"{tech_name}_{commodity}_set_point"

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
        rated_name = f"{tech_name}_rated_{commodity}_production"

        if self.storage_techs_to_control.get(tech_name, False):
            # tech_name is storage and does have an attached controller
            set_point_name = f"{tech_name}_{commodity}_demand"
        else:
            # if tech_name is not in storage_techs_to_control
            # or storage tech does not have an attached controller
            set_point_name = f"{tech_name}_{commodity}_set_point"

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
        technologies.  The logic is identical for all three categories —
        iterate over each technology's commodities and register the
        appropriate inputs (production output, rated capacity) and output
        (control set-point) — with one difference:

        * **Curtailable / Storage** (``demand_profile is None``):
          ``initial_set_point`` is ``0.0``.  Curtailable techs are later
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
                or ``"storage"``.  Used to name the attribute lists.
            tech_list (list[str]): Technology names belonging to this category
                (e.g. ``self.curtailable_techs``).
            demand_profile (float | np.ndarray | None, optional):
                Only relevant for **dispatchable** techs.  When provided, the
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
            # split the demand across the storage technologies
            storage_share = demand / n_storage
            for set_point_name, commodity in zip(
                self.storage_set_point_names, self.storage_commodity_names
            ):
                if commodity == self.commodity:
                    if f"_{commodity}_demand" in set_point_name:
                        # storage tech has a controller, output combined demand (always positive)
                        # TODO: update to output whatever is input to storage + storage_share
                        outputs[set_point_name] = np.clip(storage_share, a_min=0.0, a_max=None)
                    else:
                        # storage tech does not have a controller,
                        # output set point (charge/discharge) command
                        # charge when remaining demand is negative
                        # discharge when remaining demand is positive
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
