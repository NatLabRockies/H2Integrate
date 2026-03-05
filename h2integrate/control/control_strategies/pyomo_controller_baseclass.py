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
    max_charge_percent: float = field(validator=range_val(0, 1))
    min_charge_percent: float = field(validator=range_val(0, 1))
    init_charge_percent: float = field(validator=range_val(0, 1))
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


def dummy_function():
    """Dummy function used for setting OpenMDAO input/output defaults but otherwise unused.

    Returns:
        None: empty output
    """
    return None


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

        Adds discrete inputs named 'dispatch_block_rule_function' (and variants
        suffixed with source tech names for cross-tech connections) plus a
        discrete output 'pyomo_dispatch_solver' that will hold the assembled
        callable after compute().
        """

        # get technology group name
        self.tech_group_name = self.pathname.split(".")

        # initialize dispatch inputs to None
        self.dispatch_options = None

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
            callable: Function(performance_model, performance_model_kwargs, inputs, commodity)
                executing rolling-window heuristic dispatch or optimization and returning:
                (total_out, storage_out, unmet_demand, unused_commodity, soc)
        """
        # initialize the pyomo model
        self.pyomo_model = pyomo.ConcreteModel()

        index_set = pyomo.Set(initialize=range(self.config.n_control_window))

        self.source_techs = []
        self.dispatch_tech = []

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
                    self.dispatch_tech.append(source_tech)
                else:
                    dispatch_block_rule_function = discrete_inputs[
                        f"{'dispatch_block_rule_function'}_{source_tech}"
                    ]
                # create pyomo block and set attr
                blocks = pyomo.Block(index_set, rule=dispatch_block_rule_function)
                setattr(self.pyomo_model, source_tech, blocks)
                self.source_techs.append(source_tech)
            else:
                continue

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
                        f"{commodity}_in"          : available generated commodity profile.
                        f"{commodity}_demand"   : demanded commodity output profile.
                commodity (str, optional):
                    Base commodity name (e.g. "electricity", "hydrogen"). Default:
                    self.config.commodity.

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

            # initialize outputs
            unmet_demand = np.zeros(self.n_timesteps)
            storage_commodity_out = np.zeros(self.n_timesteps)
            total_commodity_out = np.zeros(self.n_timesteps)
            unused_commodity = np.zeros(self.n_timesteps)
            soc = np.zeros(self.n_timesteps)

            # get the starting index for each control window
            window_start_indices = list(range(0, self.n_timesteps, self.config.n_control_window))

            control_strategy = self.options["tech_config"]["control_strategy"]["model"]

            # TODO: implement optional kwargs for this method: maybe this will remove if statement here
            if "Heuristic" in control_strategy:
                # Initialize parameters for heuristic dispatch strategy
                self.initialize_parameters(inputs)
            elif "Optimized" in control_strategy:
                # Initialize parameters for optimized dispatch strategy
                self.initialize_parameters(
                    inputs[f"{commodity_name}_in"], inputs[f"{commodity_name}_demand"]
                )

            else:
                raise (
                    NotImplementedError(
                        f"Control strategy '{control_strategy}' was given, \
                        but has not been implemented yet."
                    )
                )

            # loop over all control windows, where t is the starting index of each window
            for t in window_start_indices:
                # get the inputs over the current control window
                commodity_in = inputs[f"{self.config.commodity}_in"][
                    t : t + self.config.n_control_window
                ]
                demand_in = inputs[f"{commodity_name}_demand"][t : t + self.config.n_control_window]

                if "Heuristic" in control_strategy:
                    # Update time series parameters for the heuristic method
                    self.update_time_series_parameters()
                    # determine dispatch commands for the current control window
                    # using the heuristic method
                    self.set_fixed_dispatch(
                        commodity_in,
                        self.config.system_commodity_interface_limit,
                        demand_in,
                    )

                elif "Optimized" in control_strategy:
                    # Progress report
                    if t % (self.n_timesteps // 4) < self.n_control_window:
                        percentage = round((t / self.n_timesteps) * 100)
                        print(f"{percentage}% done with optimal dispatch")
                    # Update time series parameters for the optimization method
                    self.update_time_series_parameters(
                        commodity_in=commodity_in,
                        commodity_demand=demand_in,
                        updated_initial_soc=self.updated_initial_soc,
                    )
                    # Run dispatch optimization to minimize costs while meeting demand
                    self.solve_dispatch_model(
                        start_time=t,
                        n_days=self.n_timesteps // 24,
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
                # update SOC for next time window
                self.updated_initial_soc = soc_control_window[-1] / 100  # turn into ratio

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
