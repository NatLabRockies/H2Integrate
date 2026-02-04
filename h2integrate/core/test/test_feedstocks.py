"""
Tests for feedstock performance and cost models.

These tests validate the feedstock components that provide resource inputs to technologies,
including natural gas, electricity, water, and other feedstock types.
"""

import numpy as np
import pytest
import openmdao.api as om

from h2integrate.core.feedstocks import FeedstockCostModel, FeedstockPerformanceModel


def create_basic_feedstock_config(
    feedstock_type="natural_gas",
    units="MMBtu",
    rated_capacity=100.0,
    price=4.2,
    annual_cost=0.0,
    start_up_cost=100000.0,
):
    """Create a basic feedstock configuration for testing."""
    tech_config = {
        "model_inputs": {
            "shared_parameters": {
                "feedstock_type": feedstock_type,
                "units": units,
            },
            "performance_parameters": {
                "rated_capacity": rated_capacity,
            },
            "cost_parameters": {
                "price": price,
                "annual_cost": annual_cost,
                "start_up_cost": start_up_cost,
                "cost_year": 2023,
            },
        }
    }
    plant_config = {"plant": {"plant_life": 30, "simulation": {"n_timesteps": 8760}}}
    driver_config = {}
    return tech_config, plant_config, driver_config


def test_single_feedstock_natural_gas():
    """Test a single natural gas feedstock with basic parameters."""
    tech_config, plant_config, driver_config = create_basic_feedstock_config()

    # Test performance model
    perf_model = FeedstockPerformanceModel()
    perf_model.options["tech_config"] = tech_config
    perf_model.options["plant_config"] = plant_config
    perf_model.options["driver_config"] = driver_config

    prob = om.Problem()
    prob.model.add_subsystem("feedstock_perf", perf_model)
    prob.setup()
    prob.run_model()

    # Check that output is generated correctly
    ng_output = prob.get_val("feedstock_perf.natural_gas_out")
    assert len(ng_output) == 8760
    assert np.all(ng_output == 100.0)

    # Test cost model
    cost_model = FeedstockCostModel()
    cost_model.options["tech_config"] = tech_config
    cost_model.options["plant_config"] = plant_config
    cost_model.options["driver_config"] = driver_config

    prob_cost = om.Problem()
    prob_cost.model.add_subsystem("feedstock_cost", cost_model)
    prob_cost.setup()

    # Set some consumption values
    consumption = np.full(8760, 50.0)  # 50 MMBtu/hour
    prob_cost.set_val("feedstock_cost.natural_gas_consumed", consumption)
    prob_cost.run_model()

    # Check outputs
    capex = prob_cost.get_val("feedstock_cost.CapEx")[0]
    opex = prob_cost.get_val("feedstock_cost.VarOpEx")[0]

    assert capex == 100000.0  # start_up_cost
    expected_opex = 0.0 + 4.2 * consumption.sum()  # annual_cost + price * consumption
    assert opex == pytest.approx(expected_opex, abs=1e-5)


def test_multiple_same_type_feedstocks():
    """Test multiple feedstocks of the same type with different parameters."""
    # Test two natural gas feedstocks with different capacities and prices
    tech_config1, plant_config, driver_config = create_basic_feedstock_config(
        rated_capacity=50.0, price=4.0, start_up_cost=50000.0
    )
    tech_config2, _, _ = create_basic_feedstock_config(
        rated_capacity=150.0, price=4.5, start_up_cost=150000.0
    )

    # Test both feedstocks can coexist and have different outputs
    perf_model1 = FeedstockPerformanceModel()
    perf_model1.options.update(
        {
            "tech_config": tech_config1,
            "plant_config": plant_config,
            "driver_config": driver_config,
        }
    )

    perf_model2 = FeedstockPerformanceModel()
    perf_model2.options.update(
        {
            "tech_config": tech_config2,
            "plant_config": plant_config,
            "driver_config": driver_config,
        }
    )

    prob = om.Problem()
    prob.model.add_subsystem("feedstock1", perf_model1)
    prob.model.add_subsystem("feedstock2", perf_model2)
    prob.setup()
    prob.run_model()

    ng_output1 = prob.get_val("feedstock1.natural_gas_out")
    ng_output2 = prob.get_val("feedstock2.natural_gas_out")

    assert np.all(ng_output1 == 50.0)
    assert np.all(ng_output2 == 150.0)


def test_multiple_different_type_feedstocks():
    """Test feedstocks of different types (natural gas, electricity, water)."""
    # Natural gas feedstock
    ng_config, plant_config, driver_config = create_basic_feedstock_config(
        feedstock_type="natural_gas", units="MMBtu", rated_capacity=100.0, price=4.2
    )

    # Electricity feedstock
    elec_config, _, _ = create_basic_feedstock_config(
        feedstock_type="electricity", units="MW*h", rated_capacity=50.0, price=0.05
    )

    # Water feedstock
    water_config, _, _ = create_basic_feedstock_config(
        feedstock_type="water", units="galUS", rated_capacity=1000.0, price=0.001
    )

    # Test all three feedstock types
    perf_ng = FeedstockPerformanceModel()
    perf_ng.options.update(
        {"tech_config": ng_config, "plant_config": plant_config, "driver_config": driver_config}
    )

    perf_elec = FeedstockPerformanceModel()
    perf_elec.options.update(
        {
            "tech_config": elec_config,
            "plant_config": plant_config,
            "driver_config": driver_config,
        }
    )

    perf_water = FeedstockPerformanceModel()
    perf_water.options.update(
        {
            "tech_config": water_config,
            "plant_config": plant_config,
            "driver_config": driver_config,
        }
    )

    prob = om.Problem()
    prob.model.add_subsystem("ng_feedstock", perf_ng)
    prob.model.add_subsystem("elec_feedstock", perf_elec)
    prob.model.add_subsystem("water_feedstock", perf_water)
    prob.setup()
    prob.run_model()

    # Check outputs
    ng_out = prob.get_val("ng_feedstock.natural_gas_out")
    elec_out = prob.get_val("elec_feedstock.electricity_out")
    water_out = prob.get_val("water_feedstock.water_out")

    assert np.all(ng_out == 100.0)
    assert np.all(elec_out == 50.0)
    assert np.all(water_out == 1000.0)


def test_variable_pricing():
    """Test feedstock with variable pricing (array of prices)."""
    # Create hourly price array that varies throughout the year
    hourly_prices = np.full(8760, 4.2)
    # Add some variation - higher prices during peak hours
    for i in range(8760):
        hour_of_day = i % 24
        if 16 <= hour_of_day <= 20:  # Peak hours
            hourly_prices[i] = 6.0
        elif 22 <= hour_of_day or hour_of_day <= 6:  # Off-peak hours
            hourly_prices[i] = 3.0

    tech_config, plant_config, driver_config = create_basic_feedstock_config(
        price=hourly_prices.tolist()
    )

    cost_model = FeedstockCostModel()
    cost_model.options["tech_config"] = tech_config
    cost_model.options["plant_config"] = plant_config
    cost_model.options["driver_config"] = driver_config

    prob = om.Problem()
    prob.model.add_subsystem("feedstock_cost", cost_model)
    prob.setup()

    # Set consumption pattern
    consumption = np.full(8760, 30.0)  # 30 MMBtu/hour
    prob.set_val("feedstock_cost.natural_gas_consumed", consumption)
    prob.run_model()

    # Check that OpEx reflects variable pricing
    opex = prob.get_val("feedstock_cost.VarOpEx")[0]
    expected_opex = 0.0 + np.sum(hourly_prices * consumption)
    assert opex == pytest.approx(expected_opex, abs=1e-5)

    # OpEx should be different from constant pricing
    constant_price_opex = 0.0 + 4.2 * consumption.sum()
    assert opex != pytest.approx(constant_price_opex, abs=2)


def test_zero_cost_feedstock():
    """Test feedstock with zero costs (free resource)."""
    tech_config, plant_config, driver_config = create_basic_feedstock_config(
        price=0.0, annual_cost=0.0, start_up_cost=0.0
    )

    cost_model = FeedstockCostModel()
    cost_model.options["tech_config"] = tech_config
    cost_model.options["plant_config"] = plant_config
    cost_model.options["driver_config"] = driver_config

    prob = om.Problem()
    prob.model.add_subsystem("feedstock_cost", cost_model)
    prob.setup()

    consumption = np.full(8760, 100.0)
    prob.set_val("feedstock_cost.natural_gas_consumed", consumption)
    prob.run_model()

    capex = prob.get_val("feedstock_cost.CapEx")[0]
    opex = prob.get_val("feedstock_cost.OpEx")[0]

    assert capex == 0.0
    assert opex == 0.0
