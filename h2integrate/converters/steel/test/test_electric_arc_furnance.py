import pytest
import openmdao.api as om
from pytest import fixture

from h2integrate import EXAMPLE_DIR
from h2integrate.core.inputs.validation import load_driver_yaml
from h2integrate.converters.steel.electric_arc_furnance import (
    EAFPlantCostComponent,
    EAFPlantPerformanceComponent,
)


@fixture
def steel_eaf_config_rosner_ng():
    shared_params = {
        "eaf_type": "ng",
        "eaf_capacity": 1000000,
        "site_name": "IL",
    }
    performance_params = {"model_name": "rosner"}
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


def test_baseline_steel_eaf_costs_rosner_ng(
    plant_config, driver_config, steel_eaf_config_rosner_ng, subtests
):
    expected_capex = 264034898.3329662
    expected_var_om = 31.31789319
    expected_fixed_om = 38298777.651658
    capacity = 1189772 / 365  # t/day

    prob = om.Problem()
    steel_eaf_perf = EAFPlantPerformanceComponent(
        plant_config=plant_config,
        tech_config=steel_eaf_config_rosner_ng,
        driver_config=driver_config,
    )

    steel_eaf_cost = EAFPlantCostComponent(
        plant_config=plant_config,
        tech_config=steel_eaf_config_rosner_ng,
        driver_config=driver_config,
    )

    prob.model.add_subsystem("eaf_perf", steel_eaf_perf, promotes=["*"])
    prob.model.add_subsystem("eaf_cost", steel_eaf_cost, promotes=["*"])
    prob.setup()
    prob.run_model()

    annual_steel = prob.get_val("eaf_perf.total_steel_produced", units="t/year")
    with subtests.test("Annual Steel"):
        assert pytest.approx(annual_steel[0] / 365, rel=1e-3) == capacity
    with subtests.test("CapEx"):
        assert pytest.approx(prob.get_val("eaf_cost.CapEx")[0], rel=1e-6) == expected_capex
    with subtests.test("OpEx"):
        assert pytest.approx(prob.get_val("eaf_cost.OpEx")[0], rel=1e-6) == expected_fixed_om
    with subtests.test("VarOpEx"):
        assert pytest.approx(prob.get_val("eaf_cost.VarOpEx")[0], rel=1e-6) == expected_var_om
