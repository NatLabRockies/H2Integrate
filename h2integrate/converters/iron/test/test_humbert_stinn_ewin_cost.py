import pytest
import openmdao.api as om
from pytest import fixture

from h2integrate import EXAMPLE_DIR
from h2integrate.core.inputs.validation import load_driver_yaml
from h2integrate.converters.iron.humbert_ewin_perf import HumbertEwinPerformanceComponent
from h2integrate.converters.iron.humbert_stinn_ewin_cost import HumbertStinnEwinCostComponent


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
    driver_config = load_driver_yaml(EXAMPLE_DIR / "27_iron_electrowinning" / "driver_config.yaml")
    return driver_config


@fixture
def tech_config():
    tech_config = {
        "model_inputs": {
            "shared_parameters": {
                "electrolysis_type": "ahe",
            },
            "performance_parameters": {
                "ore_fe_wt_pct": 65.0,
                "capacity_mw": 600.0,
            },
        }
    }
    return tech_config


@fixture
def feedstocks_dict():
    feedstocks_dict = {
        "electricity": {
            "rated_capacity": 600000.0,  # kW
            "units": "kW",
            "price": 0.05802,  # $/kWh
        },
        "iron_ore": {
            "rated_capacity": 237794.77,  # kg/h
            "units": "kg/h",
            "price": 27.5409,  # USD/kg TODO: update
        },
    }
    return feedstocks_dict


def setup_and_run(plant_config, driver_config, tech_config, feedstocks_dict):
    prob = om.Problem()

    iron_ewin_perf = HumbertEwinPerformanceComponent(
        plant_config=plant_config, tech_config=tech_config, driver_config={}
    )

    iron_ewin_cost = HumbertStinnEwinCostComponent(
        plant_config=plant_config, tech_config=tech_config, driver_config={}
    )

    prob.model.add_subsystem("perf", iron_ewin_perf, promotes=["*"])
    prob.model.add_subsystem("cost", iron_ewin_cost, promotes=["*"])
    prob.setup()

    for feedstock_name, feedstock_info in feedstocks_dict.items():
        prob.set_val(
            f"perf.{feedstock_name}_in",
            feedstock_info["rated_capacity"],
            units=feedstock_info["units"],
        )

    prob.run_model()

    capex = prob.get_val("cost.CapEx", units="USD")
    fopex = prob.get_val("cost.OpEx", units="USD/year")
    vopex = prob.get_val("cost.VarOpEx", units="USD/year")

    return capex, fopex, vopex


def test_humbert_stinn_ewin_cost_component(
    plant_config, driver_config, tech_config, feedstocks_dict, subtests
):
    expected_capex_ahe = 6038571901.89  # USD
    expected_fopex_ahe = 67050786.5  # USD/year
    expected_vopex_ahe = 835954.89  # USD/year
    expected_capex_mse = 19918313452.1  # USD
    expected_fopex_mse = 51295503.77  # USD/year
    expected_vopex_mse = 1220341.02  # USD/year
    expected_capex_moe = 7307164315.34  # USD
    expected_fopex_moe = 21761330.82  # USD/year
    expected_vopex_moe = 3316122.05  # USD/year

    tech_config["model_inputs"]["shared_parameters"]["electrolysis_type"] = "ahe"
    capex, fopex, vopex = setup_and_run(plant_config, driver_config, tech_config, feedstocks_dict)
    with subtests.test("ahe_capex"):
        assert (
            pytest.approx(
                capex,
                rel=1e-3,
            )
            == expected_capex_ahe
        )
    with subtests.test("ahe_fopex"):
        assert (
            pytest.approx(
                fopex,
                rel=1e-3,
            )
            == expected_fopex_ahe
        )
    with subtests.test("ahe_vopex"):
        assert (
            pytest.approx(
                vopex,
                rel=1e-3,
            )
            == expected_vopex_ahe
        )
    tech_config["model_inputs"]["shared_parameters"]["electrolysis_type"] = "mse"
    capex, fopex, vopex = setup_and_run(plant_config, driver_config, tech_config, feedstocks_dict)
    with subtests.test("mse_capex"):
        assert (
            pytest.approx(
                capex,
                rel=1e-3,
            )
            == expected_capex_mse
        )
    with subtests.test("mse_fopex"):
        assert (
            pytest.approx(
                fopex,
                rel=1e-3,
            )
            == expected_fopex_mse
        )
    with subtests.test("mse_vopex"):
        assert (
            pytest.approx(
                vopex,
                rel=1e-3,
            )
            == expected_vopex_mse
        )
    tech_config["model_inputs"]["shared_parameters"]["electrolysis_type"] = "moe"
    capex, fopex, vopex = setup_and_run(plant_config, driver_config, tech_config, feedstocks_dict)
    with subtests.test("moe_capex"):
        assert (
            pytest.approx(
                capex,
                rel=1e-3,
            )
            == expected_capex_moe
        )
    with subtests.test("moe_fopex"):
        assert (
            pytest.approx(
                fopex,
                rel=1e-3,
            )
            == expected_fopex_moe
        )
    with subtests.test("moe_vopex"):
        assert (
            pytest.approx(
                vopex,
                rel=1e-3,
            )
            == expected_vopex_moe
        )
