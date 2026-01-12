import pytest
import openmdao.api as om
from pytest import fixture

from h2integrate import EXAMPLE_DIR
from h2integrate.core.inputs.validation import load_driver_yaml
from h2integrate.converters.iron.humbert_ewin_perf import HumbertEwinPerformanceComponent


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
            "rated_capacity": 281426,  # kg/h
            "units": "kg/h",
            "price": 27.5409,  # USD/kg TODO: update
        },
    }
    return feedstocks_dict


def test_humbert_ewin_performance_component(
    plant_config, driver_config, tech_config, feedstocks_dict, subtests
):
    expected_sponge_iron_out = 1602439024.4  # kg/year

    prob = om.Problem()

    iron_ewin_perf = HumbertEwinPerformanceComponent(
        plant_config=plant_config, tech_config=tech_config, driver_config={}
    )

    prob.model.add_subsystem("perf", iron_ewin_perf, promotes=["*"])
    prob.setup()

    for feedstock_name, feedstock_info in feedstocks_dict.items():
        prob.set_val(
            f"perf.{feedstock_name}_in",
            feedstock_info["rated_capacity"],
            units=feedstock_info["units"],
        )

    prob.run_model()

    annual_sponge_iron = prob.get_val("perf.total_sponge_iron_produced", units="kg/year")

    with subtests.test("sponge_iron_out"):
        assert (
            pytest.approx(
                annual_sponge_iron,
                rel=1e-3,
            )
            == expected_sponge_iron_out
        )
