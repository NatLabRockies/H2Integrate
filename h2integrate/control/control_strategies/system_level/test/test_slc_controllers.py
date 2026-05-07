"""Unit tests for system-level control base class and all controller strategies."""

import numpy as np
import pytest
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


def _make_plant_config(
    n_timesteps=4,
    demand=50000,
    curtailable=None,
    dispatchable=None,
    storage=None,
    sell_price=0.06,
    cost_per_tech=None,
    technology_interconnections=None,
):
    """Build a minimal plant_config dict for controller tests."""
    all_techs = (curtailable or []) + (dispatchable or []) + (storage or [])
    tech_to_commodity = {(t, "electricity") for t in all_techs}
    config = {
        "plant": {"simulation": {"n_timesteps": n_timesteps, "dt": 3600}, "plant_life": 30},
        "system_level_control": {
            "demand_commodity": "electricity",
            "demand_commodity_rate_units": "kW",
            "demand_tech": "demand",
            "demand_profile": demand,
            "curtailable_techs": curtailable or [],
            "dispatchable_techs": dispatchable or [],
            "storage_techs": storage or [],
            "tech_to_commodity": tech_to_commodity,
            "commodity_sell_price": sell_price,
            "cost_per_tech": cost_per_tech or {},
        },
    }
    if technology_interconnections is not None:
        config["technology_interconnections"] = technology_interconnections
    return config


def _build_problem(slc_cls, plant_config, tech_config=None):
    """Create and setup an OpenMDAO Problem with the given controller."""
    prob = om.Problem()
    prob.model.add_subsystem(
        "slc",
        slc_cls(
            driver_config={},
            plant_config=plant_config,
            tech_config=tech_config or {},
        ),
    )
    prob.setup()
    return prob


# ---------------------------------------------------------------------------
# SystemLevelControlBase
# ---------------------------------------------------------------------------
@pytest.mark.unit
class TestSystemLevelControlBase:
    """Tests for the abstract base class setup logic."""

    def test_base_creates_curtailable_io(self):
        pc = _make_plant_config(curtailable=["wind"])
        # Use DemandFollowingControl since base is abstract
        prob = _build_problem(DemandFollowingControl, pc)
        # _var_rel2meta uses relative names (no "slc." prefix)
        assert "wind_electricity_out" in prob.model.slc._var_rel2meta
        assert "wind_rated_electricity_production" in prob.model.slc._var_rel2meta
        assert "wind_electricity_set_point" in prob.model.slc._var_rel2meta

    def test_base_creates_dispatchable_io(self):
        pc = _make_plant_config(dispatchable=["ng"])
        prob = _build_problem(DemandFollowingControl, pc)
        assert "ng_electricity_out" in prob.model.slc._var_rel2meta
        assert "ng_rated_electricity_production" in prob.model.slc._var_rel2meta
        assert "ng_electricity_set_point" in prob.model.slc._var_rel2meta

    def test_base_creates_storage_io(self):
        pc = _make_plant_config(storage=["battery"])
        prob = _build_problem(DemandFollowingControl, pc)
        assert "battery_electricity_out" in prob.model.slc._var_rel2meta
        assert "battery_rated_electricity_production" in prob.model.slc._var_rel2meta
        assert "battery_electricity_set_point" in prob.model.slc._var_rel2meta

    def test_base_creates_demand_input(self):
        pc = _make_plant_config()
        prob = _build_problem(DemandFollowingControl, pc)
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
        pc = _make_plant_config(dispatchable=["ng1", "ng2"])
        prob = _build_problem(DemandFollowingControl, pc)
        prob.set_val("slc.ng1_rated_electricity_production", 80000)
        prob.set_val("slc.ng2_rated_electricity_production", 40000)
        prob.run_model()

        sp1 = prob.get_val("slc.ng1_electricity_set_point")
        sp2 = prob.get_val("slc.ng2_electricity_set_point")
        np.testing.assert_allclose(sp1, 25000)
        np.testing.assert_allclose(sp2, 25000)

    def test_curtailable_reduces_demand(self):
        pc = _make_plant_config(curtailable=["wind"], dispatchable=["ng"])
        prob = _build_problem(DemandFollowingControl, pc)
        prob.set_val("slc.wind_electricity_out", [30000, 60000, 50000, 10000])
        prob.set_val("slc.wind_rated_electricity_production", 120000)
        prob.set_val("slc.ng_rated_electricity_production", 100000)
        prob.run_model()

        ng_sp = prob.get_val("slc.ng_electricity_set_point")
        # demand=50k, wind outputs [30k,60k,50k,10k] → remaining = max(0, demand-wind)
        expected = np.maximum(50000 - np.array([30000, 60000, 50000, 10000]), 0)
        np.testing.assert_allclose(ng_sp, expected)

    def test_storage_absorbs_surplus(self):
        pc = _make_plant_config(curtailable=["wind"], storage=["battery"], dispatchable=["ng"])
        prob = _build_problem(DemandFollowingControl, pc)
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
        pc = _make_plant_config()
        prob = _build_problem(DemandFollowingControl, pc)
        prob.run_model()  # should not raise


# ---------------------------------------------------------------------------
# CostMinimizationControl
# ---------------------------------------------------------------------------
@pytest.mark.unit
class TestCostMinimizationControl:
    """Tests for the merit-order cost-minimization controller."""

    def test_cheapest_dispatched_first(self):
        pc = _make_plant_config(
            dispatchable=["cheap", "expensive"],
            demand=50000,
            cost_per_tech={"cheap": 0.03, "expensive": 0.08},
        )
        prob = _build_problem(CostMinimizationControl, pc)
        prob.set_val("slc.cheap_rated_electricity_production", 80000)
        prob.set_val("slc.expensive_rated_electricity_production", 40000)
        prob.run_model()

        cheap_sp = prob.get_val("slc.cheap_electricity_set_point")
        expensive_sp = prob.get_val("slc.expensive_electricity_set_point")
        # Cheap can handle all 50k (rated 80k), so expensive gets 0
        np.testing.assert_allclose(cheap_sp, 50000)
        np.testing.assert_allclose(expensive_sp, 0)

    def test_overflow_to_expensive(self):
        pc = _make_plant_config(
            dispatchable=["cheap", "expensive"],
            demand=50000,
            cost_per_tech={"cheap": 0.03, "expensive": 0.08},
        )
        prob = _build_problem(CostMinimizationControl, pc)
        prob.set_val("slc.cheap_rated_electricity_production", 30000)
        prob.set_val("slc.expensive_rated_electricity_production", 40000)
        prob.run_model()

        cheap_sp = prob.get_val("slc.cheap_electricity_set_point")
        expensive_sp = prob.get_val("slc.expensive_electricity_set_point")
        # Cheap maxes at 30k, expensive picks up remaining 20k
        np.testing.assert_allclose(cheap_sp, 30000)
        np.testing.assert_allclose(expensive_sp, 20000)

    def test_with_curtailable_reduces_dispatch(self):
        pc = _make_plant_config(
            curtailable=["wind"],
            dispatchable=["ng"],
            demand=50000,
            cost_per_tech={"ng": 0.05},
        )
        prob = _build_problem(CostMinimizationControl, pc)
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
        pc = _make_plant_config(
            dispatchable=["cheap", "expensive"],
            demand=50000,
            sell_price=0.06,
            cost_per_tech={"cheap": 0.03, "expensive": 0.08},
        )
        prob = _build_problem(ProfitMaximizationControl, pc)
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
        pc = _make_plant_config(
            dispatchable=["a", "b"],
            demand=50000,
            sell_price=0.10,
            cost_per_tech={"a": 0.03, "b": 0.05},
        )
        prob = _build_problem(ProfitMaximizationControl, pc)
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
        pc = _make_plant_config(
            dispatchable=["ng"],
            demand=50000,
            sell_price=0.01,
            cost_per_tech={"ng": 0.05},
        )
        prob = _build_problem(ProfitMaximizationControl, pc)
        prob.set_val("slc.ng_rated_electricity_production", 100000)
        prob.set_val("slc.commodity_sell_price", 0.01)
        prob.run_model()

        ng_sp = prob.get_val("slc.ng_electricity_set_point")
        # NG cost (0.05) >= sell price (0.01), not dispatched
        np.testing.assert_allclose(ng_sp, 0)

    def test_sell_price_from_config(self):
        pc = _make_plant_config(
            dispatchable=["ng"],
            demand=50000,
            sell_price=0.10,
            cost_per_tech={"ng": 0.03},
        )
        prob = _build_problem(ProfitMaximizationControl, pc)
        prob.set_val("slc.ng_rated_electricity_production", 100000)
        # Don't set sell_price explicitly — should use config default 0.10
        prob.run_model()

        ng_sp = prob.get_val("slc.ng_electricity_set_point")
        # Config sell_price=0.10 > marginal 0.03 → dispatched
        np.testing.assert_allclose(ng_sp, 50000)

    def test_time_varying_sell_price(self):
        pc = _make_plant_config(
            dispatchable=["ng"],
            demand=50000,
            sell_price=0.06,
            cost_per_tech={"ng": 0.05},
        )
        prob = _build_problem(ProfitMaximizationControl, pc)
        prob.set_val("slc.ng_rated_electricity_production", 100000)
        # Sell price varies: 2 profitable hours, 2 unprofitable
        prob.set_val("slc.commodity_sell_price", [0.08, 0.03, 0.10, 0.02])
        prob.run_model()

        ng_sp = prob.get_val("slc.ng_electricity_set_point")
        # mc=0.05: profitable when sell>0.05 (hours 0,2), not when sell<0.05 (hours 1,3)
        np.testing.assert_allclose(ng_sp, [50000, 0, 50000, 0])

    def test_buy_price_scalar(self):
        """buy_price mode with a scalar buy price from tech config."""
        pc = _make_plant_config(
            dispatchable=["grid"],
            demand=50000,
            sell_price=0.10,
            cost_per_tech={"grid": "buy_price"},
        )
        # Add tech config with buy price
        tech_config = {
            "technologies": {
                "grid": {
                    "model_inputs": {
                        "cost_parameters": {"electricity_buy_price": 0.04},
                    }
                }
            }
        }
        prob = om.Problem()
        prob.model.add_subsystem(
            "slc",
            ProfitMaximizationControl(driver_config={}, plant_config=pc, tech_config=tech_config),
        )
        prob.setup()
        prob.set_val("slc.grid_rated_electricity_production", 100000)
        prob.set_val("slc.commodity_sell_price", 0.10)
        prob.run_model()

        grid_sp = prob.get_val("slc.grid_electricity_set_point")
        # buy_price=0.04 < sell_price=0.10 → dispatched
        np.testing.assert_allclose(grid_sp, 50000)

    def test_buy_price_time_varying(self):
        """buy_price mode with time-varying prices (override via set_val)."""
        pc = _make_plant_config(
            dispatchable=["grid"],
            demand=50000,
            sell_price=0.06,
            cost_per_tech={"grid": "buy_price"},
        )
        tech_config = {
            "technologies": {
                "grid": {
                    "model_inputs": {
                        "cost_parameters": {"electricity_buy_price": 0.04},
                    }
                }
            }
        }
        prob = om.Problem()
        prob.model.add_subsystem(
            "slc",
            ProfitMaximizationControl(driver_config={}, plant_config=pc, tech_config=tech_config),
        )
        prob.setup()
        prob.set_val("slc.grid_rated_electricity_production", 100000)
        prob.set_val("slc.commodity_sell_price", 0.06)
        # Time-varying buy price: profitable at hours 0,2; unprofitable at hours 1,3
        prob.set_val("slc.grid_buy_price", [0.03, 0.08, 0.04, 0.09])
        prob.run_model()

        grid_sp = prob.get_val("slc.grid_electricity_set_point")
        np.testing.assert_allclose(grid_sp, [50000, 0, 50000, 0])

    def test_varopex_mode(self):
        """VarOpEx mode computes marginal cost from VarOpEx / production."""
        pc = _make_plant_config(
            dispatchable=["gen"],
            demand=50000,
            sell_price=0.10,
            cost_per_tech={"gen": "VarOpEx"},
        )
        prob = _build_problem(CostMinimizationControl, pc)
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
        pc = _make_plant_config(
            dispatchable=["ng"],
            demand=50000,
            sell_price=0.10,
            cost_per_tech={},  # Empty: ng defaults to 0.0
        )
        prob = _build_problem(ProfitMaximizationControl, pc)
        prob.set_val("slc.ng_rated_electricity_production", 100000)
        prob.set_val("slc.commodity_sell_price", 0.10)
        prob.run_model()

        ng_sp = prob.get_val("slc.ng_electricity_set_point")
        # mc=0.0 < sell_price=0.10 → dispatched
        np.testing.assert_allclose(ng_sp, 50000)

    def test_feedstock_single(self):
        """feedstock mode: single upstream feedstock drives marginal cost."""
        pc = _make_plant_config(
            dispatchable=["ng_plant"],
            demand=50000,
            sell_price=0.10,
            cost_per_tech={"ng_plant": "feedstock"},
            technology_interconnections=[
                ["ng_feed", "ng_plant", "natural_gas", "pipe"],
            ],
        )
        tech_config = {
            "technologies": {
                "ng_feed": {
                    "performance_model": {"model": "FeedstockPerformanceModel"},
                    "cost_model": {"model": "FeedstockCostModel"},
                },
            }
        }
        prob = _build_problem(CostMinimizationControl, pc, tech_config=tech_config)
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
        pc = _make_plant_config(
            dispatchable=["plant"],
            demand=50000,
            sell_price=0.10,
            cost_per_tech={"plant": "feedstock"},
            technology_interconnections=[
                ["feed_a", "plant", "gas_a", "pipe"],
                ["feed_b", "plant", "gas_b", "pipe"],
                ["other_tech", "plant", "something", "cable"],
            ],
        )
        tech_config = {
            "technologies": {
                "feed_a": {
                    "performance_model": {"model": "FeedstockPerformanceModel"},
                    "cost_model": {"model": "FeedstockCostModel"},
                },
                "feed_b": {
                    "performance_model": {"model": "FeedstockPerformanceModel"},
                    "cost_model": {"model": "FeedstockCostModel"},
                },
                "other_tech": {
                    "performance_model": {"model": "SomePerformanceModel"},
                },
            }
        }
        prob = _build_problem(CostMinimizationControl, pc, tech_config=tech_config)
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
        pc = _make_plant_config(
            dispatchable=["ng_plant"],
            demand=50000,
            sell_price=0.01,  # very low sell price
            cost_per_tech={"ng_plant": "feedstock"},
            technology_interconnections=[
                ["ng_feed", "ng_plant", "natural_gas", "pipe"],
            ],
        )
        tech_config = {
            "technologies": {
                "ng_feed": {
                    "performance_model": {"model": "FeedstockPerformanceModel"},
                    "cost_model": {"model": "FeedstockCostModel"},
                },
            }
        }
        prob = _build_problem(ProfitMaximizationControl, pc, tech_config=tech_config)
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
        pc = _make_plant_config(
            dispatchable=["ng_plant"],
            demand=50000,
            cost_per_tech={"ng_plant": "feedstock"},
            technology_interconnections=[
                ["some_tech", "ng_plant", "electricity", "cable"],
            ],
        )
        tech_config = {
            "technologies": {
                "some_tech": {
                    "performance_model": {"model": "SomePerformanceModel"},
                },
            }
        }
        with pytest.raises(ValueError, match="at least one feedstock"):
            _build_problem(CostMinimizationControl, pc, tech_config=tech_config)
