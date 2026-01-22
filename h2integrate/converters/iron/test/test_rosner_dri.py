import numpy as np
import pytest
import openmdao.api as om
from pytest import fixture

from h2integrate import EXAMPLE_DIR
from h2integrate.core.inputs.validation import load_driver_yaml
from h2integrate.converters.iron.iron_dri_plant import (
    HydrogenIronReductionPlantCostComponent,
    NaturalGasIronReductionPlantCostComponent,
    HydrogenIronReductionPlantPerformanceComponent,
    NaturalGasIronReductionPlantPerformanceComponent,
)


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


@fixture
def ng_dri_base_config():
    tech_config = {
        "model_inputs": {
            "shared_parameters": {
                "pig_iron_production_rate_tonnes_per_hr": 1418095 / 8760,  # t/h
            },
            "cost_parameters": {
                "skilled_labor_cost": 40.85,  # 2022 USD/hr
                "unskilled_labor_cost": 30.0,  # 2022 USD/hr
            },
        }
    }
    return tech_config


@fixture
def ng_feedstock_availability_costs():
    feedstocks_dict = {
        "electricity": {
            "rated_capacity": 27000,  # need 26949.46472431 kW
            "units": "kW",
            "price": 0.05802,  # USD/kW
        },
        "natural_gas": {
            "rated_capacity": 1270,  # need 1268.934 MMBtu at each timestep
            "units": "MMBtu",
            "price": 0.0,
        },
        "reformer_catalyst": {
            "rated_capacity": 0.001,  # need 0.00056546 m**3/h
            "units": "m**3",
            "price": 0.0,
        },
        "water": {
            "rated_capacity": 40000.0,  # need 38071.049649 galUS/h
            "units": "galUS",
            "price": 1670.0,  # cost is $0.441167535/t, equal to $1670.0004398318847/galUS
        },
        "iron_ore": {
            "rated_capacity": 263.75,
            "units": "t/h",
            "price": 27.5409 * 1e3,  # USD/t
        },
    }
    return feedstocks_dict


@fixture
def h2_feedstock_availability_costs():
    feedstocks_dict = {
        "electricity": {
            # (1418095/8760)t-pig_iron/h * 98.17925 kWh/t-pig_iron = 15893.55104 kW
            "rated_capacity": 16000,  # need 15893.55104 kW
            "units": "kW",
            "price": 0.05802,  # USD/kW TODO: update
        },
        "natural_gas": {
            "rated_capacity": 81.0,  # need 80.101596 MMBtu at each timestep
            "units": "MMBtu",
            "price": 0.0,
        },
        "hydrogen": {
            "rated_capacity": 9.0,  # need 8.957895917766855 t/h
            "units": "t/h",
            "price": 0.0,
        },
        "water": {
            "rated_capacity": 24000.0,  # need 23066.4878077501 galUS/h
            "units": "galUS",
            "price": 1670.0,  # TODO: update cost is $0.441167535/t, equal to $1670.0004398318847/galUS
        },
        "iron_ore": {
            "rated_capacity": 221.5,  # need 221.2679060330504 t/h
            "units": "t/h",
            "price": 27.5409 * 1e3,  # USD/t TODO: update
        },
    }
    return feedstocks_dict


def test_ng_dri_performance(
    plant_config, ng_dri_base_config, ng_feedstock_availability_costs, subtests
):
    expected_pig_iron_annual_production_tpd = 3885.1917808219177  # t/d

    prob = om.Problem()

    iron_dri_perf = NaturalGasIronReductionPlantPerformanceComponent(
        plant_config=plant_config,
        tech_config=ng_dri_base_config,
        driver_config={},
    )
    prob.model.add_subsystem("perf", iron_dri_perf, promotes=["*"])
    prob.setup()

    for feedstock_name, feedstock_info in ng_feedstock_availability_costs.items():
        prob.set_val(
            f"perf.{feedstock_name}_in",
            feedstock_info["rated_capacity"],
            units=feedstock_info["units"],
        )
    prob.run_model()

    annual_pig_iron = np.sum(prob.get_val("perf.pig_iron_out", units="t/h"))
    with subtests.test("Annual Pig Iron"):
        assert (
            pytest.approx(annual_pig_iron / 365, rel=1e-3)
            == expected_pig_iron_annual_production_tpd
        )


def test_ng_dri_performance_limited_feedstock(
    plant_config, ng_dri_base_config, ng_feedstock_availability_costs, subtests
):
    expected_pig_iron_annual_production_tpd = 3885.1917808219177 / 2  # t/d
    # make iron ore feedstock half of whats needed
    water_usage_rate_gal_pr_tonne = 200.60957937294563
    water_half_availability_gal_pr_hr = (
        water_usage_rate_gal_pr_tonne * expected_pig_iron_annual_production_tpd / 24
    )
    ng_feedstock_availability_costs["water"].update(
        {"rated_capacity": water_half_availability_gal_pr_hr}
    )

    prob = om.Problem()

    iron_dri_perf = NaturalGasIronReductionPlantPerformanceComponent(
        plant_config=plant_config,
        tech_config=ng_dri_base_config,
        driver_config={},
    )
    prob.model.add_subsystem("perf", iron_dri_perf, promotes=["*"])
    prob.setup()

    for feedstock_name, feedstock_info in ng_feedstock_availability_costs.items():
        prob.set_val(
            f"perf.{feedstock_name}_in",
            feedstock_info["rated_capacity"],
            units=feedstock_info["units"],
        )
    prob.run_model()

    annual_pig_iron = np.sum(prob.get_val("perf.pig_iron_out", units="t/h"))
    with subtests.test("Annual Pig Iron"):
        assert (
            pytest.approx(annual_pig_iron / 365, rel=1e-3)
            == expected_pig_iron_annual_production_tpd
        )


def test_ng_dri_performance_cost(
    plant_config, ng_dri_base_config, ng_feedstock_availability_costs, subtests
):
    expected_capex = 403808062.6981323
    expected_fixed_om = 60103761.59958463
    expected_pig_iron_annual_production_tpd = 3885.1917808219177  # t/d

    prob = om.Problem()

    iron_dri_perf = NaturalGasIronReductionPlantPerformanceComponent(
        plant_config=plant_config,
        tech_config=ng_dri_base_config,
        driver_config={},
    )
    iron_dri_cost = NaturalGasIronReductionPlantCostComponent(
        plant_config=plant_config,
        tech_config=ng_dri_base_config,
        driver_config={},
    )

    prob.model.add_subsystem("perf", iron_dri_perf, promotes=["*"])
    prob.model.add_subsystem("cost", iron_dri_cost, promotes=["*"])
    prob.setup()

    for feedstock_name, feedstock_info in ng_feedstock_availability_costs.items():
        prob.set_val(
            f"perf.{feedstock_name}_in",
            feedstock_info["rated_capacity"],
            units=feedstock_info["units"],
        )

    prob.run_model()

    # difference from IronPlantCostComponent:
    # IronPlantCostComponent: maintenance_materials is included in Fixed OpEx
    # NaturalGasIronReductionPlantCostComponent: maintenance_materials is the variable O&M

    annual_pig_iron = np.sum(prob.get_val("perf.pig_iron_out", units="t/h"))
    with subtests.test("Annual Pig Iron"):
        assert (
            pytest.approx(annual_pig_iron / 365, rel=1e-3)
            == expected_pig_iron_annual_production_tpd
        )
    with subtests.test("CapEx"):
        # expected difference of 0.044534%
        assert pytest.approx(prob.get_val("cost.CapEx")[0], rel=1e-3) == expected_capex
    with subtests.test("OpEx"):
        assert (
            pytest.approx(prob.get_val("cost.OpEx")[0] + prob.get_val("cost.VarOpEx")[0], rel=1e-3)
            == expected_fixed_om
        )


def test_h2_dri_performance(
    plant_config, ng_dri_base_config, h2_feedstock_availability_costs, subtests
):
    expected_pig_iron_annual_production_tpd = 3885.1917808219177  # t/d

    prob = om.Problem()

    iron_dri_perf = HydrogenIronReductionPlantPerformanceComponent(
        plant_config=plant_config,
        tech_config=ng_dri_base_config,
        driver_config={},
    )
    prob.model.add_subsystem("perf", iron_dri_perf, promotes=["*"])
    prob.setup()

    for feedstock_name, feedstock_info in h2_feedstock_availability_costs.items():
        prob.set_val(
            f"perf.{feedstock_name}_in",
            feedstock_info["rated_capacity"],
            units=feedstock_info["units"],
        )
    prob.run_model()

    annual_pig_iron = np.sum(prob.get_val("perf.pig_iron_out", units="t/h"))
    with subtests.test("Annual Pig Iron"):
        assert (
            pytest.approx(annual_pig_iron / 365, rel=1e-3)
            == expected_pig_iron_annual_production_tpd
        )


def test_h2_dri_performance_cost(
    plant_config, ng_dri_base_config, h2_feedstock_availability_costs, subtests
):
    expected_capex = 246546589.2914324
    expected_fixed_om = 53360873.348792635

    expected_pig_iron_annual_production_tpd = 3885.1917808219177  # t/d

    prob = om.Problem()

    iron_dri_perf = HydrogenIronReductionPlantPerformanceComponent(
        plant_config=plant_config,
        tech_config=ng_dri_base_config,
        driver_config={},
    )
    iron_dri_cost = HydrogenIronReductionPlantCostComponent(
        plant_config=plant_config,
        tech_config=ng_dri_base_config,
        driver_config={},
    )

    prob.model.add_subsystem("perf", iron_dri_perf, promotes=["*"])
    prob.model.add_subsystem("cost", iron_dri_cost, promotes=["*"])
    prob.setup()

    for feedstock_name, feedstock_info in h2_feedstock_availability_costs.items():
        prob.set_val(
            f"perf.{feedstock_name}_in",
            feedstock_info["rated_capacity"],
            units=feedstock_info["units"],
        )

    prob.run_model()

    annual_pig_iron = np.sum(prob.get_val("perf.pig_iron_out", units="t/h"))
    with subtests.test("Annual Pig Iron"):
        assert (
            pytest.approx(annual_pig_iron / 365, rel=1e-3)
            == expected_pig_iron_annual_production_tpd
        )
    with subtests.test("CapEx"):
        # expected difference of 0.044534%
        assert pytest.approx(prob.get_val("cost.CapEx")[0], rel=1e-3) == expected_capex
    with subtests.test("OpEx"):
        assert (
            pytest.approx(prob.get_val("cost.OpEx")[0] + prob.get_val("cost.VarOpEx")[0], rel=1e-3)
            == expected_fixed_om
        )
