"""Unit tests for pure system-level control topology helpers."""

import pytest

from h2integrate.core.connection_utils import create_technology_graph
from h2integrate.control.control_strategies.system_level.slc_topology import (
    find_commodity_suppliers,
)


@pytest.mark.unit
def test_find_commodity_suppliers(subtests):
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
        graph = create_technology_graph(
            [
                ["wind", "gen_combiner", "electricity", "cable"],
                ["solar", "gen_combiner", "electricity", "cable"],
                ["gen_combiner", "battery", "electricity", "cable"],
                ["gen_combiner", "elec_combiner", "electricity", "cable"],
                ["battery", "elec_combiner", "electricity", "cable"],
                ["elec_combiner", "electricity_splitter", "electricity", "cable"],
                ["electricity_splitter", "electrolyzer", "electricity", "cable"],
                ["electricity_splitter", "haber_bosch", "electricity", "cable"],
            ]
        )
        suppliers = {"battery", "solar", "wind"}
        assert find_commodity_suppliers(
            graph, "electrolyzer", "electricity", supplier_techs=suppliers
        ) == ("battery", "solar", "wind")
        assert find_commodity_suppliers(
            graph, "haber_bosch", "electricity", supplier_techs=suppliers
        ) == ("battery", "solar", "wind")

    with subtests.test("distinct electricity sources do not cross a converter"):
        graph = create_technology_graph(
            [
                ["grid", "haber_bosch", "electricity", "cable"],
                ["wind", "electrolyzer", "electricity", "cable"],
                ["electrolyzer", "haber_bosch", "hydrogen", "pipe"],
            ]
        )
        # The old ancestor-based lookup also returned wind for Haber-Bosch electricity.
        assert find_commodity_suppliers(
            graph,
            "haber_bosch",
            "electricity",
            supplier_techs={"grid", "wind", "electrolyzer"},
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
        graph = create_technology_graph(
            [
                ["electrolyzer", "haber_bosch", "hydrogen", "pipe"],
                ["electrolyzer", "haber_bosch", "oxygen", "pipe"],
                ["electrolyzer", "haber_bosch", "heat", "pipe"],
            ]
        )
        assert find_commodity_suppliers(graph, "haber_bosch", "oxygen") == ("electrolyzer",)

    with subtests.test("commodity loop terminates"):
        graph = create_technology_graph(
            [
                ["a", "b", "electricity", "cable"],
                ["b", "a", "electricity", "cable"],
            ]
        )
        assert find_commodity_suppliers(graph, "a", "electricity") == ("b",)

    with subtests.test("feedstock can be included or filtered out"):
        graph = create_technology_graph([["n2_feedstock", "haber_bosch", "nitrogen", "pipe"]])
        assert find_commodity_suppliers(
            graph, "haber_bosch", "nitrogen", supplier_techs={"n2_feedstock"}
        ) == ("n2_feedstock",)
        assert (
            find_commodity_suppliers(graph, "haber_bosch", "nitrogen", supplier_techs={"grid"})
            == ()
        )
