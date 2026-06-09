"""
Tests for feedstock performance and cost models.

These tests validate the feedstock components that provide resource inputs to technologies,
including natural gas, electricity, water, and other feedstock types.
"""

from pathlib import Path

import numpy as np
import pandas as pd
import pytest
import openmdao.api as om
from pytest import fixture

from h2integrate.feedstocks import (
    FeedstockCostModel,
    FeedstockPerformanceModel,
    EIANaturalGasFeedstockCostModel,
)
from h2integrate.preprocess.eia import convert_to_hourly


@fixture
def plant_config():
    return {
        "plant": {
            "plant_life": 30,
            "simulation": {
                "n_timesteps": 8760,
                "dt": 3600,
            },
        },
    }


@fixture
def ng_feedstock_input_config():
    tech_config = {
        "model_inputs": {
            "shared_parameters": {
                "commodity": "natural_gas",
                "commodity_rate_units": "MMBtu/h",
            },
            "performance_parameters": {
                "rated_capacity": 100.0,
            },
            "cost_parameters": {
                "price": 4.2,  # USD/MMBtu
                "annual_cost": 0,
                "start_up_cost": 0,
                "cost_year": 2023,
                "commodity_amount_units": "MMBtu",  # optional
            },
        }
    }
    return tech_config


@fixture
def eia_ng_feedstock_tech_config():
    tech_config = {
        "model_inputs": {
            "shared_parameters": {
                "commodity": "natural_gas",
                "commodity_rate_units": "MMBtu/h",
            },
            "performance_parameters": {
                "rated_capacity": 100.0,
            },
            "cost_parameters": {
                "price": 4.2,  # USD/MMBtu
                "annual_cost": 0,
                "start_up_cost": 100000.0,
                "cost_year": 2025,
                "resource_year": 2001,
                "state": "MN",
                "monthly": True,
                "price_category": "industrial",
                "filename": Path(__file__).parent / "test_eia_ng_data.csv",
                "commodity_amount_units": "MMBtu",
            },
        }
    }
    return tech_config


@pytest.mark.unit
def test_feedstock_standard_outputs(plant_config, ng_feedstock_input_config, subtests):
    perf_model = FeedstockPerformanceModel(
        plant_config=plant_config, tech_config=ng_feedstock_input_config, driver_config={}
    )
    cost_model = FeedstockCostModel(
        plant_config=plant_config, tech_config=ng_feedstock_input_config, driver_config={}
    )
    prob = om.Problem()
    prob.model.add_subsystem("ng_feedstock_source", perf_model)
    prob.model.add_subsystem("ng_feedstock", cost_model)
    # Connect the feedstock performance model output to the cost model input
    prob.model.connect(
        "ng_feedstock_source.natural_gas_out",
        "ng_feedstock.natural_gas_out",
    )

    prob.setup()
    # Set some consumption values
    consumption = np.full(8760, 50.0)  # 50 MMBtu/hour
    prob.set_val("ng_feedstock.natural_gas_consumed", consumption)
    prob.run_model()
    with subtests.test("Check feedstock capacity factor"):
        ng_cf = prob.get_val("ng_feedstock.capacity_factor", units="unitless").mean()
        assert pytest.approx(ng_cf, rel=1e-6) == 0.5
    with subtests.test("Check feedstock rated production"):
        rated_production_source = prob.get_val(
            "ng_feedstock_source.natural_gas_capacity", units="MMBtu/h"
        )
        rated_production = prob.get_val(
            "ng_feedstock.rated_natural_gas_production", units="MMBtu/h"
        )
        assert pytest.approx(rated_production, rel=1e-6) == rated_production_source
    with subtests.test("Check feedstock total consumption"):
        total_consumption = prob.get_val("ng_feedstock.total_natural_gas_consumed", units="MMBtu")
        assert pytest.approx(total_consumption, rel=1e-6) == consumption.sum()
    with subtests.test("Check feedstock annual consumption"):
        annual_consumption = prob.get_val(
            "ng_feedstock.annual_natural_gas_consumed", units="MMBtu/yr"
        )
        assert pytest.approx(annual_consumption, rel=1e-6) == consumption.sum()


def create_basic_feedstock_config(
    feedstock_type="natural_gas",
    units="MMBtu/h",
    rated_capacity=100.0,
    price=4.2,
    annual_cost=0.0,
    start_up_cost=100000.0,
):
    """Create a basic feedstock configuration for testing."""
    tech_config = {
        "model_inputs": {
            "shared_parameters": {
                "commodity": feedstock_type,
                "commodity_rate_units": units,
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
    driver_config = {}
    return tech_config, driver_config


@pytest.mark.unit
def test_single_feedstock_natural_gas(plant_config):
    """Test a single natural gas feedstock with basic parameters."""
    tech_config, driver_config = create_basic_feedstock_config()

    # Test performance model
    perf_model = FeedstockPerformanceModel(
        tech_config=tech_config,
        plant_config=plant_config,
        driver_config=driver_config,
    )

    prob = om.Problem()
    prob.model.add_subsystem("feedstock_perf", perf_model)
    prob.setup()
    prob.run_model()

    # Check that output is generated correctly
    ng_output = prob.get_val("feedstock_perf.natural_gas_out")
    assert len(ng_output) == 8760
    assert np.all(ng_output == 100.0)

    # Test cost model
    cost_model = FeedstockCostModel(
        tech_config=tech_config,
        plant_config=plant_config,
        driver_config=driver_config,
    )

    prob_cost = om.Problem()
    prob_cost.model.add_subsystem("feedstock_cost", cost_model)
    prob_cost.setup()

    # Set some consumption values
    consumption = np.full(8760, 50.0)  # 50 MMBtu/hour
    prob_cost.set_val("feedstock_cost.natural_gas_consumed", consumption)
    prob_cost.run_model()

    # Check outputs
    capex = prob_cost.get_val("feedstock_cost.CapEx", units="USD")[0]
    opex = prob_cost.get_val("feedstock_cost.VarOpEx", units="USD/year")[0]

    assert capex == 100000.0  # start_up_cost
    expected_opex = 0.0 + 4.2 * consumption.sum()  # annual_cost + price * consumption
    assert opex == pytest.approx(expected_opex, abs=1e-5)


@pytest.mark.unit
def test_eia_natural_gas_feedstock(plant_config, eia_ng_feedstock_tech_config):
    """Test a single natural gas feedstock with basic parameters."""
    tech_config = eia_ng_feedstock_tech_config
    _, driver_config = create_basic_feedstock_config()

    # Test performance model
    perf_model = FeedstockPerformanceModel(
        tech_config=tech_config,
        plant_config=plant_config,
        driver_config={},
    )

    prob = om.Problem()
    prob.model.add_subsystem("feedstock_perf", perf_model)
    prob.setup()
    prob.run_model()

    # Check that output is generated correctly
    ng_output = prob.get_val("feedstock_perf.natural_gas_out")
    assert len(ng_output) == 8760
    assert np.all(ng_output == 100.0)

    # Test cost model
    cost_model = EIANaturalGasFeedstockCostModel(
        tech_config=tech_config,
        plant_config=plant_config,
        driver_config={},
    )

    prob_cost = om.Problem()
    prob_cost.model.add_subsystem("feedstock_cost", cost_model)
    prob_cost.setup()

    # Set some consumption values
    consumption = np.full(8760, 50.0)  # 50 MMBtu/hour
    prob_cost.set_val("feedstock_cost.natural_gas_consumed", consumption)
    prob_cost.run_model()

    # replicate price data
    price = pd.DataFrame(
        [
            ["01/01/2001", 12.23029],
            ["02/01/2001", 6.950207],
            ["03/01/2001", 6.182573],
            ["04/01/2001", 6.410788],
            ["05/01/2001", 5.715768],
            ["06/01/2001", 4.439834],
            ["07/01/2001", 3.910788],
            ["08/01/2001", 3.827801],
            ["09/01/2001", 3.807054],
            ["10/01/2001", 2.572614],
            ["11/01/2001", 4.159751],
            ["12/01/2001", 4.294606],
        ],
        columns=["period", "price"],
    )
    price.period = pd.to_datetime(price.period)
    price = price.set_index("period")
    price = convert_to_hourly(price)
    price = price.price.to_numpy()

    # Check outputs
    capex = prob_cost.get_val("feedstock_cost.CapEx", units="USD")[0]
    opex = prob_cost.get_val("feedstock_cost.VarOpEx", units="USD/year")[0]

    assert capex == 100000.0  # start_up_cost
    expected_opex = 0.0 + (price * consumption).sum()
    assert opex == pytest.approx(expected_opex, abs=1e-5)


@pytest.mark.unit
def test_multiple_same_type_feedstocks(plant_config):
    """Test multiple feedstocks of the same type with different parameters."""
    # Test two natural gas feedstocks with different capacities and prices
    units = "MMBtu/h"
    tech_config1, driver_config = create_basic_feedstock_config(
        rated_capacity=50.0, price=4.0, start_up_cost=50000.0, units=units
    )
    tech_config2, _ = create_basic_feedstock_config(
        rated_capacity=150.0, price=4.5, start_up_cost=150000.0, units=units
    )

    # Test both feedstocks can coexist and have different outputs
    perf_model1 = FeedstockPerformanceModel(
        tech_config=tech_config1,
        plant_config=plant_config,
        driver_config=driver_config,
    )

    perf_model2 = FeedstockPerformanceModel(
        tech_config=tech_config2,
        plant_config=plant_config,
        driver_config=driver_config,
    )

    prob = om.Problem()
    prob.model.add_subsystem("feedstock1", perf_model1)
    prob.model.add_subsystem("feedstock2", perf_model2)
    prob.setup()
    prob.run_model()

    ng_output1 = prob.get_val("feedstock1.natural_gas_out", units=units)
    ng_output2 = prob.get_val("feedstock2.natural_gas_out", units=units)

    assert np.all(ng_output1 == 50.0)
    assert np.all(ng_output2 == 150.0)


@pytest.mark.unit
def test_multiple_different_type_feedstocks(plant_config):
    """Test feedstocks of different types (natural gas, electricity, water)."""
    # Natural gas feedstock
    ng_units = "MMBtu/h"
    ng_config, driver_config = create_basic_feedstock_config(
        feedstock_type="natural_gas", units=ng_units, rated_capacity=100.0, price=4.2
    )

    # Electricity feedstock
    ec_units = "MW*h"
    elec_config, _ = create_basic_feedstock_config(
        feedstock_type="electricity", units=ec_units, rated_capacity=50.0, price=0.05
    )

    # Water feedstock
    h2o_units = "galUS"
    water_config, _ = create_basic_feedstock_config(
        feedstock_type="water", units=h2o_units, rated_capacity=1000.0, price=0.001
    )

    # Test all three feedstock types
    perf_ng = FeedstockPerformanceModel(
        tech_config=ng_config,
        plant_config=plant_config,
        driver_config=driver_config,
    )

    perf_elec = FeedstockPerformanceModel(
        tech_config=elec_config,
        plant_config=plant_config,
        driver_config=driver_config,
    )

    perf_water = FeedstockPerformanceModel(
        tech_config=water_config,
        plant_config=plant_config,
        driver_config=driver_config,
    )

    prob = om.Problem()
    prob.model.add_subsystem("ng_feedstock", perf_ng)
    prob.model.add_subsystem("elec_feedstock", perf_elec)
    prob.model.add_subsystem("water_feedstock", perf_water)
    prob.setup()
    prob.run_model()

    # Check outputs
    ng_out = prob.get_val("ng_feedstock.natural_gas_out", units=ng_units)
    elec_out = prob.get_val("elec_feedstock.electricity_out", units=ec_units)
    water_out = prob.get_val("water_feedstock.water_out", units=h2o_units)

    assert np.all(ng_out == 100.0)
    assert np.all(elec_out == 50.0)
    assert np.all(water_out == 1000.0)


@pytest.mark.unit
def test_variable_pricing(plant_config):
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

    tech_config, driver_config = create_basic_feedstock_config(price=hourly_prices.tolist())

    cost_model = FeedstockCostModel(
        tech_config=tech_config,
        plant_config=plant_config,
        driver_config=driver_config,
    )

    prob = om.Problem()
    prob.model.add_subsystem("feedstock_cost", cost_model)
    prob.setup()

    # Set consumption pattern
    consumption = np.full(8760, 30.0)  # 30 MMBtu/hour
    prob.set_val("feedstock_cost.natural_gas_consumed", consumption)
    prob.run_model()

    # Check that OpEx reflects variable pricing
    opex = prob.get_val("feedstock_cost.VarOpEx", units="USD/year")[0]
    expected_opex = 0.0 + np.sum(hourly_prices * consumption)
    assert opex == pytest.approx(expected_opex, abs=1e-5)

    # OpEx should be different from constant pricing
    constant_price_opex = 0.0 + 4.2 * consumption.sum()
    assert opex != pytest.approx(constant_price_opex, abs=2)


@pytest.mark.unit
def test_zero_cost_feedstock(plant_config):
    """Test feedstock with zero costs (free resource)."""
    tech_config, driver_config = create_basic_feedstock_config(
        price=0.0, annual_cost=0.0, start_up_cost=0.0
    )

    cost_model = FeedstockCostModel(
        tech_config=tech_config,
        plant_config=plant_config,
        driver_config=driver_config,
    )

    prob = om.Problem()
    prob.model.add_subsystem("feedstock_cost", cost_model)
    prob.setup()

    consumption = np.full(8760, 100.0)
    prob.set_val("feedstock_cost.natural_gas_consumed", consumption)
    prob.run_model()

    capex = prob.get_val("feedstock_cost.CapEx", units="USD")[0]
    opex = prob.get_val("feedstock_cost.OpEx", units="USD/year")[0]

    assert capex == 0.0
    assert opex == 0.0


@pytest.mark.unit
def test_per_year_pricing(plant_config):
    """Test feedstock with per-year pricing (array of length plant_life)."""
    plant_life = 30
    n_timesteps = 8760

    # Different price each year
    yearly_prices = np.linspace(3.0, 6.0, plant_life).tolist()

    tech_config, driver_config = create_basic_feedstock_config(
        price=yearly_prices, start_up_cost=0.0
    )

    cost_model = FeedstockCostModel(
        tech_config=tech_config,
        plant_config=plant_config,
        driver_config=driver_config,
    )

    prob = om.Problem()
    prob.model.add_subsystem("feedstock_cost", cost_model)
    prob.setup()

    consumption = np.full(n_timesteps, 50.0)  # 50 MMBtu/h
    prob.set_val("feedstock_cost.natural_gas_consumed", consumption)
    prob.run_model()

    dt = plant_config["plant"]["simulation"]["dt"]
    total_consumption = consumption.sum() * (dt / 3600)
    expected_varopex = total_consumption * np.array(yearly_prices)

    varopex = prob.get_val("feedstock_cost.VarOpEx", units="USD/year")
    np.testing.assert_allclose(varopex, expected_varopex)


@pytest.mark.unit
def test_per_year_pricing_invalid_length(plant_config):
    """Test that an invalid price array length raises ValueError."""
    bad_prices = [4.2] * 15  # Neither n_timesteps (8760) nor plant_life (30)

    tech_config, driver_config = create_basic_feedstock_config(price=bad_prices)

    cost_model = FeedstockCostModel(
        tech_config=tech_config,
        plant_config=plant_config,
        driver_config=driver_config,
    )

    prob = om.Problem()
    prob.model.add_subsystem("feedstock_cost", cost_model)

    with pytest.raises(ValueError, match="must match n_timesteps.*or plant_life"):
        prob.setup()
