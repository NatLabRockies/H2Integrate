from openmdao.solvers.linear.linear_runonce import LinearRunOnce
from openmdao.solvers.nonlinear.nonlinear_runonce import NonlinearRunOnce


class CustomNonLinearRunOnce(NonlinearRunOnce):
    """A simple custom nonlinear solver skeleton."""

    SOLVER = "NL: RUNONCE"

    def solve(self):
        print("nonlinear solver bingo!")
        self.was_called = True
        super().solve()

    # def __init__(self, **kwargs):
    #     super().__init__(**kwargs)
    #     # Define custom options or tolerances here, e.g.:
    #     self.options.declare('maxiter', default=10, types=int)

    # def solve(self, model):
    #     """Perform the non-linear solve on the model."""
    #     maxiter = self.options['maxiter']

    #     for iter_count in range(maxiter):
    #         # 1. Execute the model or subsystems
    #         model.run_solve_nonlinear()

    #         # 2. Compute residuals or check convergence criteria
    #         # (e.g., check norm of residuals)
    #         # if converged: break

    #     # Record iteration / handle failure if needed


class CustomLinearRunOnce(LinearRunOnce):
    SOLVER = "LN: CUSTOM"

    def solve(self, mode, rel_systems=None):
        self.was_called = True
        super().solve(mode=mode, rel_systems=rel_systems)
