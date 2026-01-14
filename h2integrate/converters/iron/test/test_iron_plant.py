import pytest
import openmdao.api as om
from pytest import fixture

from h2integrate import EXAMPLE_DIR
from h2integrate.core.inputs.validation import load_driver_yaml
from h2integrate.converters.iron.iron_plant import (
    IronPlantCostComponent,
    IronPlantPerformanceComponent,
)


@fixture
def iron_dri_config_rosner_ng():
    shared_params = {
        "winning_type": "ng",
        "iron_win_capacity": 1418095,
        "site_name": "IL",
    }
    performance_params = {"win_capacity_demon": "iron", "model_name": "rosner"}
    cost_params = {
        "LCOE": 58.02,
        "LCOH": 7.10,
        "LCOI_ore": 125.25996463784443,
        "iron_transport_cost": 30.566808424134745,
        "ore_profit_pct": 6.0,
        "varom_model_name": "rosner",
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


def test_baseline_iron_dri_costs_rosner_ng(
    plant_config, driver_config, iron_dri_config_rosner_ng, subtests
):
    expected_capex = 403808062.6981323
    expected_var_om = 369445330.68402404
    expected_fixed_om = 60103761.59958463
    capacity = 3885.1917808219177

    prob = om.Problem()
    iron_dri_perf = IronPlantPerformanceComponent(
        plant_config=plant_config,
        tech_config=iron_dri_config_rosner_ng,
        driver_config=driver_config,
    )

    iron_dri_cost = IronPlantCostComponent(
        plant_config=plant_config,
        tech_config=iron_dri_config_rosner_ng,
        driver_config=driver_config,
    )

    prob.model.add_subsystem("dri_perf", iron_dri_perf, promotes=["*"])
    prob.model.add_subsystem("dri_cost", iron_dri_cost, promotes=["*"])
    prob.setup()
    prob.run_model()

    annual_pig_iron = prob.get_val("dri_perf.total_pig_iron_produced", units="t/year")
    with subtests.test("Annual Ore"):
        assert pytest.approx(annual_pig_iron[0] / 365, rel=1e-3) == capacity
    with subtests.test("CapEx"):
        assert pytest.approx(prob.get_val("dri_cost.CapEx")[0], rel=1e-6) == expected_capex
    with subtests.test("OpEx"):
        assert pytest.approx(prob.get_val("dri_cost.OpEx")[0], rel=1e-6) == expected_fixed_om
    with subtests.test("VarOpEx"):
        assert pytest.approx(prob.get_val("dri_cost.VarOpEx")[0], rel=1e-6) == expected_var_om


def test_baseline_iron_dri_costs_rosner_h2(
    plant_config, driver_config, iron_dri_config_rosner_ng, subtests
):
    expected_capex = 246546589.2914324
    expected_var_om = 888529893.2442514
    expected_fixed_om = 53360873.348792635
    capacity = 3885.1917808219177

    iron_dri_config_rosner_ng["model_inputs"]["shared_parameters"].update({"winning_type": "h2"})
    prob = om.Problem()
    iron_dri_perf = IronPlantPerformanceComponent(
        plant_config=plant_config,
        tech_config=iron_dri_config_rosner_ng,
        driver_config=driver_config,
    )

    iron_dri_cost = IronPlantCostComponent(
        plant_config=plant_config,
        tech_config=iron_dri_config_rosner_ng,
        driver_config=driver_config,
    )

    prob.model.add_subsystem("dri_perf", iron_dri_perf, promotes=["*"])
    prob.model.add_subsystem("dri_cost", iron_dri_cost, promotes=["*"])
    prob.setup()
    prob.run_model()

    annual_pig_iron = prob.get_val("dri_perf.total_pig_iron_produced", units="t/year")
    with subtests.test("Annual Ore"):
        assert pytest.approx(annual_pig_iron[0] / 365, rel=1e-3) == capacity
    with subtests.test("CapEx"):
        assert pytest.approx(prob.get_val("dri_cost.CapEx")[0], rel=1e-6) == expected_capex
    with subtests.test("OpEx"):
        assert pytest.approx(prob.get_val("dri_cost.OpEx")[0], rel=1e-6) == expected_fixed_om
    with subtests.test("VarOpEx"):
        assert pytest.approx(prob.get_val("dri_cost.VarOpEx")[0], rel=1e-6) == expected_var_om
