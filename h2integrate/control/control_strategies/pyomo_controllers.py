from typing import TYPE_CHECKING

import numpy as np
import pyomo.environ as pyomo
from attrs import field, define

from h2integrate.core.utilities import BaseConfig, merge_shared_inputs
from h2integrate.core.validators import range_val
from h2integrate.control.control_strategies.controller_baseclass import ControllerBaseClass


if TYPE_CHECKING:  # to avoid circular imports
    pass


@define(kw_only=True)
class PyomoControllerBaseConfig(BaseConfig):
    """
    Configuration data container for Pyomo-based storage / dispatch controllers.

    This class groups the fundamental parameters needed by derived controller
    implementations. Values are typically populated from the technology
    `tech_config.yaml` (merged under the "control" section).

    Attributes:
        max_capacity (float):
            Physical maximum stored commodity capacity (inventory, not a rate).
            Units correspond to the base commodity units (e.g., kg, MWh).
        max_charge_percent (float):
            Upper bound on state of charge expressed as a fraction in [0, 1].
            1.0 means the controller may fill to max_capacity.
        min_charge_percent (float):
            Lower bound on state of charge expressed as a fraction in [0, 1].
            0.0 allows full depletion; >0 reserves minimum inventory.
        init_charge_percent (float):
            Initial state of charge at simulation start as a fraction in [0, 1].
        n_control_window (int):
            Number of consecutive timesteps processed per control action
            (rolling control / dispatch window length).
        n_horizon_window (int):
            Number of timesteps considered for look ahead / optimization horizon.
            May be >= n_control_window (used by predictive strategies).
        commodity_name (str):
            Base name of the controlled commodity (e.g., "hydrogen", "electricity").
            Used to construct input/output variable names (e.g., f"{commodity_name}_in").
        commodity_storage_units (str):
            Units string for stored commodity rates (e.g., "kg/h", "MW").
            Used for unit annotations when creating model variables.
        tech_name (str):
            Technology identifier used to namespace Pyomo blocks / variables within
            the broader OpenMDAO model (e.g., "battery", "h2_storage").
        system_commodity_interface_limit (float | int | str |list[float]): Max interface
            (e.g. grid interface) flow used to bound dispatch (scalar or per-timestep list of
            length n_control_window).
    """

    max_capacity: float = field()
    max_charge_percent: float = field(validator=range_val(0, 1))
    min_charge_percent: float = field(validator=range_val(0, 1))
    init_charge_percent: float = field(validator=range_val(0, 1))
    n_control_window: int = field()
    n_horizon_window: int = field()
    commodity_name: str = field()
    commodity_storage_units: str = field()
    tech_name: str = field()
    system_commodity_interface_limit: float | int | str | list[float] = field()

    def __attrs_post_init__(self):
        if isinstance(self.system_commodity_interface_limit, str):
            self.system_commodity_interface_limit = float(self.system_commodity_interface_limit)
        if isinstance(self.system_commodity_interface_limit, (float, int)):
            self.system_commodity_interface_limit = [
                self.system_commodity_interface_limit
            ] * self.n_control_window


def dummy_function():
    """Dummy function used for setting OpenMDAO input/output defaults but otherwise unused.

    Returns:
        None: empty output
    """
    return None


class PyomoControllerBaseClass(ControllerBaseClass):
    def dummy_method(self, in1, in2):
        """Dummy method used for setting OpenMDAO input/output defaults but otherwise unused.

        Args:
            in1 (any): dummy input 1
            in2 (any): dummy input 2

        Returns:
            None: empty output
        """
        return None

    def setup(self):
        """Register per-technology dispatch rule inputs and expose the solver callable.

        Adds discrete inputs named 'dispatch_block_rule_function' (and variants
        suffixed with source tech names for cross-tech connections) plus a
        discrete output 'pyomo_dispatch_solver' that will hold the assembled
        callable after compute().
        """

        # get technology group name
        self.tech_group_name = self.pathname.split(".")

        # create inputs for all pyomo object creation functions from all connected technologies
        self.dispatch_connections = self.options["plant_config"]["tech_to_dispatch_connections"]
        for connection in self.dispatch_connections:
            # get connection definition
            source_tech, intended_dispatch_tech = connection
            if any(intended_dispatch_tech in name for name in self.tech_group_name):
                if source_tech == intended_dispatch_tech:
                    # When getting rules for the same tech, the tech name is not used in order to
                    # allow for automatic connections rather than complicating the h2i model set up
                    self.add_discrete_input("dispatch_block_rule_function", val=self.dummy_method)
                else:
                    self.add_discrete_input(
                        f"{'dispatch_block_rule_function'}_{source_tech}", val=self.dummy_method
                    )
            else:
                continue

        # create output for the pyomo control model
        self.add_discrete_output(
            "pyomo_dispatch_solver",
            val=dummy_function,
            desc="callable: fully formed pyomo model and execution logic to be run \
                by owning technologies performance model",
        )

    def compute(self, inputs, outputs, discrete_inputs, discrete_outputs):
        """Build Pyomo model blocks and assign the dispatch solver."""
        discrete_outputs["pyomo_dispatch_solver"] = self.pyomo_setup(discrete_inputs)

    def pyomo_setup(self, discrete_inputs):
        """Create the Pyomo model, attach per-tech Blocks, and return dispatch solver.

        Returns:
            callable: Function(performance_model, performance_model_kwargs, inputs, commodity_name)
                executing rolling-window heuristic dispatch and returning:
                (total_out, storage_out, unmet_demand, unused_commodity, soc)
        """
        # initialize the pyomo model
        self.pyomo_model = pyomo.ConcreteModel()

        index_set = pyomo.Set(initialize=range(self.config.n_control_window))

        # run each pyomo rule set up function for each technology
        for connection in self.dispatch_connections:
            # get connection definition
            source_tech, intended_dispatch_tech = connection
            # only add connections to intended dispatch tech
            if any(intended_dispatch_tech in name for name in self.tech_group_name):
                # names are specified differently if connecting within the tech group vs
                # connecting from an external tech group. This facilitates OM connections
                if source_tech == intended_dispatch_tech:
                    dispatch_block_rule_function = discrete_inputs["dispatch_block_rule_function"]
                else:
                    dispatch_block_rule_function = discrete_inputs[
                        f"{'dispatch_block_rule_function'}_{source_tech}"
                    ]
                # create pyomo block and set attr
                blocks = pyomo.Block(index_set, rule=dispatch_block_rule_function)
                setattr(self.pyomo_model, source_tech, blocks)
            else:
                continue

        # define dispatch solver
        def pyomo_dispatch_solver(
            performance_model: callable,
            performance_model_kwargs,
            inputs,
            commodity_name: str = self.config.commodity_name,
        ):
            r"""
            Execute rolling-window dispatch for the controlled technology.

            Iterates over the full simulation period in chunks of size
            `self.config.n_control_window`, (re)configures per\-window dispatch
            parameters, invokes a heuristic control strategy to set fixed
            dispatch decisions, and then calls the provided performance_model
            over each window to obtain storage output and SOC trajectories.

            Args:
                performance_model (callable):
                    Function implementing the technology performance over a control
                    window. Signature must accept (storage_dispatch_commands,
                    **performance_model_kwargs, sim_start_index=<int>)
                    and return (storage_out_window, soc_window) arrays of length
                    n_control_window.
                performance_model_kwargs (dict):
                    Extra keyword arguments forwarded unchanged to performance_model
                    at window (e.g., efficiencies, timestep size).
                inputs (dict):
                    Dictionary of numpy arrays (length = self.n_timesteps) containing at least:
                        f"{commodity_name}_in"          : available generated commodity profile.
                        f"{commodity_name}_demand"   : demanded commodity output profile.
                commodity_name (str, optional):
                    Base commodity name (e.g. "electricity", "hydrogen"). Default:
                    self.config.commodity_name.

            Returns:
                tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
                    total_commodity_out :
                        Net commodity supplied to demand each timestep (min(demand, storage + gen)).
                    storage_commodity_out :
                        Commodity supplied (positive) by the storage asset each timestep.
                    unmet_demand :
                        Positive shortfall = demand - total_out (0 if fully met).
                    unused_commodity :
                        Surplus generation + storage discharge not used to meet demand.
                    soc :
                        State of charge trajectory (percent of capacity).

            Raises:
                NotImplementedError:
                    If the configured control strategy is not implemented.

            Notes:
                1. Arrays returned have length self.n_timesteps (full simulation period).
            """
            self.initialize_parameters()

            # initialize outputs
            unmet_demand = np.zeros(self.n_timesteps)
            storage_commodity_out = np.zeros(self.n_timesteps)
            total_commodity_out = np.zeros(self.n_timesteps)
            unused_commodity = np.zeros(self.n_timesteps)
            soc = np.zeros(self.n_timesteps)

            # get the starting index for each control window
            window_start_indices = list(range(0, self.n_timesteps, self.config.n_control_window))

            control_strategy = self.options["tech_config"]["control_strategy"]["model"]

            # loop over all control windows, where t is the starting index of each window
            for t in window_start_indices:
                self.update_time_series_parameters()
                # get the inputs over the current control window
                commodity_in = inputs[self.config.commodity_name + "_in"][
                    t : t + self.config.n_control_window
                ]
                demand_in = inputs[f"{commodity_name}_demand"][t : t + self.config.n_control_window]

                if "heuristic" in control_strategy:
                    # determine dispatch commands for the current control window
                    # using the heuristic method
                    self.set_fixed_dispatch(
                        commodity_in,
                        self.config.system_commodity_interface_limit,
                        demand_in,
                    )

                else:
                    raise (
                        NotImplementedError(
                            f"Control strategy '{control_strategy}' was given, \
                            but has not been implemented yet."
                        )
                    )

                # run the performance/simulation model for the current control window
                # using the dispatch commands
                storage_commodity_out_control_window, soc_control_window = performance_model(
                    self.storage_dispatch_commands,
                    **performance_model_kwargs,
                    sim_start_index=t,
                )

                # get a list of all time indices belonging to the current control window
                window_indices = list(range(t, t + self.config.n_control_window))

                # loop over all time steps in the current control window
                for j in window_indices:
                    # save the output for the control window to the output for the full
                    # simulation
                    storage_commodity_out[j] = storage_commodity_out_control_window[j - t]
                    soc[j] = soc_control_window[j - t]
                    total_commodity_out[j] = np.minimum(
                        demand_in[j - t], storage_commodity_out[j] + commodity_in[j - t]
                    )
                    unmet_demand[j] = np.maximum(0, demand_in[j - t] - total_commodity_out[j])
                    unused_commodity[j] = np.maximum(
                        0, storage_commodity_out[j] + commodity_in[j - t] - demand_in[j - t]
                    )

            return total_commodity_out, storage_commodity_out, unmet_demand, unused_commodity, soc

        return pyomo_dispatch_solver

    @staticmethod
    def dispatch_block_rule(block, t):
        raise NotImplementedError("This function must be overridden for specific dispatch model")

    def initialize_parameters(self):
        raise NotImplementedError("This function must be overridden for specific dispatch model")

    def update_time_series_parameters(self, start_time: int):
        raise NotImplementedError("This function must be overridden for specific dispatch model")

    @staticmethod
    def _check_efficiency_value(efficiency):
        """Checks efficiency is between 0 and 1. Returns fractional value"""
        if efficiency < 0:
            raise ValueError("Efficiency value must greater than 0")
        elif efficiency > 1:
            raise ValueError("Efficiency value must between 0 and 1")
        return efficiency

    @property
    def blocks(self) -> pyomo.Block:
        return getattr(self.pyomo_model, self.config.tech_name)

    @property
    def model(self) -> pyomo.ConcreteModel:
        return self._model


class SimpleBatteryControllerHeuristic(PyomoControllerBaseClass):
    """Fixes battery dispatch operations based on user input.

    Currently, enforces available generation and grid limit assuming no battery charging from grid.

    Enforces:
        - Available generation cannot be exceeded for charging.
        - Interface (grid / export) limit bounds discharge.
        - No grid charging (unless logic extended elsewhere).
    """

    def setup(self):
        """Initialize SimpleBatteryControllerHeuristic."""
        super().setup()

        self.round_digits = 4

        self.max_charge_fraction = [0.0] * self.config.n_control_window
        self.max_discharge_fraction = [0.0] * self.config.n_control_window
        self._fixed_dispatch = [0.0] * self.config.n_control_window

    def initialize_parameters(self):
        """Initializes parameters."""

        self.minimum_storage = 0.0
        self.maximum_storage = self.config.max_capacity
        self.minimum_soc = self.config.min_charge_percent
        self.maximum_soc = self.config.max_charge_percent
        self.initial_soc = self.config.init_charge_percent

    def update_time_series_parameters(self, start_time: int = 0):
        """Updates time series parameters.

        Args:
            start_time (int): The start time.

        """
        # TODO: provide more control; currently don't use `start_time`
        # see HOPP implementation
        self.time_duration = [1.0] * len(self.blocks.index_set())

    def update_dispatch_initial_soc(self, initial_soc: float | None = None):
        """Updates dispatch initial state of charge (SOC).

        Args:
            initial_soc (float, optional): Initial state of charge. Defaults to None.

        """
        if initial_soc is not None:
            self._system_model.value("initial_SOC", initial_soc)
            self._system_model.setup()
        self.initial_soc = self._system_model.value("SOC")

    def set_fixed_dispatch(
        self,
        commodity_in: list,
        system_commodity_interface_limit: list,
    ):
        """Sets charge and discharge amount of storage dispatch using fixed_dispatch attribute
            and enforces available generation and charge/discharge limits.

        Args:
            commodity_in (list): commodity blocks.
            system_commodity_interface_limit (list): Maximum flow rate of commodity through
            the system interface (e.g. grid interface)

        Raises:
            ValueError: If commodity_in or system_commodity_interface_limit length do not
                match fixed_dispatch length.

        """
        self.check_commodity_in_discharge_limit(commodity_in, system_commodity_interface_limit)
        self._set_commodity_fraction_limits(commodity_in, system_commodity_interface_limit)
        self._heuristic_method(commodity_in)
        self._fix_dispatch_model_variables()

    def check_commodity_in_discharge_limit(
        self, commodity_in: list, system_commodity_interface_limit: list
    ):
        """Checks if commodity in and discharge limit lengths match fixed_dispatch length.

        Args:
            commodity_in (list): commodity blocks.
            system_commodity_interface_limit (list): Maximum flow rate of commodity through
            the system interface (e.g. grid interface).

        Raises:
            ValueError: If commodity_in or system_commodity_interface_limit length does not
            match fixed_dispatch length.

        """
        if len(commodity_in) != len(self.fixed_dispatch):
            raise ValueError("commodity_in must be the same length as fixed_dispatch.")
        elif len(system_commodity_interface_limit) != len(self.fixed_dispatch):
            raise ValueError(
                "system_commodity_interface_limit must be the same length as fixed_dispatch."
            )

    def _set_commodity_fraction_limits(
        self, commodity_in: list, system_commodity_interface_limit: list
    ):
        """Set storage charge and discharge fraction limits based on
        available generation and system interface capacity, respectively.

        Args:
            commodity_in (list): commodity blocks.
            system_commodity_interface_limit (list): Maximum flow rate of commodity
            through the system interface (e.g. grid interface).

        NOTE: This method assumes that storage cannot be charged by the grid.

        """
        for t in self.blocks.index_set():
            self.max_charge_fraction[t] = self.enforce_power_fraction_simple_bounds(
                (commodity_in[t]) / self.maximum_storage, self.minimum_soc, self.maximum_soc
            )
            self.max_discharge_fraction[t] = self.enforce_power_fraction_simple_bounds(
                (system_commodity_interface_limit[t] - commodity_in[t]) / self.maximum_storage,
                self.minimum_soc,
                self.maximum_soc,
            )

    @staticmethod
    def enforce_power_fraction_simple_bounds(
        storage_fraction: float,
        minimum_soc: float,
        maximum_soc: float,
    ) -> float:
        """Enforces simple bounds (0, .9) for battery power fractions.

        Args:
            storage_fraction (float): Storage fraction from heuristic method.

        Returns:
            storage_fraction (float): Bounded storage fraction.

        """
        if storage_fraction > maximum_soc:
            storage_fraction = maximum_soc
        elif storage_fraction < minimum_soc:
            storage_fraction = minimum_soc
        return storage_fraction

    def update_soc(self, storage_fraction: float, soc0: float) -> float:
        """Updates SOC based on storage fraction threshold.

        Args:
            storage_fraction (float): Storage fraction from heuristic method. Below threshold
                is charging, above is discharging.
            soc0 (float): Initial SOC.

        Returns:
            soc (float): Updated SOC.

        """
        if storage_fraction > 0.0:
            discharge_commodity = storage_fraction * self.maximum_storage
            soc = (
                soc0
                - self.time_duration[0]
                * (1 / (self.discharge_efficiency) * discharge_commodity)
                / self.maximum_storage
            )
        elif storage_fraction < 0.0:
            charge_commodity = -storage_fraction * self.maximum_storage
            soc = (
                soc0
                + self.time_duration[0]
                * (self.charge_efficiency * charge_commodity)
                / self.maximum_storage
            )
        else:
            soc = soc0

        return max(self.minimum_soc, min(self.maximum_soc, soc))

    def _heuristic_method(self, _):
        """Executes specific heuristic method to fix storage dispatch."""
        self._enforce_power_fraction_limits()

    def _enforce_power_fraction_limits(self):
        """Enforces storage fraction limits and sets _fixed_dispatch attribute."""
        for t in self.blocks.index_set():
            fd = self.user_fixed_dispatch[t]
            if fd > 0.0:  # Discharging
                if fd > self.max_discharge_fraction[t]:
                    fd = self.max_discharge_fraction[t]
            elif fd < 0.0:  # Charging
                if -fd > self.max_charge_fraction[t]:
                    fd = -self.max_charge_fraction[t]
            self._fixed_dispatch[t] = fd

    def _fix_dispatch_model_variables(self):
        """Fixes dispatch model variables based on the fixed dispatch values."""
        soc0 = self.pyomo_model.initial_soc
        for t in self.blocks.index_set():
            dispatch_factor = self._fixed_dispatch[t]
            self.blocks[t].soc.fix(self.update_soc(dispatch_factor, soc0))
            soc0 = self.blocks[t].soc.value

            if dispatch_factor == 0.0:
                # Do nothing
                self.blocks[t].charge_commodity.fix(0.0)
                self.blocks[t].discharge_commodity.fix(0.0)
            elif dispatch_factor > 0.0:
                # Discharging
                self.blocks[t].charge_commodity.fix(0.0)
                self.blocks[t].discharge_commodity.fix(dispatch_factor * self.maximum_storage)
            elif dispatch_factor < 0.0:
                # Charging
                self.blocks[t].discharge_commodity.fix(0.0)
                self.blocks[t].charge_commodity.fix(-dispatch_factor * self.maximum_storage)

    def _check_initial_soc(self, initial_soc):
        """Checks initial state-of-charge.

        Args:
            initial_soc: Initial state-of-charge value.

        Returns:
            float: Checked initial state-of-charge.

        """
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

    @property
    def fixed_dispatch(self) -> list:
        """list: List of fixed dispatch."""
        return self._fixed_dispatch

    @property
    def user_fixed_dispatch(self) -> list:
        """list: List of user fixed dispatch."""
        return self._user_fixed_dispatch

    @user_fixed_dispatch.setter
    def user_fixed_dispatch(self, fixed_dispatch: list):
        if len(fixed_dispatch) != len(self.blocks.index_set()):
            raise ValueError("fixed_dispatch must be the same length as dispatch index set.")
        elif max(fixed_dispatch) > 1.0 or min(fixed_dispatch) < -1.0:
            raise ValueError("fixed_dispatch must be normalized values between -1 and 1.")
        else:
            self._user_fixed_dispatch = fixed_dispatch

    @property
    def storage_dispatch_commands(self) -> list:
        """
        Commanded dispatch including available commodity at current time step that has not
        been used to charge the battery.
        """
        return [
            (self.blocks[t].discharge_commodity.value - self.blocks[t].charge_commodity.value)
            for t in self.blocks.index_set()
        ]

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
    def initial_soc(self) -> float:
        """Initial state-of-charge."""
        return self.pyomo_model.initial_soc.value

    @initial_soc.setter
    def initial_soc(self, initial_soc: float):
        initial_soc = self._check_initial_soc(initial_soc)
        self.pyomo_model.initial_soc = round(initial_soc, self.round_digits)

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


@define(kw_only=True)
class HeuristicLoadFollowingControllerConfig(PyomoControllerBaseConfig):
    max_charge_rate: int | float = field()
    charge_efficiency: float = field(default=None)
    discharge_efficiency: float = field(default=None)
    include_lifecycle_count: bool = field(default=False)


class HeuristicLoadFollowingController(SimpleBatteryControllerHeuristic):
    """Operates the battery based on heuristic rules to meet the demand profile based power
        available from power generation profiles and power demand profile.

    Currently, enforces available generation and grid limit assuming no battery charging from grid.

    """

    def setup(self):
        """Initialize HeuristicLoadFollowingController."""
        self.config = HeuristicLoadFollowingControllerConfig.from_dict(
            merge_shared_inputs(self.options["tech_config"]["model_inputs"], "control")
        )

        self.n_timesteps = self.options["plant_config"]["plant"]["simulation"]["n_timesteps"]

        super().setup()

        if self.config.charge_efficiency is not None:
            self.charge_efficiency = self.config.charge_efficiency
        if self.config.discharge_efficiency is not None:
            self.discharge_efficiency = self.config.discharge_efficiency

    def set_fixed_dispatch(
        self,
        commodity_in: list,
        system_commodity_interface_limit: list,
        commodity_demand: list,
    ):
        """Sets charge and discharge power of battery dispatch using fixed_dispatch attribute
            and enforces available generation and charge/discharge limits.

        Args:
            commodity_in (list): List of generated commodity in.
            system_commodity_interface_limit (list): List of max flow rates through system
                interface (e.g. grid interface).
            commodity_demand (list): The demanded commodity.

        """

        self.check_commodity_in_discharge_limit(commodity_in, system_commodity_interface_limit)
        self._set_commodity_fraction_limits(commodity_in, system_commodity_interface_limit)
        self._heuristic_method(commodity_in, commodity_demand)
        self._fix_dispatch_model_variables()

    def _heuristic_method(self, commodity_in, commodity_demand):
        """Enforces storage fraction limits and sets _fixed_dispatch attribute.
        Sets the _fixed_dispatch based on commodity_demand and commodity_in.

        Args:
            commodity_in: commodity generation profile.
            commodity_demand: Goal amount of commodity.

        """
        for t in self.blocks.index_set():
            fd = (commodity_demand[t] - commodity_in[t]) / self.maximum_storage
            if fd > 0.0:  # Discharging
                if fd > self.max_discharge_fraction[t]:
                    fd = self.max_discharge_fraction[t]
            elif fd < 0.0:  # Charging
                if -fd > self.max_charge_fraction[t]:
                    fd = -self.max_charge_fraction[t]
            self._fixed_dispatch[t] = fd
