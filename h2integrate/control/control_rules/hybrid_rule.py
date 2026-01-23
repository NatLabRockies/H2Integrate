import pyomo.environ as pyo
from pyomo.network import Arc


class PyomoDispatchPlantRule:
    """Class defining Pyomo model and rule for the optimized dispatch for load following
    for the overal optimization problem describing the system."""

    def __init__(
        self,
        pyomo_model: pyo.ConcreteModel,
        index_set: pyo.Set,
        source_techs: list,
        tech_dispatch_models: pyo.ConcreteModel,
        dispatch_options: dict,
        block_set_name: str = "hybrid",
    ):
        self.source_techs = source_techs  # self.pyomo_model
        self.options = dispatch_options  # only using dispatch_options.time_weighting_factor
        self.power_source_gen_vars = {key: [] for key in index_set}
        self.tech_dispatch_models = tech_dispatch_models
        self.load_vars = {key: [] for key in index_set}
        self.ports = {key: [] for key in index_set}
        self.arcs = []

        self.round_digits = 4

        self.model = pyomo_model
        self.blocks = pyo.Block(index_set, rule=self.dispatch_block_rule)

        self.model.__setattr__(block_set_name, self.blocks)

    def dispatch_block_rule(self, hybrid, t):
        """
        Creates and initializes pyomo dispatch model components for a the system-level dispatch

        This method sets up all model elements (parameters, variables, constraints,
        and ports) associated with a pyomo block within the dispatch model.

        Args:
            hybrid (pyo.ConcreteModel): The Pyomo model to which the technology
                components will be added.
            t (int): integer location of variables in the control time window
        """
        ##################################
        # Parameters                     #
        ##################################
        self._create_parameters(hybrid)
        ##################################
        # Variables / Ports              #
        ##################################
        self._create_variables_and_ports(hybrid, t)
        ##################################
        # Constraints                    #
        ##################################
        self._create_hybrid_constraints(hybrid, t)

    def initialize_parameters(
        self, commodity_in: list, commodity_demand: list, dispatch_params: dict
    ):
        """Initialize parameters for optimization model

        Args:
            commodity_in (list): List of generated commodity in for this time slice.
            commodity_demand (list): The demanded commodity for this time slice.
            dispatch_inputs (dict): Dictionary of the dispatch input parameters from config

        """
        self.time_weighting_factor = self.options.time_weighting_factor  # Discount factor
        for tech in self.source_techs:
            pyomo_block = self.tech_dispatch_models.__getattribute__(f"{tech}_rule")
            pyomo_block.initialize_parameters(commodity_in, commodity_demand, dispatch_params)

    def _create_variables_and_ports(self, hybrid, t):
        """Connect variables and ports from individual technology model
        to system-level pyomo model instance.

        Args:
            hybrid (pyo.ConcreteModel): The Pyomo model to which the technology
                components will be added.
            t (int): integer location of variables in the control time window
        """

        for tech in self.source_techs:
            pyomo_block = self.tech_dispatch_models.__getattribute__(f"{tech}_rule")
            gen_var, load_var = pyomo_block._create_hybrid_variables(hybrid, f"{tech}_rule")

            # Add production and load variables to system-level list
            self.power_source_gen_vars[t].append(gen_var)
            self.load_vars[t].append(load_var)
            self.ports[t].append(pyomo_block._create_hybrid_port(hybrid, f"{tech}_rule"))

    @staticmethod
    def _create_parameters(hybrid):
        """Create system-level pyomo model parameters

        Args:
            hybrid (pyo.ConcreteModel): The Pyomo model to which the technology
                components will be added.
        """
        hybrid.time_weighting_factor = pyo.Param(
            doc="Exponential time weighting factor [-]",
            initialize=1.0,
            within=pyo.PercentFraction,
            mutable=True,
            units=pyo.units.dimensionless,
        )

    def _create_hybrid_constraints(self, hybrid, t):
        """Define system-level constraints for pyomo model.

        Args:
            hybrid (pyo.ConcreteModel): The Pyomo model to which the technology
                components will be added.
            t (int): integer location of variables in the control time window
        """
        hybrid.production_total = pyo.Constraint(
            doc="hybrid system generation total",
            rule=hybrid.system_production == sum(self.power_source_gen_vars[t]),
        )

        hybrid.load_total = pyo.Constraint(
            doc="hybrid system load total",
            rule=hybrid.system_load == sum(self.load_vars[t]),
        )

    def create_arcs(self):
        """
        Defines the mapping between individual technology variables to system level
        """
        ##################################
        # Arcs                           #
        ##################################
        for tech in self.source_techs:
            pyomo_block = self.tech_dispatch_models.__getattribute__(f"{tech}_rule")

            def arc_rule(m, t):
                source_port = pyomo_block.blocks[t].port
                destination_port = self.blocks[t].__getattribute__(f"{tech}_rule_port")
                return {"source": source_port, "destination": destination_port}

            tech_hybrid_arc = Arc(self.blocks.index_set(), rule=arc_rule)
            self.model.__setattr__(f"{tech}_hybrid_arc", tech_hybrid_arc)

            tech_arc = self.model.__getattribute__(f"{tech}_hybrid_arc")
            self.arcs.append(tech_arc)

        pyo.TransformationFactory("network.expand_arcs").apply_to(self.model)

    def update_time_series_parameters(
        self, commodity_in=list, commodity_demand=list, updated_initial_soc=float
    ):
        """
        Updates the pyomo optimization problem with parameters that change with time

        Args:
            commodity_in (list): List of generated commodity in for this time slice.
            commodity_demand (list): The demanded commodity for this time slice.

        """
        # Note: currently, storage techs use commodity_demand and converter techs use commodity_in
        #   Better way to do this?
        for tech in self.source_techs:
            name = tech + "_rule"
            pyomo_block = self.tech_dispatch_models.__getattribute__(name)
            pyomo_block.update_time_series_parameters(
                commodity_in, commodity_demand, updated_initial_soc
            )

    def create_min_operating_cost_expression(self):
        """
        Creates system-level instance of minimum operating cost objective for pyomo solver.
        """

        self._delete_objective()

        def operating_cost_objective_rule(m) -> float:
            obj = 0.0
            for tech in self.source_techs:
                name = tech + "_rule"
                # Create the min_operating_cost expression for each technology
                pyomo_block = self.tech_dispatch_models.__getattribute__(name)
                # Add to the overall hybrid operating cost expression
                obj += pyomo_block.min_operating_cost_objective(self.blocks, name)
            return obj

        # Set operating cost rule in Pyomo problem objective
        self.model.objective = pyo.Objective(rule=operating_cost_objective_rule, sense=pyo.minimize)

    def _delete_objective(self):
        if hasattr(self.model, "objective"):
            self.model.del_component(self.model.objective)

    @property
    def time_weighting_factor(self) -> float:
        for t in self.blocks.index_set():
            return self.blocks[t + 1].time_weighting_factor.value

    @time_weighting_factor.setter
    def time_weighting_factor(self, weighting: float):
        for t in self.blocks.index_set():
            self.blocks[t].time_weighting_factor = round(weighting**t, self.round_digits)

    @property
    def storage_commodity_out(self) -> list:
        # THIS IS USED
        """Storage commodity out."""
        return [
            self.blocks[t].discharge_commodity.value - self.blocks[t].charge_commodity.value
            for t in self.blocks.index_set()
        ]
