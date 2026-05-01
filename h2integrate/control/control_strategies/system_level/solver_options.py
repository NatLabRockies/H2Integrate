from typing import ClassVar

import openmdao.api as om
from attrs import field, define

from h2integrate.core.utilities import BaseConfig
from h2integrate.core.validators import gt_zero, contains, gte_zero


@define(kw_only=True)
class SLCSolverOptionsConfig(BaseConfig):
    solver_name: str = field(
        default="gauss_seidel", validator=contains["gauss_seidel", "newton", "block_jacobi"]
    )
    maxiter: int = field(default=20, converter=int, validator=gte_zero())
    atol: float | None = field(default=None)
    rtol: float | None = field(default=None)
    convergence_tolerance: float = field(default=1e-6, validator=gt_zero())
    iprint: int = field(default=2)
    solver_option_kwargs: dict = field(default={})

    solver_map: ClassVar = {
        "gauss_seidel": om.NonlinearBlockGS,
        "newton": om.NewtonSolver,
        "block_jacobi": om.NonlinearBlockJac,
    }

    def __attrs_post_init__(self):
        if self.atol is None:
            self.atol = self.convergence_tolerance
        if self.rtol is None:
            self.rtol = self.convergence_tolerance

    def get_solver_options(self):
        d = self.as_dict()
        non_solver_option_attrs = [
            "solver_name",
            "solver_map",
            "solver_option_kwargs",
            "convergence_tolerance",
        ]
        solver_options = {k: v for k, v in d.items() if k not in non_solver_option_attrs}
        solver_options_full = solver_options | self.solver_option_kwargs
        return solver_options_full

    def return_nonlinear_solver(self):
        return self.solver_map[self.solver_name]
