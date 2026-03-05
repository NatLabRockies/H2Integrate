from typing import TYPE_CHECKING

from attrs import field, define

from h2integrate.core.utilities import merge_shared_inputs
from h2integrate.core.validators import range_val_or_none
from h2integrate.control.control_strategies.pyomo_controller_baseclass import (
    PyomoControllerBaseClass,
    PyomoControllerBaseConfig,
)


if TYPE_CHECKING:  # to avoid circular imports
    pass


@define(kw_only=True)
class HeuristicLoadFollowingControllerConfig(PyomoControllerBaseConfig):
    charge_efficiency: float = field(validator=range_val_or_none(0, 1), default=None)
    discharge_efficiency: float = field(validator=range_val_or_none(0, 1), default=None)


class HeuristicLoadFollowingController(PyomoControllerBaseClass):
    """Operates storage based on heuristic rules to meet the demand profile based on
        available commodity from generation profiles and demand profile.

    Currently, enforces available generation and system interface limit assuming no
    storage charging from external sources.

    """

    def setup(self):
        """Initialize the heuristic load-following controller."""
        self.config = HeuristicLoadFollowingControllerConfig.from_dict(
            merge_shared_inputs(self.options["tech_config"]["model_inputs"], "control"),
            additional_cls_name=self.__class__.__name__,
            strict=False,
        )

        self.n_timesteps = self.options["plant_config"]["plant"]["simulation"]["n_timesteps"]

        super().setup()

        self.add_input(
            "storage_capacity",
            val=self.config.max_capacity,
            units=f"{self.config.commodity_rate_units}*h",
            desc="Storage capacity",
        )

        self.max_charge_fraction = [0.0] * self.config.n_control_window
        self.max_discharge_fraction = [0.0] * self.config.n_control_window
        self._fixed_dispatch = [0.0] * self.config.n_control_window

        if self.config.charge_efficiency is not None:
            self.charge_efficiency = self.config.charge_efficiency
        if self.config.discharge_efficiency is not None:
            self.discharge_efficiency = self.config.discharge_efficiency

    def initialize_parameters(self, inputs):
        """Initializes parameters."""

        self.minimum_storage = 0.0
        self.maximum_storage = inputs["storage_capacity"][0]
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

    def set_fixed_dispatch(
        self,
        commodity_in: list,
        system_commodity_interface_limit: list,
        commodity_demand: list,
    ):
        """Sets charge and discharge amount of storage dispatch using fixed_dispatch attribute
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

    @staticmethod
    def enforce_power_fraction_simple_bounds(
        storage_fraction: float,
        minimum_soc: float,
        maximum_soc: float,
    ) -> float:
        """Enforces simple bounds for storage power fractions.

        Args:
            storage_fraction (float): Storage fraction from heuristic method.
            minimum_soc (float): Minimum state of charge fraction.
            maximum_soc (float): Maximum state of charge fraction.

        Returns:
            float: Bounded storage fraction within [minimum_soc, maximum_soc].

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
        initial_soc = round(initial_soc, self.config.round_digits)
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
        been used to charge storage.
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
        self.pyomo_model.initial_soc = round(initial_soc, self.config.round_digits)

    @property
    def minimum_soc(self) -> float:
        """Minimum state-of-charge."""
        for t in self.blocks.index_set():
            return self.blocks[t].minimum_soc.value

    @minimum_soc.setter
    def minimum_soc(self, minimum_soc: float):
        for t in self.blocks.index_set():
            self.blocks[t].minimum_soc = round(minimum_soc, self.config.round_digits)

    @property
    def maximum_soc(self) -> float:
        """Maximum state-of-charge."""
        for t in self.blocks.index_set():
            return self.blocks[t].maximum_soc.value

    @maximum_soc.setter
    def maximum_soc(self, maximum_soc: float):
        for t in self.blocks.index_set():
            self.blocks[t].maximum_soc = round(maximum_soc, self.config.round_digits)

    # Need these properties to define these values for methods in this class
    @property
    def charge_efficiency(self) -> float:
        """Charge efficiency."""
        for t in self.blocks.index_set():
            return self.blocks[t].charge_efficiency.value

    @charge_efficiency.setter
    def charge_efficiency(self, efficiency: float):
        efficiency = self._check_efficiency_value(efficiency)
        for t in self.blocks.index_set():
            self.blocks[t].charge_efficiency = round(efficiency, self.config.round_digits)

    @property
    def discharge_efficiency(self) -> float:
        """Discharge efficiency."""
        for t in self.blocks.index_set():
            return self.blocks[t].discharge_efficiency.value

    @discharge_efficiency.setter
    def discharge_efficiency(self, efficiency: float):
        efficiency = self._check_efficiency_value(efficiency)
        for t in self.blocks.index_set():
            self.blocks[t].discharge_efficiency = round(efficiency, self.config.round_digits)
