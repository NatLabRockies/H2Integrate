"""Unit tests for system-level control base class and all controller strategies."""

import warnings

import numpy as np
import pytest
import networkx as nx
import openmdao.api as om

from h2integrate.control.control_strategies.system_level.demand_following_control import (
    DemandFollowingControl,
)
from h2integrate.control.control_strategies.system_level.cost_minimization_control import (
    CostMinimizationControl,
)
from h2integrate.control.control_strategies.system_level.profit_maximization_control import (
    ProfitMaximizationControl,
)


def _build_plant_config(
    technology_interconnections, n_timesteps=4, sell_price=0.06, cost_per_tech=None
):
    if cost_per_tech is None:
        return {
            "plant": {"simulation": {"n_timesteps": n_timesteps, "dt": 3600}, "plant_life": 30},
            "system_level_control": {"control_parameters": {"commodity_sell_price": sell_price}},
            "technology_interconnections": technology_interconnections,
        }
    return {
        "plant": {"simulation": {"n_timesteps": n_timesteps, "dt": 3600}, "plant_life": 30},
        "system_level_control": {
            "control_parameters": {
                "commodity_sell_price": sell_price,
                "cost_per_tech": cost_per_tech,
            }
        },
        "technology_interconnections": technology_interconnections,
    }


def _build_technology_graph(technology_interconnections):
    technology_graph = nx.DiGraph()
    for connection in technology_interconnections:
        source = connection[0]
        destination = connection[1]
        if len(connection) == 4:
            technology_graph.add_edge(source, destination, commodity=connection[2])
        else:
            technology_graph.add_edge(source, destination)
    return technology_graph


def _build_tech_control_classifiers(
    fixed=None, flexible=None, dispatchable=None, storage=None, feedstock=None
):
    tech_control_classifiers = dict.fromkeys(fixed or [], "fixed")
    tech_control_classifiers |= dict.fromkeys(flexible or [], "flexible")
    tech_control_classifiers |= dict.fromkeys(dispatchable or [], "dispatchable")
    tech_control_classifiers |= dict.fromkeys(storage or [], "storage")
    tech_control_classifiers |= dict.fromkeys(feedstock or [], "feedstock")
    return tech_control_classifiers


def _build_slc_topology(
    technology_graph,
    tech_control_classifiers: dict,
    demand_tech: str = "demand",
    demand_commodity: str = "electricity",
    demand_commodity_rate_units: str = "kW",
    storage_techs_with_control: list = [],
):
    sources_to_commodities = {
        (e[0], e[-1]) for e in technology_graph.edges(data="commodity") if e[-1] is not None
    }

    tech_to_commodities = {
        (e[0], e[-1]) for e in sources_to_commodities if e[0] in tech_control_classifiers
    }

    storage_techs = [k for k, v in tech_control_classifiers.items() if v == "storage"]
    storage_techs_to_control = {
        k: True if k in storage_techs_with_control else False for k in storage_techs
    }

    slc_topology = {
        "demand_commodity": demand_commodity,
        "demand_commodity_rate_units": demand_commodity_rate_units,
        "demand_tech": demand_tech,
        "tech_to_commodity": tech_to_commodities,
        "storage_techs_to_control": storage_techs_to_control,
        "technology_graph": technology_graph,
        "tech_control_classifiers": tech_control_classifiers,
    }
    return slc_topology


def _build_problem(slc_cls, plant_config, slc_topology, demand=50000, tech_config={}):
    """Create and setup an OpenMDAO Problem with the given controller."""
    prob = om.Problem()

    feedstock_techs = [
        k for k, v in slc_topology["tech_control_classifiers"].items() if v == "feedstock"
    ]
    feedstock_subsystem_names = []
    for fi, feedstock_tech in enumerate(feedstock_techs):
        feedstock_commodity = [
            e[-1] for e in slc_topology["tech_to_commodity"] if e[0] == feedstock_tech
        ]
        feedstock_comp = prob.model.add_subsystem(f"IVC{fi}", om.Group())
        feedstock_comp.add_subsystem(
            "feedstock",
            om.IndepVarComp(
                name=f"{feedstock_tech}_{feedstock_commodity[0]}_out",
                val=np.full(plant_config["plant"]["simulation"]["n_timesteps"], 1e9),
                units="MMBtu/h",
            ),
        )

        feedstock_subsystem_names.append(
            f"IVC{fi}.feedstock.{feedstock_tech}_{feedstock_commodity[0]}_out"
        )

    prob.model.add_subsystem(
        "slc",
        slc_cls(
            driver_config={},
            plant_config=plant_config,
            tech_config=tech_config,
            slc_topology=slc_topology,
        ),
    )

    for feedstock_name in feedstock_subsystem_names:
        connection_destination = feedstock_name.split(".")[-1]
        prob.model.connect(feedstock_name, f"slc.{connection_destination}")

    prob.setup()

    # Set demand profile from config
    demand_name = f"slc.{slc_topology['demand_commodity']}_demand"
    prob.set_val(demand_name, demand)

    return prob


# ---------------------------------------------------------------------------
# SystemLevelControlBase
# ---------------------------------------------------------------------------
@pytest.mark.unit
class TestSystemLevelControlBase:
    """Tests for the abstract base class setup logic."""

    def test_base_creates_flexible_io(self):
        tech_connections = [["wind", "demand", "electricity", "cable"]]
        plant_config = _build_plant_config(tech_connections)
        tech_graph = _build_technology_graph(tech_connections)
        tech_control_classifiers = _build_tech_control_classifiers(flexible=["wind"])
        slc_topology = _build_slc_topology(tech_graph, tech_control_classifiers)
        # Use DemandFollowingControl since base is abstract
        prob = _build_problem(DemandFollowingControl, plant_config, slc_topology)
        # _var_rel2meta uses relative names (no "slc." prefix)
        assert "wind_electricity_out" in prob.model.slc._var_rel2meta
        assert "wind_rated_electricity_production" in prob.model.slc._var_rel2meta
        assert "wind_electricity_set_point" in prob.model.slc._var_rel2meta

    def test_base_creates_dispatchable_io(self):
        tech_connections = [["ng", "demand", "electricity", "cable"]]
        plant_config = _build_plant_config(tech_connections)
        tech_graph = _build_technology_graph(tech_connections)
        tech_control_classifiers = _build_tech_control_classifiers(dispatchable=["ng"])
        slc_topology = _build_slc_topology(tech_graph, tech_control_classifiers)
        prob = _build_problem(DemandFollowingControl, plant_config, slc_topology)
        assert "ng_electricity_out" in prob.model.slc._var_rel2meta
        assert "ng_rated_electricity_production" in prob.model.slc._var_rel2meta
        assert "ng_electricity_set_point" in prob.model.slc._var_rel2meta

    def test_base_creates_storage_io(self):
        tech_connections = [["battery", "demand", "electricity", "cable"]]
        plant_config = _build_plant_config(tech_connections)
        tech_graph = _build_technology_graph(tech_connections)
        tech_control_classifiers = _build_tech_control_classifiers(storage=["battery"])
        slc_topology = _build_slc_topology(tech_graph, tech_control_classifiers)
        prob = _build_problem(DemandFollowingControl, plant_config, slc_topology)

        assert "battery_electricity_out" in prob.model.slc._var_rel2meta
        assert "battery_rated_electricity_production" in prob.model.slc._var_rel2meta
        assert "battery_electricity_set_point" in prob.model.slc._var_rel2meta

    def test_base_creates_demand_input(self):
        plant_config = _build_plant_config([])
        tech_graph = _build_technology_graph([])
        tech_control_classifiers = _build_tech_control_classifiers()
        slc_topology = _build_slc_topology(tech_graph, tech_control_classifiers)
        prob = _build_problem(DemandFollowingControl, plant_config, slc_topology)

        assert "electricity_demand" in prob.model.slc._var_rel2meta

    def test_backward_compat_alias(self):
        """DemandFollowingControl should be an alias for DemandFollowingControl."""
        assert DemandFollowingControl is DemandFollowingControl


# ---------------------------------------------------------------------------
# DemandFollowingControl
# ---------------------------------------------------------------------------
@pytest.mark.unit
class TestDemandFollowingControl:
    """Tests for the demand-following (equal-share) controller."""

    def test_equal_share_two_dispatchable(self):
        tech_connections = [
            ["ng1", "combiner", "electricity", "cable"],
            ["ng2", "combiner", "electricity", "cable"],
            ["combiner", "demand", "electricity", "cable"],
        ]
        plant_config = _build_plant_config(tech_connections)
        tech_graph = _build_technology_graph(tech_connections)
        tech_control_classifiers = _build_tech_control_classifiers(dispatchable=["ng1", "ng2"])
        slc_topology = _build_slc_topology(tech_graph, tech_control_classifiers)
        prob = _build_problem(DemandFollowingControl, plant_config, slc_topology)

        prob.set_val("slc.ng1_rated_electricity_production", 80000)
        prob.set_val("slc.ng2_rated_electricity_production", 40000)
        prob.run_model()

        sp1 = prob.get_val("slc.ng1_electricity_set_point")
        sp2 = prob.get_val("slc.ng2_electricity_set_point")
        np.testing.assert_allclose(sp1, 25000)
        np.testing.assert_allclose(sp2, 25000)

    def test_flexible_reduces_demand(self):
        tech_connections = [
            ["wind", "combiner", "electricity", "cable"],
            ["ng", "combiner", "electricity", "cable"],
            ["combiner", "demand", "electricity", "cable"],
        ]
        plant_config = _build_plant_config(tech_connections)
        tech_graph = _build_technology_graph(tech_connections)
        tech_control_classifiers = _build_tech_control_classifiers(
            flexible=["wind"], dispatchable=["ng"]
        )
        slc_topology = _build_slc_topology(tech_graph, tech_control_classifiers)
        prob = _build_problem(DemandFollowingControl, plant_config, slc_topology)

        prob.set_val("slc.wind_electricity_out", [30000, 60000, 50000, 10000])
        prob.set_val("slc.wind_rated_electricity_production", 120000)
        prob.set_val("slc.ng_rated_electricity_production", 100000)
        prob.run_model()

        ng_sp = prob.get_val("slc.ng_electricity_set_point")
        # demand=50k, wind outputs [30k,60k,50k,10k] → remaining = max(0, demand-wind)
        expected = np.maximum(50000 - np.array([30000, 60000, 50000, 10000]), 0)
        np.testing.assert_allclose(ng_sp, expected)

    def test_storage_absorbs_surplus(self):
        tech_connections = [
            ["wind", "battery", "electricity", "cable"],
            ["wind", "combiner", "electricity", "cable"],
            ["battery", "combiner", "electricity", "cable"],
            ["ng", "combiner", "electricity", "cable"],
            ["combiner", "demand", "electricity", "cable"],
        ]
        plant_config = _build_plant_config(tech_connections)
        tech_graph = _build_technology_graph(tech_connections)
        tech_control_classifiers = _build_tech_control_classifiers(
            flexible=["wind"], storage=["battery"], dispatchable=["ng"]
        )
        slc_topology = _build_slc_topology(tech_graph, tech_control_classifiers)
        prob = _build_problem(DemandFollowingControl, plant_config, slc_topology)

        prob.set_val("slc.wind_electricity_out", [70000, 30000, 50000, 50000])
        prob.set_val("slc.wind_rated_electricity_production", 120000)
        prob.set_val("slc.battery_electricity_out", [0, 0, 0, 0])
        prob.set_val("slc.battery_rated_electricity_production", 50000)
        prob.set_val("slc.ng_rated_electricity_production", 100000)
        prob.run_model()

        batt_sp = prob.get_val("slc.battery_electricity_set_point")
        # demand - wind = [50k-70k, 50k-30k, 0, 0] = [-20k, 20k, 0, 0]
        expected = np.array([-20000, 20000, 0, 0])
        np.testing.assert_allclose(batt_sp, expected)

    def test_no_techs_runs(self):
        """Controller with no techs should still run without error."""
        plant_config = _build_plant_config([])
        tech_graph = _build_technology_graph([])
        tech_control_classifiers = _build_tech_control_classifiers()
        slc_topology = _build_slc_topology(tech_graph, tech_control_classifiers)
        prob = _build_problem(DemandFollowingControl, plant_config, slc_topology)

        prob.run_model()  # should not raise


# ---------------------------------------------------------------------------
# CostMinimizationControl
# ---------------------------------------------------------------------------
@pytest.mark.unit
class TestCostMinimizationControl:
    """Tests for the merit-order cost-minimization controller."""

    def test_cheapest_dispatched_first(self):
        tech_connections = [
            ["cheap", "combiner", "electricity", "cable"],
            ["expensive", "combiner", "electricity", "cable"],
            ["combiner", "demand", "electricity", "cable"],
        ]
        plant_config = _build_plant_config(
            tech_connections, cost_per_tech={"cheap": 0.03, "expensive": 0.08}
        )
        tech_graph = _build_technology_graph(tech_connections)
        tech_control_classifiers = _build_tech_control_classifiers(
            dispatchable=["cheap", "expensive"]
        )
        slc_topology = _build_slc_topology(tech_graph, tech_control_classifiers)
        prob = _build_problem(CostMinimizationControl, plant_config, slc_topology, demand=50000)

        prob.set_val("slc.cheap_rated_electricity_production", 80000)
        prob.set_val("slc.expensive_rated_electricity_production", 40000)
        prob.run_model()

        cheap_sp = prob.get_val("slc.cheap_electricity_set_point")
        expensive_sp = prob.get_val("slc.expensive_electricity_set_point")
        # Cheap can handle all 50k (rated 80k), so expensive gets 0
        np.testing.assert_allclose(cheap_sp, 50000)
        np.testing.assert_allclose(expensive_sp, 0)

    def test_overflow_to_expensive(self):
        tech_connections = [
            ["cheap", "combiner", "electricity", "cable"],
            ["expensive", "combiner", "electricity", "cable"],
            ["combiner", "demand", "electricity", "cable"],
        ]
        plant_config = _build_plant_config(
            tech_connections, cost_per_tech={"cheap": 0.03, "expensive": 0.08}
        )
        tech_graph = _build_technology_graph(tech_connections)
        tech_control_classifiers = _build_tech_control_classifiers(
            dispatchable=["cheap", "expensive"]
        )
        slc_topology = _build_slc_topology(tech_graph, tech_control_classifiers)
        prob = _build_problem(CostMinimizationControl, plant_config, slc_topology, demand=50000)

        prob.set_val("slc.cheap_rated_electricity_production", 30000)
        prob.set_val("slc.expensive_rated_electricity_production", 40000)
        prob.run_model()

        cheap_sp = prob.get_val("slc.cheap_electricity_set_point")
        expensive_sp = prob.get_val("slc.expensive_electricity_set_point")
        # Cheap maxes at 30k, expensive picks up remaining 20k
        np.testing.assert_allclose(cheap_sp, 30000)
        np.testing.assert_allclose(expensive_sp, 20000)

    def test_with_flexible_reduces_dispatch(self):
        tech_connections = [
            ["wind", "combiner", "electricity", "cable"],
            ["ng", "combiner", "electricity", "cable"],
            ["combiner", "demand", "electricity", "cable"],
        ]
        plant_config = _build_plant_config(tech_connections, cost_per_tech={"ng": 0.05})
        tech_graph = _build_technology_graph(tech_connections)
        tech_control_classifiers = _build_tech_control_classifiers(
            flexible=["wind"], dispatchable=["ng"]
        )
        slc_topology = _build_slc_topology(tech_graph, tech_control_classifiers)
        prob = _build_problem(CostMinimizationControl, plant_config, slc_topology, demand=50000)

        prob.set_val("slc.wind_electricity_out", [40000, 40000, 40000, 40000])
        prob.set_val("slc.wind_rated_electricity_production", 120000)
        prob.set_val("slc.ng_rated_electricity_production", 100000)
        prob.run_model()

        ng_sp = prob.get_val("slc.ng_electricity_set_point")
        # demand 50k - wind 40k = 10k remaining
        np.testing.assert_allclose(ng_sp, 10000)


# ---------------------------------------------------------------------------
# ProfitMaximizationControl
# ---------------------------------------------------------------------------
@pytest.mark.unit
class TestProfitMaximizationControl:
    """Tests for the profit-maximization controller."""

    def test_unprofitable_tech_not_dispatched(self):
        tech_connections = [
            ["cheap", "combiner", "electricity", "cable"],
            ["expensive", "combiner", "electricity", "cable"],
            ["combiner", "demand", "electricity", "cable"],
        ]
        plant_config = _build_plant_config(
            tech_connections, sell_price=0.06, cost_per_tech={"cheap": 0.03, "expensive": 0.08}
        )
        tech_graph = _build_technology_graph(tech_connections)
        tech_control_classifiers = _build_tech_control_classifiers(
            dispatchable=["cheap", "expensive"]
        )
        slc_topology = _build_slc_topology(tech_graph, tech_control_classifiers)
        prob = _build_problem(ProfitMaximizationControl, plant_config, slc_topology, demand=50000)

        prob.set_val("slc.cheap_rated_electricity_production", 30000)
        prob.set_val("slc.expensive_rated_electricity_production", 40000)
        prob.set_val("slc.commodity_sell_price", 0.06)
        prob.run_model()

        cheap_sp = prob.get_val("slc.cheap_electricity_set_point")
        expensive_sp = prob.get_val("slc.expensive_electricity_set_point")
        # Cheap (0.03 < 0.06) dispatched up to rated 30k
        # Expensive (0.08 >= 0.06) NOT dispatched, demand unmet
        np.testing.assert_allclose(cheap_sp, 30000)
        np.testing.assert_allclose(expensive_sp, 0)

    def test_all_profitable(self):
        tech_connections = [
            ["a", "combiner", "electricity", "cable"],
            ["b", "combiner", "electricity", "cable"],
            ["combiner", "demand", "electricity", "cable"],
        ]
        plant_config = _build_plant_config(
            tech_connections, sell_price=0.10, cost_per_tech={"a": 0.03, "b": 0.05}
        )
        tech_graph = _build_technology_graph(tech_connections)
        tech_control_classifiers = _build_tech_control_classifiers(dispatchable=["a", "b"])
        slc_topology = _build_slc_topology(tech_graph, tech_control_classifiers)
        prob = _build_problem(ProfitMaximizationControl, plant_config, slc_topology, demand=50000)

        prob.set_val("slc.a_rated_electricity_production", 80000)
        prob.set_val("slc.b_rated_electricity_production", 40000)
        prob.set_val("slc.commodity_sell_price", 0.10)
        prob.run_model()

        a_sp = prob.get_val("slc.a_electricity_set_point")
        b_sp = prob.get_val("slc.b_electricity_set_point")
        # Both profitable, cheapest first: a gets 50k (rated 80k), b gets 0
        np.testing.assert_allclose(a_sp, 50000)
        np.testing.assert_allclose(b_sp, 0)

    def test_none_profitable(self):
        tech_connections = [
            ["ng", "demand", "electricity", "cable"],
        ]
        plant_config = _build_plant_config(
            tech_connections, sell_price=0.01, cost_per_tech={"ng": 0.05}
        )
        tech_graph = _build_technology_graph(tech_connections)
        tech_control_classifiers = _build_tech_control_classifiers(dispatchable=["ng"])
        slc_topology = _build_slc_topology(tech_graph, tech_control_classifiers)
        prob = _build_problem(ProfitMaximizationControl, plant_config, slc_topology, demand=50000)

        prob.set_val("slc.ng_rated_electricity_production", 100000)
        prob.set_val("slc.commodity_sell_price", 0.01)
        prob.run_model()

        ng_sp = prob.get_val("slc.ng_electricity_set_point")
        # NG cost (0.05) >= sell price (0.01), not dispatched
        np.testing.assert_allclose(ng_sp, 0)

    def test_sell_price_from_config(self):
        tech_connections = [
            ["ng", "demand", "electricity", "cable"],
        ]
        plant_config = _build_plant_config(
            tech_connections, sell_price=0.10, cost_per_tech={"ng": 0.03}
        )
        tech_graph = _build_technology_graph(tech_connections)
        tech_control_classifiers = _build_tech_control_classifiers(dispatchable=["ng"])
        slc_topology = _build_slc_topology(tech_graph, tech_control_classifiers)
        prob = _build_problem(ProfitMaximizationControl, plant_config, slc_topology, demand=50000)

        prob.set_val("slc.ng_rated_electricity_production", 100000)
        # Don't set sell_price explicitly — should use config default 0.10
        prob.run_model()

        ng_sp = prob.get_val("slc.ng_electricity_set_point")
        # Config sell_price=0.10 > marginal 0.03 → dispatched
        np.testing.assert_allclose(ng_sp, 50000)

    def test_time_varying_sell_price(self):
        tech_connections = [
            ["ng", "demand", "electricity", "cable"],
        ]
        plant_config = _build_plant_config(
            tech_connections, sell_price=0.06, cost_per_tech={"ng": 0.05}
        )
        tech_graph = _build_technology_graph(tech_connections)
        tech_control_classifiers = _build_tech_control_classifiers(dispatchable=["ng"])
        slc_topology = _build_slc_topology(tech_graph, tech_control_classifiers)
        prob = _build_problem(ProfitMaximizationControl, plant_config, slc_topology, demand=50000)

        prob.set_val("slc.ng_rated_electricity_production", 100000)
        # Sell price varies: 2 profitable hours, 2 unprofitable
        prob.set_val("slc.commodity_sell_price", [0.08, 0.03, 0.10, 0.02])
        prob.run_model()

        ng_sp = prob.get_val("slc.ng_electricity_set_point")
        # mc=0.05: profitable when sell>0.05 (hours 0,2), not when sell<0.05 (hours 1,3)
        np.testing.assert_allclose(ng_sp, [50000, 0, 50000, 0])

    def test_buy_price_scalar(self):
        """buy_price mode with a scalar buy price from tech config."""
        tech_config = {
            "technologies": {
                "grid": {
                    "model_inputs": {
                        "cost_parameters": {"electricity_buy_price": 0.04},
                    }
                }
            }
        }

        tech_connections = [
            ["grid", "demand", "electricity", "cable"],
        ]
        plant_config = _build_plant_config(
            tech_connections, sell_price=0.10, cost_per_tech={"grid": "buy_price"}
        )
        tech_graph = _build_technology_graph(tech_connections)
        tech_control_classifiers = _build_tech_control_classifiers(dispatchable=["grid"])
        slc_topology = _build_slc_topology(tech_graph, tech_control_classifiers)
        prob = _build_problem(
            ProfitMaximizationControl,
            plant_config,
            slc_topology,
            demand=50000,
            tech_config=tech_config,
        )

        prob.set_val("slc.electricity_demand", 50000)
        prob.set_val("slc.grid_rated_electricity_production", 100000)
        prob.set_val("slc.commodity_sell_price", 0.10)
        prob.run_model()

        grid_sp = prob.get_val("slc.grid_electricity_set_point")
        # buy_price=0.04 < sell_price=0.10 → dispatched
        np.testing.assert_allclose(grid_sp, 50000)

    def test_buy_price_time_varying(self):
        """buy_price mode with time-varying prices (override via set_val)."""

        tech_config = {
            "technologies": {
                "grid": {
                    "model_inputs": {
                        "cost_parameters": {"electricity_buy_price": 0.04},
                    }
                }
            }
        }
        tech_connections = [
            ["grid", "demand", "electricity", "cable"],
        ]
        plant_config = _build_plant_config(
            tech_connections, sell_price=0.06, cost_per_tech={"grid": "buy_price"}
        )
        tech_graph = _build_technology_graph(tech_connections)
        tech_control_classifiers = _build_tech_control_classifiers(dispatchable=["grid"])
        slc_topology = _build_slc_topology(tech_graph, tech_control_classifiers)
        prob = _build_problem(
            ProfitMaximizationControl,
            plant_config,
            slc_topology,
            demand=50000,
            tech_config=tech_config,
        )

        prob.set_val("slc.electricity_demand", 50000)
        prob.set_val("slc.grid_rated_electricity_production", 100000)
        prob.set_val("slc.commodity_sell_price", 0.06)
        # Time-varying buy price: profitable at hours 0,2; unprofitable at hours 1,3
        prob.set_val("slc.grid_buy_price", [0.03, 0.08, 0.04, 0.09])
        prob.run_model()

        grid_sp = prob.get_val("slc.grid_electricity_set_point")
        np.testing.assert_allclose(grid_sp, [50000, 0, 50000, 0])

    def test_varopex_mode(self):
        """VarOpEx mode computes marginal cost from VarOpEx / production."""
        tech_connections = [
            ["gen", "demand", "electricity", "cable"],
        ]
        plant_config = _build_plant_config(
            tech_connections, sell_price=0.10, cost_per_tech={"gen": "VarOpEx"}
        )
        tech_graph = _build_technology_graph(tech_connections)
        tech_control_classifiers = _build_tech_control_classifiers(dispatchable=["gen"])
        slc_topology = _build_slc_topology(tech_graph, tech_control_classifiers)
        prob = _build_problem(CostMinimizationControl, plant_config, slc_topology, demand=50000)

        prob.set_val("slc.gen_rated_electricity_production", 100000)
        # Set VarOpEx ($/year, shape=plant_life=30) and production
        prob.set_val("slc.gen_VarOpEx", np.full(30, 500000.0))
        # Simulate 4 hours of 100 MW production → 400 MWh
        prob.set_val("slc.gen_electricity_out", np.full(4, 100000.0))
        prob.run_model()

        gen_sp = prob.get_val("slc.gen_electricity_set_point")
        # VarOpEx=500k $/yr, production=100MW*4h=400MWh over 4h
        # Annual production = 400 MWh / (4/8760) = 876,000 MWh
        # mc = 500k / 876k ≈ 0.571 $/MWh ≈ 0.000571 $/kWh
        # This is very cheap, so it should be dispatched fully
        np.testing.assert_allclose(gen_sp, 50000)

    def test_cost_per_tech_default_zero(self):
        """Techs not listed in cost_per_tech default to zero marginal cost."""

        tech_connections = [
            ["ng", "demand", "electricity", "cable"],
        ]
        plant_config = _build_plant_config(tech_connections, sell_price=0.10, cost_per_tech={})
        tech_graph = _build_technology_graph(tech_connections)
        tech_control_classifiers = _build_tech_control_classifiers(dispatchable=["ng"])
        slc_topology = _build_slc_topology(tech_graph, tech_control_classifiers)
        prob = _build_problem(ProfitMaximizationControl, plant_config, slc_topology, demand=50000)

        prob.set_val("slc.ng_rated_electricity_production", 100000)
        prob.set_val("slc.commodity_sell_price", 0.10)
        prob.run_model()

        ng_sp = prob.get_val("slc.ng_electricity_set_point")
        # mc=0.0 < sell_price=0.10 → dispatched
        np.testing.assert_allclose(ng_sp, 50000)

    def test_feedstock_single(self):
        """feedstock mode: single upstream feedstock drives marginal cost."""

        tech_connections = [
            ["ng_feed", "ng_plant", "natural_gas", "pipe"],
            ["ng_plant", "demand", "electricity", "cable"],
        ]
        plant_config = _build_plant_config(
            tech_connections, sell_price=0.10, cost_per_tech={"ng_plant": "feedstock"}
        )
        tech_graph = _build_technology_graph(tech_connections)
        tech_control_classifiers = _build_tech_control_classifiers(
            dispatchable=["ng_plant"], feedstock=["ng_feed"]
        )
        slc_topology = _build_slc_topology(tech_graph, tech_control_classifiers)
        prob = _build_problem(CostMinimizationControl, plant_config, slc_topology, demand=50000)

        prob.set_val("slc.ng_plant_rated_electricity_production", 100000)
        # Feedstock VarOpEx: $1M/yr; production: 100 MW * 4 h = 400 MWh
        prob.set_val("slc.ng_feed_VarOpEx", np.full(30, 1_000_000.0))
        prob.set_val("slc.ng_plant_electricity_out", np.full(4, 100000.0))
        prob.run_model()

        sp = prob.get_val("slc.ng_plant_electricity_set_point")
        # Annual production = 400 MWh / (4/8760) = 876,000 MWh
        # mc = 1M / 876k ≈ 1.14 $/MWh ≈ 0.00114 $/kWh → very cheap
        np.testing.assert_allclose(sp, 50000)

    def test_feedstock_multiple(self):
        """feedstock mode: multiple upstream feedstocks are summed."""
        tech_connections = [
            ["feed_a", "plant", "gas_a", "pipe"],
            ["feed_b", "plant", "gas_b", "pipe"],
            ["other_tech", "plant", "something", "cable"],
            ["plant", "demand", "electricity", "cable"],
        ]

        plant_config = _build_plant_config(
            tech_connections, sell_price=0.10, cost_per_tech={"plant": "feedstock"}
        )
        tech_graph = _build_technology_graph(tech_connections)
        tech_control_classifiers = _build_tech_control_classifiers(
            dispatchable=["plant"], feedstock=["feed_a", "feed_b"]
        )
        slc_topology = _build_slc_topology(tech_graph, tech_control_classifiers)
        prob = _build_problem(CostMinimizationControl, plant_config, slc_topology, demand=50000)

        prob.set_val("slc.plant_rated_electricity_production", 100000)
        # Two feedstocks: $500k and $300k → total $800k/yr
        prob.set_val("slc.feed_a_VarOpEx", np.full(30, 500_000.0))
        prob.set_val("slc.feed_b_VarOpEx", np.full(30, 300_000.0))
        prob.set_val("slc.plant_electricity_out", np.full(4, 100000.0))
        prob.run_model()

        sp = prob.get_val("slc.plant_electricity_set_point")
        # Total VarOpEx = 800k, annual production = 876,000 MWh
        # mc ≈ 0.913 $/MWh ≈ 0.000913 $/kWh → very cheap
        np.testing.assert_allclose(sp, 50000)

    def test_feedstock_profit_max_unprofitable(self):
        """feedstock mode in profit max: unprofitable when feedstock costs exceed sell price."""

        tech_connections = [
            ["ng_feed", "ng_plant", "natural_gas", "pipe"],
            ["ng_plant", "demand", "electricity", "cable"],
        ]
        # use a very low sell price
        plant_config = _build_plant_config(
            tech_connections, sell_price=0.01, cost_per_tech={"ng_plant": "feedstock"}
        )
        tech_graph = _build_technology_graph(tech_connections)
        tech_control_classifiers = _build_tech_control_classifiers(
            dispatchable=["ng_plant"], feedstock=["ng_feed"]
        )
        slc_topology = _build_slc_topology(tech_graph, tech_control_classifiers)
        prob = _build_problem(ProfitMaximizationControl, plant_config, slc_topology, demand=50000)

        prob.set_val("slc.ng_plant_rated_electricity_production", 100000)
        prob.set_val("slc.commodity_sell_price", 0.01)
        # Very expensive feedstock: $100M/yr → high marginal cost
        prob.set_val("slc.ng_feed_VarOpEx", np.full(30, 100_000_000.0))
        prob.set_val("slc.ng_plant_electricity_out", np.full(4, 100000.0))
        prob.run_model()

        sp = prob.get_val("slc.ng_plant_electricity_set_point")
        # mc = 100M / 876k ≈ 114 $/MWh ≈ 0.114 $/kWh > sell 0.01 → NOT dispatched
        np.testing.assert_allclose(sp, 0)

    def test_feedstock_no_feedstock_raises(self):
        """feedstock mode raises ValueError when no feedstock is found upstream."""

        tech_connections = [
            ["some_tech", "ng_plant", "electricity", "cable"],
        ]

        plant_config = _build_plant_config(
            tech_connections, sell_price=0.01, cost_per_tech={"ng_plant": "feedstock"}
        )
        tech_graph = _build_technology_graph(tech_connections)
        tech_control_classifiers = _build_tech_control_classifiers(dispatchable=["ng_plant"])
        slc_topology = _build_slc_topology(tech_graph, tech_control_classifiers)

        with pytest.raises(ValueError, match="at least one feedstock"):
            _build_problem(CostMinimizationControl, plant_config, slc_topology, demand=50000)


# ---------------------------------------------------------------------------
# Heterogeneous-commodity dispatch (backward demand propagation)
# ---------------------------------------------------------------------------
def _tech_config_with_ratios(ratios_by_tech):
    """Build a tech_config carrying static conversion ratios.

    Args:
        ratios_by_tech (dict): Mapping of ``tech_name`` to a dict of
            ``{"<in>_per_<out>": ratio}`` entries.

    Returns:
        dict: A ``tech_config`` with the nested ``model_inputs.
        control_parameters.conversion_ratios`` structure the base class reads.
    """
    return {
        "technologies": {
            tech: {"model_inputs": {"control_parameters": {"conversion_ratios": ratios}}}
            for tech, ratios in ratios_by_tech.items()
        }
    }


def _build_hetero_problem(
    slc_cls,
    plant_config,
    slc_topology,
    tech_config,
    demand,
    upstream_out=None,
    commodity_units=None,
):
    """Build an SLC problem wiring non-demand commodity outputs via IVCs.

    Every ``(tech, commodity)`` output whose commodity differs from the demand
    commodity is fed by an ``IndepVarComp`` and connected into the controller,
    mirroring the real plant connections so ``units_by_conn`` inputs resolve.

    Args:
        slc_cls: Controller class to instantiate.
        plant_config (dict): Plant config.
        slc_topology (dict): SLC topology.
        tech_config (dict): Tech config (carries conversion ratios).
        demand (float | array): Demand-commodity demand profile.
        upstream_out (dict): Optional ``{(tech, commodity): value}`` outputs for
            the wired IVCs (defaults to zero).
        commodity_units (dict): Optional ``{commodity: units}`` for the IVCs.

    Returns:
        om.Problem: A setup problem with the demand value applied.
    """
    upstream_out = upstream_out or {}
    commodity_units = commodity_units or {}
    n_timesteps = plant_config["plant"]["simulation"]["n_timesteps"]
    demand_commodity = slc_topology["demand_commodity"]

    prob = om.Problem()

    ivc_connections = []
    for i, (tech, commodity) in enumerate(sorted(slc_topology["tech_to_commodity"])):
        if commodity == demand_commodity:
            continue
        val = upstream_out.get((tech, commodity), 0.0)
        val = np.full(n_timesteps, val) if np.isscalar(val) else np.asarray(val, dtype=float)
        ivc = prob.model.add_subsystem(f"src{i}", om.IndepVarComp())
        ivc.add_output(f"{tech}_{commodity}_out", val=val, units=commodity_units.get(commodity))
        ivc_connections.append((f"src{i}.{tech}_{commodity}_out", f"slc.{tech}_{commodity}_out"))

    prob.model.add_subsystem(
        "slc",
        slc_cls(
            driver_config={},
            plant_config=plant_config,
            tech_config=tech_config,
            slc_topology=slc_topology,
        ),
    )
    for src, dst in ivc_connections:
        prob.model.connect(src, dst)

    prob.setup()
    prob.set_val(f"slc.{demand_commodity}_demand", demand)
    return prob


@pytest.mark.unit
class TestHeterogeneousCommodityControl:
    """Backward demand propagation across commodity converters."""

    def test_detect_converters_chain(self):
        """Converters are detected across a grid -> electrolyzer -> synloop chain."""
        tech_connections = [
            ["grid", "electrolyzer", "electricity", "cable"],
            ["electrolyzer", "synloop", "hydrogen", "pipe"],
            ["synloop", "demand", "ammonia", "pipe"],
        ]
        plant_config = _build_plant_config(tech_connections)
        tech_graph = _build_technology_graph(tech_connections)
        classifiers = _build_tech_control_classifiers(
            dispatchable=["grid", "electrolyzer", "synloop"]
        )
        slc_topology = _build_slc_topology(
            tech_graph, classifiers, demand_commodity="ammonia", demand_commodity_rate_units="kg/h"
        )
        tech_config = _tech_config_with_ratios(
            {
                "electrolyzer": {"electricity_per_hydrogen": 51.0},
                "synloop": {"hydrogen_per_ammonia": 0.18},
            }
        )
        prob = _build_hetero_problem(
            DemandFollowingControl,
            plant_config,
            slc_topology,
            tech_config,
            demand=100.0,
            commodity_units={"electricity": "kW", "hydrogen": "kg/h"},
        )
        assert prob.model.slc._converters == {
            ("electricity", "electrolyzer", "hydrogen"),
            ("hydrogen", "synloop", "ammonia"),
        }

    def test_single_converter_static_propagation(self):
        """A single converter translates hydrogen demand into electricity demand."""
        tech_connections = [
            ["grid", "electrolyzer", "electricity", "cable"],
            ["electrolyzer", "demand", "hydrogen", "pipe"],
        ]
        plant_config = _build_plant_config(tech_connections)
        tech_graph = _build_technology_graph(tech_connections)
        classifiers = _build_tech_control_classifiers(dispatchable=["grid", "electrolyzer"])
        slc_topology = _build_slc_topology(
            tech_graph,
            classifiers,
            demand_commodity="hydrogen",
            demand_commodity_rate_units="kg/h",
        )
        tech_config = _tech_config_with_ratios({"electrolyzer": {"electricity_per_hydrogen": 51.0}})
        prob = _build_hetero_problem(
            DemandFollowingControl,
            plant_config,
            slc_topology,
            tech_config,
            demand=100.0,
            commodity_units={"electricity": "kW"},
        )
        prob.set_val("slc.grid_rated_electricity_production", 1e9)
        prob.set_val("slc.electrolyzer_rated_hydrogen_production", 1e6)
        prob.run_model()

        np.testing.assert_allclose(prob.get_val("slc.electrolyzer_hydrogen_set_point"), 100.0)
        np.testing.assert_allclose(prob.get_val("slc.grid_electricity_set_point"), 100.0 * 51.0)

    def test_chained_converter_static_propagation(self):
        """Demand propagates through a two-converter chain to the electricity source."""
        tech_connections = [
            ["grid", "electrolyzer", "electricity", "cable"],
            ["electrolyzer", "synloop", "hydrogen", "pipe"],
            ["synloop", "demand", "ammonia", "pipe"],
        ]
        plant_config = _build_plant_config(tech_connections)
        tech_graph = _build_technology_graph(tech_connections)
        classifiers = _build_tech_control_classifiers(
            dispatchable=["grid", "electrolyzer", "synloop"]
        )
        slc_topology = _build_slc_topology(
            tech_graph,
            classifiers,
            demand_commodity="ammonia",
            demand_commodity_rate_units="kg/h",
        )
        tech_config = _tech_config_with_ratios(
            {
                "electrolyzer": {"electricity_per_hydrogen": 51.0},
                "synloop": {"hydrogen_per_ammonia": 0.18},
            }
        )
        prob = _build_hetero_problem(
            DemandFollowingControl,
            plant_config,
            slc_topology,
            tech_config,
            demand=100.0,
            commodity_units={"electricity": "kW", "hydrogen": "kg/h"},
        )
        prob.set_val("slc.grid_rated_electricity_production", 1e9)
        prob.set_val("slc.electrolyzer_rated_hydrogen_production", 1e6)
        prob.set_val("slc.synloop_rated_ammonia_production", 1e6)
        prob.run_model()

        np.testing.assert_allclose(prob.get_val("slc.synloop_ammonia_set_point"), 100.0)
        np.testing.assert_allclose(
            prob.get_val("slc.electrolyzer_hydrogen_set_point"), 100.0 * 0.18
        )
        np.testing.assert_allclose(
            prob.get_val("slc.grid_electricity_set_point"), 100.0 * 0.18 * 51.0
        )

    def test_derived_demand_reuses_flexible_and_dispatchable(self):
        """Derived electricity demand flows through the shared flexible/dispatchable steps."""
        tech_connections = [
            ["wind", "electrolyzer", "electricity", "cable"],
            ["grid", "electrolyzer", "electricity", "cable"],
            ["electrolyzer", "demand", "hydrogen", "pipe"],
        ]
        plant_config = _build_plant_config(tech_connections)
        tech_graph = _build_technology_graph(tech_connections)
        classifiers = _build_tech_control_classifiers(
            flexible=["wind"], dispatchable=["grid", "electrolyzer"]
        )
        slc_topology = _build_slc_topology(
            tech_graph,
            classifiers,
            demand_commodity="hydrogen",
            demand_commodity_rate_units="kg/h",
        )
        tech_config = _tech_config_with_ratios({"electrolyzer": {"electricity_per_hydrogen": 50.0}})
        prob = _build_hetero_problem(
            DemandFollowingControl,
            plant_config,
            slc_topology,
            tech_config,
            demand=100.0,
            upstream_out={("wind", "electricity"): 1000.0},
            commodity_units={"electricity": "kW"},
        )
        prob.set_val("slc.wind_rated_electricity_production", 2000.0)
        prob.set_val("slc.grid_rated_electricity_production", 1e9)
        prob.set_val("slc.electrolyzer_rated_hydrogen_production", 1e6)
        prob.run_model()

        # Derived electricity demand = 100 kg/h * 50 kWh/kg = 5000 kW
        # Flexible wind runs at rated (2000 kW), curtailing 5000 - 1000 = 4000 kW of demand
        np.testing.assert_allclose(prob.get_val("slc.electrolyzer_hydrogen_set_point"), 100.0)
        np.testing.assert_allclose(prob.get_val("slc.wind_electricity_set_point"), 2000.0)
        np.testing.assert_allclose(prob.get_val("slc.grid_electricity_set_point"), 4000.0)

    def test_missing_ratio_warns_and_keeps_legacy_dispatch(self):
        """A converter without a ratio warns once and skips propagation."""
        tech_connections = [
            ["grid", "electrolyzer", "electricity", "cable"],
            ["electrolyzer", "demand", "hydrogen", "pipe"],
        ]
        plant_config = _build_plant_config(tech_connections)
        tech_graph = _build_technology_graph(tech_connections)
        classifiers = _build_tech_control_classifiers(dispatchable=["grid", "electrolyzer"])
        slc_topology = _build_slc_topology(
            tech_graph,
            classifiers,
            demand_commodity="hydrogen",
            demand_commodity_rate_units="kg/h",
        )
        prob = _build_hetero_problem(
            DemandFollowingControl,
            plant_config,
            slc_topology,
            tech_config={},
            demand=100.0,
            commodity_units={"electricity": "kW"},
        )
        prob.set_val("slc.grid_rated_electricity_production", 1e9)
        prob.set_val("slc.electrolyzer_rated_hydrogen_production", 1e6)

        with pytest.warns(UserWarning, match="No conversion ratio"):
            prob.run_model()

        # Hydrogen demand is still met; electricity is not driven (keeps default set-point)
        np.testing.assert_allclose(prob.get_val("slc.electrolyzer_hydrogen_set_point"), 100.0)
        np.testing.assert_allclose(prob.get_val("slc.grid_electricity_set_point"), 1.0)

    def test_cost_min_merit_order_at_derived_level(self):
        """Merit order applies to derived electricity demand under cost minimization."""
        tech_connections = [
            ["cheap", "electrolyzer", "electricity", "cable"],
            ["expensive", "electrolyzer", "electricity", "cable"],
            ["electrolyzer", "demand", "hydrogen", "pipe"],
        ]
        plant_config = _build_plant_config(
            tech_connections, cost_per_tech={"cheap": 0.03, "expensive": 0.08}
        )
        tech_graph = _build_technology_graph(tech_connections)
        classifiers = _build_tech_control_classifiers(
            dispatchable=["cheap", "expensive", "electrolyzer"]
        )
        slc_topology = _build_slc_topology(
            tech_graph,
            classifiers,
            demand_commodity="hydrogen",
            demand_commodity_rate_units="kg/h",
        )
        tech_config = _tech_config_with_ratios({"electrolyzer": {"electricity_per_hydrogen": 50.0}})
        prob = _build_hetero_problem(
            CostMinimizationControl,
            plant_config,
            slc_topology,
            tech_config,
            demand=100.0,
            commodity_units={"electricity": "kW"},
        )
        prob.set_val("slc.cheap_rated_electricity_production", 3000.0)
        prob.set_val("slc.expensive_rated_electricity_production", 5000.0)
        prob.set_val("slc.electrolyzer_rated_hydrogen_production", 1e6)
        prob.run_model()

        # Derived electricity demand = 5000 kW; cheapest tech fills first
        np.testing.assert_allclose(prob.get_val("slc.electrolyzer_hydrogen_set_point"), 100.0)
        np.testing.assert_allclose(prob.get_val("slc.cheap_electricity_set_point"), 3000.0)
        np.testing.assert_allclose(prob.get_val("slc.expensive_electricity_set_point"), 2000.0)

    def test_dynamic_ratio_overrides_static(self):
        """Measured consumption drives the ratio, overriding the static tech-config value."""
        tech_connections = [
            ["grid", "electrolyzer", "electricity", "cable"],
            ["electrolyzer", "demand", "hydrogen", "pipe"],
        ]
        plant_config = _build_plant_config(tech_connections)
        tech_graph = _build_technology_graph(tech_connections)
        classifiers = _build_tech_control_classifiers(dispatchable=["grid", "electrolyzer"])
        slc_topology = _build_slc_topology(
            tech_graph,
            classifiers,
            demand_commodity="hydrogen",
            demand_commodity_rate_units="kg/h",
        )
        # Static ratio is 50, but the measured ratio (5100 / 100 = 51) should win.
        tech_config = _tech_config_with_ratios({"electrolyzer": {"electricity_per_hydrogen": 50.0}})
        prob = _build_hetero_problem(
            DemandFollowingControl,
            plant_config,
            slc_topology,
            tech_config,
            demand=100.0,
            commodity_units={"electricity": "kW"},
        )
        prob.set_val("slc.grid_rated_electricity_production", 1e9)
        prob.set_val("slc.electrolyzer_rated_hydrogen_production", 1e6)
        prob.set_val("slc.electrolyzer_hydrogen_out", 100.0)
        prob.set_val("slc.electrolyzer_electricity_consumed", 5100.0)
        prob.run_model()

        np.testing.assert_allclose(prob.get_val("slc.grid_electricity_set_point"), 100.0 * 51.0)

    def test_dynamic_ratio_time_varying_with_zero_output_fallback(self):
        """Per-timestep measured ratios apply; a zero-output timestep falls back to static."""
        tech_connections = [
            ["grid", "electrolyzer", "electricity", "cable"],
            ["electrolyzer", "demand", "hydrogen", "pipe"],
        ]
        plant_config = _build_plant_config(tech_connections)
        tech_graph = _build_technology_graph(tech_connections)
        classifiers = _build_tech_control_classifiers(dispatchable=["grid", "electrolyzer"])
        slc_topology = _build_slc_topology(
            tech_graph,
            classifiers,
            demand_commodity="hydrogen",
            demand_commodity_rate_units="kg/h",
        )
        tech_config = _tech_config_with_ratios({"electrolyzer": {"electricity_per_hydrogen": 50.0}})
        prob = _build_hetero_problem(
            DemandFollowingControl,
            plant_config,
            slc_topology,
            tech_config,
            demand=100.0,
            commodity_units={"electricity": "kW"},
        )
        prob.set_val("slc.grid_rated_electricity_production", 1e9)
        prob.set_val("slc.electrolyzer_rated_hydrogen_production", 1e6)
        # Third timestep produces no hydrogen, so its ratio falls back to the static 50.
        prob.set_val("slc.electrolyzer_hydrogen_out", [100.0, 100.0, 0.0, 100.0])
        prob.set_val("slc.electrolyzer_electricity_consumed", [5100.0, 4000.0, 9999.0, 6000.0])
        prob.run_model()

        # ratio = [51, 40, 50 (fallback), 60]; derived electricity = 100 * ratio
        np.testing.assert_allclose(
            prob.get_val("slc.grid_electricity_set_point"), [5100.0, 4000.0, 5000.0, 6000.0]
        )

    def test_dynamic_ratio_without_static_does_not_warn(self):
        """A connected consumption signal enables propagation with no static ratio or warning."""
        tech_connections = [
            ["grid", "electrolyzer", "electricity", "cable"],
            ["electrolyzer", "demand", "hydrogen", "pipe"],
        ]
        plant_config = _build_plant_config(tech_connections)
        tech_graph = _build_technology_graph(tech_connections)
        classifiers = _build_tech_control_classifiers(dispatchable=["grid", "electrolyzer"])
        slc_topology = _build_slc_topology(
            tech_graph,
            classifiers,
            demand_commodity="hydrogen",
            demand_commodity_rate_units="kg/h",
        )
        prob = _build_hetero_problem(
            DemandFollowingControl,
            plant_config,
            slc_topology,
            tech_config={},
            demand=100.0,
            commodity_units={"electricity": "kW"},
        )
        prob.set_val("slc.grid_rated_electricity_production", 1e9)
        prob.set_val("slc.electrolyzer_rated_hydrogen_production", 1e6)
        prob.set_val("slc.electrolyzer_hydrogen_out", 100.0)
        prob.set_val("slc.electrolyzer_electricity_consumed", 5100.0)

        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            prob.run_model()

        assert not any("No conversion ratio" in str(w.message) for w in caught)
        np.testing.assert_allclose(prob.get_val("slc.grid_electricity_set_point"), 100.0 * 51.0)
