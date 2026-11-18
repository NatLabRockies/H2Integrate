import warnings
from copy import deepcopy

import numpy as np
import pytest
import openmdao.api as om

import h2integrate.core.h2integrate_model as model_module
from h2integrate.core.h2integrate_model import H2IntegrateModel


class Producer(om.ExplicitComponent):
    # This linear loop has the independent solution production = 2 * bias.
    _time_step_bounds = (1, 3600)
    _control_classifier = "fixed"
    _is_steppable = True

    def initialize(self):
        for name in ("driver_config", "plant_config", "tech_config"):
            self.options.declare(name, default={})

    def setup(self):
        self.add_input("command", val=0.0)
        self.add_input("capacity", val=1.0)
        self.add_output("rated_electricity_production", val=0.0)
        self.add_output("capacity_factor", val=1.0)

    def compute(self, inputs, outputs):
        outputs["rated_electricity_production"] = inputs["command"] * inputs["capacity"]


class Controller(om.ExplicitComponent):
    _time_step_bounds = (1, 3600)
    _control_classifier = "fixed"
    _is_steppable = True

    def initialize(self):
        for name in ("driver_config", "plant_config", "tech_config"):
            self.options.declare(name, default={})

    def setup(self):
        self.add_input("production", val=0.0)
        self.add_input("bias", val=1.0)
        self.add_output("command", val=0.0)

    def compute(self, inputs, outputs):
        outputs["command"] = 0.5 * inputs["production"] + inputs["bias"]


class LocalController(Controller):
    _reads_performance_outputs = True


class SentinelFinance(om.ExplicitComponent):
    def initialize(self):
        for name in (
            "driver_config",
            "plant_config",
            "tech_config",
            "commodity_type",
            "description",
        ):
            self.options.declare(name, default=None, allow_none=True)
        self.productions = []

    def setup(self):
        self.add_input("rated_electricity_production", val=0.0)
        self.add_input("capacity_factor", val=1.0)
        self.add_output("price", val=0.0)
        self.add_output("price_constraint", val=0.0)

    def compute(self, inputs, outputs):
        production = inputs["rated_electricity_production"][0]
        self.productions.append(production)
        # Match the large zero-production sentinel that can dominate the solver norm.
        if production <= 0.0:
            warnings.warn("zero production", RuntimeWarning, stacklevel=2)
            outputs["price"] = 1e12
        else:
            outputs["price"] = 10.0 / production
        outputs["price_constraint"] = outputs["price"]


@pytest.fixture
def coupled_model(monkeypatch):
    # Exercise H2Integrate's real assembly with inexpensive analytical components.
    registry = model_module.supported_models.copy()
    registry.update(
        Producer=Producer,
        Controller=Controller,
        LocalController=LocalController,
        SentinelFinance=SentinelFinance,
    )
    monkeypatch.setattr(model_module, "supported_models", registry)
    monkeypatch.setattr(model_module, "no_cost_models", {"Producer", "Controller"})

    def tech(name):
        return {"performance_model": {"model": name}, "model_inputs": {}}

    config = {
        "name": "coupled_finance",
        "driver_config": {"general": {"create_om_reports": False}},
        "technology_config": {
            "technologies": {"producer": tech("Producer"), "controller": tech("Controller")}
        },
        "plant_config": {
            "plant": {"plant_life": 1, "simulation": {"n_timesteps": 8760, "dt": 3600}},
            "technology_interconnections": [
                ["producer", "controller", ["rated_electricity_production", "production"]],
                ["controller", "producer", "command"],
            ],
            "finance_parameters": {
                "finance_groups": {
                    "commodity": "electricity",
                    "commodity_stream": "producer",
                    "finance_model": "SentinelFinance",
                    "model_inputs": {},
                },
                "cost_adjustment_parameters": {
                    "target_dollar_year": 2022,
                    "cost_year_adjustment_inflation": 0.02,
                },
            },
        },
    }

    def build(edit_config=None):
        test_config = deepcopy(config)
        if edit_config is not None:
            edit_config(test_config)
        h2i = H2IntegrateModel(test_config)
        solver = h2i.plant.nonlinear_solver
        if not isinstance(solver, om.NonlinearRunOnce):
            solver.options["maxiter"] = 100
            solver.options["atol"] = 1e-9
            solver.options["rtol"] = 1e-9
            solver.options["iprint"] = 0
        return h2i

    return build


@pytest.mark.unit
def test_sentinel_false_convergence_baseline():
    # Keeping finance in the iterative group reproduces the original premature stop.
    prob = om.Problem(reports=False)
    plant = prob.model.add_subsystem("plant", om.Group())
    plant.add_subsystem("producer", Producer())
    plant.add_subsystem("controller", Controller())
    finance = plant.add_subsystem("finance", SentinelFinance())
    plant.connect("producer.rated_electricity_production", "controller.production")
    plant.connect("controller.command", "producer.command")
    plant.connect("producer.rated_electricity_production", "finance.rated_electricity_production")
    plant.nonlinear_solver = om.NonlinearBlockGS(maxiter=100, atol=1e-6, rtol=1e-6, iprint=0)
    prob.setup()
    with pytest.warns(RuntimeWarning, match="zero production"):
        prob.run_model()
    assert finance.productions[0] == 0.0
    assert prob.get_val("plant.producer.rated_electricity_production")[0] == pytest.approx(1.5)


@pytest.mark.unit
def test_finance_runs_once_after_convergence_and_refreshes(coupled_model):
    h2i = coupled_model()
    assert type(h2i.prob) is om.Problem
    h2i.setup()
    finance = h2i.model.finance_subgroup_default.electricity_finance_default
    with warnings.catch_warnings():
        warnings.simplefilter("error", RuntimeWarning)
        h2i.prob.run_model()
    assert len(finance.productions) == 1
    assert finance.productions[0] == pytest.approx(2.0, rel=1e-6)
    assert h2i.prob.get_val("finance_subgroup_default.price")[0] == pytest.approx(5.0, rel=1e-6)

    # A valid-invalid-valid sequence must refresh finance on every evaluation.
    h2i.prob.set_val("producer.capacity", 0.0)
    with pytest.warns(RuntimeWarning, match="zero production"):
        h2i.prob.run_model()
    assert finance.productions[-1] == 0.0
    assert h2i.prob.get_val("finance_subgroup_default.price")[0] == 1e12
    h2i.prob.set_val("producer.capacity", 1.0)
    h2i.prob.set_val("controller.bias", 2.0)
    h2i.prob.run_model()
    assert len(finance.productions) == 3
    assert finance.productions[-1] == pytest.approx(4.0, rel=1e-6)
    assert h2i.prob.get_val("finance_subgroup_default.price")[0] == pytest.approx(2.5, rel=1e-6)


@pytest.mark.unit
def test_finance_is_not_called_when_operations_raise(coupled_model):
    h2i = coupled_model()
    h2i.setup()
    h2i.prob.run_model()
    finance = h2i.model.finance_subgroup_default.electricity_finance_default
    assert len(finance.productions) == 1
    # Force a failed solve after a valid one to ensure stale finance is not recomputed.
    h2i.prob.set_val("controller.bias", 2.0)
    h2i.plant.nonlinear_solver.options["maxiter"] = 1
    with pytest.raises(om.AnalysisError, match="failed to converge"):
        h2i.prob.run_model()
    assert len(finance.productions) == 1
    h2i.plant.nonlinear_solver.options["maxiter"] = 100
    h2i.prob.run_model()
    assert len(finance.productions) == 2
    assert h2i.prob.get_val("finance_subgroup_default.price")[0] == pytest.approx(2.5, rel=1e-6)


@pytest.mark.unit
def test_finite_difference_reevaluates_finance(coupled_model):
    h2i = coupled_model()
    h2i.model.add_design_var("controller.bias")
    h2i.model.add_objective("finance_subgroup_default.price")
    h2i.model.approx_totals(method="fd", step=1e-4)
    h2i.setup()
    h2i.prob.run_model()
    finance = h2i.model.finance_subgroup_default.electricity_finance_default
    count = len(finance.productions)
    # At bias=1, price=5/bias and the independently known derivative is -5.
    totals = h2i.prob.compute_totals(of=["finance_subgroup_default.price"], wrt=["controller.bias"])
    assert len(finance.productions) > count
    np.testing.assert_allclose(
        totals["finance_subgroup_default.price", "controller.bias"], [[-5.0]], rtol=1e-3
    )


@pytest.mark.unit
def test_optimizer_reevaluates_and_records_finance(coupled_model, tmp_path):
    h2i = coupled_model()
    h2i.model.add_design_var("controller.bias", lower=0.5, upper=2.0)
    h2i.model.add_objective("finance_subgroup_default.price")
    # Separate responses verify that both objective and constraint paths remain usable.
    h2i.model.add_constraint("finance_subgroup_default.price_constraint", upper=9.0)
    h2i.model.approx_totals(method="fd", step=1e-4)
    h2i.prob.driver = om.ScipyOptimizeDriver(optimizer="SLSQP", disp=False)
    record_path = tmp_path / "finance_cases.sql"
    h2i.prob.driver.add_recorder(om.SqliteRecorder(str(record_path)))
    h2i.setup()
    h2i.prob.run_driver()
    finance = h2i.model.finance_subgroup_default.electricity_finance_default
    assert len(finance.productions) > 1
    assert h2i.prob.get_val("controller.bias")[0] == pytest.approx(2.0, abs=1e-5)
    assert h2i.prob.get_val("finance_subgroup_default.price")[0] == pytest.approx(2.5, rel=1e-6)
    count = len(finance.productions)
    h2i.prob.set_val("controller.bias", 1.0)
    h2i.prob.run_driver()
    assert len(finance.productions) > count
    assert h2i.prob.get_val("finance_subgroup_default.price")[0] == pytest.approx(2.5, rel=1e-6)
    h2i.prob.cleanup()
    cases = om.CaseReader(str(record_path)).get_cases("driver")
    assert cases[-1].get_val("finance_subgroup_default.price")[0] == pytest.approx(2.5, rel=1e-6)


@pytest.mark.unit
def test_finance_inside_plant_can_feed_technology(coupled_model):
    def make_acyclic(config):
        config["plant_config"]["technology_interconnections"].pop()

    h2i = coupled_model(make_acyclic)
    assert not h2i._separate_finance
    h2i.model.connect("finance_subgroup_default.price", "controller.bias")
    h2i.setup()
    h2i.prob.set_val("producer.command", 2.0)
    h2i.prob.run_model()
    assert h2i.prob.get_val("controller.bias")[0] == pytest.approx(5.0)


@pytest.mark.unit
def test_coupled_finance_cannot_disable_nonconvergence_errors(coupled_model):
    h2i = coupled_model()
    h2i.slc = True
    h2i.plant_config["system_level_control"] = {
        "solver_options": {"solver_option_kwargs": {"err_on_non_converge": False}}
    }
    with pytest.raises(ValueError, match="err_on_non_converge cannot be disabled"):
        h2i.set_plant_solver()


@pytest.mark.unit
def test_local_finance_in_coupled_plant_is_rejected(coupled_model):
    def add_local_finance(config):
        config["technology_config"]["technologies"]["producer"]["finance_model"] = {
            "model": "SentinelFinance"
        }

    with pytest.raises(
        NotImplementedError,
        match="Technology-specific finance model 'SentinelFinance' for technology 'producer'",
    ):
        coupled_model(add_local_finance).setup()


@pytest.mark.unit
def test_technology_self_connection_is_rejected(coupled_model):
    def add_self_connection(config):
        config["plant_config"]["technology_interconnections"].append(
            ["producer", "producer", "command"]
        )

    with pytest.raises(NotImplementedError, match="Technology self-connections are not supported"):
        coupled_model(add_self_connection)


@pytest.mark.unit
def test_local_finance_in_iterative_technology_is_rejected(coupled_model):
    def add_local_finance(config):
        # The local solver is iterative even though the plant graph is acyclic.
        config["plant_config"]["technology_interconnections"].pop()
        producer = config["technology_config"]["technologies"]["producer"]
        producer["control_strategy"] = {"model": "LocalController"}
        producer["finance_model"] = {"model": "SentinelFinance"}

    with pytest.raises(
        NotImplementedError,
        match=r"Technology-specific finance model for 'producer'.*iterative technology group",
    ):
        coupled_model(add_local_finance).setup()


@pytest.mark.unit
def test_local_finance_remains_supported_in_acyclic_plant(coupled_model):
    def add_local_finance(config):
        config["plant_config"]["technology_interconnections"].pop()
        config["plant_config"].pop("finance_parameters")
        config["technology_config"]["technologies"]["producer"]["finance_model"] = {
            "model": "SentinelFinance"
        }

    h2i = coupled_model(add_local_finance)
    h2i.setup()
    h2i.prob.set_val("producer.command", 2.0)
    h2i.prob.run_model()
    assert h2i.prob.get_val("producer.price")[0] == pytest.approx(5.0)


@pytest.mark.unit
def test_multiple_finance_subgroups_run_after_operations(coupled_model):
    def add_subgroups(config):
        # Each subgroup must see the same converged production.
        config["plant_config"]["finance_parameters"]["finance_subgroups"] = {
            name: {
                "commodity": "electricity",
                "commodity_stream": "producer",
                "technologies": ["producer", "controller"],
                "finance_groups": ["default"],
            }
            for name in ("first", "second")
        }

    h2i = coupled_model(add_subgroups)
    h2i.setup()
    h2i.prob.run_model()
    for name in ("first", "second"):
        subgroup = getattr(h2i.model, f"finance_subgroup_{name}")
        assert subgroup.electricity_finance_default.productions == pytest.approx([2.0], rel=1e-6)
        assert h2i.prob.get_val(f"finance_subgroup_{name}.price")[0] == pytest.approx(5.0, rel=1e-6)


@pytest.mark.unit
def test_coupled_plant_without_finance(coupled_model):
    def remove_finance(config):
        config["plant_config"].pop("finance_parameters")

    h2i = coupled_model(remove_finance)
    h2i.setup()
    h2i.prob.run_model()
    assert h2i.prob.get_val("producer.rated_electricity_production")[0] == pytest.approx(
        2.0, rel=1e-6
    )
