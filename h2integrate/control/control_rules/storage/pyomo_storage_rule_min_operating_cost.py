import pyomo.environ as pyo
from pyomo.network import Port


# @define
# class PyomoDispatchStorageMinOperatingCostsConfig(PyomoRuleBaseConfig):
#     """
#     Configuration class for the PyomoDispatchStorageMinOperatingCostsConfig.

#     This class defines the parameters required to configure the `PyomoRuleBaseConfig`.

#     Attributes:
#         cost_per_charge (float): cost of the commodity per charge (in $/kWh).
#         cost_per_discharge (float): cost of the commodity per discharge (in $/kWh).
#     """

#     cost_per_charge: float = field()
#     cost_per_discharge: float = field()
#     # roundtrip_efficiency: float = field(default=0.88)
#     commodity_met_value: float = field()


class PyomoRuleStorageMinOperatingCosts:
    """Class defining Pyomo rules for the optimized dispatch for load following
    for generic commodity storage components."""

    def __init__(
        self,
        commodity_info: dict,
        pyomo_model: pyo.ConcreteModel,
        index_set: pyo.Set,
        block_set_name: str = "storage",
    ):
        self.round_digits = 4
        self.block_set_name = block_set_name
        self.commodity_name = commodity_info["commodity_name"]
        self.commodity_storage_units = commodity_info["commodity_storage_units"]

        self._model = pyomo_model
        self._blocks = pyo.Block(index_set, rule=self.dispatch_block_rule_function)
        setattr(self.model, self.block_set_name, self.blocks)
        print("HEYYYY-storage")

    def initialize_parameters(
        self, commodity_in: list, commodity_demand: list, dispatch_inputs: dict
    ):
        # Dispatch Parameters
        self.cost_per_charge = dispatch_inputs["cost_per_charge"]
        self.cost_per_discharge = dispatch_inputs["cost_per_discharge"]
        self.commodity_met_value = dispatch_inputs["commodity_met_value"]
        # Storage parameters
        self.minimum_storage = 0.0
        self.maximum_storage = dispatch_inputs["max_capacity"]
        print("maximum_storage", self.maximum_storage)
        print(self.minimum_storage)
        self.minimum_soc = dispatch_inputs["min_charge_percent"]
        self.maximum_soc = dispatch_inputs["max_charge_percent"]
        self.initial_soc = dispatch_inputs["initial_soc_percent"]
        self.charge_efficiency = dispatch_inputs.get("charge_efficiency", 0.94)
        self.discharge_commodity_efficiency = dispatch_inputs.get("discharge_efficiency", 0.94)

        # Set charge and discharge rate equal to each other for now
        self.max_charge = dispatch_inputs["max_charge_rate"]
        self.max_discharge = dispatch_inputs["max_charge_rate"]

        # System parameters
        self.commodity_load_demand = [commodity_demand[t] for t in self.blocks.index_set()]
        self.load_production_limit = [commodity_demand[t] for t in self.blocks.index_set()]
        self._set_initial_soc_constraint()

    def dispatch_block_rule_function(self, pyomo_model: pyo.ConcreteModel, tech_name: str):
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
        self._create_parameters(pyomo_model, tech_name)
        # Variables
        self._create_variables(pyomo_model, tech_name)
        # Constraints
        self._create_constraints(pyomo_model, tech_name)
        # Ports
        self._create_ports(pyomo_model, tech_name)

    # Base model setup
    def _create_parameters(self, pyomo_model: pyo.ConcreteModel, t):
        """Create storage-related parameters in the Pyomo model.

        This method defines key storage parameters such as capacity limits,
        state-of-charge (SOC) bounds, efficiencies, and time duration for each
        time step.

        Args:
            pyomo_model (pyo.ConcreteModel): Pyomo model instance representing
                the storage system.
            t: Time index or iterable representing time steps (unused in this method).
        """
        ##################################
        # Storage Parameters             #
        ##################################
        pyomo_model.time_duration = pyo.Param(
            doc=pyomo_model.name + " time step [hour]",
            default=1.0,
            within=pyo.NonNegativeReals,
            mutable=True,
            units=pyo.units.hr,
        )
        pyomo_model.cost_per_charge = pyo.Param(
            doc="Operating cost of "
            + pyomo_model.name
            + " charging [$/"
            + self.commodity_storage_units
            + "]",
            default=0.0,
            within=pyo.NonNegativeReals,
            mutable=True,
            units=eval("pyo.units.USD / pyo.units." + self.commodity_storage_units + "h"),
        )
        pyomo_model.cost_per_discharge = pyo.Param(
            doc="Operating cost of "
            + pyomo_model.name
            + " discharging [$/"
            + self.commodity_storage_units
            + "]",
            default=0.0,
            within=pyo.NonNegativeReals,
            mutable=True,
            units=eval("pyo.units.USD / pyo.units." + self.commodity_storage_units + "h"),
        )
        pyomo_model.minimum_storage = pyo.Param(
            doc=pyomo_model.name + " minimum storage rating [" + self.commodity_storage_units + "]",
            default=0.0,
            within=pyo.NonNegativeReals,
            mutable=True,
            units=eval("pyo.units." + self.commodity_storage_units),
        )
        pyomo_model.maximum_storage = pyo.Param(
            doc=pyomo_model.name + " maximum storage rating [" + self.commodity_storage_units + "]",
            default=1000.0,
            within=pyo.NonNegativeReals,
            mutable=False,
            units=eval("pyo.units." + self.commodity_storage_units + "h"),
        )
        pyomo_model.minimum_soc = pyo.Param(
            doc=pyomo_model.name + " minimum state-of-charge [-]",
            default=0.1,
            within=pyo.PercentFraction,
            mutable=True,
            units=pyo.units.dimensionless,
        )
        pyomo_model.maximum_soc = pyo.Param(
            doc=pyomo_model.name + " maximum state-of-charge [-]",
            default=0.9,
            within=pyo.PercentFraction,
            mutable=True,
            units=pyo.units.dimensionless,
        )

        ##################################
        # Efficiency Parameters          #
        ##################################
        pyomo_model.charge_efficiency = pyo.Param(
            doc=pyomo_model.name + " Charging efficiency [-]",
            default=0.938,
            within=pyo.PercentFraction,
            mutable=True,
            units=pyo.units.dimensionless,
        )
        pyomo_model.discharge_efficiency = pyo.Param(
            doc=pyomo_model.name + " discharging efficiency [-]",
            default=0.938,
            within=pyo.PercentFraction,
            mutable=True,
            units=pyo.units.dimensionless,
        )
        ##################################
        # Capacity Parameters            #
        ##################################
        pyomo_model.max_charge = pyo.Param(
            doc=pyomo_model.name + " maximum charge [" + self.commodity_storage_units + "]",
            within=pyo.NonNegativeReals,
            mutable=True,
            units=eval("pyo.units." + self.commodity_storage_units),
        )
        pyomo_model.max_discharge = pyo.Param(
            doc=pyomo_model.name + " maximum discharge [" + self.commodity_storage_units + "]",
            within=pyo.NonNegativeReals,
            mutable=True,
            units=eval("pyo.units." + self.commodity_storage_units),
        )
        ##################################
        # System Parameters              #
        ##################################
        pyomo_model.epsilon = pyo.Param(
            doc="A small value used in objective for binary logic",
            default=1e-3,
            within=pyo.NonNegativeReals,
            mutable=True,
            units=pyo.units.USD,
        )
        pyomo_model.commodity_met_value = pyo.Param(
            doc="Commodity demand met value per generation [$/"
            + self.commodity_storage_units
            + "]",
            default=0.0,
            within=pyo.Reals,
            mutable=True,
            units=eval("pyo.units.USD / pyo.units." + self.commodity_storage_units + "h"),
        )
        # grid.electricity_purchase_price = pyomo.Param(
        #     doc="Electricity purchase price [$/MWh]",
        #     default=0.0,
        #     within=pyomo.Reals,
        #     mutable=True,
        #     units=u.USD / u.MWh,
        # )
        pyomo_model.commodity_load_demand = pyo.Param(
            doc="Load demand for the commodity [" + self.commodity_storage_units + "]",
            default=1000.0,
            within=pyo.NonNegativeReals,
            mutable=True,
            units=eval("pyo.units." + self.commodity_storage_units),
        )
        pyomo_model.load_production_limit = pyo.Param(
            doc="Production limit for load [" + self.commodity_storage_units + "]",
            default=1000.0,
            within=pyo.NonNegativeReals,
            mutable=True,
            units=eval("pyo.units." + self.commodity_storage_units),
        )

    def _create_variables(self, pyomo_model: pyo.ConcreteModel, t):
        """Create storage-related decision variables in the Pyomo model.

        This method defines binary and continuous variables representing
        charging/discharging modes, energy flows, and state-of-charge.

        Args:
            pyomo_model (pyo.ConcreteModel): Pyomo model instance representing
                the storage system.
            t: Time index or iterable representing time steps (unused in this method).
        """
        ##################################
        # Variables                      #
        ##################################
        pyomo_model.is_charging = pyo.Var(
            doc="1 if " + pyomo_model.name + " is charging; 0 Otherwise [-]",
            domain=pyo.Binary,
            units=pyo.units.dimensionless,
        )
        pyomo_model.is_discharging = pyo.Var(
            doc="1 if " + pyomo_model.name + " is discharging; 0 Otherwise [-]",
            domain=pyo.Binary,
            units=pyo.units.dimensionless,
        )
        pyomo_model.soc0 = pyo.Var(
            doc=pyomo_model.name + " initial state-of-charge at beginning of period[-]",
            domain=pyo.PercentFraction,
            bounds=(pyomo_model.minimum_soc, pyomo_model.maximum_soc),
            units=pyo.units.dimensionless,
        )
        pyomo_model.soc = pyo.Var(
            doc=pyomo_model.name + " state-of-charge at end of period [-]",
            domain=pyo.PercentFraction,
            bounds=(pyomo_model.minimum_soc, pyomo_model.maximum_soc),
            units=pyo.units.dimensionless,
        )
        pyomo_model.charge_commodity = pyo.Var(
            doc=self.commodity_name
            + " into "
            + pyomo_model.name
            + " ["
            + self.commodity_storage_units
            + "]",
            domain=pyo.NonNegativeReals,
            units=eval("pyo.units." + self.commodity_storage_units),
        )
        pyomo_model.discharge_commodity = pyo.Var(
            doc=self.commodity_name
            + " out of "
            + pyomo_model.name
            + " ["
            + self.commodity_storage_units
            + "]",
            domain=pyo.NonNegativeReals,
            units=eval("pyo.units." + self.commodity_storage_units),
        )
        ##################################
        # System Variables               #
        ##################################
        pyomo_model.system_production = pyo.Var(
            doc="System generation [" + self.commodity_storage_units + "]",
            domain=pyo.NonNegativeReals,
            units=eval("pyo.units." + self.commodity_storage_units),
        )
        pyomo_model.system_load = pyo.Var(
            doc="System load [" + self.commodity_storage_units + "]",
            domain=pyo.NonNegativeReals,
            units=eval("pyo.units." + self.commodity_storage_units),
        )
        pyomo_model.commodity_out = pyo.Var(
            doc="Commodity out of the system [" + self.commodity_storage_units + "]",
            domain=pyo.NonNegativeReals,
            bounds=(0, pyomo_model.commodity_load_demand),
            units=eval("pyo.units." + self.commodity_storage_units),
        )
        pyomo_model.is_generating = pyo.Var(
            doc="System is producing commodity binary [-]",
            domain=pyo.Binary,
            units=pyo.units.dimensionless,
        )
        # TODO: Not needed for now, add back in later if needed
        # pyomo_model.electricity_purchased = pyo.Var(
        #     doc="Electricity purchased [MW]",
        #     domain=pyo.NonNegativeReals,
        #     units=u.MW,
        # )

    def _create_constraints(self, pyomo_model: pyo.ConcreteModel, t):
        """Create operational and state-of-charge constraints for storage.

        This method defines constraints that enforce:
        - Mutual exclusivity between charging and discharging.
        - Upper and lower bounds on charge/discharge flows.
        - The state-of-charge balance over time.

        Args:
            pyomo_model (pyo.ConcreteModel): Pyomo model instance representing
                the storage system.
            t: Time index or iterable representing time steps (unused in this method).
        """
        ##################################
        # Charging Constraints           #
        ##################################
        # Charge commodity bounds
        pyomo_model.charge_commodity_ub = pyo.Constraint(
            doc=pyomo_model.name + " charging storage upper bound",
            expr=pyomo_model.charge_commodity <= pyomo_model.max_charge * pyomo_model.is_charging,
        )
        pyomo_model.charge_commodity_lb = pyo.Constraint(
            doc=pyomo_model.name + " charging storage lower bound",
            expr=pyomo_model.charge_commodity
            >= pyomo_model.minimum_storage * pyomo_model.is_charging,
        )
        # Discharge commodity bounds
        pyomo_model.discharge_commodity_lb = pyo.Constraint(
            doc=pyomo_model.name + " Discharging storage lower bound",
            expr=pyomo_model.discharge_commodity
            >= pyomo_model.minimum_storage * pyomo_model.is_discharging,
        )
        pyomo_model.discharge_commodity_ub = pyo.Constraint(
            doc=pyomo_model.name + " Discharging storage upper bound",
            expr=pyomo_model.discharge_commodity
            <= pyomo_model.max_discharge * pyomo_model.is_discharging,
        )
        # Storage packing constraint
        pyomo_model.charge_discharge_packing = pyo.Constraint(
            doc=pyomo_model.name + " packing constraint for charging and discharging binaries",
            expr=pyomo_model.is_charging + pyomo_model.is_discharging <= 1,
        )
        ##################################
        # System constraints             #
        ##################################
        pyomo_model.balance = pyo.Constraint(
            doc="Transmission energy balance",
            expr=(
                pyomo_model.commodity_out == pyomo_model.system_production - pyomo_model.system_load
            ),
        )
        pyomo_model.production_limit = pyo.Constraint(
            doc="Transmission limit on electricity sales",
            expr=pyomo_model.commodity_out
            <= pyomo_model.commodity_load_demand * pyomo_model.is_generating,
        )
        # pyomo_model.purchases_transmission_limit = pyomo.Constraint(
        #     doc="Transmission limit on electricity purchases",
        #     expr=(
        #         grid.electricity_purchased
        #         <= grid.load_transmission_limit * (1 - grid.is_generating)
        #     ),
        # )

        ##################################
        # SOC Inventory Constraints      #
        ##################################

        def soc_inventory_rule(m):
            return m.soc == (
                m.soc0
                + m.time_duration
                * (
                    m.charge_efficiency * m.charge_commodity
                    - (1 / m.discharge_efficiency) * m.discharge_commodity
                )
                / m.maximum_storage
            )

        # Storage State-of-charge balance
        pyomo_model.soc_inventory = pyo.Constraint(
            doc=pyomo_model.name + " state-of-charge inventory balance",
            rule=soc_inventory_rule,
        )

    def _set_initial_soc_constraint(self):
        ##################################
        # SOC Linking                    #
        ##################################
        self.model.initial_soc = pyo.Param(
            doc=self.commodity_name + " initial state-of-charge at beginning of the horizon[-]",
            within=pyo.PercentFraction,
            default=0.5,
            mutable=True,
            units=pyo.units.dimensionless,
        )

        ##################################
        # SOC Constraints                #
        ##################################
        # Linking time periods together
        def storage_soc_linking_rule(m, t):
            if t == self.blocks.index_set().first():
                return self.blocks[t].soc0 == m.initial_soc
            return self.blocks[t].soc0 == self.blocks[t - 1].soc

        self.model.soc_linking = pyo.Constraint(
            self.blocks.index_set(),
            doc=self.block_set_name + " state-of-charge block linking constraint",
            rule=storage_soc_linking_rule,
        )

    def _create_ports(self, pyomo_model: pyo.ConcreteModel, t):
        """Create Pyomo ports for connecting the storage component.

        Ports are used to connect inflows and outflows of the storage system
        (e.g., charging and discharging commodities) to the overall Pyomo model.

        Args:
            pyomo_model (pyo.ConcreteModel): Pyomo model instance representing
                the storage system.
            t: Time index or iterable representing time steps (unused in this method).
        """
        ##################################
        # Ports                          #
        ##################################
        pyomo_model.port = Port()
        pyomo_model.port.add(pyomo_model.charge_commodity)
        pyomo_model.port.add(pyomo_model.discharge_commodity)
        pyomo_model.port.add(pyomo_model.system_production)
        pyomo_model.port.add(pyomo_model.system_load)
        pyomo_model.port.add(pyomo_model.commodity_out)
        # pyomo_model.port.add(pyomo_model.electricity_purchased)

    # Update time series parameters for next optimization window
    def update_time_series_parameters(
        self,
        start_time: int,
        commodity_in: list,
        commodity_demand: list,
        #   time_commodity_met_value:list
    ):
        """Update time series parameters method.

        Args:
            start_time (int): The starting time index for the update.
            commodity_in (list): List of commodity input values for each time step.
        """
        self.time_duration = [1.0] * len(self.blocks.index_set())
        self.commodity_load_demand = [commodity_demand[t] for t in self.blocks.index_set()]
        self.load_production_limit = [commodity_demand[t] for t in self.blocks.index_set()]
        # TODO: add back in if needed, needed for variable time series pricing
        # self.commodity_met_value = [time_commodity_met_value[t]
        #                                 for t in self.blocks.index_set()]

    # Objective functions
    def min_operating_cost_objective(self, hybrid_blocks, tech_name: str):
        """Storage instance of minimum operating cost objective.

        Args:
            hybrid_blocks (Pyomo.block): A generalized container for defining hierarchical
                models by adding modeling components as attributes.

        """
        self.obj = sum(
            hybrid_blocks[t].time_weighting_factor
            * self.blocks[t].time_duration
            * (
                self.blocks[t].cost_per_discharge * hybrid_blocks[t].discharge_commodity
                - self.blocks[t].cost_per_charge * hybrid_blocks[t].charge_commodity
                + (self.blocks[t].commodity_load_demand - hybrid_blocks[t].commodity_out)
                * self.blocks[t].commodity_met_value
                #                                 + (
                #     * self.blocks[t].electricity_purchase_price
                #     * hybrid_blocks[t].electricity_purchased
                # )
            )
            # Try to incentivize battery charging
            for t in self.blocks.index_set()
        )
        return self.obj

    # System-level functions
    def _create_hybrid_port(self, hybrid_model: pyo.ConcreteModel, tech_name: str):
        """Create hybrid ports for storage to add to pyomo model instance.

        Args:
            hybrid_model (pyo.ConcreteModel): hybrid_model the ports should be added to.
            tech_name (str): The name or key identifying the technology for which
            ports are created.
        """
        setattr(
            hybrid_model,
            f"{tech_name}_port",
            Port(
                initialize={
                    "system_production": hybrid_model.system_production,
                    "system_load": hybrid_model.system_load,
                    "commodity_out": hybrid_model.commodity_out,
                    "charge_commodity": hybrid_model.charge_commodity,
                    "discharge_commodity": hybrid_model.discharge_commodity,
                }
            ),
        )
        return getattr(hybrid_model, f"{tech_name}_port")

    def _create_hybrid_variables(self, hybrid_model: pyo.ConcreteModel, tech_name: str):
        """Create hybrid variables for storage to add to pyomo model instance.

        Args:
            hybrid_model (pyo.ConcreteModel): hybrid_model the variables should be added to.
            tech_name (str): The name or key identifying the technology for which
            variables are created.
        """
        ##################################
        # System Variables               #
        ##################################
        # TODO: fix the units on these
        hybrid_model.system_production = pyo.Var(
            doc="System generation [MW]",
            domain=pyo.NonNegativeReals,
            units=eval("pyo.units." + self.commodity_storage_units),
        )
        hybrid_model.system_load = pyo.Var(
            doc="System load [MW]",
            domain=pyo.NonNegativeReals,
            units=eval("pyo.units." + self.commodity_storage_units),
        )
        hybrid_model.commodity_out = pyo.Var(
            doc="Electricity sold [MW]",
            domain=pyo.NonNegativeReals,
            units=eval("pyo.units." + self.commodity_storage_units),
        )
        ##################################
        # Storage Variables              #
        ##################################
        hybrid_model.charge_commodity = pyo.Var(
            doc=self.commodity_name
            + " into "
            + tech_name
            + " ["
            + self.commodity_storage_units
            + "]",
            domain=pyo.NonNegativeReals,
            units=eval("pyo.units." + self.commodity_storage_units),
        )
        hybrid_model.discharge_commodity = pyo.Var(
            doc=self.commodity_name
            + " out of "
            + tech_name
            + " ["
            + self.commodity_storage_units
            + "]",
            domain=pyo.NonNegativeReals,
            units=eval("pyo.units." + self.commodity_storage_units),
        )
        return hybrid_model.discharge_commodity, hybrid_model.charge_commodity

    def _check_initial_soc(self, initial_soc: float) -> float:
        """Check that initial state-of-charge is within valid bounds.

        Args:
            initial_soc (float): Initial state-of-charge to be checked.
        Returns:
            float: Validated initial state-of-charge.
        """
        if initial_soc > 1:
            initial_soc /= 100.0
        initial_soc = round(initial_soc, self.round_digits)
        if initial_soc > self.maximum_soc:
            print(
                "Warning: Storage dispatch was initialized with a state-of-charge greater than "
                "maximum value!"
            )
            print(f"Initial SOC = {initial_soc}")
            print("Initial SOC was set to maximum value.")
            initial_soc = self.maximum_soc
        elif initial_soc < self.minimum_soc:
            print(
                "Warning: Storage dispatch was initialized with a state-of-charge less than "
                "minimum value!"
            )
            print(f"Initial SOC = {initial_soc}")
            print("Initial SOC was set to minimum value.")
            initial_soc = self.minimum_soc
        return initial_soc

    @staticmethod
    def _check_efficiency_value(efficiency):
        """Checks efficiency is between 0 and 1 or 0 and 100. Returns fractional value"""
        if efficiency < 0:
            raise ValueError("Efficiency value must greater than 0")
        elif efficiency > 1:
            efficiency /= 100
            if efficiency > 1:
                raise ValueError("Efficiency value must between 0 and 1 or 0 and 100")
        return efficiency

    # Dispatch Model Variables
    @property
    def blocks(self) -> pyo.Block:
        return self._blocks

    @property
    def model(self) -> pyo.ConcreteModel:
        return self._model

    # INPUTS
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

    # Property getters and setters for time series parameters
    @property
    def max_charge(self) -> float:
        """Maximum charge amount."""
        for t in self.blocks.index_set():
            return self.blocks[t].max_charge.value

    @max_charge.setter
    def max_charge(self, max_charge: float):
        for t in self.blocks.index_set():
            self.blocks[t].max_charge = round(max_charge, self.round_digits)

    @property
    def max_discharge(self) -> float:
        """Maximum discharge amount."""
        for t in self.blocks.index_set():
            return self.blocks[t].max_discharge.value

    @max_discharge.setter
    def max_discharge(self, max_discharge: float):
        for t in self.blocks.index_set():
            self.blocks[t].max_discharge = round(max_discharge, self.round_digits)

    # @property
    # def initial_soc(self) -> float:
    #     """Initial state-of-charge."""
    #     return pyomo_model.initial_soc.value

    # @initial_soc.setter
    # def initial_soc(self, initial_soc: float):
    #     initial_soc = self._check_initial_soc(initial_soc)
    #     pyomo_model.initial_soc = round(initial_soc, self.round_digits)

    @property
    def minimum_soc(self) -> float:
        """Minimum state-of-charge."""
        for t in self.blocks.index_set():
            return self.blocks[t].minimum_soc.value

    @minimum_soc.setter
    def minimum_soc(self, minimum_soc: float):
        for t in self.blocks.index_set():
            self.blocks[t].minimum_soc = round(minimum_soc, self.round_digits)

    @property
    def maximum_soc(self) -> float:
        """Maximum state-of-charge."""
        for t in self.blocks.index_set():
            return self.blocks[t].maximum_soc.value

    @maximum_soc.setter
    def maximum_soc(self, maximum_soc: float):
        for t in self.blocks.index_set():
            self.blocks[t].maximum_soc = round(maximum_soc, self.round_digits)

    @property
    def minimum_storage(self) -> float:
        """Minimum storage."""
        for t in self.blocks.index_set():
            return self.blocks[t].minimum_storage.value

    @minimum_storage.setter
    def minimum_storage(self, minimum_storage: float):
        for t in self.blocks.index_set():
            self.blocks[t].minimum_storage = round(minimum_storage, self.round_digits)

    @property
    def maximum_storage(self) -> float:
        """Maximum storage."""
        for t in self.blocks.index_set():
            return self.blocks[t].maximum_storage.value

    @maximum_storage.setter
    def maximum_storage(self, capacity_value: float):
        for t in self.blocks.index_set():
            self.blocks[t].maximum_storage = round(capacity_value, self.round_digits)

    @property
    def charge_efficiency(self) -> float:
        """Charge efficiency."""
        for t in self.blocks.index_set():
            return self.blocks[t].charge_efficiency.value

    @charge_efficiency.setter
    def charge_efficiency(self, efficiency: float):
        efficiency = self._check_efficiency_value(efficiency)
        for t in self.blocks.index_set():
            self.blocks[t].charge_efficiency = round(efficiency, self.round_digits)

    @property
    def discharge_efficiency(self) -> float:
        """Discharge efficiency."""
        for t in self.blocks.index_set():
            return self.blocks[t].discharge_efficiency.value

    @discharge_efficiency.setter
    def discharge_efficiency(self, efficiency: float):
        efficiency = self._check_efficiency_value(efficiency)
        for t in self.blocks.index_set():
            self.blocks[t].discharge_efficiency = round(efficiency, self.round_digits)

    @property
    def round_trip_efficiency(self) -> float:
        """Round trip efficiency."""
        return self.charge_efficiency * self.discharge_efficiency

    @round_trip_efficiency.setter
    def round_trip_efficiency(self, round_trip_efficiency: float):
        round_trip_efficiency = self._check_efficiency_value(round_trip_efficiency)
        # Assumes equal charge and discharge efficiencies
        efficiency = round_trip_efficiency ** (1 / 2)
        self.charge_efficiency = efficiency
        self.discharge_efficiency = efficiency

    @property
    def cost_per_charge(self) -> float:
        """Cost per charge."""
        for t in self.blocks.index_set():
            return self.blocks[t].cost_per_charge.value

    @cost_per_charge.setter
    def cost_per_charge(self, om_dollar_per_kwh: float):
        for t in self.blocks.index_set():
            self.blocks[t].cost_per_charge = round(om_dollar_per_kwh, self.round_digits)

    @property
    def cost_per_discharge(self) -> float:
        """Cost per discharge."""
        for t in self.blocks.index_set():
            return self.blocks[t].cost_per_discharge.value

    @cost_per_discharge.setter
    def cost_per_discharge(self, om_dollar_per_kwh: float):
        for t in self.blocks.index_set():
            self.blocks[t].cost_per_discharge = round(om_dollar_per_kwh, self.round_digits)

    @property
    def commodity_load_demand(self) -> list:
        return [self.blocks[t].commodity_load_demand.value for t in self.blocks.index_set()]

    @commodity_load_demand.setter
    def commodity_load_demand(self, commodity_demand: list):
        if len(commodity_demand) == len(self.blocks):
            for t, limit in zip(self.blocks, commodity_demand):
                self.blocks[t].commodity_load_demand.set_value(round(limit, self.round_digits))
        else:
            raise ValueError("'commodity_demand' list must be the same length as time horizon")

    @property
    def load_production_limit(self) -> list:
        return [self.blocks[t].load_production_limit.value for t in self.blocks.index_set()]

    @load_production_limit.setter
    def load_production_limit(self, commodity_demand: list):
        if len(commodity_demand) == len(self.blocks):
            for t, limit in zip(self.blocks, commodity_demand):
                self.blocks[t].load_production_limit.set_value(round(limit, self.round_digits))
        else:
            raise ValueError("'commodity_demand' list must be the same length as time horizon")

    @property
    def commodity_met_value(self) -> float:
        return [self.blocks[t].commodity_met_value.value for t in self.blocks.index_set()]

    @commodity_met_value.setter
    def commodity_met_value(self, price_per_kwh: float):
        for t in self.blocks.index_set():
            self.blocks[t].commodity_met_value = round(price_per_kwh, self.round_digits)

        ### The following method is if the value of meeting the demand is variable
        # if len(price_per_kwh) == len(self.blocks):
        #     for t, price in zip(self.blocks, price_per_kwh):
        #         self.blocks[t].commodity_met_value.set_value(
        #             round(price, self.round_digits)
        #         )
        # else:
        #     raise ValueError(
        #         "'price_per_kwh' list must be the same length as time horizon"
        #     )

    # OUTPUTS
    @property
    def is_charging(self) -> list:
        """Storage is charging."""
        return [self.blocks[t].is_charging.value for t in self.blocks.index_set()]

    @property
    def is_discharging(self) -> list:
        """Storage is discharging."""
        return [self.blocks[t].is_discharging.value for t in self.blocks.index_set()]

    @property
    def soc(self) -> list:
        """State-of-charge."""
        return [self.blocks[t].soc.value for t in self.blocks.index_set()]

    @property
    def charge_commodity(self) -> list:
        """Charge commodity."""
        return [self.blocks[t].charge_commodity.value for t in self.blocks.index_set()]

    @property
    def discharge_commodity(self) -> list:
        """Discharge commodity."""
        return [self.blocks[t].discharge_commodity.value for t in self.blocks.index_set()]

    @property
    def storage_output(self) -> list:
        """Storage Output."""
        return [
            self.blocks[t].discharge_commodity.value - self.blocks[t].charge_commodity.value
            for t in self.blocks.index_set()
        ]

    @property
    def system_production(self) -> list:
        return [self.blocks[t].system_production.value for t in self.blocks.index_set()]

    @property
    def system_load(self) -> list:
        return [self.blocks[t].system_load.value for t in self.blocks.index_set()]

    @property
    def commodity_out(self) -> list:
        return [self.blocks[t].commodity_out.value for t in self.blocks.index_set()]

    @property
    def storage_commodity_out(self) -> list:
        """Storage commodity out."""
        return [
            self.blocks[t].discharge_commodity.value - self.blocks[t].charge_commodity.value
            for t in self.blocks.index_set()
        ]

    # @property
    # def electricity_purchased(self) -> list:
    #     return [
    #         self.blocks[t].electricity_purchased.value for t in self.blocks.index_set()
    #     ]

    @property
    def is_generating(self) -> list:
        return [self.blocks[t].is_generating.value for t in self.blocks.index_set()]

    @property
    def not_generating(self) -> list:
        return [self.blocks[t].not_generating.value for t in self.blocks.index_set()]
