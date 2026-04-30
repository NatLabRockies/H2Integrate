import numpy as np
import networkx as nx
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

        self.techs_to_commodities = self._create_sources_to_commodities(
            self.options["plant_config"].get("technology_interconnections")
        )
        self.commodities_to_units = {self.commodity: self.commodity_units}
        self._setup_curtailable_techs()
        self._setup_dispatchable_techs(demand_profile)
        self._setup_storage_techs()

    def _create_sources_to_commodities(self, tech_interconnections):
        techs_to_connect = set(
            self.curtailable_techs + self.dispatchable_techs + self.storage_techs
        )

        G = nx.DiGraph()
        for connection in tech_interconnections:
            source = connection[0]
            destination = connection[1]
            if len(connection) == 4:
                G.add_edge(source, destination, commodity=connection[2])
            else:
                G.add_edge(source, destination)

        # Use a set to remove duplicates (in case one tech produces multiple commodities)
        sources_to_commodities = {
            (e[0], e[-1]) for e in G.edges(data="commodity") if e[-1] is not None
        }
        # Remove feedstocks and connectors
        techs_to_commodities = {
            (e[0], e[-1]) for e in sources_to_commodities if e[0] in techs_to_connect
        }
        return techs_to_commodities

    def _setup_curtailable_techs(self):
        """Create I/O for curtailable technologies."""
        self.curtailable_input_names = []
        self.curtailable_set_point_names = []
        self.curtailable_rated_names = []
        self.curtailable_commodity_names = []
        for tech_name in self.curtailable_techs:
            tech_commodities = [e[1] for e in self.techs_to_commodities if e[0] == tech_name]
            for commodity in tech_commodities:
                in_name = f"{tech_name}_{commodity}_out"
                set_point_name = f"{tech_name}_{commodity}_set_point"
                rated_name = f"{tech_name}_rated_{commodity}_production"

                # Determine units of the commodity
                if commodity in self.commodities_to_units:
                    commodity_units = self.commodities_to_units[commodity]
                    self.add_input(
                        in_name,
                        val=0.0,
                        shape=self.n_timesteps,
                        units=commodity_units,
                        desc=f"{commodity} output from {tech_name}",
                    )
                else:
                    # commodity units not yet defined, so get it
                    meta_data = self.add_input(
                        in_name,
                        val=0.0,
                        shape=self.n_timesteps,
                        units=None,
                        units_by_conn=True,
                        desc=f"{commodity} output from {tech_name}",
                    )
                    self.commodities_to_units.update({commodity: meta_data["units"]})

                self.add_input(
                    rated_name,
                    val=0.0,
                    units=self.commodities_to_units[commodity],
                    desc=f"Rated {commodity} production for {tech_name}",
                )
                self.add_output(
                    set_point_name,
                    val=0.0,
                    shape=self.n_timesteps,
                    units=self.commodities_to_units[commodity],
                    desc=f"Set point for {tech_name} {commodity} curtailment",
                )
                self.curtailable_commodity_names.append(commodity)
                self.curtailable_input_names.append(in_name)
                self.curtailable_set_point_names.append(set_point_name)
                self.curtailable_rated_names.append(rated_name)

    def _setup_dispatchable_techs(self, demand_profile):
        """Create I/O for dispatchable technologies."""
        n_dispatchable = len(self.dispatchable_techs)
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
                in_name = f"{tech_name}_{self.commodity}_out"
                set_point_name = f"{tech_name}_{self.commodity}_set_point"
                rated_name = f"{tech_name}_rated_{self.commodity}_production"
                if commodity in self.commodities_to_units:
                    commodity_units = self.commodities_to_units[commodity]
                    self.add_input(
                        in_name,
                        val=0.0,
                        shape=self.n_timesteps,
                        units=commodity_units,
                        desc=f"{commodity} output from {tech_name}",
                    )
                else:
                    # commodity units not yet defined, so get it
                    meta_data = self.add_input(
                        in_name,
                        val=0.0,
                        shape=self.n_timesteps,
                        units=None,
                        units_by_conn=True,
                        desc=f"{commodity} output from {tech_name}",
                    )
                    self.commodities_to_units.update({commodity: meta_data["units"]})

                self.add_input(
                    rated_name,
                    val=0.0,
                    units=self.commodities_to_units[commodity],
                    desc=f"Rated {commodity} production for {tech_name}",
                )
                self.add_output(
                    set_point_name,
                    val=initial_set_point,
                    shape=self.n_timesteps,
                    units=self.commodities_to_units[commodity],
                    desc=f"Set point for {tech_name} {commodity} production",
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
                in_name = f"{tech_name}_{self.commodity}_out"
                set_point_name = f"{tech_name}_{self.commodity}_set_point"
                rated_name = f"{tech_name}_rated_{self.commodity}_production"
                if commodity in self.commodities_to_units:
                    commodity_units = self.commodities_to_units[commodity]
                    self.add_input(
                        in_name,
                        val=0.0,
                        shape=self.n_timesteps,
                        units=commodity_units,
                        desc=f"{commodity} output from {tech_name}",
                    )
                else:
                    # commodity units not yet defined, so get it
                    meta_data = self.add_input(
                        in_name,
                        val=0.0,
                        shape=self.n_timesteps,
                        units=None,
                        units_by_conn=True,
                        desc=f"{commodity} output from {tech_name}",
                    )
                    self.commodities_to_units.update({commodity: meta_data["units"]})
                self.add_input(
                    rated_name,
                    val=0.0,
                    units=self.commodities_to_units[commodity],
                    desc=f"Rated {commodity} production for {tech_name}",
                )
                self.add_output(
                    set_point_name,
                    val=0.0,
                    shape=self.n_timesteps,
                    units=self.commodities_to_units[commodity],
                    desc=f"Set point for {tech_name} {commodity} production",
                )
                self.storage_commodity_names.append(commodity)
                self.storage_input_names.append(in_name)
                self.storage_set_point_names.append(set_point_name)
                self.storage_rated_names.append(rated_name)

    def _subtract_curtailable(self, inputs, outputs, demand):
        """Apply curtailable techs: set_point = rated, subtract output from demand.

        Returns the updated demand array.
        """
        for in_name, set_point_name, rated_name in zip(
            self.curtailable_input_names,
            self.curtailable_set_point_names,
            self.curtailable_rated_names,
        ):
            outputs[set_point_name] = inputs[rated_name] * np.ones(self.n_timesteps)
            demand -= inputs[in_name]
        return demand

    def _dispatch_storage(self, inputs, outputs, demand):
        """Dispatch storage techs proportionally and subtract actual output from demand.

        Positive set_point = discharge, negative = charge.
        Returns the updated demand array.
        """
        n_storage = len(self.storage_set_point_names)
        if n_storage > 0:
            storage_share = demand / n_storage
            for set_point_name in self.storage_set_point_names:
                outputs[set_point_name] = storage_share

        for in_name in self.storage_input_names:
            demand -= inputs[in_name]
        return demand
