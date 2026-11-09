from copy import deepcopy

import numpy as np
import pytest
import openmdao.api as om

from h2integrate.core.model_baseclass import SkippableComputeMixin
from h2integrate.core.time_marching_solver import TimeMarchingPlantSolver


N_TIMESTEPS = 12
WINDOW = 4


class WindowedProducer(om.ExplicitComponent):
    """Writes each window's start index into its slice of the output."""

    def initialize(self):
        self.options.declare("fail_at", default=None, allow_none=True)
        self.window_starts_dict = {}

    def setup(self):
        self.add_input("timestep_index", val=0)
        self.add_output("production", val=0.0, shape=N_TIMESTEPS)

    def compute(self, inputs, outputs):
        start = int(inputs["timestep_index"][0])
        self.window_starts_dict[start] = self.window_starts_dict.get(start, 0) + 1
        if start == self.options["fail_at"]:
            raise RuntimeError(f"Failed in the window starting at {start}")
        outputs["production"][start : start + WINDOW] = start


class TotalCost(SkippableComputeMixin, om.ExplicitComponent):
    """Sums the full production profile, like a cost model run after the simulation."""

    def initialize(self):
        super().initialize()
        self.n_computes = 0

    def setup(self):
        self.add_input("production", shape=N_TIMESTEPS)
        self.add_output("total", val=0.0)

    def compute(self, inputs, outputs):
        self.n_computes += 1
        outputs["total"] = inputs["production"].sum()


def build_problem(fail_at=None):
    plant_config = {
        "plant": {"simulation": {"n_timesteps": N_TIMESTEPS, "n_timesteps_window": WINDOW}}
    }
    plant = om.Group()
    plant.add_subsystem("perf", WindowedProducer(fail_at=fail_at), promotes=["*"])
    plant.add_subsystem("cost", TotalCost(), promotes=["*"])
    plant.nonlinear_solver = TimeMarchingPlantSolver(plant_config=plant_config)

    prob = om.Problem()
    prob.model.add_subsystem("plant", plant)
    prob.setup()
    return prob


@pytest.mark.unit
def test_time_marching_solver_steps_through_windows(subtests):
    prob = build_problem()
    prob.run_model()
    perf = prob.model.plant.perf
    cost = prob.model.plant.cost
    expected_production = np.repeat([0.0, 4.0, 8.0], WINDOW)

    with subtests.test("Performance model runs once per window, in order"):
        assert list(perf.window_starts_dict.keys()) == [0, 4, 8]
        assert np.all(np.asarray(list(perf.window_starts_dict.values())) >= 1)

    with subtests.test("Each window fills its slice of the output"):
        np.testing.assert_array_equal(prob.get_val("plant.production"), expected_production)

    with subtests.test("Skippable models compute only on the final window"):
        assert cost.n_computes == perf.window_starts_dict[8]
        assert prob.get_val("plant.total") == pytest.approx(expected_production.sum())

    with subtests.test("Skippable models are re-enabled after the run"):
        assert cost.options["skip_compute"] is False

    with subtests.test("A second run repeats the same steps"):
        window_starts_firstrun = deepcopy(perf.window_starts_dict)
        prob.run_model()
        assert np.all(
            np.asarray([v - window_starts_firstrun[k] for k, v in perf.window_starts_dict.items()])
            > 0
        )
        assert cost.n_computes == perf.window_starts_dict[8]


@pytest.mark.unit
def test_time_marching_solver_reenables_skipped_models_after_failure():
    prob = build_problem(fail_at=4)

    with pytest.raises(RuntimeError, match="window starting at 4"):
        prob.run_model()

    assert list(prob.model.plant.perf.window_starts_dict.keys()) == [0, 4]
    assert prob.model.plant.cost.n_computes == 0
    assert prob.model.plant.cost.options["skip_compute"] is False
