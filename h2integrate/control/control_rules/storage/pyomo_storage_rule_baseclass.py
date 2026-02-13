import pyomo.environ as pyo
from pyomo.network import Port

from h2integrate.control.control_rules.pyomo_rule_baseclass import PyomoRuleBaseClass


class PyomoRuleStorageBaseclass(PyomoRuleBaseClass):
    """Base class defining Pyomo rules for generic commodity storage components."""

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
        pyomo_model.minimum_storage = pyo.Param(
            doc=pyomo_model.name
            + " minimum storage rating ["
            + self.config.commodity_rate_units
            + "]",
            default=0.0,
            within=pyo.NonNegativeReals,
            mutable=True,
            units=eval("pyo.units." + self.config.commodity_rate_units),
        )
        pyomo_model.maximum_storage = pyo.Param(
            doc=pyomo_model.name
            + " maximum storage rating ["
            + self.config.commodity_rate_units
            + "]",
            within=pyo.NonNegativeReals,
            mutable=True,
            units=eval("pyo.units." + self.config.commodity_rate_units),
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

        pyomo_model.capacity = pyo.Param(
            doc=pyomo_model.name + " capacity [" + self.config.commodity_rate_units + "]",
            within=pyo.NonNegativeReals,
            mutable=True,
            units=eval("pyo.units." + self.config.commodity_rate_units),
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
            doc=self.config.commodity
            + " into "
            + pyomo_model.name
            + " ["
            + self.config.commodity_rate_units
            + "]",
            domain=pyo.NonNegativeReals,
            units=eval("pyo.units." + self.config.commodity_rate_units),
        )
        pyomo_model.discharge_commodity = pyo.Var(
            doc=self.config.commodity
            + " out of "
            + pyomo_model.name
            + " ["
            + self.config.commodity_rate_units
            + "]",
            domain=pyo.NonNegativeReals,
            units=eval("pyo.units." + self.config.commodity_rate_units),
        )

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
            expr=pyomo_model.charge_commodity
            <= pyomo_model.maximum_storage * pyomo_model.is_charging,
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
            <= pyomo_model.maximum_storage * pyomo_model.is_discharging,
        )
        # Storage packing constraint
        pyomo_model.charge_discharge_packing = pyo.Constraint(
            doc=pyomo_model.name + " packing constraint for charging and discharging binaries",
            expr=pyomo_model.is_charging + pyomo_model.is_discharging <= 1,
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
                / m.capacity
            )

        # Storage State-of-charge balance
        pyomo_model.soc_inventory = pyo.Constraint(
            doc=pyomo_model.name + " state-of-charge inventory balance",
            rule=soc_inventory_rule,
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
