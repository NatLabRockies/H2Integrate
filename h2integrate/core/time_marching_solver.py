import numpy as np
from openmdao.core.analysis_error import AnalysisError
from openmdao.recorders.recording_iteration_stack import Recording
from openmdao.solvers.nonlinear.nonlinear_block_gs import NonlinearBlockGS


class TimeMarchingPlantSolver(NonlinearBlockGS):
    """
    Custom nonlinear solver to manage running the plant group in a loop.

    """

    def __init__(self, plant_config: dict, **solver_options):
        super().__init__(**({"iprint": 0, "err_on_non_converge": True} | solver_options))
        if not self.options["err_on_non_converge"]:
            raise ValueError("Time marching requires err_on_non_converge=True.")
        if self.options["maxiter"] < 1:
            raise ValueError("Time marching requires at least one solver iteration per window.")
        self.plant_config = plant_config

    def solve(self):
        # Should only be used when system is the plant group
        system = self._system()

        # Find subsystems that take timestep_index as an input
        # Should only be performance models
        timestep_keys = [k for k in system._inputs.keys() if k.endswith("timestep_index")]

        n_timesteps = self.plant_config["plant"]["simulation"]["n_timesteps"]
        n_timesteps_window = self.plant_config["plant"]["simulation"]["n_timesteps_window"]

        # Make time stepping loop
        sim_starts = np.arange(0, n_timesteps, n_timesteps_window)

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

        try:
            with Recording(type(self).__name__, self._iter_count, self):
                for ss in sim_starts:
                    # Update timestep_index in all subsystems
                    for tk in timestep_keys:
                        system._inputs[tk] = ss

                    if ss == final_timestep_index:
                        # Allow skippable subsystems to compute once, on the final
                        # simulation period.
                        for s in skippable_subsystems:
                            s.options["skip_compute"] = False

                    try:
                        super().solve()
                    except AnalysisError as err:
                        raise AnalysisError(
                            f"Time-marching window starting at timestep {ss} failed: {err}"
                        ) from err

        finally:
            # A failed step must not leave cost and finance models skipped on the next run.
            for s in skippable_subsystems:
                s.options["skip_compute"] = False
