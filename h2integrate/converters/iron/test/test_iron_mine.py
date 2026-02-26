import pytest
import openmdao.api as om
from pytest import fixture

from h2integrate import EXAMPLE_DIR
from h2integrate.core.inputs.validation import load_driver_yaml
from h2integrate.converters.iron.iron_mine import (
    IronMineCostComponent,
    IronMinePerformanceComponent,
)


@fixture
def iron_ore_config_martin_om():
    shared_params = {
        "mine": "Northshore",
        "taconite_pellet_type": "drg",
    }
    performance_params = {"ore_cf_estimate": 0.9, "model_name": "martin_ore"}
    cost_params = {
        "LCOE": 58.02,
        "LCOH": 7.10,
        "model_name": "martin_ore",
        "varom_model_name": "martin_ore",
        "installation_years": 3,
        "operational_year": 2035,
        # 'plant_life': 30,
    }

    tech_config = {
        "model_inputs": {
            "cost_parameters": cost_params,
            "performance_parameters": performance_params,
            "shared_parameters": shared_params,
        }
    }
    return tech_config


@fixture
def iron_ore_config_rosner_om():
    shared_params = {
        "mine": "Northshore",
        "taconite_pellet_type": "drg",
    }
    performance_params = {"ore_cf_estimate": 0.9, "model_name": "martin_ore"}
    cost_params = {
        "LCOE": 58.02,
        "LCOH": 7.10,
        "model_name": "martin_ore",
        "varom_model_name": "rosner_ore",
        "installation_years": 3,
        "operational_year": 2035,
        # 'plant_life': 30,
    }

    tech_config = {
        "model_inputs": {
            "cost_parameters": cost_params,
            "performance_parameters": performance_params,
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


# baseline case
def test_baseline_iron_ore_costs_martin(
    plant_config, driver_config, iron_ore_config_martin_om, subtests
):
    martin_ore_capex = 1221599018.626594
    martin_ore_var_om = 441958721.59532887
    martin_ore_fixed_om = 0.0

    prob = om.Problem()
    iron_ore_perf = IronMinePerformanceComponent(
        plant_config=plant_config,
        tech_config=iron_ore_config_martin_om,
        driver_config=driver_config,
    )

    iron_ore_cost = IronMineCostComponent(
        plant_config=plant_config,
        tech_config=iron_ore_config_martin_om,
        driver_config=driver_config,
    )

    prob.model.add_subsystem("ore_perf", iron_ore_perf, promotes=["*"])
    prob.model.add_subsystem("ore_cost", iron_ore_cost, promotes=["*"])
    prob.setup()
    prob.run_model()

    annual_ore = prob.get_val("ore_perf.total_iron_ore_produced", units="t/year")
    with subtests.test("Annual Ore"):
        assert pytest.approx(annual_ore[0] / 365, rel=1e-6) == 12385.195376438356
    with subtests.test("CapEx"):
        assert (
            pytest.approx(prob.get_val("ore_cost.CapEx", units="USD")[0], rel=1e-6)
            == martin_ore_capex
        )
    with subtests.test("OpEx"):
        assert (
            pytest.approx(prob.get_val("ore_cost.OpEx", units="USD/year")[0], rel=1e-6)
            == martin_ore_fixed_om
        )
    with subtests.test("VarOpEx"):
        assert (
            pytest.approx(prob.get_val("ore_cost.VarOpEx", units="USD/year")[0], rel=1e-6)
            == martin_ore_var_om
        )


def test_baseline_iron_ore_costs_rosner(
    plant_config, driver_config, iron_ore_config_rosner_om, subtests
):
    rosner_ore_capex = 1221599018.626594
    rosner_ore_var_om = 441958721.59532887
    rosner_ore_fixed_om = 0.0
    prob = om.Problem()
    iron_ore_perf = IronMinePerformanceComponent(
        plant_config=plant_config,
        tech_config=iron_ore_config_rosner_om,
        driver_config=driver_config,
    )

    iron_ore_cost = IronMineCostComponent(
        plant_config=plant_config,
        tech_config=iron_ore_config_rosner_om,
        driver_config=driver_config,
    )

    prob.model.add_subsystem("ore_perf", iron_ore_perf, promotes=["*"])
    prob.model.add_subsystem("ore_cost", iron_ore_cost, promotes=["*"])
    prob.setup()
    prob.run_model()
    annual_ore = prob.get_val("ore_perf.total_iron_ore_produced", units="t/year")
    with subtests.test("Annual Ore"):
        assert pytest.approx(annual_ore[0] / 365, rel=1e-6) == 12385.195376438356
    with subtests.test("CapEx"):
        assert (
            pytest.approx(prob.get_val("ore_cost.CapEx", units="USD")[0], rel=1e-6)
            == rosner_ore_capex
        )
    with subtests.test("OpEx"):
        assert (
            pytest.approx(prob.get_val("ore_cost.OpEx", units="USD/year")[0], rel=1e-6)
            == rosner_ore_fixed_om
        )
    with subtests.test("VarOpEx"):
        assert (
            pytest.approx(prob.get_val("ore_cost.VarOpEx", units="USD/year")[0], rel=1e-6)
            == rosner_ore_var_om
        )
