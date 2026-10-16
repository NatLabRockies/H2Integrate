"""Topology-aware dispatch tests for heterogeneous-commodity system-level control.

Each test builds a small plant, sets round numbers on the controller inputs, and checks the
set points against a hand calculation.
"""

import warnings

import numpy as np
import pytest
import networkx as nx
import openmdao.api as om
from test_slc_topology import HETEROGENEOUS_EXAMPLE, HETEROGENEOUS_EXAMPLE_CLASSIFIERS
from test_slc_controllers import (
    _build_plant_config,
    _build_slc_topology,
    _build_hetero_problem,
    _build_tech_control_classifiers,
)

from h2integrate.core.connection_utils import create_technology_graph
from h2integrate.control.control_strategies.system_level.demand_following_control import (
    DemandFollowingControl,
)
from h2integrate.control.control_strategies.system_level.cost_minimization_control import (
    CostMinimizationControl,
)
from h2integrate.control.control_strategies.system_level.profit_maximization_control import (
    ProfitMaximizationControl,
)


# Spec 05 Appendix A: wind feeds the electrolyzer, a grid feeds only the Haber-Bosch loop.
GRID_TO_HABER_BOSCH = [
    ["wind", "electrolyzer", "electricity", "cable"],
    ["electrolyzer", "haber_bosch", "hydrogen", "pipe"],
    ["grid", "haber_bosch", "electricity", "cable"],
    ["n2_feedstock", "haber_bosch", "nitrogen", "pipe"],
    ["haber_bosch", "ammonia_demand", "ammonia", "pipe"],
]


def _grid_to_haber_bosch_problem(
    controller=DemandFollowingControl, wind_classifier="flexible", connections=None
):
    """Build the Appendix A problem with its measured and rated values applied."""
    if connections is None:
        connections = GRID_TO_HABER_BOSCH
    plant_config = _build_plant_config(connections)
    classifiers = _build_tech_control_classifiers(
        dispatchable=["grid", "electrolyzer", "haber_bosch"], feedstock=["n2_feedstock"]
    )
    classifiers["wind"] = wind_classifier
    slc_topology = _build_slc_topology(
        create_technology_graph(connections),
        classifiers,
        demand_tech="ammonia_demand",
        demand_commodity="ammonia",
        demand_commodity_rate_units="kg/h",
    )
    prob = _build_hetero_problem(
        controller,
        plant_config,
        slc_topology,
        {},
        demand=100.0,
        upstream_out={("wind", "electricity"): 1200.0, ("electrolyzer", "hydrogen"): 18.0},
        commodity_units={"electricity": "kW", "hydrogen": "kg/h", "nitrogen": "kg/h"},
    )
    prob.set_val("slc.wind_rated_electricity_production", 1500.0)
    prob.set_val("slc.grid_rated_electricity_production", 500.0)
    prob.set_val("slc.electrolyzer_rated_hydrogen_production", 40.0)
    prob.set_val("slc.haber_bosch_rated_ammonia_production", 1000.0)
    # Measured: 0.18 kg H2 and 0.5 kWh per kg NH3, and 55 kWh per kg H2.
    prob.set_val("slc.haber_bosch_ammonia_out", 100.0)
    prob.set_val("slc.haber_bosch_hydrogen_consumed", 18.0)
    prob.set_val("slc.haber_bosch_electricity_consumed", 50.0)
    prob.set_val("slc.electrolyzer_electricity_consumed", 990.0)
    return prob


def _set_point_outputs(problem):
    """Return every set-point output on the controller, keyed by relative name."""
    names = sorted(name for name in problem.model.slc._var_rel2meta if name.endswith("_set_point"))
    return {name: problem.get_val(f"slc.{name}").copy() for name in names}


def _heterogeneous_example_problem(connections):
    """Build the full shared-splitter example topology with hand-set profiles."""
    plant_config = _build_plant_config(connections)
    classifiers = HETEROGENEOUS_EXAMPLE_CLASSIFIERS.copy()
    topology = _build_slc_topology(
        create_technology_graph(connections),
        classifiers,
        demand_tech="ammonia_load_demand",
        demand_commodity="ammonia",
        demand_commodity_rate_units="kg/h",
    )
    problem = _build_hetero_problem(
        DemandFollowingControl,
        plant_config,
        topology,
        {},
        demand=100.0,
        upstream_out={
            ("wind", "electricity"): 1200.0,
            ("solar", "electricity"): 300.0,
            ("battery", "electricity"): 0.0,
            ("electrolyzer", "hydrogen"): 18.0,
            ("haber_bosch", "ammonia"): 100.0,
        },
        commodity_units={"electricity": "kW", "hydrogen": "kg/h", "nitrogen": "kg/h"},
    )
    for tech_name, commodity, capacity in (
        ("wind", "electricity", 1500.0),
        ("solar", "electricity", 500.0),
        ("battery", "electricity", 500.0),
        ("electrolyzer", "hydrogen", 40.0),
        ("haber_bosch", "ammonia", 1000.0),
    ):
        problem.set_val(f"slc.{tech_name}_rated_{commodity}_production", capacity)
    problem.set_val("slc.haber_bosch_ammonia_out", 100.0)
    problem.set_val("slc.haber_bosch_hydrogen_consumed", 18.0)
    problem.set_val("slc.haber_bosch_electricity_consumed", 50.0)
    problem.set_val("slc.electrolyzer_electricity_consumed", 990.0)
    return problem


class DummyElectrolyzer(om.ExplicitComponent):
    electricity_per_hydrogen = 55.0

    def initialize(self):
        self.options.declare("n_timesteps", types=int)

    def setup(self):
        n_timesteps = self.options["n_timesteps"]
        self.add_input("electricity_in", val=np.zeros(n_timesteps), units="kW")
        self.add_input("hydrogen_set_point", val=np.zeros(n_timesteps), units="kg/h")
        self.add_output("hydrogen_out", val=np.zeros(n_timesteps), units="kg/h")
        self.add_output("electricity_consumed", val=np.zeros(n_timesteps), units="kW")

    def compute(self, inputs, outputs):
        outputs["hydrogen_out"] = np.minimum(
            inputs["hydrogen_set_point"], inputs["electricity_in"] / self.electricity_per_hydrogen
        )
        outputs["electricity_consumed"] = self.electricity_per_hydrogen * outputs["hydrogen_out"]


class DummyHaberBosch(om.ExplicitComponent):
    hydrogen_per_ammonia = 0.18
    electricity_per_ammonia = 0.5

    def initialize(self):
        self.options.declare("n_timesteps", types=int)

    def setup(self):
        n_timesteps = self.options["n_timesteps"]
        self.add_input("hydrogen_in", val=np.zeros(n_timesteps), units="kg/h")
        self.add_input("electricity_in", val=np.zeros(n_timesteps), units="kW")
        self.add_input("ammonia_set_point", val=np.zeros(n_timesteps), units="kg/h")
        self.add_output("ammonia_out", val=np.zeros(n_timesteps), units="kg/h")
        self.add_output("hydrogen_consumed", val=np.zeros(n_timesteps), units="kg/h")
        self.add_output("electricity_consumed", val=np.zeros(n_timesteps), units="kW")

    def compute(self, inputs, outputs):
        outputs["ammonia_out"] = np.minimum.reduce(
            (
                inputs["ammonia_set_point"],
                inputs["hydrogen_in"] / self.hydrogen_per_ammonia,
                inputs["electricity_in"] / self.electricity_per_ammonia,
            )
        )
        outputs["hydrogen_consumed"] = self.hydrogen_per_ammonia * outputs["ammonia_out"]
        outputs["electricity_consumed"] = self.electricity_per_ammonia * outputs["ammonia_out"]


class DummyGrid(om.ExplicitComponent):
    def initialize(self):
        self.options.declare("n_timesteps", types=int)

    def setup(self):
        n_timesteps = self.options["n_timesteps"]
        self.add_input("electricity_set_point", val=np.zeros(n_timesteps), units="kW")
        self.add_output("electricity_out", val=np.zeros(n_timesteps), units="kW")

    def compute(self, inputs, outputs):
        outputs["electricity_out"] = inputs["electricity_set_point"]


def _build_seed_independence_problem(rated_capacities, n_timesteps=8):
    connections = [
        ["wind", "electrolyzer", "electricity", "cable"],
        ["electrolyzer", "haber_bosch", "hydrogen", "pipe"],
        ["grid", "haber_bosch", "electricity", "cable"],
        ["haber_bosch", "ammonia_demand", "ammonia", "pipe"],
    ]
    plant_config = _build_plant_config(connections, n_timesteps=n_timesteps)
    classifiers = _build_tech_control_classifiers(
        flexible=["wind"], dispatchable=["grid", "electrolyzer", "haber_bosch"]
    )
    topology = _build_slc_topology(
        create_technology_graph(connections),
        classifiers,
        demand_tech="ammonia_demand",
        demand_commodity="ammonia",
        demand_commodity_rate_units="kg/h",
    )
    topology["demand_profile"] = np.full(n_timesteps, 100.0)

    problem = om.Problem()
    problem.model.nonlinear_solver = om.NonlinearBlockGS(
        maxiter=100, atol=1e-12, rtol=1e-12, use_aitken=True, iprint=0, err_on_non_converge=True
    )
    wind = om.IndepVarComp()
    wind.add_output("electricity_out", val=np.full(n_timesteps, 1200.0), units="kW")
    problem.model.add_subsystem("wind", wind)
    problem.model.add_subsystem(
        "slc",
        DemandFollowingControl(
            driver_config={}, plant_config=plant_config, tech_config={}, slc_topology=topology
        ),
    )
    problem.model.add_subsystem("grid", DummyGrid(n_timesteps=n_timesteps))
    problem.model.add_subsystem("electrolyzer", DummyElectrolyzer(n_timesteps=n_timesteps))
    problem.model.add_subsystem("haber_bosch", DummyHaberBosch(n_timesteps=n_timesteps))

    problem.model.connect("wind.electricity_out", "slc.wind_electricity_out")
    problem.model.connect("wind.electricity_out", "electrolyzer.electricity_in")
    problem.model.connect("slc.grid_electricity_set_point", "grid.electricity_set_point")
    problem.model.connect("grid.electricity_out", "slc.grid_electricity_out")
    problem.model.connect("grid.electricity_out", "haber_bosch.electricity_in")
    problem.model.connect("slc.electrolyzer_hydrogen_set_point", "electrolyzer.hydrogen_set_point")
    problem.model.connect("electrolyzer.hydrogen_out", "slc.electrolyzer_hydrogen_out")
    problem.model.connect("electrolyzer.hydrogen_out", "haber_bosch.hydrogen_in")
    problem.model.connect("slc.haber_bosch_ammonia_set_point", "haber_bosch.ammonia_set_point")
    problem.model.connect("haber_bosch.ammonia_out", "slc.haber_bosch_ammonia_out")
    problem.model.connect("haber_bosch.hydrogen_consumed", "slc.haber_bosch_hydrogen_consumed")
    problem.model.connect(
        "haber_bosch.electricity_consumed", "slc.haber_bosch_electricity_consumed"
    )
    problem.model.connect(
        "electrolyzer.electricity_consumed", "slc.electrolyzer_electricity_consumed"
    )

    problem.setup()
    problem.set_val("slc.ammonia_demand", np.full(n_timesteps, 100.0))
    for tech_name, commodity, capacity in zip(
        ("wind", "grid", "electrolyzer", "haber_bosch"),
        ("electricity", "electricity", "hydrogen", "ammonia"),
        rated_capacities,
        strict=True,
    ):
        problem.set_val(f"slc.{tech_name}_rated_{commodity}_production", capacity)
    return problem


@pytest.mark.unit
def test_grid_to_haber_bosch_does_not_pool_electricity(subtests):
    """Wind surplus at the electrolyzer cannot cover the grid-only Haber-Bosch electricity."""
    prob = _grid_to_haber_bosch_problem()
    prob.run_model()

    with subtests.test("ammonia demand is committed to Haber-Bosch"):
        np.testing.assert_allclose(prob.get_val("slc.haber_bosch_ammonia_set_point"), 100.0)

    # Haber-Bosch draws 100 kg/h * 0.5 kWh/kg = 50 kW, and only the grid can supply it.
    with subtests.test("grid covers the Haber-Bosch electricity"):
        np.testing.assert_allclose(prob.get_val("slc.grid_electricity_set_point"), 50.0)

    # Haber-Bosch needs 100 kg/h * 0.18 = 18 kg/h of hydrogen.
    with subtests.test("electrolyzer covers the Haber-Bosch hydrogen"):
        np.testing.assert_allclose(prob.get_val("slc.electrolyzer_hydrogen_set_point"), 18.0)

    with subtests.test("wind runs at its rated production"):
        np.testing.assert_allclose(prob.get_val("slc.wind_electricity_set_point"), 1500.0)


@pytest.mark.unit
def test_appendix_a_dispatch_trace(subtests):
    problem = _grid_to_haber_bosch_problem()
    problem.run_model()
    trace = problem.model.slc.dispatch_trace
    dispatch_order = (
        "ammonia:ammonia_demand",
        "electricity:haber_bosch",
        "hydrogen:haber_bosch",
        "electricity:electrolyzer",
    )

    with subtests.test("bus demands and unmet residuals"):
        assert trace["dispatch_order"] == dispatch_order
        assert set(trace["bus_demand"]) == set(dispatch_order)
        assert set(trace["bus_residual"]) == set(dispatch_order)
        for bus_name, demand in zip(dispatch_order, (100.0, 50.0, 18.0, 990.0), strict=True):
            np.testing.assert_array_equal(trace["bus_demand"][bus_name], np.full(4, demand))
            np.testing.assert_array_equal(trace["bus_residual"][bus_name], np.zeros(4))

    with subtests.test("measured conversion ratios and source labels"):
        expected_ratios = {
            ("electricity", "haber_bosch", "ammonia"): 0.5,
            ("hydrogen", "haber_bosch", "ammonia"): 0.18,
            ("electricity", "electrolyzer", "hydrogen"): 55.0,
        }
        assert set(trace["ratios"]) == set(expected_ratios)
        for key, expected in expected_ratios.items():
            np.testing.assert_array_equal(trace["ratios"][key]["value"], np.full(4, expected))
            np.testing.assert_array_equal(trace["ratios"][key]["source"], np.full(4, "measured"))

    with subtests.test("converter contributions by input bus"):
        expected_contributions = {
            "electricity:haber_bosch": {"haber_bosch": 50.0},
            "hydrogen:haber_bosch": {"haber_bosch": 18.0},
            "electricity:electrolyzer": {"electrolyzer": 990.0},
        }
        assert set(trace["contributions"]) == set(expected_contributions)
        for bus_name, tech_contributions in expected_contributions.items():
            assert set(trace["contributions"][bus_name]) == set(tech_contributions)
            for tech_name, expected in tech_contributions.items():
                np.testing.assert_array_equal(
                    trace["contributions"][bus_name][tech_name], np.full(4, expected)
                )


@pytest.mark.unit
def test_appendix_a_set_points_ignore_connection_order(subtests):
    baseline_problem = _grid_to_haber_bosch_problem()
    baseline_problem.run_model()
    expected = _set_point_outputs(baseline_problem)

    connection_orders = [list(reversed(GRID_TO_HABER_BOSCH))]
    for seed in range(10):
        order = np.random.default_rng(seed).permutation(len(GRID_TO_HABER_BOSCH))
        connection_orders.append([GRID_TO_HABER_BOSCH[index] for index in order])

    for index, connections in enumerate(connection_orders):
        problem = _grid_to_haber_bosch_problem(connections=connections)
        problem.run_model()
        actual = _set_point_outputs(problem)

        with subtests.test(f"connection order {index}"):
            assert actual.keys() == expected.keys()
            for name in expected:
                np.testing.assert_allclose(actual[name], expected[name], rtol=1e-12, atol=1e-12)


@pytest.mark.unit
def test_converged_set_points_are_independent_of_capacity_seeds(subtests):
    n_timesteps = 8
    capacity_sets = (
        (1500.0, 500.0, 40.0, 1000.0),
        (1500.0, 900.0, 80.0, 1500.0),
        (1500.0, 1100.0, 120.0, 2000.0),
    )
    expected_set_points = {
        "wind_electricity_set_point": 1500.0,
        "grid_electricity_set_point": 50.0,
        "electrolyzer_hydrogen_set_point": 18.0,
        "haber_bosch_ammonia_set_point": 100.0,
    }
    results = []

    for capacity_set in capacity_sets:
        problem = _build_seed_independence_problem(capacity_set, n_timesteps=n_timesteps)
        problem.run_model()
        results.append(
            {name: problem.get_val(f"slc.{name}").copy() for name in expected_set_points}
        )

    with subtests.test("Appendix A set points converge for each capacity set"):
        for result in results:
            for name, expected in expected_set_points.items():
                np.testing.assert_allclose(
                    result[name], np.full(n_timesteps, expected), rtol=1e-6, atol=1e-8
                )

    with subtests.test("changing capacity seeds does not change converged set points"):
        for result in results[1:]:
            for name in expected_set_points:
                np.testing.assert_allclose(result[name], results[0][name], rtol=1e-6, atol=1e-8)


@pytest.mark.unit
@pytest.mark.parametrize(
    "controller", [DemandFollowingControl, CostMinimizationControl, ProfitMaximizationControl]
)
def test_dispatchable_producers_stay_on_their_own_bus(controller, subtests):
    """A dispatchable wind plant only serves the electrolyzer, and the grid only Haber-Bosch."""
    prob = _grid_to_haber_bosch_problem(controller, wind_classifier="dispatchable")
    prob.run_model()

    # The electrolyzer's 18 kg/h * 55 kWh/kg = 990 kW falls only on wind, and Haber-Bosch's
    # 100 kg/h * 0.5 kWh/kg = 50 kW only on the grid. Pooled, the 1040 kW would split by
    # merit order or evenly across both producers.
    with subtests.test("wind covers the electrolyzer electricity"):
        np.testing.assert_allclose(prob.get_val("slc.wind_electricity_set_point"), 990.0)

    with subtests.test("grid covers the Haber-Bosch electricity"):
        np.testing.assert_allclose(prob.get_val("slc.grid_electricity_set_point"), 50.0)

    with subtests.test("electrolyzer covers the Haber-Bosch hydrogen"):
        np.testing.assert_allclose(prob.get_val("slc.electrolyzer_hydrogen_set_point"), 18.0)


@pytest.mark.unit
def test_fuel_cell_does_not_create_a_commodity_cycle(subtests):
    """Electricity -> hydrogen -> electricity works when the two electricity buses are separate."""
    connections = [
        ["wind", "electrolyzer", "electricity", "cable"],
        ["electrolyzer", "fuel_cell", "hydrogen", "pipe"],
        ["fuel_cell", "demand", "electricity", "cable"],
    ]
    classifiers = _build_tech_control_classifiers(
        dispatchable=["wind", "electrolyzer", "fuel_cell"]
    )
    slc_topology = _build_slc_topology(
        create_technology_graph(connections),
        classifiers,
        demand_commodity="electricity",
        demand_commodity_rate_units="kW",
    )
    prob = _build_hetero_problem(
        DemandFollowingControl,
        _build_plant_config(connections),
        slc_topology,
        {},
        demand=100.0,
        upstream_out={("electrolyzer", "hydrogen"): 2.5},
        commodity_units={"hydrogen": "kg/h"},
    )
    # Measured: the fuel cell turns 2.5 kg/h of hydrogen into 100 kW (0.025 kg/kWh) and the
    # electrolyzer turns 137.5 kW into 2.5 kg/h (55 kWh/kg).
    prob.set_val("slc.fuel_cell_electricity_out", 100.0)
    prob.set_val("slc.fuel_cell_hydrogen_consumed", 2.5)
    prob.set_val("slc.electrolyzer_electricity_consumed", 137.5)
    with warnings.catch_warnings():
        warnings.simplefilter("error")
        prob.run_model()

    with subtests.test("the fuel cell serves the demand on its own electricity bus"):
        np.testing.assert_allclose(prob.get_val("slc.fuel_cell_electricity_set_point"), 100.0)

    with subtests.test("hydrogen demand is 100 kW * 0.025 kg/kWh"):
        np.testing.assert_allclose(prob.get_val("slc.electrolyzer_hydrogen_set_point"), 2.5)

    with subtests.test("wind serves the electrolyzer electricity, not the demand"):
        np.testing.assert_allclose(prob.get_val("slc.wind_electricity_set_point"), 137.5)


def _splitter_problem(splitter_outputs, connections=None):
    """Wind through a splitter to an electrolyzer and a Haber-Bosch loop (Appendix A numbers)."""
    if connections is None:
        connections = [
            ["wind", "electricity_splitter", "electricity", "cable"],
            *[["electricity_splitter", tech, "electricity", "cable"] for tech in splitter_outputs],
            ["electrolyzer", "haber_bosch", "hydrogen", "pipe"],
            ["haber_bosch", "ammonia_demand", "ammonia", "pipe"],
        ]
    classifiers = _build_tech_control_classifiers(
        flexible=["wind"], dispatchable=["electrolyzer", "haber_bosch"]
    )
    classifiers["electricity_splitter"] = "splitter"
    slc_topology = _build_slc_topology(
        create_technology_graph(connections),
        classifiers,
        demand_tech="ammonia_demand",
        demand_commodity="ammonia",
        demand_commodity_rate_units="kg/h",
    )
    prob = _build_hetero_problem(
        DemandFollowingControl,
        _build_plant_config(connections),
        slc_topology,
        {},
        demand=100.0,
        upstream_out={("wind", "electricity"): 1200.0, ("electrolyzer", "hydrogen"): 18.0},
        commodity_units={"electricity": "kW", "hydrogen": "kg/h"},
    )
    prob.set_val("slc.wind_rated_electricity_production", 1500.0)
    prob.set_val("slc.haber_bosch_ammonia_out", 100.0)
    prob.set_val("slc.haber_bosch_hydrogen_consumed", 18.0)
    prob.set_val("slc.haber_bosch_electricity_consumed", 50.0)
    prob.set_val("slc.electrolyzer_electricity_consumed", 990.0)
    return prob


@pytest.mark.unit
def test_splitter_allocates_to_the_consumer_behind_out1(subtests):
    # Electrolyzer: 18 kg/h * 55 kWh/kg = 990 kW. Haber-Bosch: 100 kg/h * 0.5 kWh/kg = 50 kW.
    with subtests.test("out1 to the electrolyzer"):
        prob = _splitter_problem(["electrolyzer", "haber_bosch"])
        prob.run_model()
        np.testing.assert_allclose(
            prob.get_val("slc.electricity_splitter_electricity_set_point"), 990.0
        )

    with subtests.test("out1 to Haber-Bosch"):
        prob = _splitter_problem(["haber_bosch", "electrolyzer"])
        prob.run_model()
        np.testing.assert_allclose(
            prob.get_val("slc.electricity_splitter_electricity_set_point"), 50.0
        )


@pytest.mark.unit
def test_splitter_set_points_ignore_order_while_out1_is_preserved(subtests):
    splitter_outputs = ["electrolyzer", "haber_bosch"]
    connections = [
        ["wind", "electricity_splitter", "electricity", "cable"],
        ["electricity_splitter", "electrolyzer", "electricity", "cable"],
        ["electricity_splitter", "haber_bosch", "electricity", "cable"],
        ["electrolyzer", "haber_bosch", "hydrogen", "pipe"],
        ["haber_bosch", "ammonia_demand", "ammonia", "pipe"],
    ]
    priority_connections = [edge for edge in connections if edge[0] == "electricity_splitter"]
    other_connections = [edge for edge in connections if edge[0] != "electricity_splitter"]

    baseline_problem = _splitter_problem(splitter_outputs, connections=connections)
    baseline_problem.run_model()
    expected = _set_point_outputs(baseline_problem)

    for seed in range(10):
        order = np.random.default_rng(seed).permutation(len(other_connections))
        shuffled_connections = [other_connections[index] for index in order] + priority_connections
        problem = _splitter_problem(splitter_outputs, connections=shuffled_connections)
        problem.run_model()
        actual = _set_point_outputs(problem)

        with subtests.test(f"non-priority connection shuffle {seed}"):
            assert actual.keys() == expected.keys()
            for name in expected:
                np.testing.assert_allclose(actual[name], expected[name], rtol=1e-12, atol=1e-12)


@pytest.mark.unit
def test_heterogeneous_example_set_points_ignore_connection_order(subtests):
    connections = HETEROGENEOUS_EXAMPLE
    priority_connections = [edge for edge in connections if edge[0] == "electricity_splitter"]
    other_connections = [edge for edge in connections if edge[0] != "electricity_splitter"]

    baseline_problem = _heterogeneous_example_problem(connections)
    baseline_problem.run_model()
    expected = _set_point_outputs(baseline_problem)

    connection_orders = [list(reversed(other_connections)) + priority_connections]
    for seed in range(10):
        order = np.random.default_rng(seed).permutation(len(other_connections))
        connection_orders.append(
            [other_connections[index] for index in order] + priority_connections
        )

    for index, shuffled_connections in enumerate(connection_orders):
        problem = _heterogeneous_example_problem(shuffled_connections)
        problem.run_model()
        actual = _set_point_outputs(problem)

        with subtests.test(f"heterogeneous connection order {index}"):
            assert actual.keys() == expected.keys()
            for name in expected:
                np.testing.assert_allclose(actual[name], expected[name], rtol=1e-12, atol=1e-12)


@pytest.mark.unit
def test_heterogeneous_example_splitter_swap_changes_priority_draw(subtests):
    connections = [edge.copy() for edge in HETEROGENEOUS_EXAMPLE]
    splitter_positions = [
        index for index, edge in enumerate(connections) if edge[0] == "electricity_splitter"
    ]
    assert len(splitter_positions) == 2
    connections[splitter_positions[0]], connections[splitter_positions[1]] = (
        connections[splitter_positions[1]],
        connections[splitter_positions[0]],
    )
    problem = _heterogeneous_example_problem(connections)
    problem.run_model()

    with subtests.test("out1 priority moves from electrolyzer to Haber-Bosch"):
        np.testing.assert_allclose(
            problem.get_val("slc.electricity_splitter_electricity_set_point"), 50.0
        )


@pytest.mark.unit
def test_splitter_allocates_the_demand_to_a_priority_demand_technology():
    connections = [
        ["wind", "electricity_splitter", "electricity", "cable"],
        ["electricity_splitter", "demand", "electricity", "cable"],
        ["electricity_splitter", "other_load", "electricity", "cable"],
    ]
    classifiers = _build_tech_control_classifiers(flexible=["wind"])
    classifiers["electricity_splitter"] = "splitter"
    slc_topology = _build_slc_topology(
        create_technology_graph(connections),
        classifiers,
        demand_commodity="electricity",
        demand_commodity_rate_units="kW",
    )
    prob = _build_hetero_problem(
        DemandFollowingControl,
        _build_plant_config(connections),
        slc_topology,
        {},
        demand=[10.0, 20.0, 30.0, 40.0],
    )
    prob.run_model()

    np.testing.assert_allclose(
        prob.get_val("slc.electricity_splitter_electricity_set_point"), [10.0, 20.0, 30.0, 40.0]
    )


@pytest.mark.unit
def test_compute_builds_no_networkx_graph(monkeypatch):
    prob = _grid_to_haber_bosch_problem()
    prob.final_setup()

    def _raise(*args, **kwargs):
        raise AssertionError("compute must not build a networkx graph")

    monkeypatch.setattr(nx.DiGraph, "__init__", _raise)
    prob.run_model()
