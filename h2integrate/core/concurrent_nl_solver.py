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

        n_timesteps = self.plant_config["plant"]["simulation"]["n_timesteps"]
        n_steps_per_compute = self.plant_config["plant"]["simulation"]["n_steps_per_compute"]

        # Make time stepping loop
        sim_starts = np.arange(0, n_timesteps, n_steps_per_compute)

        final_timestep_index = sim_starts[-1]

        # Subsystems whose compute() can be skipped on intermediate timesteps
        # (cost/finance models; see SkippableComputeMixin). Found by option
        # rather than by type to avoid coupling this solver to specific
        # baseclasses.
        skippable_subsystems = [
            s
            for s in system.system_iter(include_self=False, recurse=True)
            if "skip_compute" in getattr(s, "options", {})
        ]

        # Skip those subsystems' calculations in most of the simulation periods.
        for s in skippable_subsystems:
            s.options["skip_compute"] = True

        with Recording("NLRunOnce", 0, self) as rec:
            for ss in sim_starts:
                # Update timestep_index in all subsystems
                for tk in timestep_keys:
                    system._inputs[tk] = ss

                if ss == final_timestep_index:
                    # Allow skippable subsystems to compute once, on the final
                    # simulation period.
                    for s in skippable_subsystems:
                        s.options["skip_compute"] = False

                # Run one GS iteration on the plant group
                self._gs_iter()

            rec.abs = 0.0
            rec.rel = 0.0
