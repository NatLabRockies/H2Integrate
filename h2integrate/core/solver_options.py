from typing import ClassVar

import openmdao.api as om
from attrs import field, define, validators

from h2integrate.core.utilities import BaseConfig


@define(kw_only=True)
class FeedbackNLSolverOptionsConfig(BaseConfig):
    """Configuration for the nonlinear solver used H2I if there are
    feedback loops in the technology interconnections.

    The default nonlinear solver is the "gaus_seidel" solver
    `om.NonlinearBlockGS <https://openmdao.org/newdocs/versions/latest/features/building_blocks/solvers/nonlinear_block_gs.html>_`.

    Controls which OpenMDAO nonlinear solver is applied to the plant group and
    how it converges. The ``convergence_tolerance`` sets both ``atol`` and ``rtol``
    by default; either can be overridden individually.

    Attributes:
        solver_name (str, optional): Solver type. One of ``"gauss_seidel"``, ``"newton"``, or
            ``"block_jacobi"``. Defaults to ``"gaus_seidel"``
        maxiter (int, optional): Maximum number of nonlinear iterations. Defaults to 10.
        atol (float | None, optional): Absolute convergence tolerance. Uses
            ``convergence_tolerance`` if None. Defaults to 1e-10.
        rtol (float | None, optional): Relative convergence tolerance. Uses
            ``convergence_tolerance`` if None. Defaults to 1e-10.
        convergence_tolerance (float | None, optional): Convenience value used to set both
            ``atol`` and ``rtol`` when they are not specified individually. Defaults to None.
        iprint (int, optional): Solver print level (0 = silent, 2 = verbose). Defaults to 2.
        debug_print (bool, optional): If true, prints the input and output values of the variables.
            Defaults to False.
        solver_option_kwargs (dict, optional): Additional keyword arguments passed directly to the
            solver's ``options`` dict.

    """

    solver_name: str = field(
        default="gauss_seidel", validator=validators.in_(["gauss_seidel", "newton", "block_jacobi"])
    )
    maxiter: int = field(default=10, converter=int, validator=validators.ge(0))
    atol: float | None = field(default=1e-10, validator=validators.optional(validators.gt(0)))
    rtol: float | None = field(default=1e-10, validator=validators.optional(validators.gt(0)))
    convergence_tolerance: float | None = field(
        default=None, validator=validators.optional(validators.gt(0))
    )
    iprint: int = field(default=2)
    debug_print: bool = field(default=False)
    solver_option_kwargs: dict = field(default={})

    # Maps user-facing solver names to OpenMDAO solver classes
    solver_map: ClassVar = {
        "gauss_seidel": om.NonlinearBlockGS,
        "newton": om.NewtonSolver,
        "block_jacobi": om.NonlinearBlockJac,
    }

    def __attrs_post_init__(self):
        if self.convergence_tolerance is None:
            if self.atol is None or self.rtol is None:
                msg = "Please provide `convergence_tolerance` if `atol` or `rtol` is set to None."
                raise AttributeError(msg)
        # Default atol/rtol to the shared convergence_tolerance if not set
        if self.atol is None:
            self.atol = self.convergence_tolerance
        if self.rtol is None:
            self.rtol = self.convergence_tolerance

        # TODO: could add check to ensure that no duplicate keys are
        # provided in solver_option_kwargs

    def get_solver_options(self):
        """Build the options dict to apply to the nonlinear solver.

        Merges config attributes with any extra ``solver_option_kwargs``

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
        ]
        solver_options = {k: v for k, v in d.items() if k not in non_solver_option_attrs}
        # Merge extra kwargs and translate max_iter
        solver_options_full = solver_options | self.solver_option_kwargs
        return solver_options_full

    def return_nonlinear_solver(self):
        """Return the OpenMDAO nonlinear solver class for ``solver_name``."""
        return self.solver_map[self.solver_name]
