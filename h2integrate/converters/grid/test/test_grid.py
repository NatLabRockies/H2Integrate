import numpy as np
import pytest
import openmdao.api as om
from pytest import fixture

from h2integrate.converters.grid.grid import GridCostModel, GridPerformanceModel
from h2integrate.core.h2integrate_model import H2IntegrateModel


@fixture
def plant_config(n_timesteps):
    """Set up test fixtures."""
    plant_config = {
        "plant": {
            "plant_life": 30,
            "simulation": {
                "n_timesteps": n_timesteps,
                "dt": 3600,
            },
        }
    }
    return plant_config


@pytest.mark.unit
@pytest.mark.parametrize("n_timesteps", [8760])
def test_grid_performance_outputs(plant_config, subtests):
    prob = om.Problem()
    plant_life = int(plant_config["plant"]["plant_life"])
    n_timesteps = int(plant_config["plant"]["simulation"]["n_timesteps"])
    tech_config = {
        "model_inputs": {
            "shared_parameters": {
                "interconnection_size": 50000.0  # 50 MW
            }
        }
    }

    prob.model.add_subsystem(
        "comp",
        GridPerformanceModel(driver_config={}, plant_config=plant_config, tech_config=tech_config),
    )

    prob.setup()

    # Set demand below interconnection limit
    demand = np.full(n_timesteps, 30000.0)  # 30 MW demand
    prob.set_val("comp.electricity_demand", demand)

    prob.run_model()

    commodity = "electricity"
    commodity_amount_units = "kW*h"
    commodity_rate_units = "kW"

    # Check that replacement schedule is between 0 and 1
    with subtests.test("0 <= replacement_schedule <=1"):
        assert np.all(prob.get_val("comp.replacement_schedule", units="unitless") >= 0)
        assert np.all(prob.get_val("comp.replacement_schedule", units="unitless") <= 1)

    with subtests.test("replacement_schedule length"):
        assert len(prob.get_val("comp.replacement_schedule", units="unitless")) == plant_life

    # Check that capacity factor is between 0 and 1 with units of "unitless"
    with subtests.test("0 <= capacity_factor (unitless) <=1"):
        assert np.all(prob.get_val("comp.capacity_factor", units="unitless") >= 0)
        assert np.all(prob.get_val("comp.capacity_factor", units="unitless") <= 1)

    # Check that capacity factor is between 1 and 100 with units of "percent"
    with subtests.test("1 <= capacity_factor (percent) <=1"):
        assert np.all(prob.get_val("comp.capacity_factor", units="percent") >= 1)
        assert np.all(prob.get_val("comp.capacity_factor", units="percent") <= 100)

    with subtests.test("capacity_factor length"):
        assert len(prob.get_val("comp.capacity_factor", units="unitless")) == plant_life

    # Test that rated commodity production is greater than zero
    with subtests.test(f"rated_{commodity}_production > 0"):
        assert np.all(
            prob.get_val(f"comp.rated_{commodity}_production", units=commodity_rate_units) > 0
        )

    with subtests.test(f"rated_{commodity}_production length"):
        assert (
            len(prob.get_val(f"comp.rated_{commodity}_production", units=commodity_rate_units)) == 1
        )

    # Test that total commodity production is greater than zero
    with subtests.test(f"total_{commodity}_produced > 0"):
        assert np.all(
            prob.get_val(f"comp.total_{commodity}_produced", units=commodity_amount_units) > 0
        )
    with subtests.test(f"total_{commodity}_produced length"):
        assert (
            len(prob.get_val(f"comp.total_{commodity}_produced", units=commodity_amount_units)) == 1
        )

    # Test that annual commodity production is greater than zero
    with subtests.test(f"annual_{commodity}_produced > 0"):
        assert np.all(
            prob.get_val(f"comp.annual_{commodity}_produced", units=f"{commodity_amount_units}/yr")
            > 0
        )

    with subtests.test(f"annual_{commodity}_produced[1:] == annual_{commodity}_produced[0]"):
        annual_production = prob.get_val(
            f"comp.annual_{commodity}_produced", units=f"{commodity_amount_units}/yr"
        )
        assert np.all(annual_production[1:] == annual_production[0])

    with subtests.test(f"annual_{commodity}_produced length"):
        assert len(annual_production) == plant_life

    # Test that commodity output has some values greater than zero
    with subtests.test(f"Some of {commodity}_out > 0"):
        assert np.any(prob.get_val(f"comp.{commodity}_out", units=commodity_rate_units) > 0)

    with subtests.test(f"{commodity}_out length"):
        assert len(prob.get_val(f"comp.{commodity}_out", units=commodity_rate_units)) == n_timesteps

    # Test default values
    with subtests.test("operational_life default value"):
        assert prob.get_val("comp.operational_life", units="yr") == plant_life
    with subtests.test("replacement_schedule value"):
        assert np.all(prob.get_val("comp.replacement_schedule", units="unitless") == 0)


@pytest.mark.unit
@pytest.mark.parametrize("n_timesteps", [10])
def test_buying_electricity(plant_config, n_timesteps):
    """Test buying electricity from grid (electricity flows out)."""
    prob = om.Problem()

    tech_config = {
        "model_inputs": {
            "shared_parameters": {
                "interconnection_size": 50000.0  # 50 MW
            }
        }
    }

    prob.model.add_subsystem(
        "grid",
        GridPerformanceModel(driver_config={}, plant_config=plant_config, tech_config=tech_config),
    )

    prob.setup()

    # Set demand below interconnection limit
    demand = np.full(n_timesteps, 30000.0)  # 30 MW demand
    prob.set_val("grid.electricity_demand", demand)

    prob.run_model()

    # Should get full demand since it's below interconnection limit
    electricity_out = prob.get_val("grid.electricity_out")
    np.testing.assert_array_almost_equal(electricity_out, demand)


@pytest.mark.unit
@pytest.mark.parametrize("n_timesteps", [10])
def test_buying_with_interconnection_limit(plant_config, n_timesteps):
    """Test that buying is limited by interconnection size."""
    prob = om.Problem()

    interconnection_size = 40000.0  # 40 MW
    tech_config = {
        "model_inputs": {"shared_parameters": {"interconnection_size": interconnection_size}}
    }

    prob.model.add_subsystem(
        "grid",
        GridPerformanceModel(driver_config={}, plant_config=plant_config, tech_config=tech_config),
    )

    prob.setup()

    # Set demand above interconnection limit
    demand = np.full(n_timesteps, 60000.0)  # 60 MW demand
    prob.set_val("grid.electricity_demand", demand)

    prob.run_model()

    # Should be limited to interconnection size
    electricity_out = prob.get_val("grid.electricity_out")
    np.testing.assert_array_almost_equal(
        electricity_out, np.full(n_timesteps, interconnection_size)
    )


@pytest.mark.unit
@pytest.mark.parametrize("n_timesteps", [10])
def test_selling_electricity(plant_config, n_timesteps):
    """Test selling electricity to grid (electricity flows in)."""
    prob = om.Problem()

    tech_config = {
        "model_inputs": {
            "shared_parameters": {
                "interconnection_size": 100000.0  # 100 MW
            }
        }
    }

    prob.model.add_subsystem(
        "grid",
        GridPerformanceModel(driver_config={}, plant_config=plant_config, tech_config=tech_config),
    )

    prob.setup()

    # Set electricity flowing into grid
    electricity_in = np.full(n_timesteps, 50000.0)  # 50 MW
    prob.set_val("grid.electricity_in", electricity_in)

    prob.run_model()

    # The electricity_in represents what's being sold (no separate output needed)
    # Just verify it was accepted
    actual_in = prob.get_val("grid.electricity_in")
    np.testing.assert_array_almost_equal(actual_in, electricity_in)


@pytest.mark.unit
@pytest.mark.parametrize("n_timesteps", [10])
def test_simultaneous_buy_and_sell(plant_config, n_timesteps):
    """Test that grid can handle both buying and selling simultaneously."""
    prob = om.Problem()

    tech_config = {
        "model_inputs": {
            "shared_parameters": {
                "interconnection_size": 75000.0  # 75 MW
            }
        }
    }

    prob.model.add_subsystem(
        "grid",
        GridPerformanceModel(driver_config={}, plant_config=plant_config, tech_config=tech_config),
    )

    prob.setup()

    # Set both flows
    electricity_in = np.full(n_timesteps, 30000.0)  # 30 MW in
    electricity_demand = np.full(n_timesteps, 40000.0)  # 40 MW out

    prob.set_val("grid.electricity_in", electricity_in)
    prob.set_val("grid.electricity_demand", electricity_demand)

    prob.run_model()

    electricity_out = prob.get_val("grid.electricity_out")
    np.testing.assert_array_almost_equal(electricity_out, electricity_demand)


@pytest.mark.unit
@pytest.mark.parametrize("n_timesteps", [10])
def test_varying_demand_profile(plant_config, n_timesteps):
    """Test with time-varying demand profile."""
    prob = om.Problem()

    tech_config = {"model_inputs": {"shared_parameters": {"interconnection_size": 100000.0}}}

    prob.model.add_subsystem(
        "grid",
        GridPerformanceModel(driver_config={}, plant_config=plant_config, tech_config=tech_config),
    )

    prob.setup()

    # Create varying demand profile
    demand = np.array([10000, 20000, 30000, 50000, 70000, 90000, 110000, 80000, 60000, 40000])
    prob.set_val("grid.electricity_demand", demand)

    prob.run_model()

    electricity_out = prob.get_val("grid.electricity_out")
    # Values above 100000 should be clipped
    expected = np.clip(demand, 0, 100000)
    np.testing.assert_array_almost_equal(electricity_out, expected)


@pytest.mark.unit
@pytest.mark.parametrize("n_timesteps", [10])
def test_non_hourly_dt_demand_profile(subtests, plant_config, n_timesteps):
    """Test with time-varying demand profile."""
    plant_config["plant"]["simulation"]["dt"] = 300

    prob = om.Problem()
    commodity = "electricity"

    tech_config = {"model_inputs": {"shared_parameters": {"interconnection_size": 100000.0}}}

    prob.model.add_subsystem(
        "grid",
        GridPerformanceModel(driver_config={}, plant_config=plant_config, tech_config=tech_config),
    )

    prob.setup()

    # Create varying demand profile
    demand = np.array([10000, 20000, 30000, 50000, 70000, 90000, 110000, 80000, 60000, 40000])
    prob.set_val("grid.electricity_demand", demand, units="kW")

    prob.run_model()

    interconnection_size = tech_config["model_inputs"]["shared_parameters"]["interconnection_size"]
    dt_seconds = plant_config["plant"]["simulation"]["dt"]
    expected = np.clip(demand, 0, interconnection_size)
    expected_total = expected.sum() * dt_seconds / 3600.0
    fraction_of_year = n_timesteps * dt_seconds / 31536000.0
    expected_annual_value = expected_total / fraction_of_year

    with subtests.test(f"annual_{commodity}_produced length"):
        electricity_out = prob.get_val("grid.electricity_out", units="kW")
        np.testing.assert_array_almost_equal(electricity_out, expected)

    with subtests.test("cf"):
        cf = prob.get_val("grid.capacity_factor", units="unitless")
        expected_capacity_factor = expected.mean() / interconnection_size
        assert cf == pytest.approx(expected_capacity_factor)

    with subtests.test("total production"):
        total_energy = prob.get_val(f"grid.total_{commodity}_produced", units="kW*h")
        np.testing.assert_allclose(np.atleast_1d(total_energy), [expected_total])

    with subtests.test("annual production"):
        annual_energy = prob.get_val(f"grid.annual_{commodity}_produced", units="kW*h/year")
        np.testing.assert_allclose(
            np.atleast_1d(annual_energy),
            np.full(np.atleast_1d(annual_energy).shape, expected_annual_value),
        )


@pytest.mark.integration
def test_grid_integration_dt_1800(subtests, tmp_path):
    """Integration test: run an H2IntegrateModel with only grid technology at dt=1800 s."""
    n_timesteps = 8760 * 2
    dt_seconds = 1800
    interconnection_size = 100000.0
    demand_kw = 40000.0

    driver_config = {
        "name": "driver_config",
        "description": "Integration test driver config",
        "general": {
            "folder_output": str(tmp_path / "output"),
            "create_om_reports": False,
        },
    }

    tech_config = {
        "name": "technology_config",
        "description": "Grid-only integration test",
        "technologies": {
            "grid": {
                "performance_model": {"model": "GridPerformanceModel"},
                "model_inputs": {
                    "shared_parameters": {
                        "interconnection_size": interconnection_size,
                    }
                },
            }
        },
    }

    plant_config = {
        "name": "plant_config",
        "description": "Grid-only integration test plant",
        "plant": {
            "plant_life": 30,
            "simulation": {
                "n_timesteps": n_timesteps,
                "dt": dt_seconds,
            },
        },
    }

    h2i = H2IntegrateModel(
        {
            "name": "h2i_grid_integration_test",
            "system_summary": "Grid-only integration model",
            "driver_config": driver_config,
            "technology_config": tech_config,
            "plant_config": plant_config,
        }
    )
    h2i.setup()

    demand = np.full(n_timesteps, demand_kw)
    h2i.prob.set_val("grid.electricity_demand", demand, units="kW")
    h2i.prob.run_model()

    expected_out = np.full(n_timesteps, demand_kw)
    expected_total = expected_out.sum() * (dt_seconds / 3600)
    expected_annual = expected_total * (365 * 24 * 3600) / (n_timesteps * dt_seconds)

    with subtests.test("electricity_out equals demand when below interconnection limit"):
        electricity_out = h2i.prob.get_val("grid.electricity_out", units="kW")
        np.testing.assert_array_almost_equal(electricity_out, expected_out)

    with subtests.test("capacity factor reflects 40 percent loading"):
        capacity_factor = h2i.prob.get_val("grid.capacity_factor", units="unitless")
        np.testing.assert_array_almost_equal(capacity_factor, np.full_like(capacity_factor, 0.4))

    with subtests.test("total electricity produced scales with 1800 second timestep"):
        total_energy = h2i.prob.get_val("grid.total_electricity_produced", units="kW*h")
        assert total_energy == pytest.approx(expected_total)

    with subtests.test("annual electricity produced scales from simulated fraction of year"):
        annual_energy = h2i.prob.get_val("grid.annual_electricity_produced", units="kW*h/year")
        assert annual_energy == pytest.approx(expected_annual)


@pytest.mark.unit
@pytest.mark.parametrize("n_timesteps", [24])
def test_buy_only_mode(plant_config, n_timesteps):
    """Test cost model with only buy price configured."""
    prob = om.Problem()

    interconnection_size = 50000.0
    buy_price = 0.10  # $0.10/kWh

    tech_config = {
        "model_inputs": {
            "shared_parameters": {"interconnection_size": interconnection_size},
            "cost_parameters": {
                "cost_year": 2022,
                "interconnection_capex_per_kw": 50.0,
                "interconnection_opex_per_kw": 2.0,
                "fixed_interconnection_cost": 100000.0,
                "electricity_buy_price": buy_price,
                "electricity_sell_price": None,  # No selling
            },
        }
    }

    prob.model.add_subsystem(
        "grid",
        GridCostModel(driver_config={}, plant_config=plant_config, tech_config=tech_config),
    )

    prob.setup()

    # Set electricity bought (flowing out)
    electricity_out = np.full(n_timesteps, 30000.0)  # 30 MW
    prob.set_val("grid.electricity_out", electricity_out)

    prob.run_model()

    # Check CapEx
    expected_capex = (interconnection_size * 50.0) + 100000.0
    capex = prob.get_val("grid.CapEx", units="USD")
    assert capex == pytest.approx(expected_capex)

    # Check OpEx
    expected_opex = interconnection_size * 2.0
    opex = prob.get_val("grid.OpEx", units="USD/year")
    assert opex == pytest.approx(expected_opex)

    # Check VarOpEx (buying costs)
    expected_varopex = np.sum(electricity_out * buy_price)
    varopex = prob.get_val("grid.VarOpEx", units="USD/year")[0]
    assert varopex == pytest.approx(expected_varopex)


@pytest.mark.unit
@pytest.mark.parametrize("n_timesteps", [24])
def test_sell_only_mode(plant_config, n_timesteps):
    """Test cost model with only sell price configured."""
    prob = om.Problem()

    interconnection_size = 75000.0
    sell_price = 0.05  # $0.05/kWh

    tech_config = {
        "model_inputs": {
            "shared_parameters": {"interconnection_size": interconnection_size},
            "cost_parameters": {
                "cost_year": 2022,
                "interconnection_capex_per_kw": 50.0,
                "interconnection_opex_per_kw": 2.0,
                "fixed_interconnection_cost": 100000.0,
                "electricity_buy_price": None,  # No buying
                "electricity_sell_price": sell_price,
            },
        }
    }

    prob.model.add_subsystem(
        "grid",
        GridCostModel(driver_config={}, plant_config=plant_config, tech_config=tech_config),
    )

    prob.setup()

    # Set electricity sold (flowing in)
    electricity_sold = np.full(n_timesteps, 40000.0)  # 40 MW
    prob.set_val("grid.electricity_sold", electricity_sold)

    prob.run_model()

    # Check CapEx
    expected_capex = (interconnection_size * 50.0) + 100000.0
    capex = prob.get_val("grid.CapEx", units="USD")
    assert capex == pytest.approx(expected_capex)

    # Check OpEx
    expected_opex = interconnection_size * 2.0
    opex = prob.get_val("grid.OpEx", units="USD/year")
    assert opex == pytest.approx(expected_opex)

    # Check VarOpEx (selling revenue - negative)
    expected_varopex = -np.sum(electricity_sold * sell_price)
    varopex = prob.get_val("grid.VarOpEx", units="USD/year")[0]
    assert varopex == pytest.approx(expected_varopex)


@pytest.mark.unit
@pytest.mark.parametrize("n_timesteps", [24])
def test_both_buy_and_sell_prices(plant_config, n_timesteps):
    """Test cost model with both buy and sell prices configured."""
    prob = om.Problem()

    interconnection_size = 100000.0
    buy_price = 0.10  # $0.10/kWh
    sell_price = 0.05  # $0.05/kWh

    tech_config = {
        "model_inputs": {
            "shared_parameters": {"interconnection_size": interconnection_size},
            "cost_parameters": {
                "cost_year": 2022,
                "interconnection_capex_per_kw": 50.0,
                "interconnection_opex_per_kw": 2.0,
                "fixed_interconnection_cost": 100000.0,
                "electricity_buy_price": buy_price,
                "electricity_sell_price": sell_price,
            },
        }
    }

    prob.model.add_subsystem(
        "grid",
        GridCostModel(driver_config={}, plant_config=plant_config, tech_config=tech_config),
    )

    prob.setup()

    # Set both buying and selling
    electricity_out = np.full(n_timesteps, 20000.0)  # 20 MW bought
    electricity_sold = np.full(n_timesteps, 30000.0)  # 30 MW sold

    prob.set_val("grid.electricity_out", electricity_out)
    prob.set_val("grid.electricity_sold", electricity_sold)

    prob.run_model()

    # Check VarOpEx (buying cost - selling revenue)
    buying_cost = np.sum(electricity_out * buy_price)
    selling_revenue = np.sum(electricity_sold * sell_price)
    expected_varopex = buying_cost - selling_revenue

    varopex = prob.get_val("grid.VarOpEx", units="USD/year")[0]
    assert varopex == pytest.approx(expected_varopex)


@pytest.mark.unit
@pytest.mark.parametrize("n_timesteps", [24])
def test_time_varying_buy_price(plant_config, n_timesteps):
    """Test with time-varying electricity buy prices."""
    prob = om.Problem()

    interconnection_size = 50000.0
    # Create time-varying prices (peak/off-peak)
    buy_prices = np.array([0.08] * 6 + [0.15] * 12 + [0.08] * 6)  # 24 hours

    tech_config = {
        "model_inputs": {
            "shared_parameters": {"interconnection_size": interconnection_size},
            "cost_parameters": {
                "cost_year": 2022,
                "interconnection_capex_per_kw": 50.0,
                "interconnection_opex_per_kw": 2.0,
                "fixed_interconnection_cost": 100000.0,
                "electricity_buy_price": buy_prices.tolist(),
                "electricity_sell_price": None,
            },
        }
    }

    prob.model.add_subsystem(
        "grid",
        GridCostModel(driver_config={}, plant_config=plant_config, tech_config=tech_config),
    )

    prob.setup()

    # Set constant electricity bought
    electricity_out = np.full(n_timesteps, 25000.0)  # 25 MW
    prob.set_val("grid.electricity_out", electricity_out)

    prob.run_model()

    # Check VarOpEx with varying prices
    expected_varopex = np.sum(electricity_out * buy_prices)
    varopex = prob.get_val("grid.VarOpEx", units="USD/year")[0]
    assert varopex == pytest.approx(expected_varopex)


@pytest.mark.unit
@pytest.mark.parametrize("n_timesteps", [24])
def test_time_varying_sell_price(plant_config, n_timesteps):
    """Test with time-varying electricity sell prices."""
    prob = om.Problem()

    interconnection_size = 75000.0
    # Create time-varying sell prices
    sell_prices = np.array([0.03] * 6 + [0.07] * 12 + [0.03] * 6)  # 24 hours

    tech_config = {
        "model_inputs": {
            "shared_parameters": {"interconnection_size": interconnection_size},
            "cost_parameters": {
                "cost_year": 2022,
                "interconnection_capex_per_kw": 50.0,
                "interconnection_opex_per_kw": 2.0,
                "fixed_interconnection_cost": 100000.0,
                "electricity_buy_price": None,
                "electricity_sell_price": sell_prices.tolist(),
            },
        }
    }

    prob.model.add_subsystem(
        "grid",
        GridCostModel(driver_config={}, plant_config=plant_config, tech_config=tech_config),
    )

    prob.setup()

    # Set constant electricity sold
    electricity_sold = np.full(n_timesteps, 35000.0)  # 35 MW
    prob.set_val("grid.electricity_sold", electricity_sold)

    prob.run_model()

    # Check VarOpEx (negative for revenue)
    expected_varopex = -np.sum(electricity_sold * sell_prices)
    varopex = prob.get_val("grid.VarOpEx", units="USD/year")[0]
    assert varopex == pytest.approx(expected_varopex)


@pytest.mark.unit
@pytest.mark.parametrize("n_timesteps", [24])
def test_zero_interconnection_costs(plant_config, n_timesteps):
    """Test with zero interconnection costs."""
    prob = om.Problem()

    tech_config = {
        "model_inputs": {
            "shared_parameters": {"interconnection_size": 100000.0},
            "cost_parameters": {
                "cost_year": 2022,
                "interconnection_capex_per_kw": 0.0,
                "interconnection_opex_per_kw": 0.0,
                "fixed_interconnection_cost": 0.0,
                "electricity_buy_price": 0.10,
                "electricity_sell_price": 0.05,
            },
        }
    }

    prob.model.add_subsystem(
        "grid",
        GridCostModel(driver_config={}, plant_config=plant_config, tech_config=tech_config),
    )

    prob.setup()

    electricity_out = np.full(n_timesteps, 10000.0)
    electricity_sold = np.full(n_timesteps, 20000.0)

    prob.set_val("grid.electricity_out", electricity_out)
    prob.set_val("grid.electricity_sold", electricity_sold)

    prob.run_model()

    # Check that CapEx and OpEx are zero
    capex = prob.get_val("grid.CapEx", units="USD")
    opex = prob.get_val("grid.OpEx", units="USD/year")
    assert capex == pytest.approx(0.0)
    assert opex == pytest.approx(0.0)

    # VarOpEx should still be calculated
    expected_varopex = np.sum(electricity_out * 0.10) - np.sum(electricity_sold * 0.05)
    varopex = prob.get_val("grid.VarOpEx", units="USD/year")[0]
    assert varopex == pytest.approx(expected_varopex)
