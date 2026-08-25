import numpy as np
from openmdao.solvers.linear.linear_runonce import LinearRunOnce
from openmdao.solvers.nonlinear.nonlinear_runonce import NonlinearRunOnce


class CustomNonLinearRunOnce(NonlinearRunOnce):
    """A simple custom nonlinear solver skeleton."""

    # SOLVER = "NL: RUNONCE"

    def solve(self):
        print("nonlinear solver bingo!")
        self.was_called = True
        # super().solve()

        system = self._system()

        di_keys = list(system._discrete_inputs)
        timestep_keys = [k for k in di_keys if k.endswith("timestep_index")]

        # TODO get N_sim and N_step from H2I somehow

        # Make loop
        sim_starts = np.arange(0, 8760, 24)

        for ss in sim_starts:
            for di_k in timestep_keys:
                system._discrete_inputs[di_k] = ss

            self._gs_iter()


class CustomLinearRunOnce(LinearRunOnce):
    SOLVER = "LN: CUSTOM"

    def solve(self, mode, rel_systems=None):
        self.was_called = True
        super().solve(mode=mode, rel_systems=rel_systems)
