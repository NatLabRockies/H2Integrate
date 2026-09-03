import numpy as np
from openmdao.recorders.recording_iteration_stack import Recording
from openmdao.solvers.nonlinear.nonlinear_runonce import NonlinearRunOnce


class ConcurrentPlantNLSolver(NonlinearRunOnce):
    """
    Custom nonlinear solver to manage running the plant group in a loop.

    """

    def __init__(self, plant_config):
        super().__init__()
        self.plant_config = plant_config

    def solve(self):
        # Should only be used when system is the plant group
        system = self._system()

        # Find subsystems that take timestep_index as an input
        # Should only be performance models
        timestep_keys = [k for k in system._inputs.keys() if k.endswith("timestep_index")]

        # Find subsystems that take skip_compute as a discrete_input
        # Should only be cost models
        skip_compute_keys = [
            k for k in system._discrete_inputs.keys() if k.endswith("skip_compute")
        ]

        n_timesteps = self.plant_config["plant"]["simulation"]["n_timesteps"]
        n_steps_per_compute = self.plant_config["plant"]["simulation"]["n_steps_per_compute"]

        # Make time stepping loop
        sim_starts = np.arange(0, n_timesteps, n_steps_per_compute)

        final_timestep_index = sim_starts[-1]

        # Set skip_compute to True for relevant subsystems. This will skip
        # unnecessary computation in most of the simulation periods.
        for sk in skip_compute_keys:
            system._discrete_inputs[sk] = True

        with Recording("NLRunOnce", 0, self) as rec:
            for ss in sim_starts:
                # Update timestep_index in all subsystems
                for tk in timestep_keys:
                    system._inputs[tk] = ss

                if ss == final_timestep_index:
                    # Set skip_compute to False for the final simulation period so
                    # that the relevant calculations will be computed just once.
                    for sk in skip_compute_keys:
                        system._discrete_inputs[sk] = False

                # Run one GS iteration on the plant group
                self._gs_iter()

            rec.abs = 0.0
            rec.rel = 0.0
