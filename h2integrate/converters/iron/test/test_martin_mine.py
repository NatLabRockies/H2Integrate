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

    prob.set_val("ore_perf.electricity_in", [annual_electricity / 8760] * 8760, units="kW*h")
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
