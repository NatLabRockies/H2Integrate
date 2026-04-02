from typing import TYPE_CHECKING

import numpy as np
import pyomo.environ as pyomo
from attrs import field, define
from pyomo.util.check_units import assert_units_consistent

from h2integrate.core.utilities import merge_shared_inputs
from h2integrate.core.validators import range_val
from h2integrate.control.control_rules.plant_dispatch_model import PyomoDispatchPlantModel
from h2integrate.control.control_strategies.pyomo_controller_baseclass import (
    SolverOptions,
    PyomoControllerBaseClass,
    PyomoControllerBaseConfig,
)
from h2integrate.control.control_strategies.controller_opt_problem_state import DispatchProblemState
from h2integrate.control.control_rules.storage.pyomo_storage_rule_min_operating_cost import (
    PyomoRuleStorageMinOperatingCosts,
)
from h2integrate.control.control_rules.converters.generic_converter_min_operating_cost import (
    PyomoDispatchGenericConverterMinOperatingCosts,
)


if TYPE_CHECKING:  # to avoid circular imports
    pass


@define
class OptimizedDispatchControllerConfig(PyomoControllerBaseConfig):
    """
    Configuration data container for Pyomo-based optimal dispatch.

    This class groups the parameters needed by the optimized dispatch controller.
    Values are typically populated from the technology
    `tech_config.yaml` (merged under the "control" section).

    Attributes:
        max_charge_rate (float):
            The maximum charge that the storage can accept
            (in units of the commodity per time step).
        charge_efficiency (float):
            The efficiency of charging the storage (between 0 and 1).
        discharge_efficiency (float):
            The efficiency of discharging the storage (between 0 and 1).
        commodity (str):
            The name of the commodity being stored (e.g., "electricity", "hydrogen").
        commodity_rate_units (str):
            The rate units of the commodity being stored (e.g., "kW", "kg/h").
        cost_per_production (float):
            The cost to use the incoming produced commodity (in $/commodity_rate_units).
        cost_per_charge (float):
            The cost per unit of charging the storage (in $/commodity_rate_units).
        cost_per_discharge (float):
            The cost per unit of discharging the storage (in $/commodity_rate_units).
        commodity_met_value (float):
            The penalty for not meeting the desired load demand (in $/commodity_rate_units).
        time_weighting_factor (float):
            The weighting factor applied to future time steps in the optimization objective
            (between 0 and 1).
        time_duration (float):
            The duration of each time step in the Pyomo model in hours.
            The default of this parameter is 1.0 (i.e., 1 hour time steps).
    """

    max_charge_rate: int | float = field()
    charge_efficiency: float = field(validator=range_val(0, 1), default=None)
    discharge_efficiency: float = field(validator=range_val(0, 1), default=None)
    cost_per_production: float = field(default=None)
    cost_per_charge: float = field(default=None)
    cost_per_discharge: float = field(default=None)
    commodity_met_value: float = field(default=None)
    time_weighting_factor: float = field(validator=range_val(0, 1), default=0.995)
    time_duration: float = field(default=1.0)  # hours

    def make_dispatch_inputs(self):
        dispatch_keys = [
            "cost_per_production",
            "cost_per_charge",
            "cost_per_discharge",
            "commodity_met_value",
            "max_capacity",
            "max_soc_fraction",
            "min_soc_fraction",
            "charge_efficiency",
            "discharge_efficiency",
            "max_charge_rate",
        ]

        dispatch_inputs = {k: self.as_dict()[k] for k in dispatch_keys}
        dispatch_inputs.update({"initial_soc_fraction": self.init_soc_fraction})
        return dispatch_inputs


class OptimizedDispatchController(PyomoControllerBaseClass):
    """Operates storage based on optimization to meet the demand profile based on
        available commodity from generation profiles and demand profile while minimizing costs.

    Uses a rolling-window optimization approach with configurable horizon and control windows.

    """

    def setup(self):
        """Initialize the optimized dispatch controller."""
        self.config = OptimizedDispatchControllerConfig.from_dict(
            merge_shared_inputs(self.options["tech_config"]["model_inputs"], "control")
        )

        self.add_input(
            "max_charge_rate",
            val=self.config.max_charge_rate,
            units=self.config.commodity_rate_units,
            desc="Storage charge rate",
        )

        self.add_input(
            "storage_capacity",
            val=self.config.max_capacity,
            units=f"{self.config.commodity_rate_units}*h",
            desc="Storage capacity",
        )

        self.n_timesteps = self.options["plant_config"]["plant"]["simulation"]["n_timesteps"]

        super().setup()

        self.n_control_window = self.config.n_control_window
        self.updated_initial_soc = self.config.init_soc_fraction

        # Is this the best place to put this???
        self.commodity_info = {
            "commodity_name": self.config.commodity,
            "commodity_storage_units": self.config.commodity_rate_units,
        }
        # TODO: note that this definition of cost_per_production is not generalizable to multiple
        #       production technologies. Would need a name adjustment to connect it to
        #       production tech

        self.dispatch_inputs = self.config.make_dispatch_inputs()

    def pyomo_setup(self, discrete_inputs):
        """Create the Pyomo model, extract dispatch technology names, and return dispatch solver.

        Returns:
            callable: Function(performance_model, performance_model_kwargs, inputs, commodity)
                executing rolling-window optimization to determine dispatch and returning:
                (total_out, storage_out, unmet_demand, unused_commodity, soc)
        """
        # initialize the pyomo model
        self.pyomo_model = pyomo.ConcreteModel()

        pyomo.Set(initialize=range(self.config.n_control_window))

        self.source_techs = []
        self.dispatch_tech = []

        for connection in self.dispatch_connections:
            # get connection definition
            source_tech, intended_dispatch_tech = connection
            # only add connections to intended dispatch tech
            if any(intended_dispatch_tech in name for name in self.tech_group_name):
                # record source and dispatch techs
                if source_tech == intended_dispatch_tech:
                    self.dispatch_tech.append(source_tech)
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
            parameters, solves the Pyomo optimization model to determine
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

            # get the starting index for each control window
            window_start_indices = list(range(0, self.n_timesteps, self.config.n_control_window))

            # Initialize parameters for optimized dispatch strategy
            self.initialize_parameters(inputs)

            # loop over all control windows, where t is the starting index of each window
            for t in window_start_indices:
                # get the inputs over the current control window
                commodity_in = inputs[f"{self.config.commodity}_in"][
                    t : t + self.config.n_control_window
                ]
                demand_in = inputs[f"{commodity_name}_demand"][t : t + self.config.n_control_window]

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

            return storage_commodity_out, soc

        return pyomo_dispatch_solver

    def initialize_parameters(self, inputs):
        """Initialize parameters for optimization model

        Args:
            inputs (dict):
                Dictionary of numpy arrays (length = self.n_timesteps) containing at least:
                    f"{commodity}_in"       : Available generated commodity profile.
                    f"{commodity}_demand"   : Demanded commodity output profile.

        """
        # Where pyomo model communicates with the rest of the controller
        # self.hybrid_dispatch_model is the pyomo model, this is the thing in hybrid_rule
        if "max_charge_rate" in inputs:
            self.dispatch_inputs["max_charge_rate"] = inputs["max_charge_rate"][0]
        if "storage_capacity" in inputs:
            self.dispatch_inputs["max_capacity"] = inputs["storage_capacity"][0]
        self.hybrid_dispatch_model = self._create_dispatch_optimization_model()
        self.hybrid_dispatch_rule.create_min_operating_cost_expression()
        self.hybrid_dispatch_rule.create_arcs()
        assert_units_consistent(self.hybrid_dispatch_model)

        # This calls a class that stores problem state information such as solver metrics and
        #   the objective function. This is directly used in the H2I simulation, but is
        #   useful for tracking solver performance and debugging.
        self.problem_state = DispatchProblemState()

        # hybrid_dispatch_rule is the thing where you can access variables and hybrid_rule \
        #  functions from
        self.hybrid_dispatch_rule.initialize_parameters(inputs, self.dispatch_inputs)

    def update_time_series_parameters(
        self, commodity_in=None, commodity_demand=None, updated_initial_soc=None
    ):
        """Updates the pyomo optimization problem with parameters that change with time

        Args:
            commodity_in (list): List of generated commodity in for this time slice.
            commodity_demand (list): The demanded commodity for this time slice.
            updated_initial_soc (float): The updated initial state of charge for storage
                technologies for the current time slice.
        """
        self.hybrid_dispatch_rule.update_time_series_parameters(
            commodity_in, commodity_demand, updated_initial_soc
        )

    def solve_dispatch_model(
        self,
        start_time: int = 0,
        n_days: int = 0,
    ):
        """Solves the dispatch optimization model and stores problem metrics.

        Args:
            start_time (int): Starting timestep index for the current solve window.
            n_days (int): Total number of days in the simulation.

        """

        solver_results = self.glpk_solve_call(self.hybrid_dispatch_model)
        # The outputs of the store_problem_metrics method are not actively used in the H2I
        #   simulation, but they are useful for debugging and tracking solver performance over time.
        self.problem_state.store_problem_metrics(
            solver_results, start_time, n_days, pyomo.value(self.hybrid_dispatch_model.objective)
        )

    def _create_dispatch_optimization_model(self):
        """
        Creates monolith dispatch model by creating pyomo models for each technology, then
        aggregating them into hybrid_rule
        """
        model = pyomo.ConcreteModel(name="hybrid_dispatch")
        #################################
        # Sets                          #
        #################################
        model.forecast_horizon = pyomo.Set(
            doc="Set of time periods in time horizon",
            initialize=range(self.config.n_control_window),
        )
        for tech in self.source_techs:
            if tech == self.dispatch_tech[0]:
                dispatch = PyomoRuleStorageMinOperatingCosts(
                    self.commodity_info,
                    model,
                    model.forecast_horizon,
                    self.config.round_digits,
                    self.config.time_duration,
                    block_set_name=f"{tech}_rule",
                )
                self.pyomo_model.__setattr__(f"{tech}_rule", dispatch)
            else:
                dispatch = PyomoDispatchGenericConverterMinOperatingCosts(
                    self.commodity_info,
                    model,
                    model.forecast_horizon,
                    self.config.round_digits,
                    self.config.time_duration,
                    block_set_name=f"{tech}_rule",
                )
                self.pyomo_model.__setattr__(f"{tech}_rule", dispatch)

        # Create hybrid pyomo model, inputting individual technology models
        self.hybrid_dispatch_rule = PyomoDispatchPlantModel(
            model,
            model.forecast_horizon,
            self.source_techs,
            self.pyomo_model,
            self.config.time_weighting_factor,
            self.config.round_digits,
        )
        return model

    def compute(self, inputs, outputs, discrete_inputs, discrete_outputs):
        """Build Pyomo model blocks and assign the dispatch solver."""
        self.dispatch_inputs["max_charge_rate"] = inputs["max_charge_rate"][0]
        self.dispatch_inputs["max_capacity"] = inputs["storage_capacity"][0]

        discrete_outputs["pyomo_dispatch_solver"] = self.pyomo_setup(discrete_inputs)

    @staticmethod
    def glpk_solve_call(
        pyomo_model: pyomo.ConcreteModel,
        log_name: str = "",
        user_solver_options: dict | None = None,
    ):
        """
        This method takes in the dispatch system-level pyomo model that we have built,
        gives it to the solver, and gives back solver results.
        """

        # log_name = "annual_solve_GLPK.log"  # For debugging MILP solver
        # Ref. on solver options: https://en.wikibooks.org/wiki/GLPK/Using_GLPSOL
        glpk_solver_options = {
            "cuts": None,
            "presol": None,
            # 'mostf': None,
            # 'mipgap': 0.001,
            "tmlim": 30,
        }
        solver_options = SolverOptions(glpk_solver_options, log_name, user_solver_options, "log")
        with pyomo.SolverFactory("glpk") as solver:
            results = solver.solve(pyomo_model, options=solver_options.constructed)

        return results

    @property
    def storage_dispatch_commands(self) -> list:
        """
        Commanded dispatch including available commodity at current time step that has not
        been used to charge storage.
        """
        return self.hybrid_dispatch_rule.storage_commodity_out
