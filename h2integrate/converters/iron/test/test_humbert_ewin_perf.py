import pytest
import openmdao.api as om
from pytest import fixture

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


def setup_and_run(plant_config, tech_config, feedstocks_dict):
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

    elec_consumed = prob.get_val("perf.electricity_consumed", units="kW")
    iron_out = prob.get_val("perf.total_sponge_iron_produced", units="kg/year")
    iron_cap = prob.get_val("perf.output_capacity", units="kg/year")

    return elec_consumed, iron_out, iron_cap


def test_humbert_ewin_performance_component(plant_config, tech_config, feedstocks_dict, subtests):
    expected_elec_consumption_ahe = 506978.45  # kW
    expected_elec_consumption_mse = 452725.57  # kW
    expected_elec_consumption_moe = 567259.43  # kW
    expected_sponge_iron_out_ahe = 1354003425.43  # kg/y
    expected_sponge_iron_out_mse = 1354003425.43  # kg/y
    expected_sponge_iron_out_moe = 1354003425.43  # kg/y
    expected_output_capacity_ahe = 1602439024.39  # kg/y
    expected_output_capacity_mse = 1794469102.08  # kg/y
    expected_output_capacity_moe = 1432152588.56  # kg/y

    tech_config["model_inputs"]["shared_parameters"]["electrolysis_type"] = "ahe"
    elec_consumed, iron_out, iron_cap = setup_and_run(plant_config, tech_config, feedstocks_dict)
    with subtests.test("ahe_electricity"):
        assert (
            pytest.approx(
                elec_consumed,
                rel=1e-3,
            )
            == expected_elec_consumption_ahe
        )
    with subtests.test("ahe_production"):
        assert (
            pytest.approx(
                iron_out,
                rel=1e-3,
            )
            == expected_sponge_iron_out_ahe
        )
    with subtests.test("ahe_capacity"):
        assert (
            pytest.approx(
                iron_cap,
                rel=1e-3,
            )
            == expected_output_capacity_ahe
        )
    tech_config["model_inputs"]["shared_parameters"]["electrolysis_type"] = "mse"
    elec_consumed, iron_out, iron_cap = setup_and_run(plant_config, tech_config, feedstocks_dict)
    with subtests.test("mse_electricity"):
        assert (
            pytest.approx(
                elec_consumed,
                rel=1e-3,
            )
            == expected_elec_consumption_mse
        )
    with subtests.test("mse_production"):
        assert (
            pytest.approx(
                iron_out,
                rel=1e-3,
            )
            == expected_sponge_iron_out_mse
        )
    with subtests.test("mse_capacity"):
        assert (
            pytest.approx(
                iron_cap,
                rel=1e-3,
            )
            == expected_output_capacity_mse
        )
    tech_config["model_inputs"]["shared_parameters"]["electrolysis_type"] = "moe"
    elec_consumed, iron_out, iron_cap = setup_and_run(plant_config, tech_config, feedstocks_dict)
    with subtests.test("moe_electricity"):
        assert (
            pytest.approx(
                elec_consumed,
                rel=1e-3,
            )
            == expected_elec_consumption_moe
        )
    with subtests.test("moe_production"):
        assert (
            pytest.approx(
                iron_out,
                rel=1e-3,
            )
            == expected_sponge_iron_out_moe
        )
    with subtests.test("moe_capacity"):
        assert (
            pytest.approx(
                iron_cap,
                rel=1e-3,
            )
            == expected_output_capacity_moe
        )
