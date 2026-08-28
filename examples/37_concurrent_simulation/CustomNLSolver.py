import tqdm
import numpy as np
from openmdao.solvers.nonlinear.nonlinear_runonce import NonlinearRunOnce


# TODO more descriptive class name
class CustomNonLinearRunOnce(NonlinearRunOnce):
    """A simple custom nonlinear solver skeleton."""

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

        # TODO get N_sim and N_step from H2I config rather than a subsystem model
        n_timesteps = self.plant_config["plant"]["simulation"]["n_timesteps"]
        n_steps_per_compute = self.plant_config["plant"]["simulation"]["n_steps_per_compute"]
        # n_steps_per_compute = system.solar.PYSAMSolarPlantPerformanceModel.n_steps_per_compute
        # n_timesteps = system.solar.PYSAMSolarPlantPerformanceModel.n_timesteps

        # Make time stepping loop
        sim_starts = np.arange(0, n_timesteps, n_steps_per_compute)

        final_timestep_index = sim_starts[-1]

        # Set skip_compute to True for relevant subsystems. This will skip
        # unnecessary computation in most of the simulation periods.
        for sk in skip_compute_keys:
            system._discrete_inputs[sk] = True

        for ss in tqdm.tqdm(sim_starts):
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


# May be needed later
# class CustomLinearRunOnce(LinearRunOnce):
#     SOLVER = "LN: CUSTOM"

#     def solve(self, mode, rel_systems=None):
#         self.was_called = True
#         super().solve(mode=mode, rel_systems=rel_systems)
