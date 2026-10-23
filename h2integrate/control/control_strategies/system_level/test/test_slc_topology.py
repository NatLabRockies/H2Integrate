"""Unit tests for pure system-level control topology helpers."""

import os
import sys
import json
import textwrap
import warnings
import subprocess
from pathlib import Path
from itertools import permutations

import pytest

from h2integrate.core.connection_utils import create_technology_graph
from h2integrate.control.control_strategies.system_level.slc_topology import (
    SUPPLIER_CLASSIFIERS,
    build_dispatch_topology,
    find_commodity_suppliers,
)


def _build_topology(connections, classifiers, demand_tech, demand_commodity):
    """Build a dispatch topology the way ``H2IntegrateModel`` does."""
    graph = create_technology_graph(connections)
    tech_to_commodity = {
        (source, commodity)
        for source, _, commodities in graph.edges(data="commodity")
        if classifiers.get(source) in SUPPLIER_CLASSIFIERS
        for commodity in commodities
    }
    return build_dispatch_topology(
        graph, classifiers, tech_to_commodity, demand_tech, demand_commodity
    )


@pytest.mark.unit
def test_named_topology_fixtures_are_complete(slc_topologies, subtests):
    for name, topology_data in slc_topologies.items():
        nodes = {
            tech_name
            for source, target, _commodity, _transport in topology_data["connections"]
            for tech_name in (source, target)
        }
        with subtests.test(name):
            assert isinstance(topology_data["connections"], list)
            assert topology_data["connections"]
            assert isinstance(topology_data["classifiers"], dict)
            assert nodes <= topology_data["classifiers"].keys()
            assert topology_data["demand_tech"] in nodes
            assert topology_data["demand_commodity"]


@pytest.mark.unit
def test_find_commodity_suppliers(slc_topologies, subtests):
    with subtests.test("direct chain"):
        graph = create_technology_graph([["grid", "electrolyzer", "electricity", "cable"]])
        assert find_commodity_suppliers(graph, "electrolyzer", "electricity") == ("grid",)

    with subtests.test("combiner path and supplier filter"):
        graph = create_technology_graph(
            [
                ["wind", "elec_combiner", "electricity", "cable"],
                ["solar", "elec_combiner", "electricity", "cable"],
                ["elec_combiner", "electrolyzer", "electricity", "cable"],
            ]
        )
        assert find_commodity_suppliers(graph, "electrolyzer", "electricity") == (
            "elec_combiner",
            "solar",
            "wind",
        )
        assert find_commodity_suppliers(
            graph, "electrolyzer", "electricity", supplier_techs={"wind", "solar"}
        ) == ("solar", "wind")

    with subtests.test("heterogeneous bus through splitter and storage"):
        example = slc_topologies["hetero_example"]
        graph = create_technology_graph(example["connections"])
        suppliers = {
            tech_name
            for tech_name, classifier in example["classifiers"].items()
            if classifier in SUPPLIER_CLASSIFIERS
        }
        assert find_commodity_suppliers(
            graph, "electrolyzer", "electricity", supplier_techs=suppliers
        ) == ("battery", "solar", "wind")
        assert find_commodity_suppliers(
            graph, "haber_bosch", "electricity", supplier_techs=suppliers
        ) == ("battery", "solar", "wind")

    with subtests.test("distinct electricity sources do not cross a converter"):
        appendix = slc_topologies["grid_to_haber_bosch"]
        graph = create_technology_graph(appendix["connections"])
        # The old ancestor-based lookup also returned wind for Haber-Bosch electricity.
        assert find_commodity_suppliers(
            graph,
            "haber_bosch",
            "electricity",
            supplier_techs={
                tech_name
                for tech_name, classifier in appendix["classifiers"].items()
                if classifier in SUPPLIER_CLASSIFIERS
            },
        ) == ("grid",)

    with subtests.test("converter terminates the path"):
        graph = create_technology_graph(
            [
                ["wind", "electrolyzer", "electricity", "cable"],
                ["electrolyzer", "fuel_cell", "hydrogen", "pipe"],
                ["fuel_cell", "battery", "electricity", "cable"],
            ]
        )
        assert find_commodity_suppliers(
            graph,
            "battery",
            "electricity",
            supplier_techs={"wind", "electrolyzer", "fuel_cell"},
        ) == ("fuel_cell",)

    with subtests.test("multi-commodity edge"):
        fake_system = slc_topologies["fake_complex_system_816"]
        graph = create_technology_graph(fake_system["connections"])
        suppliers = {
            tech_name
            for tech_name, classifier in fake_system["classifiers"].items()
            if classifier in SUPPLIER_CLASSIFIERS
        }
        for commodity in ("oxygen", "heat"):
            assert find_commodity_suppliers(
                graph, "haber_bosch", commodity, supplier_techs=suppliers
            ) == ("electrolyzer",)

    with subtests.test("commodity loop terminates"):
        graph = create_technology_graph(
            [
                ["a", "b", "electricity", "cable"],
                ["b", "a", "electricity", "cable"],
            ]
        )
        assert find_commodity_suppliers(graph, "a", "electricity") == ("b",)

    with subtests.test("feedstock can be included or filtered out"):
        fake_system = slc_topologies["fake_complex_system_816"]
        graph = create_technology_graph(fake_system["connections"])
        assert find_commodity_suppliers(
            graph, "haber_bosch", "nitrogen", supplier_techs={"n2_feedstock"}
        ) == ("n2_feedstock",)
        assert (
            find_commodity_suppliers(graph, "haber_bosch", "nitrogen", supplier_techs={"grid"})
            == ()
        )


@pytest.mark.unit
def test_dispatch_topology_heterogeneous_example(slc_topologies, subtests):
    example = slc_topologies["hetero_example"]
    topology = _build_topology(
        example["connections"],
        example["classifiers"],
        example["demand_tech"],
        example["demand_commodity"],
    )
    electricity_bus = topology.buses["electricity:electrolyzer+haber_bosch"]

    with subtests.test("consumers sharing a splitter are one electricity bus"):
        assert set(topology.buses) == {
            "ammonia:ammonia_load_demand",
            "electricity:electrolyzer+haber_bosch",
            "hydrogen:haber_bosch",
            "nitrogen:haber_bosch",
        }
        assert electricity_bus.producers == ("battery", "solar", "wind")
        assert electricity_bus.consumers == ("electrolyzer", "haber_bosch")

    with subtests.test("combiners and splitters are bus members but not producers"):
        assert {"gen_combiner", "elec_combiner", "electricity_splitter"} <= set(
            electricity_bus.members
        )

    with subtests.test("hydrogen is dispatched before the electricity that backs it"):
        assert topology.demand_bus == "ammonia:ammonia_load_demand"
        assert topology.dispatch_order == (
            "ammonia:ammonia_load_demand",
            "hydrogen:haber_bosch",
            "electricity:electrolyzer+haber_bosch",
        )

    with subtests.test("a feedstock-only bus is not dispatched"):
        assert "nitrogen:haber_bosch" in topology.buses
        assert "nitrogen:haber_bosch" not in topology.dispatch_order
        assert ("haber_bosch", "nitrogen") not in topology.consumption_signals

    with subtests.test("consumption signals are one per converter input"):
        assert topology.consumption_signals == (
            ("electrolyzer", "electricity"),
            ("haber_bosch", "electricity"),
            ("haber_bosch", "hydrogen"),
        )

    with subtests.test("conversion links carry their buses and suppliers"):
        electrolyzer_link = next(link for link in topology.links if link.tech == "electrolyzer")
        assert electrolyzer_link.in_bus == "electricity:electrolyzer+haber_bosch"
        assert electrolyzer_link.out_bus == "hydrogen:haber_bosch"
        assert electrolyzer_link.suppliers == ("battery", "solar", "wind")

    with subtests.test("the splitter priority consumer is behind out1"):
        (splitter,) = topology.splitters
        assert splitter.name == "electricity_splitter"
        assert splitter.commodity == "electricity"
        assert splitter.bus == "electricity:electrolyzer+haber_bosch"
        assert splitter.priority_consumers == ("electrolyzer",)

    with subtests.test("swapping the splitter outputs swaps the priority consumer"):
        swapped = [list(connection) for connection in example["connections"]]
        splitter_outputs = [
            index
            for index, connection in enumerate(swapped)
            if connection[0] == "electricity_splitter"
        ]
        swapped[splitter_outputs[0]], swapped[splitter_outputs[1]] = (
            swapped[splitter_outputs[1]],
            swapped[splitter_outputs[0]],
        )
        swapped_topology = _build_topology(
            swapped,
            example["classifiers"],
            example["demand_tech"],
            example["demand_commodity"],
        )
        assert swapped_topology.splitters[0].priority_consumers == ("haber_bosch",)
        assert swapped_topology.dispatch_order == topology.dispatch_order

    with subtests.test("no warning for a bus whose producers all reach every consumer"):
        with warnings.catch_warnings():
            warnings.simplefilter("error")
            _build_topology(
                example["connections"],
                example["classifiers"],
                example["demand_tech"],
                example["demand_commodity"],
            )


@pytest.mark.unit
def test_dispatch_topology_grid_to_haber_bosch(slc_topologies, subtests):
    appendix = slc_topologies["grid_to_haber_bosch"]
    topology = _build_topology(
        appendix["connections"],
        appendix["classifiers"],
        appendix["demand_tech"],
        appendix["demand_commodity"],
    )

    with subtests.test("distinct electricity sources are distinct buses"):
        assert topology.buses["electricity:haber_bosch"].producers == ("grid",)
        assert topology.buses["electricity:electrolyzer"].producers == ("wind",)

    with subtests.test("dispatch order follows the demand"):
        assert topology.dispatch_order == (
            "ammonia:ammonia_demand",
            "electricity:haber_bosch",
            "hydrogen:haber_bosch",
            "electricity:electrolyzer",
        )

    with subtests.test("each converter input has its own supplier"):
        haber_bosch_electricity = next(
            link
            for link in topology.links
            if link.tech == "haber_bosch" and link.in_commodity == "electricity"
        )
        assert haber_bosch_electricity.suppliers == ("grid",)

    with subtests.test("describe summarizes the topology"):
        assert topology.describe() == "\n".join(
            [
                "Demand bus: ammonia:ammonia_demand",
                "Dispatch order:",
                "  1. ammonia:ammonia_demand (producers: haber_bosch; consumers: ammonia_demand)",
                "  2. electricity:haber_bosch (producers: grid; consumers: haber_bosch)",
                "  3. hydrogen:haber_bosch (producers: electrolyzer; consumers: haber_bosch)",
                "  4. electricity:electrolyzer (producers: wind; consumers: electrolyzer)",
                "Not dispatched: nitrogen:haber_bosch",
                "Conversion links (output bus -> input bus):",
                "  electrolyzer: hydrogen:haber_bosch -> electricity:electrolyzer",
                "  haber_bosch: ammonia:ammonia_demand -> electricity:haber_bosch",
                "  haber_bosch: ammonia:ammonia_demand -> hydrogen:haber_bosch",
            ]
        )


@pytest.mark.unit
def test_dispatch_topology_ignores_interconnection_order(slc_topologies):
    appendix = slc_topologies["grid_to_haber_bosch"]
    connections = appendix["connections"]
    expected = _build_topology(
        connections,
        appendix["classifiers"],
        appendix["demand_tech"],
        appendix["demand_commodity"],
    )
    for ordered_connections in permutations(connections):
        topology = _build_topology(
            list(ordered_connections),
            appendix["classifiers"],
            appendix["demand_tech"],
            appendix["demand_commodity"],
        )
        assert topology == expected


@pytest.mark.regression
def test_dispatch_order_is_independent_of_python_hash_seed(slc_topologies):
    script = textwrap.dedent(
        """
        import json
        import os
        import sys
        from pathlib import Path

        import networkx as nx

        system_level_path = (
            Path.cwd()
            / "h2integrate"
            / "control"
            / "control_strategies"
            / "system_level"
        )
        sys.path.insert(0, str(system_level_path))
        from slc_topology import SUPPLIER_CLASSIFIERS, build_dispatch_topology

        topology_data = json.loads(os.environ["SLC_TOPOLOGY_DATA"])
        connections = topology_data["connections"]
        classifiers = topology_data["classifiers"]
        graph = nx.DiGraph()
        for source, target, commodity, _ in connections:
            graph.add_edge(source, target, commodity=[commodity])
        tech_to_commodity = {
            (source, commodity)
            for source, _, commodities in graph.edges(data="commodity")
            if classifiers.get(source) in SUPPLIER_CLASSIFIERS
            for commodity in commodities
        }
        topology = build_dispatch_topology(
            graph,
            classifiers,
            tech_to_commodity,
            topology_data["demand_tech"],
            topology_data["demand_commodity"],
        )
        print(repr(topology.dispatch_order))
        """
    )
    dispatch_orders = []
    appendix = slc_topologies["grid_to_haber_bosch"]
    topology_json = json.dumps(
        {
            "connections": appendix["connections"],
            "classifiers": appendix["classifiers"],
            "demand_tech": appendix["demand_tech"],
            "demand_commodity": appendix["demand_commodity"],
        }
    )

    for hash_seed in ("0", "1"):
        environment = os.environ.copy()
        environment["PYTHONHASHSEED"] = hash_seed
        environment["SLC_TOPOLOGY_DATA"] = topology_json
        try:
            result = subprocess.run(
                [sys.executable, "-c", script],
                capture_output=True,
                check=False,
                text=True,
                timeout=10,
                env=environment,
                cwd=Path(__file__).resolve().parents[5],
            )
        except subprocess.TimeoutExpired:
            pytest.skip("Dispatch-order hash-seed subprocess exceeded 10 seconds.")
        assert result.returncode == 0, result.stderr
        dispatch_orders.append(result.stdout.strip())

    assert dispatch_orders[0] == dispatch_orders[1]


@pytest.mark.unit
def test_dispatch_topology_fuel_cell(subtests):
    classifiers = {
        "wind": "dispatchable",
        "electrolyzer": "dispatchable",
        "fuel_cell": "dispatchable",
        "elec_combiner": "combiner",
    }

    with subtests.test("a fuel cell feeding a separate demand bus is not a cycle"):
        topology = _build_topology(
            [
                ["wind", "electrolyzer", "electricity", "cable"],
                ["electrolyzer", "fuel_cell", "hydrogen", "pipe"],
                ["fuel_cell", "demand", "electricity", "cable"],
            ],
            classifiers,
            "demand",
            "electricity",
        )
        # Electricity appears twice in the chain, so a per-commodity order could not exist.
        assert topology.dispatch_order == (
            "electricity:demand",
            "hydrogen:fuel_cell",
            "electricity:electrolyzer",
        )

    with subtests.test("a fuel cell returning to its electrolyzer's bus is a cycle"):
        with pytest.raises(ValueError, match="form a cycle") as excinfo:
            _build_topology(
                [
                    ["wind", "elec_combiner", "electricity", "cable"],
                    ["fuel_cell", "elec_combiner", "electricity", "cable"],
                    ["elec_combiner", "electrolyzer", "electricity", "cable"],
                    ["electrolyzer", "fuel_cell", "hydrogen", "pipe"],
                    ["electrolyzer", "h2_demand", "hydrogen", "pipe"],
                ],
                classifiers,
                "h2_demand",
                "hydrogen",
            )
        assert "electrolyzer, fuel_cell" in str(excinfo.value)


@pytest.mark.unit
def test_dispatch_topology_partial_overlap_warns(subtests):
    # The grid reaches both the electrolyzer and Haber-Bosch through a splitter, but wind
    # only reaches the electrolyzer, so the bus is not one interchangeable pool.
    connections = [
        ["wind", "wind_combiner", "electricity", "cable"],
        ["grid", "grid_splitter", "electricity", "cable"],
        ["grid_splitter", "wind_combiner", "electricity", "cable"],
        ["grid_splitter", "haber_bosch", "electricity", "cable"],
        ["wind_combiner", "electrolyzer", "electricity", "cable"],
        ["electrolyzer", "haber_bosch", "hydrogen", "pipe"],
        ["haber_bosch", "ammonia_demand", "ammonia", "pipe"],
    ]
    classifiers = {
        "wind": "flexible",
        "grid": "dispatchable",
        "electrolyzer": "dispatchable",
        "haber_bosch": "dispatchable",
        "wind_combiner": "combiner",
        "grid_splitter": "splitter",
    }

    with pytest.warns(UserWarning, match="mixes producers") as record:
        topology = _build_topology(connections, classifiers, "ammonia_demand", "ammonia")

    message = str(record[0].message)
    with subtests.test("the warning names the bus and the unreachable pair"):
        assert "electricity:electrolyzer+haber_bosch" in message
        assert "wind -> haber_bosch" in message
        assert "grid ->" not in message

    with subtests.test("the bus is still dispatched as one pool"):
        assert topology.buses["electricity:electrolyzer+haber_bosch"].producers == ("grid", "wind")
        assert "electricity:electrolyzer+haber_bosch" in topology.dispatch_order


@pytest.mark.unit
def test_dispatch_topology_splitters(subtests):
    classifiers = {
        "grid": "dispatchable",
        "electrolyzer": "dispatchable",
        "haber_bosch": "dispatchable",
        "split": "splitter",
        "out1_combiner": "combiner",
        "wind": "flexible",
        "battery": "storage",
    }

    with subtests.test("priority consumers are traced through a combiner behind out1"):
        topology = _build_topology(
            [
                ["grid", "split", "electricity", "cable"],
                ["split", "out1_combiner", "electricity", "cable"],
                ["out1_combiner", "electrolyzer", "electricity", "cable"],
                ["split", "haber_bosch", "electricity", "cable"],
                ["electrolyzer", "haber_bosch", "hydrogen", "pipe"],
                ["haber_bosch", "demand", "ammonia", "pipe"],
            ],
            classifiers,
            "demand",
            "ammonia",
        )
        (splitter,) = topology.splitters
        assert splitter.priority_consumers == ("electrolyzer",)

    with subtests.test("the demand technology can be a priority consumer"):
        topology = _build_topology(
            [
                ["wind", "split", "electricity", "cable"],
                ["split", "demand", "electricity", "cable"],
                ["split", "battery", "electricity", "cable"],
            ],
            classifiers,
            "demand",
            "electricity",
        )
        (splitter,) = topology.splitters
        assert splitter.bus == "electricity:demand"
        assert splitter.priority_consumers == ("demand",)

    with subtests.test("a splitter on a bus without controlled producers is ignored"):
        topology = _build_topology(
            [
                ["n2_feedstock", "split", "nitrogen", "pipe"],
                ["split", "haber_bosch", "nitrogen", "pipe"],
                ["split", "other", "nitrogen", "pipe"],
                ["haber_bosch", "demand", "ammonia", "pipe"],
            ],
            {**classifiers, "n2_feedstock": "feedstock"},
            "demand",
            "ammonia",
        )
        assert topology.splitters == ()


@pytest.mark.unit
def test_dispatch_topology_without_demand_connection():
    topology = _build_topology([], {}, "demand", "electricity")
    assert topology.demand_bus is None
    assert topology.dispatch_order == ()
    assert topology.describe() == "Demand bus: None\nDispatch order:"
