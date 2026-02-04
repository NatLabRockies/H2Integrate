import pyomo.environ as pyo
from pyomo.network import Port


class PyomoDispatchGenericConverterMinOperatingCosts:
    """Class defining Pyomo rules for the optimized dispatch for load following
    for generic commodity production components.

    Args:
        commodity_info (dict): Dictionary of commodity information. This must contain the keys
            "commodity_name" and "commodity_storage_units".
        pyomo_model (pyo.ConcreteModel): Externally defined Pyomo model that works as the base
            model that this class builds off of.
        index_set (pyo.Set):  Externally defined Pyomo index set for time steps. This should be
            consistent with the forecast horizon of the optimization problem.
        round_digits (int): Number of digits to round to.
        block_set_name (str, optional): Name of the block set (model variables).
            Defaults to "converter".
    """

    def __init__(
        self,
        commodity_info: dict,
        pyomo_model: pyo.ConcreteModel,
        index_set: pyo.Set,
        round_digits: int,
        block_set_name: str = "converter",
    ):
        self.round_digits = round_digits
        self.block_set_name = block_set_name
        self.commodity_name = commodity_info["commodity_name"]
        self.commodity_storage_units = commodity_info["commodity_storage_units"]

        self.model = pyomo_model
        self.blocks = pyo.Block(index_set, rule=self.dispatch_block_rule_function)

        self.model.__setattr__(self.block_set_name, self.blocks)
        self.time_duration = [1.0] * len(self.blocks.index_set())

    def initialize_parameters(
        self, commodity_in: list, commodity_demand: list, dispatch_inputs: dict
    ):
        """Initialize parameters for optimization model

        Args:
            commodity_in (list): List of generated commodity in for this time slice.
            commodity_demand (list): The demanded commodity for this time slice.
            dispatch_inputs (dict): Dictionary of the dispatch input parameters from config

        """
        self.cost_per_production = dispatch_inputs["cost_per_production"]

    def dispatch_block_rule_function(self, pyomo_model: pyo.ConcreteModel):
        """
        Creates and initializes pyomo dispatch model components for a specific technology.

        This method sets up all model elements (parameters, variables, constraints,
        and ports) associated with a technology block within the dispatch model.
        It is typically called in the setup_pyomo() method of the PyomoControllerBaseClass.

        Args:
            pyomo_model (pyo.ConcreteModel): The Pyomo model to which the technology
                components will be added.
            tech_name (str): The name or key identifying the technology (e.g., "battery",
                "electrolyzer") for which model components are created.
        """
        # Parameters
        self._create_parameters(pyomo_model)
        # Variables
        self._create_variables(pyomo_model)
        # Constraints
        self._create_constraints(pyomo_model)
        # Ports
        self._create_ports(pyomo_model)

    # Base model setup
    def _create_variables(self, pyomo_model: pyo.ConcreteModel):
        """Create generic converter variables to add to Pyomo model instance.

        Args:
            pyomo_model (pyo.ConcreteModel): pyomo_model the variables should be added to.

        """
        tech_var = pyo.Var(
            doc=f"{self.commodity_name} production \
                    from {self.block_set_name} [{self.commodity_storage_units}]",
            domain=pyo.NonNegativeReals,
            bounds=(0, pyomo_model.available_production),
            units=eval("pyo.units." + self.commodity_storage_units),
            initialize=0.0,
        )

        pyomo_model.__setattr__(
            f"{self.block_set_name}_{self.commodity_name}",
            tech_var,
        )

    def _create_ports(self, pyomo_model: pyo.ConcreteModel):
        """Create generic converter ports to add to pyomo model instance.

        Args:
            pyomo_model (pyo.ConcreteModel): pyomo_model the ports should be added to.

        """
        # create port
        pyomo_model.port = Port()
        # get port attribute from generic converter pyomo model
        tech_port = pyomo_model.__getattribute__(f"{self.block_set_name}_{self.commodity_name}")
        # add port to pyomo_model
        pyomo_model.port.add(tech_port)

    def _create_parameters(self, pyomo_model: pyo.ConcreteModel):
        """Create generic converter Pyomo parameters to add to the Pyomo model instance.

        This method defines converter parameters such as available production and the
        cost per generation for the technology

        Args:
            pyomo_model (pyo.ConcreteModel): pyomo_model that parameters are added to.

        """
        ##################################
        # Parameters                     #
        ##################################
        pyomo_model.time_duration = pyo.Param(
            doc=f"{pyomo_model.name} time step [hour]",
            default=1.0,
            within=pyo.NonNegativeReals,
            mutable=True,
            units=pyo.units.hr,
        )
        pyomo_model.cost_per_production = pyo.Param(
            doc=f"Production cost for generator [$/{self.commodity_storage_units}]",
            default=0.0,
            within=pyo.NonNegativeReals,
            mutable=True,
            units=eval(f"pyo.units.USD / pyo.units.{self.commodity_storage_units}h"),
        )
        pyomo_model.available_production = pyo.Param(
            doc=f"Available production for the generator [{self.commodity_storage_units}]",
            default=0.0,
            within=pyo.Reals,
            mutable=True,
            units=eval(f"pyo.units.{self.commodity_storage_units}"),
        )

    def _create_constraints(self, pyomo_model: pyo.ConcreteModel):
        """Create generic converter Pyomo constraints to add to the Pyomo model instance.

        Method is currently empty but this serves as a placeholder to add constraints to the Pyomo
        model instance if this class is inherited.

        Args:
            pyomo_model (pyo.ConcreteModel): pyomo_model that constraints are added to.

        """

        pass

    # Update time series parameters for next optimization window
    def update_time_series_parameters(
        self, commodity_in: list, commodity_demand: list, updated_initial_soc: float
    ):
        """Updates the pyomo optimization problem with parameters that change with time

        Args:
            commodity_in (list): List of generated commodity in for this time slice.
            commodity_demand (list): The demanded commodity for this time slice.
            updated_initial_soc (float): The updated initial state of charge for storage
                technologies for the current time slice.
        """
        self.time_duration = [1.0] * len(self.blocks.index_set())
        self.available_production = [commodity_in[t] for t in self.blocks.index_set()]

    # Objective functions
    def min_operating_cost_objective(self, hybrid_blocks, tech_name: str):
        """Generic converter instance of minimum operating cost objective.

        Args:
            hybrid_blocks (Pyomo.block): A generalized container for defining hierarchical
                models by adding modeling components as attributes.
            tech_name (str): The name or key identifying the technology for which
            ports are created.
        """

        self.obj = sum(
            hybrid_blocks[t].time_weighting_factor
            * self.blocks[t].time_duration
            * self.blocks[t].cost_per_production
            * hybrid_blocks[t].__getattribute__(f"{tech_name}_{self.commodity_name}")
            for t in hybrid_blocks.index_set()
        )
        return self.obj

    # System-level functions
    def _create_hybrid_port(self, hybrid_model: pyo.ConcreteModel, tech_name: str):
        """Create generic converter ports to add to system-level pyomo model instance.

        Args:
            hybrid_model (pyo.ConcreteModel): hybrid_model the ports should be added to.
            tech_name (str): The name or key identifying the technology for which
            ports are created.
        """
        hybrid_model_tech = hybrid_model.__getattribute__(f"{tech_name}_{self.commodity_name}")
        tech_port = Port(initialize={f"{tech_name}_{self.commodity_name}": hybrid_model_tech})
        hybrid_model.__setattr__(f"{tech_name}_port", tech_port)

        return hybrid_model.__getattribute__(f"{tech_name}_port")

    def _create_hybrid_variables(self, hybrid_model: pyo.ConcreteModel, tech_name: str):
        """Create generic converter variables to add to system-level pyomo model instance.

        Args:
            hybrid_model (pyo.ConcreteModel): hybrid_model the variables should be added to.
            tech_name (str): The name or key identifying the technology for which
            variables are created.
        """
        tech_var = pyo.Var(
            doc=f"{self.commodity_name} production \
                    from {tech_name} [{self.commodity_storage_units}]",
            domain=pyo.NonNegativeReals,
            units=eval("pyo.units." + self.commodity_storage_units),
            initialize=0.0,
        )

        hybrid_model.__setattr__(f"{tech_name}_{self.commodity_name}", tech_var)

        # Returns to power_source_gen_vars and load_vars in hybrid_rule
        # load var is zero for converters
        power_source_gen_var = hybrid_model.__getattribute__(f"{tech_name}_{self.commodity_name}")
        load_var = 0
        return power_source_gen_var, load_var

    # Property getters and setters for time series parameters
    @property
    def available_production(self) -> list:
        """Available production.

        Returns:
            list: List of available production.

        """
        return [self.blocks[t].available_production.value for t in self.blocks.index_set()]

    @available_production.setter
    def available_production(self, resource: list):
        if len(resource) == len(self.blocks):
            for t, gen in zip(self.blocks, resource):
                self.blocks[t].available_production.set_value(round(gen, self.round_digits))
        else:
            raise ValueError(
                f"'resource' list ({len(resource)}) must be the same length as\
                time horizon ({len(self.blocks)})"
            )

    @property
    def cost_per_production(self) -> float:
        """Cost per generation [$/commodity_storage_units]."""
        for t in self.blocks.index_set():
            return self.blocks[t].cost_per_production.value

    @cost_per_production.setter
    def cost_per_production(self, om_dollar_per_kwh: float):
        for t in self.blocks.index_set():
            self.blocks[t].cost_per_production.set_value(
                round(om_dollar_per_kwh, self.round_digits)
            )

    @property
    def time_duration(self) -> list:
        """Time duration."""
        return [self.blocks[t].time_duration.value for t in self.blocks.index_set()]

    @time_duration.setter
    def time_duration(self, time_duration: list):
        if len(time_duration) == len(self.blocks):
            for t, delta in zip(self.blocks, time_duration):
                self.blocks[t].time_duration = round(delta, self.round_digits)
        else:
            raise ValueError(
                self.time_duration.__name__ + " list must be the same length as time horizon"
            )
