import pyomo.environ as pyo
from pyomo.network import Port


class PyomoRuleStorageMinOperatingCosts:
    """Class defining Pyomo rules for the optimized dispatch for load following
    for generic commodity storage components."""

    def __init__(
        self,
        commodity_info: dict,
        pyomo_model: pyo.ConcreteModel,
        index_set: pyo.Set,
        round_digits: int,
        block_set_name: str = "storage",
    ):
        self.round_digits = round_digits
        self.block_set_name = block_set_name
        self.commodity_name = commodity_info["commodity_name"]
        self.commodity_storage_units = commodity_info["commodity_storage_units"]
        pyo.units.load_definitions_from_strings(["USD = [currency]"])

        self.model = pyomo_model
        self.blocks = pyo.Block(index_set, rule=self.dispatch_block_rule_function)

        self.model.__setattr__(self.block_set_name, self.blocks)

    def initialize_parameters(
        self, commodity_in: list, commodity_demand: list, dispatch_inputs: dict
    ):
        """Initialize parameters for optimization model

        Args:
            commodity_in (list): List of generated commodity in for this time slice.
            commodity_demand (list): The demanded commodity for this time slice.
            dispatch_inputs (dict): Dictionary of the dispatch input parameters from config

        """
        # Dispatch Parameters
        self.set_timeseries_parameter("cost_per_charge", dispatch_inputs["cost_per_charge"])
        self.set_timeseries_parameter("cost_per_discharge", dispatch_inputs["cost_per_discharge"])
        self.set_timeseries_parameter("commodity_met_value", dispatch_inputs["commodity_met_value"])

        # Storage parameters
        self.set_timeseries_parameter("minimum_storage", 0.0)
        self.set_timeseries_parameter("maximum_storage", dispatch_inputs["max_capacity"])

        self.set_timeseries_parameter("minimum_soc", dispatch_inputs["min_charge_percent"])
        self.set_timeseries_parameter("maximum_soc", dispatch_inputs["max_charge_percent"])

        self.initial_soc = dispatch_inputs["initial_soc_percent"]
        self.charge_efficiency = dispatch_inputs.get("charge_efficiency", 0.94)
        self.discharge_efficiency = dispatch_inputs.get("discharge_efficiency", 0.94)

        # Set charge and discharge rate equal to each other for now
        self.set_timeseries_parameter("max_charge", dispatch_inputs["max_charge_rate"])
        self.set_timeseries_parameter("max_discharge", dispatch_inputs["max_charge_rate"])

        # System parameters
        self.commodity_load_demand = [commodity_demand[t] for t in self.blocks.index_set()]

        self._set_initial_soc_constraint()

    def dispatch_block_rule_function(self, pyomo_model: pyo.ConcreteModel, tech_name: str):
        """
        Creates and initializes pyomo dispatch model components for a specific technology.

        This method sets up all model elements (parameters, variables, constraints,
        and ports) associated with a technology block within the dispatch model.

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
        time step. This method also defined system parameters such as the value of
        load the load met and the production limit of the system.

        Args:
            pyomo_model (pyo.ConcreteModel): Pyomo model instance representing
                the storage system.
            t: Time index or iterable representing time steps (unused in this method).
        """
        ##################################
        # Storage Parameters             #
        ##################################

        pyo_commodity_storage_unit = eval(f"pyo.units.{self.commodity_storage_units}")
        pyo_commodity_storage_unit_hrs = eval(f"pyo.units.{self.commodity_storage_units}h")
        pyo_usd_per_commodity_storage_unit_hrs = eval(
            f"pyo.units.USD / pyo.units.{self.commodity_storage_units}h"
        )
        usd_pr_units_str = f"[$/{self.commodity_storage_units}]"

        pyomo_model.time_duration = pyo.Param(
            doc=f"{pyomo_model.name} time step [hour]",
            default=1.0,
            within=pyo.NonNegativeReals,
            mutable=True,
            units=pyo.units.hr,
        )

        pyomo_model.cost_per_charge = pyo.Param(
            doc=f"Operating cost of {pyomo_model.name} charging {usd_pr_units_str}",
            default=0.0,
            within=pyo.NonNegativeReals,
            mutable=True,
            units=pyo_usd_per_commodity_storage_unit_hrs,
        )
        pyomo_model.cost_per_discharge = pyo.Param(
            doc=f"Operating cost of {pyomo_model.name} discharging {usd_pr_units_str}",
            default=0.0,
            within=pyo.NonNegativeReals,
            mutable=True,
            units=pyo_usd_per_commodity_storage_unit_hrs,
        )
        pyomo_model.minimum_storage = pyo.Param(
            doc=f"{pyomo_model.name} minimum storage rating [{self.commodity_storage_units}]",
            default=0.0,
            within=pyo.NonNegativeReals,
            mutable=True,
            units=pyo_commodity_storage_unit,
        )
        pyomo_model.maximum_storage = pyo.Param(
            doc=f"{pyomo_model.name} maximum storage rating [{self.commodity_storage_units}]",
            default=1000.0,
            within=pyo.NonNegativeReals,
            mutable=True,
            units=pyo_commodity_storage_unit_hrs,
        )
        pyomo_model.minimum_soc = pyo.Param(
            doc=f"{pyomo_model.name} minimum state-of-charge [-]",
            default=0.1,
            within=pyo.PercentFraction,
            mutable=True,
            units=pyo.units.dimensionless,
        )
        pyomo_model.maximum_soc = pyo.Param(
            doc=f"{pyomo_model.name} maximum state-of-charge [-]",
            default=0.9,
            within=pyo.PercentFraction,
            mutable=True,
            units=pyo.units.dimensionless,
        )

        ##################################
        # Efficiency Parameters          #
        ##################################
        pyomo_model.charge_efficiency = pyo.Param(
            doc=f"{pyomo_model.name} Charging efficiency [-]",
            default=0.938,
            within=pyo.PercentFraction,
            mutable=True,
            units=pyo.units.dimensionless,
        )
        pyomo_model.discharge_efficiency = pyo.Param(
            doc=f"{pyomo_model.name} discharging efficiency [-]",
            default=0.938,
            within=pyo.PercentFraction,
            mutable=True,
            units=pyo.units.dimensionless,
        )
        ##################################
        # Capacity Parameters            #
        ##################################
        pyomo_model.max_charge = pyo.Param(
            doc=f"{pyomo_model.name} maximum charge [{self.commodity_storage_units}]",
            within=pyo.NonNegativeReals,
            mutable=True,
            units=pyo_commodity_storage_unit,
        )
        pyomo_model.max_discharge = pyo.Param(
            doc=f"{pyomo_model.name} maximum discharge [{self.commodity_storage_units}]",
            within=pyo.NonNegativeReals,
            mutable=True,
            units=pyo_commodity_storage_unit,
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
            doc=f"Commodity demand met value per generation [$/{self.commodity_storage_units}]",
            default=0.0,
            within=pyo.Reals,
            mutable=True,
            units=pyo_usd_per_commodity_storage_unit_hrs,
        )
        pyomo_model.commodity_load_demand = pyo.Param(
            doc=f"Load demand for the commodity [{self.commodity_storage_units}]",
            default=1000.0,
            within=pyo.NonNegativeReals,
            mutable=True,
            units=pyo_commodity_storage_unit,
        )

    def _create_variables(self, pyomo_model: pyo.ConcreteModel, t):
        """Create storage-related decision variables in the Pyomo model.

        This method defines binary and continuous variables representing
        charging/discharging modes, energy flows, and state-of-charge, as well
        as system variables such as system load, system production, and commodity produced.

        Args:
            pyomo_model (pyo.ConcreteModel): Pyomo model instance representing
                the storage system.
            t: Time index or iterable representing time steps (unused in this method).
        """
        ##################################
        # Variables                      #
        ##################################
        pyomo_model.is_charging = pyo.Var(
            doc=f"1 if {pyomo_model.name} is charging; 0 Otherwise [-]",
            domain=pyo.Binary,
            units=pyo.units.dimensionless,
        )
        pyomo_model.is_discharging = pyo.Var(
            doc=f"1 if {pyomo_model.name} is discharging; 0 Otherwise [-]",
            domain=pyo.Binary,
            units=pyo.units.dimensionless,
        )
        pyomo_model.soc0 = pyo.Var(
            doc=f"{pyomo_model.name} initial state-of-charge at beginning of period[-]",
            domain=pyo.PercentFraction,
            bounds=(pyomo_model.minimum_soc, pyomo_model.maximum_soc),
            units=pyo.units.dimensionless,
        )
        pyomo_model.soc = pyo.Var(
            doc=f"{pyomo_model.name} state-of-charge at end of period [-]",
            domain=pyo.PercentFraction,
            bounds=(pyomo_model.minimum_soc, pyomo_model.maximum_soc),
            units=pyo.units.dimensionless,
        )

        pyomo_model.charge_commodity = pyo.Var(
            doc=f"{self.commodity_name} into {pyomo_model.name} [{self.commodity_storage_units}]",
            domain=pyo.NonNegativeReals,
            units=eval(f"pyo.units.{self.commodity_storage_units}"),
        )
        pyomo_model.discharge_commodity = pyo.Var(
            doc=f"{self.commodity_name} out of {pyomo_model.name} [{self.commodity_storage_units}]",
            domain=pyo.NonNegativeReals,
            units=eval(f"pyo.units.{self.commodity_storage_units}"),
        )
        ##################################
        # System Variables               #
        ##################################
        pyomo_model.system_production = pyo.Var(
            doc=f"System generation [{self.commodity_storage_units}]",
            domain=pyo.NonNegativeReals,
            units=eval(f"pyo.units.{self.commodity_storage_units}"),
        )
        pyomo_model.system_load = pyo.Var(
            doc=f"System load [{self.commodity_storage_units}]",
            domain=pyo.NonNegativeReals,
            units=eval(f"pyo.units.{self.commodity_storage_units}"),
        )
        pyomo_model.commodity_out = pyo.Var(
            doc=f"Commodity out of the system [{self.commodity_storage_units}]",
            domain=pyo.NonNegativeReals,
            bounds=(0, pyomo_model.commodity_load_demand),
            units=eval(f"pyo.units.{self.commodity_storage_units}"),
        )
        pyomo_model.is_generating = pyo.Var(
            doc="System is producing commodity binary [-]",
            domain=pyo.Binary,
            units=pyo.units.dimensionless,
        )

    def _create_constraints(self, pyomo_model: pyo.ConcreteModel, t):
        """Create operational and state-of-charge constraints for storage and the system.

        This method defines constraints that enforce:
        - Mutual exclusivity between charging and discharging.
        - Upper and lower bounds on charge/discharge flows.
        - The state-of-charge balance over time.
        - The system balance of output with system production and load
        - The system output is less than or equal to the load (because of linear optimization)

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
            doc=f"{pyomo_model.name} charging storage upper bound",
            expr=pyomo_model.charge_commodity <= pyomo_model.max_charge * pyomo_model.is_charging,
        )
        pyomo_model.charge_commodity_lb = pyo.Constraint(
            doc=f"{pyomo_model.name} charging storage lower bound",
            expr=pyomo_model.charge_commodity
            >= pyomo_model.minimum_storage * pyomo_model.is_charging,
        )
        # Discharge commodity bounds
        pyomo_model.discharge_commodity_lb = pyo.Constraint(
            doc=f"{pyomo_model.name} Discharging storage lower bound",
            expr=pyomo_model.discharge_commodity
            >= pyomo_model.minimum_storage * pyomo_model.is_discharging,
        )
        pyomo_model.discharge_commodity_ub = pyo.Constraint(
            doc=f"{pyomo_model.name} Discharging storage upper bound",
            expr=pyomo_model.discharge_commodity
            <= pyomo_model.max_discharge * pyomo_model.is_discharging,
        )
        # Storage packing constraint
        pyomo_model.charge_discharge_packing = pyo.Constraint(
            doc=f"{pyomo_model.name} packing constraint for charging and discharging binaries",
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
            doc=f"{pyomo_model.name} state-of-charge inventory balance",
            rule=soc_inventory_rule,
        )

    def _set_initial_soc_constraint(self):
        """
        This method links the SOC between the end of one control period and the beginning
        of the next control period.
        """
        ##################################
        # SOC Linking                    #
        ##################################
        self.model.initial_soc = pyo.Param(
            doc=f"{self.commodity_name} initial state-of-charge at beginning of the horizon[-]",
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

    # Update time series parameters for next optimization window
    def update_time_series_parameters(
        self, commodity_in: list, commodity_demand: list, updated_initial_soc: None
    ):
        """Updates the pyomo optimization problem with parameters that change with time

        Args:
            commodity_in (list): List of generated commodity in for this time slice.
            commodity_demand (list): The demanded commodity for this time slice.
            updated_initial_soc (float): The updated initial state of charge for storage
                technologies for the current time slice.
        """
        self.time_duration = [1.0] * len(self.blocks.index_set())
        self.commodity_load_demand = [commodity_demand[t] for t in self.blocks.index_set()]
        self.model.initial_soc = updated_initial_soc
        self.initial_soc = updated_initial_soc

    # Objective functions
    def min_operating_cost_objective(self, hybrid_blocks, tech_name: str):
        """Storage instance of minimum operating cost objective.

        Args:
            hybrid_blocks (Pyomo.block): A generalized container for defining hierarchical
                models by adding modeling components as attributes.

        """
        # Note that this objective function incentivizes charging the storage and penalizes
        # discharging the storage. This is to help the storage model maintain a state of charge.
        # This is also why cost_per_discharge should not equal cost_per_charge, which can lead
        # to battery oscillation behavior.
        self.obj = sum(
            hybrid_blocks[t].time_weighting_factor
            * self.blocks[t].time_duration
            * (
                self.blocks[t].cost_per_discharge * hybrid_blocks[t].discharge_commodity
                - self.blocks[t].cost_per_charge * hybrid_blocks[t].charge_commodity
                + (self.blocks[t].commodity_load_demand - hybrid_blocks[t].commodity_out)
                * self.blocks[t].commodity_met_value
            )
            for t in self.blocks.index_set()
        )
        return self.obj

    # System-level functions
    def _create_hybrid_port(self, hybrid_model: pyo.ConcreteModel, tech_name: str):
        """Create generic storage ports to add to system-level pyomo model instance.

        Args:
            hybrid_model (pyo.ConcreteModel): hybrid_model the ports should be added to.
            tech_name (str): The name or key identifying the technology for which
            ports are created.
        """
        tech_port = Port(
            initialize={
                "system_production": hybrid_model.system_production,
                "system_load": hybrid_model.system_load,
                "commodity_out": hybrid_model.commodity_out,
                "charge_commodity": hybrid_model.charge_commodity,
                "discharge_commodity": hybrid_model.discharge_commodity,
            }
        )
        hybrid_model.__setattr__(f"{tech_name}_port", tech_port)

        return hybrid_model.__getattribute__(f"{tech_name}_port")

    def _create_hybrid_variables(self, hybrid_model: pyo.ConcreteModel, tech_name: str):
        """Create generic storage variables to add to system-level pyomo model instance.

        Args:
            hybrid_model (pyo.ConcreteModel): hybrid_model the variables should be added to.
            tech_name (str): The name or key identifying the technology for which
            variables are created.
        """
        ##################################
        # System Variables               #
        ##################################
        # TODO: fix the units on these
        pyo_commodity_units = eval("pyo.units." + self.commodity_storage_units)

        hybrid_model.system_production = pyo.Var(
            doc=f"System generation [{self.commodity_storage_units}]",
            domain=pyo.NonNegativeReals,
            units=pyo_commodity_units,
        )
        hybrid_model.system_load = pyo.Var(
            doc=f"System load [{self.commodity_storage_units}]",
            domain=pyo.NonNegativeReals,
            units=pyo_commodity_units,
        )
        hybrid_model.commodity_out = pyo.Var(
            doc=f"{self.commodity_name} sold [{self.commodity_storage_units}]",
            domain=pyo.NonNegativeReals,
            units=pyo_commodity_units,
        )
        ##################################
        # Storage Variables              #
        ##################################

        hybrid_model.charge_commodity = pyo.Var(
            doc=f"{self.commodity_name} into {tech_name} [{self.commodity_storage_units}]",
            domain=pyo.NonNegativeReals,
            units=pyo_commodity_units,
        )
        hybrid_model.discharge_commodity = pyo.Var(
            doc=f"{self.commodity_name} out of {tech_name} [{self.commodity_storage_units}]",
            domain=pyo.NonNegativeReals,
            units=pyo_commodity_units,
        )
        # Returns to power_source_gen_vars and load_vars in hybrid_rule
        power_source_gen_var = hybrid_model.discharge_commodity
        load_var = hybrid_model.charge_commodity
        return power_source_gen_var, load_var

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

    def set_timeseries_parameter(self, param_name: str, param_val: float):
        for t in self.blocks.index_set():
            val_rounded = round(param_val, self.round_digits)
            self.blocks[t].__setattr__(param_name, val_rounded)

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
    def commodity_load_demand(self) -> list:
        return [self.blocks[t].commodity_load_demand.value for t in self.blocks.index_set()]

    @commodity_load_demand.setter
    def commodity_load_demand(self, commodity_demand: list):
        if len(commodity_demand) == len(self.blocks):
            for t, limit in zip(self.blocks, commodity_demand):
                self.blocks[t].commodity_load_demand.set_value(round(limit, self.round_digits))
        else:
            raise ValueError("'commodity_demand' list must be the same length as time horizon")
