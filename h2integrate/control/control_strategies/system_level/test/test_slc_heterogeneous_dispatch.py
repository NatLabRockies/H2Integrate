"""Topology-aware dispatch tests for heterogeneous-commodity system-level control.

To add a case, append a dictionary to ``DISPATCH_CASES`` with a named topology,
inputs, and set points from a short hand calculation.
"""

import warnings

import numpy as np
import pytest
import networkx as nx
import openmdao.api as om
from test_slc_controllers import (
    _build_plant_config,
    _build_slc_topology,
    _build_hetero_problem,
    _build_tech_control_classifiers,
)

from h2integrate.core.connection_utils import create_technology_graph
from h2integrate.control.control_strategies.passthrough_controller import PassthroughController
from h2integrate.control.control_strategies.system_level.slc_topology import (
    SUPPLIER_CLASSIFIERS,
    build_dispatch_topology,
)
from h2integrate.control.control_strategies.system_level.demand_following_control import (
    DemandFollowingControl,
)
from h2integrate.control.control_strategies.system_level.cost_minimization_control import (
    CostMinimizationControl,
)
from h2integrate.control.control_strategies.system_level.profit_maximization_control import (
    ProfitMaximizationControl,
)


# Appendix A: 0.18 kg H2 and 0.5 kWh per kg NH3 at Haber-Bosch, and 55 kWh per kg H2.
APPENDIX_A_RATED = {
    "wind_rated_electricity_production": 1500.0,
    "grid_rated_electricity_production": 500.0,
    "electrolyzer_rated_hydrogen_production": 40.0,
    "haber_bosch_rated_ammonia_production": 1000.0,
}
APPENDIX_A_MEASURED = {
    "haber_bosch_ammonia_out": 100.0,
    "haber_bosch_hydrogen_consumed": 18.0,
    "haber_bosch_electricity_consumed": 50.0,
    "electrolyzer_electricity_consumed": 990.0,
}
APPENDIX_A_AVAILABLE = {("wind", "electricity"): 1200.0, ("electrolyzer", "hydrogen"): 18.0}

# Small chains used by TestHeterogeneousCommodityControl.
GRID_ELECTROLYZER = [
    ["grid", "electrolyzer", "electricity", "cable"],
    ["electrolyzer", "demand", "hydrogen", "pipe"],
]
GRID_ELECTROLYZER_HABER_BOSCH = [
    ["grid", "electrolyzer", "electricity", "cable"],
    ["electrolyzer", "haber_bosch", "hydrogen", "pipe"],
    ["haber_bosch", "demand", "ammonia", "pipe"],
]


def _chain_problem(
    connections,
    classifiers,
    demand_commodity,
    commodity_units,
    controller=DemandFollowingControl,
    upstream_out=None,
    cost_per_tech=None,
    scale_control_variables=False,
):
    """Build a 4-timestep problem with a demand of 100 kg/h of ``demand_commodity``."""
    slc_topology = _build_slc_topology(
        create_technology_graph(connections),
        classifiers,
        demand_commodity=demand_commodity,
        demand_commodity_rate_units="kg/h",
    )
    plant_config = _build_plant_config(connections, cost_per_tech=cost_per_tech)
    plant_config["system_level_control"].setdefault("solver_options", {})[
        "scale_control_variables"
    ] = scale_control_variables
    return _build_hetero_problem(
        controller,
        plant_config,
        slc_topology,
        {},
        demand=100.0,
        upstream_out=upstream_out,
        commodity_units=commodity_units,
    )


def _grid_to_haber_bosch_problem(
    topology_data,
    controller=DemandFollowingControl,
    wind_classifier=None,
    connections=None,
):
    """Build the Appendix A problem with its measured and rated values applied."""
    if connections is None:
        connections = topology_data["connections"]
    plant_config = _build_plant_config(connections)
    classifiers = topology_data["classifiers"].copy()
    if wind_classifier is not None:
        classifiers["wind"] = wind_classifier
    slc_topology = _build_slc_topology(
        create_technology_graph(connections),
        classifiers,
        demand_tech=topology_data["demand_tech"],
        demand_commodity=topology_data["demand_commodity"],
        demand_commodity_rate_units=topology_data["demand_rate_units"],
    )
    prob = _build_hetero_problem(
        controller,
        plant_config,
        slc_topology,
        {},
        demand=100.0,
        upstream_out=APPENDIX_A_AVAILABLE,
        commodity_units={"electricity": "kW", "hydrogen": "kg/h", "nitrogen": "kg/h"},
    )
    for name, value in (APPENDIX_A_RATED | APPENDIX_A_MEASURED).items():
        prob.set_val(f"slc.{name}", value)
    return prob


def _set_point_outputs(problem):
    """Return every set-point output on the controller, keyed by relative name."""
    names = sorted(name for name in problem.model.slc._var_rel2meta if name.endswith("_set_point"))
    return {name: problem.get_val(f"slc.{name}").copy() for name in names}


def run_slc_once(
    topology: dict,
    controller_cls: type,
    demand: float | np.ndarray,
    rated: dict[str, float | np.ndarray] | None = None,
    measured: dict[str, float | np.ndarray] | None = None,
    available: dict[tuple[str, str], float | np.ndarray] | None = None,
) -> tuple[om.Problem, dict[str, np.ndarray], dict]:
    """Build, configure, and run one controller case from a named topology fixture."""
    plant_config = _build_plant_config(
        topology["connections"], cost_per_tech=topology.get("cost_per_tech")
    )
    slc_topology = _build_slc_topology(
        create_technology_graph(topology["connections"]),
        topology["classifiers"],
        demand_tech=topology["demand_tech"],
        demand_commodity=topology["demand_commodity"],
        demand_commodity_rate_units=topology["demand_rate_units"],
        storage_techs_with_control=topology.get("storage_techs_with_control", []),
    )
    problem = _build_hetero_problem(
        controller_cls,
        plant_config,
        slc_topology,
        topology.get("tech_config", {}),
        demand=demand,
        upstream_out=available,
        commodity_units=topology.get("commodity_units", {}),
    )
    for variable_name, value in (rated or {}).items():
        problem.set_val(f"slc.{variable_name}", value)
    for variable_name, value in (measured or {}).items():
        problem.set_val(f"slc.{variable_name}", value)
    problem.run_model()
    return problem, _set_point_outputs(problem), problem.model.slc.dispatch_trace


def _build_dispatch_topology_from_fixture(topology_data):
    graph = create_technology_graph(topology_data["connections"])
    tech_to_commodity = {
        (source, commodity)
        for source, _target, commodities in graph.edges(data="commodity")
        if topology_data["classifiers"].get(source) in SUPPLIER_CLASSIFIERS
        for commodity in commodities
    }
    return build_dispatch_topology(
        graph,
        topology_data["classifiers"],
        tech_to_commodity,
        topology_data["demand_tech"],
        topology_data["demand_commodity"],
    )


DISPATCH_CASES = [
    # Measured ratios give Haber-Bosch 100 x 0.5 = 50 kW (grid only), 100 x 0.18 = 18 kg/h H2,
    # and 18 x 55 = 990 kW (wind only). Pooling electricity would leave the grid at 0 kW (P2).
    {
        "topology": "grid_to_haber_bosch",
        "demand": 100.0,
        "rated": APPENDIX_A_RATED,
        "measured": APPENDIX_A_MEASURED,
        "available": APPENDIX_A_AVAILABLE,
        "expected_set_points": {
            "haber_bosch_ammonia_set_point": 100.0,
            "grid_electricity_set_point": 50.0,
            "electrolyzer_hydrogen_set_point": 18.0,
            "wind_electricity_set_point": 1500.0,
        },
    },
    # Capacity seeds 500/1000, 40/1000, and 1500/40 give 50 kW, 4 kg/h, and 150 kW.
    {
        "topology": "grid_to_haber_bosch",
        "demand": 100.0,
        "rated": APPENDIX_A_RATED,
        "measured": {},
        "available": {("wind", "electricity"): 1200.0},
        "expected_set_points": {
            "haber_bosch_ammonia_set_point": 100.0,
            "grid_electricity_set_point": 50.0,
            "electrolyzer_hydrogen_set_point": 4.0,
            "wind_electricity_set_point": 1500.0,
        },
    },
]


@pytest.mark.unit
@pytest.mark.parametrize("case", DISPATCH_CASES, ids=["measured-ratios", "capacity-seeds"])
def test_named_dispatch_cases_are_hand_calculable(case, slc_topologies):
    _problem, set_points, _trace = run_slc_once(
        slc_topologies[case["topology"]],
        DemandFollowingControl,
        case["demand"],
        rated=case["rated"],
        measured=case["measured"],
        available=case["available"],
    )

    for name, expected in case["expected_set_points"].items():
        np.testing.assert_allclose(set_points[name], expected)


@pytest.mark.unit
def test_setup_warns_for_controller_output_outside_dispatch_topology():
    orphan_topology = {
        "connections": [
            ["grid", "demand", "electricity", "cable"],
            ["orphan_tech", "unused_load", "hydrogen", "pipe"],
        ],
        "classifiers": {"grid": "dispatchable", "orphan_tech": "dispatchable"},
        "demand_tech": "demand",
        "demand_commodity": "electricity",
        "demand_rate_units": "kW",
        "commodity_units": {"hydrogen": "kg/h"},
    }

    with pytest.warns(UserWarning, match=r"orphan_tech \(hydrogen\)") as record:
        run_slc_once(orphan_topology, DemandFollowingControl, demand=100.0)

    assert len(record) == 1


@pytest.mark.unit
def test_fake_complex_system_816_converter_set_and_suppliers(slc_topologies, subtests):
    topology = _build_dispatch_topology_from_fixture(slc_topologies["fake_complex_system_816"])
    converters = {(link.in_commodity, link.tech, link.out_commodity) for link in topology.links}
    expected_converters = {
        ("salt_water", "desalination", "fresh_water"),
        ("electricity", "electrolyzer", "hydrogen"),
        ("electricity", "electrolyzer", "oxygen"),
        ("electricity", "electrolyzer", "heat"),
        ("fresh_water", "electrolyzer", "hydrogen"),
        ("fresh_water", "electrolyzer", "oxygen"),
        ("fresh_water", "electrolyzer", "heat"),
        ("hydrogen", "haber_bosch", "ammonia"),
        ("heat", "haber_bosch", "ammonia"),
        ("oxygen", "haber_bosch", "ammonia"),
        ("electricity", "haber_bosch", "ammonia"),
        ("nitrogen", "haber_bosch", "ammonia"),
    }

    with subtests.test("the fake system has twelve distinct conversions"):
        assert len(converters) == 12
        assert converters == expected_converters

    with subtests.test("converter suppliers exclude combiners"):
        suppliers = {(link.in_commodity, link.tech): link.suppliers for link in topology.links}
        expected_suppliers = {
            ("salt_water", "desalination"): ("ocean",),
            ("hydrogen", "haber_bosch"): ("electrolyzer", "h2_storage"),
            ("heat", "haber_bosch"): ("electrolyzer",),
            ("oxygen", "haber_bosch"): ("electrolyzer",),
            ("nitrogen", "haber_bosch"): ("n2_feedstock",),
            ("electricity", "haber_bosch"): ("grid",),
            ("fresh_water", "electrolyzer"): ("desalination",),
            ("electricity", "electrolyzer"): ("battery", "solar", "wind"),
        }
        for key, expected in expected_suppliers.items():
            assert suppliers[key] == expected


@pytest.mark.unit
@pytest.mark.parametrize("topology_name", ["nh3_with_storage_816", "complex_multi_commodity_816"])
def test_816_example_topology_fixtures_build(topology_name, slc_topologies):
    topology = _build_dispatch_topology_from_fixture(slc_topologies[topology_name])

    assert topology.demand_bus is not None
    assert topology.dispatch_order
    assert topology.dispatch_order[0] == topology.demand_bus


def _heterogeneous_example_problem(topology_data, connections=None):
    """Build the full shared-splitter example topology with hand-set profiles."""
    if connections is None:
        connections = topology_data["connections"]
    plant_config = _build_plant_config(connections)
    classifiers = topology_data["classifiers"].copy()
    topology = _build_slc_topology(
        create_technology_graph(connections),
        classifiers,
        demand_tech=topology_data["demand_tech"],
        demand_commodity=topology_data["demand_commodity"],
        demand_commodity_rate_units=topology_data["demand_rate_units"],
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
    for name, value in APPENDIX_A_MEASURED.items():
        problem.set_val(f"slc.{name}", value)
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


def _build_seed_independence_problem(rated_capacities, topology_data, n_timesteps=8):
    connections = topology_data["connections"]
    plant_config = _build_plant_config(connections, n_timesteps=n_timesteps)
    classifiers = topology_data["classifiers"].copy()
    topology = _build_slc_topology(
        create_technology_graph(connections),
        classifiers,
        demand_tech=topology_data["demand_tech"],
        demand_commodity=topology_data["demand_commodity"],
        demand_commodity_rate_units=topology_data["demand_rate_units"],
    )
    topology["demand_profile"] = np.full(n_timesteps, 100.0)

    problem = om.Problem()
    problem.model.nonlinear_solver = om.NonlinearBlockGS(
        maxiter=100, atol=1e-12, rtol=1e-12, use_aitken=True, iprint=0, err_on_non_converge=True
    )
    wind = om.IndepVarComp()
    wind.add_output("electricity_out", val=np.full(n_timesteps, 1200.0), units="kW")
    problem.model.add_subsystem("wind", wind)
    nitrogen = om.IndepVarComp()
    nitrogen.add_output("n2_feedstock_nitrogen_out", val=np.full(n_timesteps, 1e9), units="kg/h")
    problem.model.add_subsystem("nitrogen", nitrogen)
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
    problem.model.connect("nitrogen.n2_feedstock_nitrogen_out", "slc.n2_feedstock_nitrogen_out")
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
def test_appendix_a_dispatch_trace(slc_topologies, subtests):
    problem = _grid_to_haber_bosch_problem(slc_topologies["grid_to_haber_bosch"])
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

    with subtests.test("plant-wide electricity and hydrogen per unit of ammonia"):
        # Electricity: (50 + 990) / 100 = 10.4 kW per kg/h. Hydrogen: 18 / 100 = 0.18.
        assert set(trace["demand_ratios"]) == {"electricity", "hydrogen"}
        np.testing.assert_allclose(trace["demand_ratios"]["electricity"], np.full(4, 10.4))
        np.testing.assert_allclose(trace["demand_ratios"]["hydrogen"], np.full(4, 0.18))


@pytest.mark.unit
def test_appendix_a_set_points_ignore_connection_order(slc_topologies, subtests):
    appendix = slc_topologies["grid_to_haber_bosch"]
    connections = appendix["connections"]
    baseline_problem = _grid_to_haber_bosch_problem(appendix)
    baseline_problem.run_model()
    expected = _set_point_outputs(baseline_problem)

    connection_orders = [list(reversed(connections))]
    for seed in range(10):
        order = np.random.default_rng(seed).permutation(len(connections))
        connection_orders.append([connections[index] for index in order])

    for index, connections in enumerate(connection_orders):
        problem = _grid_to_haber_bosch_problem(appendix, connections=connections)
        problem.run_model()
        actual = _set_point_outputs(problem)

        with subtests.test(f"connection order {index}"):
            assert actual.keys() == expected.keys()
            for name in expected:
                np.testing.assert_allclose(actual[name], expected[name], rtol=1e-12, atol=1e-12)


@pytest.mark.unit
def test_converged_set_points_are_independent_of_capacity_seeds(slc_topologies, subtests):
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
        problem = _build_seed_independence_problem(
            capacity_set, slc_topologies["grid_to_haber_bosch"], n_timesteps=n_timesteps
        )
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
def test_dispatchable_producers_stay_on_their_own_bus(controller, slc_topologies, subtests):
    """A dispatchable wind plant only serves the electrolyzer, and the grid only Haber-Bosch."""
    prob = _grid_to_haber_bosch_problem(
        slc_topologies["grid_to_haber_bosch"], controller, wind_classifier="dispatchable"
    )
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
        upstream_out=APPENDIX_A_AVAILABLE,
        commodity_units={"electricity": "kW", "hydrogen": "kg/h"},
    )
    prob.set_val("slc.wind_rated_electricity_production", 1500.0)
    for name, value in APPENDIX_A_MEASURED.items():
        prob.set_val(f"slc.{name}", value)
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
def test_heterogeneous_example_set_points_ignore_connection_order(slc_topologies, subtests):
    example = slc_topologies["hetero_example"]
    connections = example["connections"]
    priority_connections = [edge for edge in connections if edge[0] == "electricity_splitter"]
    other_connections = [edge for edge in connections if edge[0] != "electricity_splitter"]

    baseline_problem = _heterogeneous_example_problem(example)
    baseline_problem.run_model()
    expected = _set_point_outputs(baseline_problem)

    connection_orders = [list(reversed(other_connections)) + priority_connections]
    for seed in range(10):
        order = np.random.default_rng(seed).permutation(len(other_connections))
        connection_orders.append(
            [other_connections[index] for index in order] + priority_connections
        )

    for index, shuffled_connections in enumerate(connection_orders):
        problem = _heterogeneous_example_problem(example, shuffled_connections)
        problem.run_model()
        actual = _set_point_outputs(problem)

        with subtests.test(f"heterogeneous connection order {index}"):
            assert actual.keys() == expected.keys()
            for name in expected:
                np.testing.assert_allclose(actual[name], expected[name], rtol=1e-12, atol=1e-12)


@pytest.mark.unit
def test_heterogeneous_example_splitter_swap_changes_priority_draw(slc_topologies, subtests):
    example = slc_topologies["hetero_example"]
    connections = [edge.copy() for edge in example["connections"]]
    splitter_positions = [
        index for index, edge in enumerate(connections) if edge[0] == "electricity_splitter"
    ]
    assert len(splitter_positions) == 2
    connections[splitter_positions[0]], connections[splitter_positions[1]] = (
        connections[splitter_positions[1]],
        connections[splitter_positions[0]],
    )
    problem = _heterogeneous_example_problem(example, connections)
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
def test_compute_builds_no_networkx_graph(monkeypatch, slc_topologies):
    prob = _grid_to_haber_bosch_problem(slc_topologies["grid_to_haber_bosch"])
    prob.final_setup()

    def _raise(*args, **kwargs):
        raise AssertionError("compute must not build a networkx graph")

    monkeypatch.setattr(nx.DiGraph, "__init__", _raise)
    prob.run_model()


@pytest.mark.unit
class TestHeterogeneousCommodityControl:
    """Backward demand propagation across commodity converters."""

    def test_detect_converters_chain(self):
        """Converters are detected across a grid -> electrolyzer -> Haber-Bosch chain."""
        problem = _chain_problem(
            GRID_ELECTROLYZER_HABER_BOSCH,
            _build_tech_control_classifiers(dispatchable=["grid", "electrolyzer", "haber_bosch"]),
            "ammonia",
            {"electricity": "kW", "hydrogen": "kg/h"},
        )
        links = problem.model.slc._dispatch_topology.links
        assert {(link.in_commodity, link.tech, link.out_commodity) for link in links} == {
            ("electricity", "electrolyzer", "hydrogen"),
            ("hydrogen", "haber_bosch", "ammonia"),
        }

    def test_single_converter_capacity_propagation(self):
        """A single converter seeds electricity demand from the rated capacity ratio."""
        problem = _chain_problem(
            GRID_ELECTROLYZER,
            _build_tech_control_classifiers(dispatchable=["grid", "electrolyzer"]),
            "hydrogen",
            {"electricity": "kW"},
        )
        problem.set_val("slc.grid_rated_electricity_production", 51e6)
        problem.set_val("slc.electrolyzer_rated_hydrogen_production", 1e6)
        problem.run_model()

        np.testing.assert_allclose(problem.get_val("slc.electrolyzer_hydrogen_set_point"), 100.0)
        np.testing.assert_allclose(problem.get_val("slc.grid_electricity_set_point"), 5100.0)

    def test_chained_converter_capacity_propagation(self):
        """Demand propagates through a two-converter chain via capacity ratios."""
        problem = _chain_problem(
            GRID_ELECTROLYZER_HABER_BOSCH,
            _build_tech_control_classifiers(dispatchable=["grid", "electrolyzer", "haber_bosch"]),
            "ammonia",
            {"electricity": "kW", "hydrogen": "kg/h"},
        )
        problem.set_val("slc.haber_bosch_rated_ammonia_production", 1e6)
        problem.set_val("slc.electrolyzer_rated_hydrogen_production", 0.18e6)
        problem.set_val("slc.grid_rated_electricity_production", 51.0 * 0.18e6)
        problem.run_model()

        np.testing.assert_allclose(problem.get_val("slc.haber_bosch_ammonia_set_point"), 100.0)
        np.testing.assert_allclose(problem.get_val("slc.electrolyzer_hydrogen_set_point"), 18.0)
        np.testing.assert_allclose(problem.get_val("slc.grid_electricity_set_point"), 918.0)

    def test_derived_demand_reuses_flexible_and_dispatchable(self):
        """Derived electricity demand flows through the shared flexible/dispatchable steps."""
        problem = _chain_problem(
            [
                ["wind", "electrolyzer", "electricity", "cable"],
                ["grid", "electrolyzer", "electricity", "cable"],
                ["electrolyzer", "demand", "hydrogen", "pipe"],
            ],
            _build_tech_control_classifiers(
                flexible=["wind"], dispatchable=["grid", "electrolyzer"]
            ),
            "hydrogen",
            {"electricity": "kW"},
            upstream_out={("wind", "electricity"): 1000.0},
        )
        problem.set_val("slc.wind_rated_electricity_production", 2000.0)
        problem.set_val("slc.grid_rated_electricity_production", 48000.0)
        problem.set_val("slc.electrolyzer_rated_hydrogen_production", 1000.0)
        problem.run_model()

        np.testing.assert_allclose(problem.get_val("slc.electrolyzer_hydrogen_set_point"), 100.0)
        np.testing.assert_allclose(problem.get_val("slc.wind_electricity_set_point"), 2000.0)
        np.testing.assert_allclose(problem.get_val("slc.grid_electricity_set_point"), 4000.0)

    def test_missing_ratio_warns_and_keeps_legacy_dispatch(self):
        """A converter with no measurement and zero rated capacities warns once."""
        problem = _chain_problem(
            GRID_ELECTROLYZER,
            _build_tech_control_classifiers(dispatchable=["grid", "electrolyzer"]),
            "hydrogen",
            {"electricity": "kW"},
        )
        with pytest.warns(UserWarning, match="No conversion ratio"):
            problem.run_model()

        np.testing.assert_allclose(problem.get_val("slc.electrolyzer_hydrogen_set_point"), 100.0)
        np.testing.assert_allclose(problem.get_val("slc.grid_electricity_set_point"), 1.0)

    @pytest.mark.parametrize(
        "controller,expected_dispatch",
        [
            (DemandFollowingControl, (2500.0, 2500.0)),
            (CostMinimizationControl, (3000.0, 2000.0)),
            (ProfitMaximizationControl, (3000.0, 2000.0)),
        ],
    )
    def test_dispatchable_hook_at_derived_level(self, controller, expected_dispatch, subtests):
        """Each strategy writes all dispatchables on the hydrogen and electricity buses."""
        problem = _chain_problem(
            [
                ["cheap", "electrolyzer", "electricity", "cable"],
                ["expensive", "electrolyzer", "electricity", "cable"],
                ["electrolyzer", "demand", "hydrogen", "pipe"],
            ],
            _build_tech_control_classifiers(dispatchable=["cheap", "expensive", "electrolyzer"]),
            "hydrogen",
            {"electricity": "kW"},
            controller=controller,
            cost_per_tech={"cheap": 0.03, "expensive": 0.08},
        )
        problem.set_val("slc.cheap_rated_electricity_production", 3000.0)
        problem.set_val("slc.expensive_rated_electricity_production", 5000.0)
        problem.set_val("slc.electrolyzer_rated_hydrogen_production", 160.0)
        problem.run_model()

        with subtests.test("both buses follow the strategy's dispatchable policy"):
            assert len(problem.model.slc._dispatch_topology.dispatch_order) == 2
            np.testing.assert_allclose(
                problem.get_val("slc.electrolyzer_hydrogen_set_point"), 100.0
            )
            np.testing.assert_allclose(
                problem.get_val("slc.cheap_electricity_set_point"), expected_dispatch[0]
            )
            np.testing.assert_allclose(
                problem.get_val("slc.expensive_electricity_set_point"), expected_dispatch[1]
            )

        with subtests.test("zero demand overwrites every dispatchable set point"):
            problem.set_val("slc.hydrogen_demand", 0.0)
            problem.run_model()
            for name in ("electrolyzer_hydrogen", "cheap_electricity", "expensive_electricity"):
                np.testing.assert_array_equal(problem.get_val(f"slc.{name}_set_point"), np.zeros(4))
            for residual in problem.model.slc.dispatch_trace["bus_residual"].values():
                np.testing.assert_array_equal(residual, np.zeros(4))

    def test_dynamic_ratio_overrides_capacity(self):
        """Measured consumption drives the ratio, overriding the capacity seed."""
        problem = _chain_problem(
            GRID_ELECTROLYZER,
            _build_tech_control_classifiers(dispatchable=["grid", "electrolyzer"]),
            "hydrogen",
            {"electricity": "kW"},
        )
        problem.set_val("slc.grid_rated_electricity_production", 50e6)
        problem.set_val("slc.electrolyzer_rated_hydrogen_production", 1e6)
        problem.set_val("slc.electrolyzer_hydrogen_out", 100.0)
        problem.set_val("slc.electrolyzer_electricity_consumed", 5100.0)
        problem.run_model()

        np.testing.assert_allclose(problem.get_val("slc.grid_electricity_set_point"), 5100.0)

    def test_set_point_outputs_use_rate_references(self):
        problem = _chain_problem(
            GRID_ELECTROLYZER,
            _build_tech_control_classifiers(dispatchable=["grid", "electrolyzer"]),
            "hydrogen",
            {"electricity": "kW"},
            scale_control_variables=True,
        )
        metadata = problem.model.slc._var_rel2meta

        assert metadata["grid_electricity_set_point"]["ref"] == 1e5
        assert metadata["grid_electricity_set_point"]["res_ref"] == 1e5
        assert metadata["electrolyzer_hydrogen_set_point"]["ref"] == 1e3
        assert metadata["electrolyzer_hydrogen_set_point"]["res_ref"] == 1e3

    def test_passthrough_command_uses_rate_references(self):
        problem = om.Problem()
        problem.model.add_subsystem(
            "controller",
            PassthroughController(
                commodity="electricity",
                n_timesteps=4,
                commodity_rate_units="kW",
                scale_output=True,
            ),
        )
        problem.setup()

        metadata = problem.model.controller._var_rel2meta["electricity_command_value"]
        assert metadata["ref"] == 1e5
        assert metadata["res_ref"] == 1e5

    def test_dynamic_ratio_time_varying_with_zero_output_fallback(self):
        """Per-timestep measurements fill zero output with their measured mean."""
        problem = _chain_problem(
            GRID_ELECTROLYZER,
            _build_tech_control_classifiers(dispatchable=["grid", "electrolyzer"]),
            "hydrogen",
            {"electricity": "kW"},
        )
        problem.set_val("slc.grid_rated_electricity_production", 50e6)
        problem.set_val("slc.electrolyzer_rated_hydrogen_production", 1e6)
        problem.set_val("slc.electrolyzer_hydrogen_out", [100.0, 100.0, 0.0, 100.0])
        problem.set_val("slc.electrolyzer_electricity_consumed", [5100.0, 4000.0, 9999.0, 6000.0])
        problem.run_model()

        np.testing.assert_allclose(
            problem.get_val("slc.grid_electricity_set_point"),
            [5100.0, 4000.0, 5033.333333333333, 6000.0],
        )

    def test_dynamic_ratio_without_capacity_does_not_warn(self):
        """A connected consumption signal enables propagation with no capacity seed or warning."""
        problem = _chain_problem(
            GRID_ELECTROLYZER,
            _build_tech_control_classifiers(dispatchable=["grid", "electrolyzer"]),
            "hydrogen",
            {"electricity": "kW"},
        )
        problem.set_val("slc.electrolyzer_hydrogen_out", 100.0)
        problem.set_val("slc.electrolyzer_electricity_consumed", 5100.0)

        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            problem.run_model()

        assert not any("No conversion ratio" in str(warning.message) for warning in caught)
        np.testing.assert_allclose(problem.get_val("slc.grid_electricity_set_point"), 5100.0)

    def test_capacity_seed_scales_with_rated_capacities(self):
        """The capacity seed alone sets demand to rated input divided by rated output."""
        for rated_electricity, expected_ratio in ((40e6, 40.0), (80e6, 80.0)):
            problem = _chain_problem(
                GRID_ELECTROLYZER,
                _build_tech_control_classifiers(dispatchable=["grid", "electrolyzer"]),
                "hydrogen",
                {"electricity": "kW"},
            )
            problem.set_val("slc.grid_rated_electricity_production", rated_electricity)
            problem.set_val("slc.electrolyzer_rated_hydrogen_production", 1e6)
            problem.run_model()

            np.testing.assert_allclose(
                problem.get_val("slc.grid_electricity_set_point"), 100.0 * expected_ratio
            )

    def test_splitter_aggregates_derived_demand_across_producers(self):
        """A shared input bus sums demand from distinct converter outputs."""
        problem = _chain_problem(
            [
                ["grid", "ely_a", "electricity", "cable"],
                ["grid", "ely_b", "electricity", "cable"],
                ["ely_a", "haber_bosch", "hydrogen", "pipe"],
                ["ely_b", "haber_bosch", "hydrogen", "pipe"],
                ["haber_bosch", "demand", "ammonia", "pipe"],
            ],
            _build_tech_control_classifiers(dispatchable=["grid", "ely_a", "ely_b", "haber_bosch"]),
            "ammonia",
            {"electricity": "kW", "hydrogen": "kg/h"},
        )
        problem.set_val("slc.haber_bosch_rated_ammonia_production", 1000.0)
        problem.set_val("slc.ely_a_rated_hydrogen_production", 100.0)
        problem.set_val("slc.ely_b_rated_hydrogen_production", 100.0)
        problem.set_val("slc.grid_rated_electricity_production", 5100.0)
        problem.run_model()

        np.testing.assert_allclose(problem.get_val("slc.haber_bosch_ammonia_set_point"), 100.0)
        np.testing.assert_allclose(problem.get_val("slc.ely_a_hydrogen_set_point"), 10.0)
        np.testing.assert_allclose(problem.get_val("slc.ely_b_hydrogen_set_point"), 10.0)
        np.testing.assert_allclose(problem.get_val("slc.grid_electricity_set_point"), 1020.0)

    def test_electricity_splitter_feeds_electrolyzer_and_haber_bosch(self):
        """Two converters sharing one electricity bus sum their demand."""
        problem = _chain_problem(
            [
                ["grid", "electrolyzer", "electricity", "cable"],
                ["grid", "haber_bosch", "electricity", "cable"],
                ["electrolyzer", "haber_bosch", "hydrogen", "pipe"],
                ["haber_bosch", "demand", "ammonia", "pipe"],
            ],
            _build_tech_control_classifiers(dispatchable=["grid", "electrolyzer", "haber_bosch"]),
            "ammonia",
            {"electricity": "kW", "hydrogen": "kg/h"},
        )
        problem.set_val("slc.haber_bosch_rated_ammonia_production", 1000.0)
        problem.set_val("slc.electrolyzer_rated_hydrogen_production", 200.0)
        problem.set_val("slc.grid_rated_electricity_production", 10200.0)
        problem.run_model()

        np.testing.assert_allclose(problem.get_val("slc.haber_bosch_ammonia_set_point"), 100.0)
        np.testing.assert_allclose(problem.get_val("slc.electrolyzer_hydrogen_set_point"), 20.0)
        np.testing.assert_allclose(problem.get_val("slc.grid_electricity_set_point"), 2040.0)

    def test_coproduct_converter_max_combines_input_demand_without_double_counting(self):
        """Two outputs from the same converter combine their shared input by maximum."""
        problem = _chain_problem(
            [
                ["ng_source", "reformer", "natural_gas", "pipe"],
                ["reformer", "haber_bosch", "hydrogen", "pipe"],
                ["reformer", "haber_bosch", "electricity", "cable"],
                ["haber_bosch", "demand", "ammonia", "pipe"],
            ],
            _build_tech_control_classifiers(dispatchable=["ng_source", "reformer", "haber_bosch"]),
            "ammonia",
            {"natural_gas": "kg/h", "hydrogen": "kg/h", "electricity": "kW"},
            upstream_out={("reformer", "hydrogen"): 10.0, ("reformer", "electricity"): 40.0},
        )
        links = problem.model.slc._dispatch_topology.links
        converters = {(link.in_commodity, link.tech, link.out_commodity) for link in links}
        assert ("natural_gas", "reformer", "hydrogen") in converters
        assert ("natural_gas", "reformer", "electricity") in converters

        problem.set_val("slc.haber_bosch_rated_ammonia_production", 1000.0)
        problem.set_val("slc.reformer_rated_hydrogen_production", 200.0)
        problem.set_val("slc.reformer_rated_electricity_production", 300.0)
        problem.set_val("slc.reformer_natural_gas_consumed", 100.0)
        problem.run_model()

        np.testing.assert_allclose(problem.get_val("slc.haber_bosch_ammonia_set_point"), 100.0)
        np.testing.assert_allclose(problem.get_val("slc.reformer_hydrogen_set_point"), 20.0)
        np.testing.assert_allclose(problem.get_val("slc.reformer_electricity_set_point"), 30.0)
        np.testing.assert_allclose(problem.get_val("slc.ng_source_natural_gas_set_point"), 200.0)
