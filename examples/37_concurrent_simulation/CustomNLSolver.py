import numpy as np
from openmdao.solvers.nonlinear.nonlinear_runonce import NonlinearRunOnce


# TODO more descriptive class name
class CustomNonLinearRunOnce(NonlinearRunOnce):
    """A simple custom nonlinear solver skeleton."""

    def solve(self):
        # Should only be used when system is the plant group
        system = self._system()

        # Find subsystems that take timestep_index as a discrete input
        timestep_keys = [k for k in system._discrete_inputs.keys() if k.endswith("timestep_index")]

        # TODO get N_sim and N_step from H2I config rather than a subsystem model
        n_steps_per_compute = system.solar.PYSAMSolarPlantPerformanceModel.n_steps_per_compute
        n_timesteps = system.solar.PYSAMSolarPlantPerformanceModel.n_timesteps

        # Make time stepping loop
        sim_starts = np.arange(0, n_timesteps, n_steps_per_compute)

        for ss in sim_starts:
            # Update timestep_index in all subsystems
            for tk in timestep_keys:
                system._discrete_inputs[tk] = ss

            # Run one GS iteration on the plant group
            self._gs_iter()


# May be needed later
# class CustomLinearRunOnce(LinearRunOnce):
#     SOLVER = "LN: CUSTOM"

#     def solve(self, mode, rel_systems=None):
#         self.was_called = True
#         super().solve(mode=mode, rel_systems=rel_systems)
