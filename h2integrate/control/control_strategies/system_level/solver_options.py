from typing import ClassVar

import openmdao.api as om
from attrs import field, define

from h2integrate.core.utilities import BaseConfig
from h2integrate.core.validators import gt_zero, contains, gte_zero


@define(kw_only=True)
class SLCSolverOptionsConfig(BaseConfig):
    """Configuration for the nonlinear solver used by the system-level controller.

    Controls which OpenMDAO nonlinear solver is applied to the plant group and
    how it converges. The ``convergence_tolerance`` sets both ``atol`` and ``rtol``
    by default; either can be overridden individually.

    Attributes:
        solver_name: Solver type. One of ``"gauss_seidel"``, ``"newton"``, or
            ``"block_jacobi"``.
        max_iter: Maximum number of nonlinear iterations.
        atol: Absolute convergence tolerance. Defaults to ``convergence_tolerance``.
        rtol: Relative convergence tolerance. Defaults to ``convergence_tolerance``.
        convergence_tolerance: Convenience value used to set both ``atol`` and ``rtol``
            when they are not specified individually.
        iprint: Solver print level (0 = silent, 2 = verbose).
        solver_option_kwargs: Additional keyword arguments passed directly to the
            solver's ``options`` dict.
    """

    solver_name: str = field(
        default="gauss_seidel", validator=contains(["gauss_seidel", "newton", "block_jacobi"])
    )
    max_iter: int = field(default=20, converter=int, validator=gte_zero)
    atol: float | None = field(default=None)
    rtol: float | None = field(default=None)
    convergence_tolerance: float = field(default=1e-6, validator=gt_zero)
    iprint: int = field(default=2)
    solver_option_kwargs: dict = field(default={})

    # Maps user-facing solver names to OpenMDAO solver classes
    solver_map: ClassVar = {
        "gauss_seidel": om.NonlinearBlockGS,
        "newton": om.NewtonSolver,
        "block_jacobi": om.NonlinearBlockJac,
    }

    def __attrs_post_init__(self):
        # Default atol/rtol to the shared convergence_tolerance if not set
        if self.atol is None:
            self.atol = self.convergence_tolerance
        if self.rtol is None:
            self.rtol = self.convergence_tolerance

    def get_solver_options(self):
        """Build the options dict to apply to the nonlinear solver.

        Merges config attributes with any extra ``solver_option_kwargs`` and
        renames ``max_iter`` to ``maxiter`` (the OpenMDAO option name).

        Returns:
            dict: Keyword arguments suitable for ``solver.options[k] = v``.
        """
        d = self.as_dict()
        # These attrs configure *which* solver or are handled separately
        non_solver_option_attrs = [
            "solver_name",
            "solver_map",
            "solver_option_kwargs",
            "convergence_tolerance",
            "max_iter",
        ]
        solver_options = {k: v for k, v in d.items() if k not in non_solver_option_attrs}
        # Merge extra kwargs and translate max_iter → maxiter for OpenMDAO
        solver_options_full = (
            solver_options | self.solver_option_kwargs | {"maxiter": self.max_iter}
        )
        return solver_options_full

    def return_nonlinear_solver(self):
        """Return the OpenMDAO nonlinear solver class for ``solver_name``."""
        return self.solver_map[self.solver_name]
