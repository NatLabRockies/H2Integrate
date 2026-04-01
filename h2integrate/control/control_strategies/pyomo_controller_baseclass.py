from typing import TYPE_CHECKING

import numpy as np
import openmdao.api as om
import pyomo.environ as pyomo
from attrs import field, define

from h2integrate.core.utilities import BaseConfig
from h2integrate.core.validators import range_val


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
        max_soc_fraction (float):
            Upper bound on state of charge expressed as a fraction in [0, 1].
            1.0 means the controller may fill to max_capacity.
        min_soc_fraction (float):
            Lower bound on state of charge expressed as a fraction in [0, 1].
            0.0 allows full depletion; >0 reserves minimum inventory.
        init_soc_fraction (float):
            Initial state of charge at simulation start as a fraction in [0, 1].
        n_control_window (int):
            Number of consecutive timesteps processed per control action
            (rolling control / dispatch window length).
        commodity (str):
            Base name of the controlled commodity (e.g., "hydrogen", "electricity").
            Used to construct input/output variable names (e.g., f"{commodity}_in").
        commodity_rate_units (str):
            Units string for stored commodity rates (e.g., "kg/h", "MW").
            Used for unit annotations when creating model variables.
        tech_name (str):
            Technology identifier used to namespace Pyomo blocks / variables within
            the broader OpenMDAO model (e.g., "battery", "h2_storage").
        system_commodity_interface_limit (float | int | str |list[float]): Max interface
            (e.g. grid interface) flow used to bound dispatch (scalar or per-timestep list of
            length n_control_window).
        round_digits (int):
            The number of digits to round to in the Pyomo model for numerical stability.
            The default of this parameter is 4.
    """

    max_capacity: float = field()
    max_soc_fraction: float = field(validator=range_val(0, 1))
    min_soc_fraction: float = field(validator=range_val(0, 1))
    init_soc_fraction: float = field(validator=range_val(0, 1))
    n_control_window: int = field()
    commodity: str = field()
    commodity_rate_units: str = field()
    tech_name: str = field()
    system_commodity_interface_limit: float | int | str | list[float] = field()
    round_digits: int = field(default=4)

    def __attrs_post_init__(self):
        if isinstance(self.system_commodity_interface_limit, str):
            self.system_commodity_interface_limit = float(self.system_commodity_interface_limit)
        if isinstance(self.system_commodity_interface_limit, float | int):
            self.system_commodity_interface_limit = [
                self.system_commodity_interface_limit
            ] * self.n_control_window


class PyomoControllerBaseClass(om.ExplicitComponent):
    def initialize(self):
        """
        Declare options for the component. See "Attributes" section in class doc strings for
        details.
        """

        self.options.declare("driver_config", types=dict)
        self.options.declare("plant_config", types=dict)
        self.options.declare("tech_config", types=dict)

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

        Adds discrete output 'pyomo_dispatch_solver' that will hold the assembled
        callable after compute().
        """

        # get technology group name
        self.tech_group_name = self.pathname.split(".")

        # initialize dispatch inputs to None
        self.dispatch_options = None

        # create inputs for all pyomo object creation functions from all connected technologies
        self.dispatch_connections = self.options["plant_config"]["tech_to_dispatch_connections"]

        # create output for the pyomo control model
        self.add_discrete_output(
            "pyomo_dispatch_solver",
            val=lambda: None,
            desc="callable: fully formed pyomo model and execution logic to be run \
                by owning technologies performance model",
        )

    def compute(self, inputs, outputs, discrete_inputs, discrete_outputs):
        """Build Pyomo model blocks and assign the dispatch solver."""
        discrete_outputs["pyomo_dispatch_solver"] = self.pyomo_setup(discrete_inputs)

    def pyomo_setup(self, discrete_inputs):
        """Create the Pyomo model and return dispatch solver.

        Returns:
            callable: Function(performance_model, performance_model_kwargs, inputs, commodity)
                executing rolling-window dispatch and returning:
                (total_out, storage_out, unmet_demand, unused_commodity, soc)
        """
        # initialize the pyomo model
        self.pyomo_model = pyomo.ConcreteModel()

        # define dispatch solver
        def pyomo_dispatch_solver(
            performance_model: callable,
            performance_model_kwargs,
            inputs,
            pyomo_model=self.pyomo_model,
            commodity_name: str = self.config.commodity,
        ):
            """
            Execute rolling-window dispatch for the controlled technology.

            Iterates over the full simulation period in chunks of size
            `self.config.n_control_window`, (re)configures per-window dispatch
            parameters, applies the chosen control strategy, and then calls the
            provided performance_model over each window to obtain storage output and
            SOC trajectories.

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
                        f"{commodity}_in"          : available generated commodity profile.
                        f"{commodity}_demand"   : demanded commodity output profile.
                commodity (str, optional):
                    Base commodity name (e.g. "electricity", "hydrogen"). Default:
                    self.config.commodity.

            Returns:
                tuple[np.ndarray, np.ndarray]:
                    storage_commodity_out :
                        Commodity supplied (positive) by the storage asset each timestep.
                    soc :
                        State of charge trajectory (percent of capacity).

            Raises:
                NotImplementedError:
                    If the configured control strategy is not implemented.

            Notes:
                1. Arrays returned have length self.n_timesteps (full simulation period).
            """

            # initialize outputs
            storage_commodity_out = np.zeros(self.n_timesteps)
            soc = np.zeros(self.n_timesteps)

            # This is where the pyomo controller interface is defined in individual
            #   pyomo controllers

            # The structure should be as follows:
            # 1. initialize_parameters()
            # 2. update_time_series_parameters()
            # 3. solve dispatch model or set fixed dispatch
            # 4. update outputs

            return storage_commodity_out, soc

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


class SolverOptions:
    """Class for housing solver options"""

    def __init__(
        self,
        solver_spec_options: dict,
        log_name: str = "",
        user_solver_options: dict | None = None,
        solver_spec_log_key: str = "logfile",
    ):
        self.instance_log = "dispatch_solver.log"
        self.solver_spec_options = solver_spec_options
        self.user_solver_options = user_solver_options

        self.constructed = solver_spec_options
        if log_name != "":
            self.constructed[solver_spec_log_key] = self.instance_log
        if user_solver_options is not None:
            self.constructed.update(user_solver_options)
