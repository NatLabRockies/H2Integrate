from pyomo.opt import TerminationCondition


class DispatchProblemState:
    """Class for tracking dispatch problem solve state and metrics"""

    def __init__(self):
        self._start_time = ()
        self._n_days = ()
        self._termination_condition = ()
        self._solve_time = ()
        self._objective = ()
        self._upper_bound = ()
        self._lower_bound = ()
        self._constraints = ()
        self._variables = ()
        self._non_zeros = ()
        self._gap = ()
        self._n_non_optimal_solves = 0

    def store_problem_metrics(self, solver_results, start_time, n_days, objective_value):
        """
        This method takes the solver results and formats them for debugging.
        """
        self.value("start_time", start_time)
        self.value("n_days", n_days)

        # Unpack the solver results dictionary
        solver_results_dict = {
            k.lower().replace(" ", "_"): v.value
            for k, v in solver_results.solver._list[0].items()
            if k != "Statistics"
        }
        # Reformat variables names to take out spaces for progromatic simplicity
        solver_problem_dict = {
            k.lower().replace(" ", "_"): v.value for k, v in solver_results.problem._list[0].items()
        }
        # Simpify names of quantities of interest
        prob_to_attr_map = {
            "number_of_nonzeros": "non_zeros",
            "number_of_variables": "variables",
            "number_of_constraints": "constraints",
            "lower_bound": "lower_bound",
            "upper_bound": "upper_bound",
        }

        # Save termination condition, solve time, and objective values
        self.termination_condition = str(solver_results_dict["termination_condition"])
        if "time" in solver_results_dict:
            # if optimally solved, the results will have a time variable
            self.value("solve_time", solver_results_dict["time"])
        else:
            # if the solve timed-out (not optimal), the results will have a wallclock_time variable
            self.value("solve_time", solver_results_dict["wallclock_time"])

        self.value("objective", objective_value)

        # Map values into this class structure
        for solver_prob_key, attribute_name in prob_to_attr_map.items():
            self.value(attribute_name, solver_problem_dict[solver_prob_key])

        # solver_results.solution.Gap not defined
        upper_bound = solver_problem_dict["upper_bound"]
        lower_bound = solver_problem_dict["lower_bound"]
        if upper_bound != 0.0:
            # if the upper bound is not equal to zero, calculate the gap between the lower and upper
            #   bounds (i.e. the feasible space for the solution)
            gap = abs(upper_bound - lower_bound) / abs(upper_bound)
        elif lower_bound == 0.0:
            # If upper bound = 0 from the previous if, and the lower bound also equals 0, then the
            #   gap is zero
            gap = 0.0
        else:
            # Otherwise, the upper bound is infinite, and thus so is the solution space
            gap = float("inf")
        self.value("gap", gap)

        # This keeps track of the number of non-optimal solves (i.e. satisfactory)
        if not solver_results_dict["termination_condition"] == TerminationCondition.optimal:
            self._n_non_optimal_solves += 1

    def value(self, metric_name: str, set_value=None):
        if set_value is not None:
            data = list(self.__getattribute__(f"_{metric_name}"))
            data.append(set_value)
            self.__setattr__(f"_{metric_name}", tuple(data))

        else:
            return self.__getattribute__(f"_{metric_name}")
