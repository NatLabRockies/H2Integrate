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
        self._setup_curtailable_techs()
        self._setup_dispatchable_techs(demand_profile)
        self._setup_storage_techs()

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

    def _setup_curtailable_techs(self):
        """Create I/O for curtailable technologies."""
        self.curtailable_input_names = []
        self.curtailable_set_point_names = []
        self.curtailable_rated_names = []
        self.curtailable_commodity_names = []
        for tech_name in self.curtailable_techs:
            tech_commodities = [e[1] for e in self.techs_to_commodities if e[0] == tech_name]
            for commodity in tech_commodities:
                if commodity in self.commodities_to_units:
                    # The units of this commodity are defined in self.commodities_to_units
                    in_name, set_point_name, rated_name = self._setup_commodity_for_given_units(
                        tech_name, commodity, self.commodities_to_units[commodity], add_in_name=True
                    )
                elif commodity in self.commodities_to_ref_var:
                    # The units of this commodity are defined by a reference variable
                    in_name, set_point_name, rated_name = self._setup_commodity_for_copy_units(
                        tech_name,
                        commodity,
                        self.commodities_to_ref_var[commodity],
                        add_in_name=True,
                    )
                else:
                    # The units of this commodity are unknown at this moment
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
                        # If the units are still unknown, use the in_name of this
                        # technology as the reference variable for future technologies
                        # that use this commodity
                        self.commodities_to_ref_var[commodity] = in_name
                        in_name, set_point_name, rated_name = self._setup_commodity_for_copy_units(
                            tech_name,
                            commodity,
                            self.commodities_to_ref_var[commodity],
                            add_in_name=False,
                        )
                    else:
                        # If the units are known from a connection,
                        # then use those units for this commodity
                        self.commodities_to_units.update({commodity: meta_data["units"]})
                        in_name, set_point_name, rated_name = self._setup_commodity_for_given_units(
                            tech_name,
                            commodity,
                            self.commodities_to_units[commodity],
                            add_in_name=False,
                        )

                self.curtailable_commodity_names.append(commodity)
                self.curtailable_input_names.append(in_name)
                self.curtailable_set_point_names.append(set_point_name)
                self.curtailable_rated_names.append(rated_name)

    def _setup_dispatchable_techs(self, demand_profile):
        """Create I/O for dispatchable technologies."""
        # calculate the number of dispatchable technologies that
        # produce the demanded commodity
        n_dispatchable = len(
            [
                s
                for s in self.dispatchable_techs
                if self.commodity in self._get_commodity_for_tech(s)
            ]
        )
        if n_dispatchable > 0:
            if np.isscalar(demand_profile):
                initial_set_point = demand_profile / n_dispatchable
            else:
                initial_set_point = np.array(demand_profile) / n_dispatchable
        else:
            initial_set_point = 0.0

        self.dispatchable_input_names = []
        self.dispatchable_set_point_names = []
        self.dispatchable_rated_names = []
        self.dispatchable_commodity_names = []
        for tech_name in self.dispatchable_techs:
            tech_commodities = [e[1] for e in self.techs_to_commodities if e[0] == tech_name]
            for commodity in tech_commodities:
                if commodity in self.commodities_to_units:
                    in_name, set_point_name, rated_name = self._setup_commodity_for_given_units(
                        tech_name,
                        commodity,
                        self.commodities_to_units[commodity],
                        add_in_name=True,
                        initial_set_point=initial_set_point,
                    )
                elif commodity in self.commodities_to_ref_var:
                    in_name, set_point_name, rated_name = self._setup_commodity_for_copy_units(
                        tech_name,
                        commodity,
                        self.commodities_to_ref_var[commodity],
                        add_in_name=True,
                        initial_set_point=initial_set_point,
                    )
                else:
                    # commodity units not yet defined
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
                        self.commodities_to_ref_var[commodity] = in_name
                        in_name, set_point_name, rated_name = self._setup_commodity_for_copy_units(
                            tech_name,
                            commodity,
                            self.commodities_to_ref_var[commodity],
                            add_in_name=False,
                            initial_set_point=initial_set_point,
                        )
                    else:
                        self.commodities_to_units.update({commodity: meta_data["units"]})
                        in_name, set_point_name, rated_name = self._setup_commodity_for_given_units(
                            tech_name,
                            commodity,
                            self.commodities_to_units[commodity],
                            add_in_name=False,
                            initial_set_point=initial_set_point,
                        )

                self.dispatchable_commodity_names.append(commodity)
                self.dispatchable_input_names.append(in_name)
                self.dispatchable_set_point_names.append(set_point_name)
                self.dispatchable_rated_names.append(rated_name)

    def _setup_storage_techs(self):
        """Create I/O for storage technologies."""
        self.storage_input_names = []
        self.storage_set_point_names = []
        self.storage_rated_names = []
        self.storage_commodity_names = []
        for tech_name in self.storage_techs:
            tech_commodities = [e[1] for e in self.techs_to_commodities if e[0] == tech_name]
            for commodity in tech_commodities:
                if commodity in self.commodities_to_units:
                    in_name, set_point_name, rated_name = self._setup_commodity_for_given_units(
                        tech_name, commodity, self.commodities_to_units[commodity], add_in_name=True
                    )
                elif commodity in self.commodities_to_ref_var:
                    in_name, set_point_name, rated_name = self._setup_commodity_for_copy_units(
                        tech_name,
                        commodity,
                        self.commodities_to_ref_var[commodity],
                        add_in_name=True,
                    )
                else:
                    # commodity units not yet defined
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
                        self.commodities_to_ref_var[commodity] = in_name
                        in_name, set_point_name, rated_name = self._setup_commodity_for_copy_units(
                            tech_name,
                            commodity,
                            self.commodities_to_ref_var[commodity],
                            add_in_name=False,
                        )
                    else:
                        self.commodities_to_units.update({commodity: meta_data["units"]})
                        in_name, set_point_name, rated_name = self._setup_commodity_for_given_units(
                            tech_name,
                            commodity,
                            self.commodities_to_units[commodity],
                            add_in_name=False,
                        )

                self.storage_commodity_names.append(commodity)
                self.storage_input_names.append(in_name)
                self.storage_set_point_names.append(set_point_name)
                self.storage_rated_names.append(rated_name)

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
