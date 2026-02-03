import numpy as np
import pytest
import openmdao.api as om
from pytest import fixture

from h2integrate import EXAMPLE_DIR
from h2integrate.core.inputs.validation import load_driver_yaml
from h2integrate.converters.iron.martin_mine_cost_model import MartinIronMineCostComponent
from h2integrate.converters.iron.martin_mine_perf_model import MartinIronMinePerformanceComponent


@fixture
def iron_ore_config_martin_om():
    shared_params = {
        "mine": "Northshore",
        "taconite_pellet_type": "drg",
        "max_ore_production_rate_tonnes_per_hr": 516.0497610311598,
    }
    tech_config = {
        "model_inputs": {
            "shared_parameters": shared_params,
        }
    }
    return tech_config


@fixture
def plant_config():
    plant_config = {
        "plant": {
            "plant_life": 30,
            "simulation": {
                "n_timesteps": 8760,
                "dt": 3600,
            },
        },
        "finance_parameters": {
            "cost_adjustment_parameters": {
                "cost_year_adjustment_inflation": 0.025,
                "target_dollar_year": 2022,
            }
        },
    }
    return plant_config


@fixture
def driver_config():
    driver_config = load_driver_yaml(EXAMPLE_DIR / "21_iron_mn_to_il" / "driver_config.yaml")
    return driver_config


def test_iron_mine_performance_outputs(
    plant_config, driver_config, iron_ore_config_martin_om, subtests
):
    prob = om.Problem()
    iron_ore_perf = MartinIronMinePerformanceComponent(
        plant_config=plant_config,
        tech_config=iron_ore_config_martin_om,
        driver_config=driver_config,
    )
    prob.model.add_subsystem("comp", iron_ore_perf, promotes=["*"])
    prob.setup()

    annual_crude_ore = 25.0 * 1e6
    annual_electricity = 1030.0 * 1e6
    ore_rated_capacity = 516.0497610311598

    prob.set_val("comp.electricity_in", [annual_electricity / 8760] * 8760, units="kW")
    prob.set_val("comp.crude_ore_in", [annual_crude_ore / 8760] * 8760, units="t/h")
    prob.set_val("comp.iron_ore_demand", [ore_rated_capacity] * 8760, units="t/h")

    prob.run_model()
    commodity = "iron_ore"
    commodity_rate_units = "kg/h"
    commodity_amount_units = "kg"
    plant_life = int(plant_config["plant"]["plant_life"])
    n_timesteps = int(plant_config["plant"]["simulation"]["n_timesteps"])

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


def test_baseline_iron_ore_costs(plant_config, driver_config, iron_ore_config_martin_om, subtests):
    martin_ore_capex = 1221599018.626594
    martin_ore_fixed_om = 0.0

    prob = om.Problem()
    iron_ore_perf = MartinIronMinePerformanceComponent(
        plant_config=plant_config,
        tech_config=iron_ore_config_martin_om,
        driver_config=driver_config,
    )

    iron_ore_cost = MartinIronMineCostComponent(
        plant_config=plant_config,
        tech_config=iron_ore_config_martin_om,
        driver_config=driver_config,
    )

    prob.model.add_subsystem("ore_perf", iron_ore_perf, promotes=["*"])
    prob.model.add_subsystem("ore_cost", iron_ore_cost, promotes=["*"])
    prob.setup()

    ore_annual_production_capacity_tpy = 4520595.90663296  # from old model

    annual_crude_ore = 25.0 * 1e6
    annual_electricity = 1030.0 * 1e6
    ore_rated_capacity = 516.0497610311598

    prob.set_val("ore_perf.electricity_in", [annual_electricity / 8760] * 8760, units="kW")
    prob.set_val("ore_perf.crude_ore_in", [annual_crude_ore / 8760] * 8760, units="t/h")
    prob.set_val("ore_perf.iron_ore_demand", [ore_rated_capacity] * 8760, units="t/h")

    prob.run_model()

    with subtests.test("Annual Ore"):
        annual_ore_produced = np.sum(prob.get_val("ore_perf.iron_ore_out", units="t/h"))
        assert pytest.approx(annual_ore_produced, rel=1e-6) == ore_annual_production_capacity_tpy
    with subtests.test("CapEx"):
        assert pytest.approx(prob.get_val("ore_cost.CapEx")[0], rel=1e-6) == martin_ore_capex
    with subtests.test("OpEx"):
        assert pytest.approx(prob.get_val("ore_cost.OpEx")[0], rel=1e-6) == martin_ore_fixed_om
    with subtests.test("VarOpEx"):
        varopex_per_t = prob.get_val("ore_cost.VarOpEx")[0] / annual_ore_produced
        assert pytest.approx(varopex_per_t, abs=0.5) == 97.76558025830259
