import numpy as np
import pytest
import openmdao.api as om
from pytest import fixture

from h2integrate import EXAMPLE_DIR
from h2integrate.core.inputs.validation import load_driver_yaml
from h2integrate.converters.steel.steel_eaf_plant import (
    HydrogenEAFPlantCostComponent,
    NaturalGasEAFPlantCostComponent,
    HydrogenEAFPlantPerformanceComponent,
    NaturalGasEAFPlantPerformanceComponent,
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
def ng_eaf_base_config():
    tech_config = {
        "model_inputs": {
            "shared_parameters": {
                "steel_production_rate_tonnes_per_hr": 1189772 / 8760,  # t/h
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
            "rated_capacity": 56640,  # need 56636.07192 kW
            "units": "kW",
            "price": 0.05802,  # USD/kW
        },
        "natural_gas": {
            "rated_capacity": 277,  # need 276.5024456918746 MMBtu at each timestep
            "units": "MMBtu",
            "price": 0.0,
        },
        "water": {
            "rated_capacity": 10000.0,  # need 9082.97025163801 galUS/h
            "units": "galUS",
            "price": 1670.0,  # cost is $0.441167535/t, equal to $1670.0004398318847/galUS
        },
        "pig_iron": {
            "rated_capacity": 162,  # need 161.88297569673742 t/h
            "units": "t/h",
            "price": 27.5409 * 1e3,  # USD/t TODO UPDATE
        },
    }
    return feedstocks_dict


@fixture
def h2_feedstock_availability_costs():
    feedstocks_dict = {
        "electricity": {
            # (1189678/8760)t-steel/h * 433.170439 kWh/t-steel = 58828.00702 kW
            "rated_capacity": 58830,  # need 58828.00702 kW
            "units": "kW",
            "price": 0.05802,  # USD/kW TODO: update
        },
        "natural_gas": {
            "rated_capacity": 13.0,  # need 12.136117946872957 MMBtu at each timestep
            "units": "MMBtu",
            "price": 0.0,
        },
        "carbon": {
            "rated_capacity": 8.0,  # need 7.306469908675799 t/h
            "units": "t/h",
            "price": 0.0,
        },
        "lime": {
            "rated_capacity": 2.5,  # need 2.460840794520548 t/h
            "units": "t/h",
            "price": 0.0,
        },
        "water": {
            "rated_capacity": 6000.0,  # need 5766.528266260271 galUS/h
            "units": "galUS",
            "price": 1670.0,  # TODO: update cost is $0.441167535/t, equal to $1670.0004398318847/galUS
        },
        "pig_iron": {
            "rated_capacity": 162,  # need 161.88297569673742 t/h
            "units": "t/h",
            "price": 27.5409 * 1e3,  # USD/t TODO: update
        },
    }
    return feedstocks_dict


def test_ng_eaf_performance(
    plant_config, ng_eaf_base_config, ng_feedstock_availability_costs, subtests
):
    expected_steel_annual_production_tpd = 3259.391781  # t/d

    prob = om.Problem()

    iron_dri_perf = NaturalGasEAFPlantPerformanceComponent(
        plant_config=plant_config,
        tech_config=ng_eaf_base_config,
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

    annual_pig_iron = np.sum(prob.get_val("perf.steel_out", units="t/h"))
    with subtests.test("Annual Steel"):
        assert (
            pytest.approx(annual_pig_iron / 365, rel=1e-3) == expected_steel_annual_production_tpd
        )


def test_ng_eaf_performance_limited_feedstock(
    plant_config, ng_eaf_base_config, ng_feedstock_availability_costs, subtests
):
    expected_steel_annual_production_tpd = 3259.391781 / 2  # t/d
    # make steel feedstock half of whats needed
    water_usage_rate_gal_pr_tonne = 66.881
    water_half_availability_gal_pr_hr = (
        water_usage_rate_gal_pr_tonne * expected_steel_annual_production_tpd / 24
    )
    ng_feedstock_availability_costs["water"].update(
        {"rated_capacity": water_half_availability_gal_pr_hr}
    )

    prob = om.Problem()

    iron_eaf_perf = NaturalGasEAFPlantPerformanceComponent(
        plant_config=plant_config,
        tech_config=ng_eaf_base_config,
        driver_config={},
    )
    prob.model.add_subsystem("perf", iron_eaf_perf, promotes=["*"])
    prob.setup()

    for feedstock_name, feedstock_info in ng_feedstock_availability_costs.items():
        prob.set_val(
            f"perf.{feedstock_name}_in",
            feedstock_info["rated_capacity"],
            units=feedstock_info["units"],
        )
    prob.run_model()

    annual_steel = np.sum(prob.get_val("perf.steel_out", units="t/h"))
    with subtests.test("Annual Steel"):
        assert pytest.approx(annual_steel / 365, rel=1e-3) == expected_steel_annual_production_tpd


def test_ng_eaf_performance_cost(
    plant_config, ng_eaf_base_config, ng_feedstock_availability_costs, subtests
):
    ng_eaf_base_config["model_inputs"]["shared_parameters"][
        "steel_production_rate_tonnes_per_hr"
    ] = 838926.9489 / 8760
    expected_capex = 264034898.3329662
    expected_fixed_om = 38298777.651658
    expected_steel_annual_production_tpd = 2298.43  # t/d

    prob = om.Problem()

    iron_eaf_perf = NaturalGasEAFPlantPerformanceComponent(
        plant_config=plant_config,
        tech_config=ng_eaf_base_config,
        driver_config={},
    )
    iron_eaf_cost = NaturalGasEAFPlantCostComponent(
        plant_config=plant_config,
        tech_config=ng_eaf_base_config,
        driver_config={},
    )

    prob.model.add_subsystem("perf", iron_eaf_perf, promotes=["*"])
    prob.model.add_subsystem("cost", iron_eaf_cost, promotes=["*"])
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

    annual_steel = np.sum(prob.get_val("perf.steel_out", units="t/h"))
    with subtests.test("Annual Pig Iron"):
        assert pytest.approx(annual_steel / 365, rel=1e-3) == expected_steel_annual_production_tpd
    with subtests.test("CapEx"):
        # expected difference of 0.044534%
        assert pytest.approx(prob.get_val("cost.CapEx")[0], rel=1e-3) == expected_capex
    with subtests.test("OpEx"):
        assert (
            pytest.approx(prob.get_val("cost.OpEx")[0] + prob.get_val("cost.VarOpEx")[0], rel=1e-3)
            == expected_fixed_om
        )


def test_h2_eaf_performance(
    plant_config, ng_eaf_base_config, h2_feedstock_availability_costs, subtests
):
    expected_steel_annual_production_tpd = 3259.391781  # t/d

    prob = om.Problem()

    iron_dri_perf = HydrogenEAFPlantPerformanceComponent(
        plant_config=plant_config,
        tech_config=ng_eaf_base_config,
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

    annual_steel = np.sum(prob.get_val("perf.steel_out", units="t/h"))
    with subtests.test("Annual Steel"):
        assert pytest.approx(annual_steel / 365, rel=1e-3) == expected_steel_annual_production_tpd


def test_h2_eaf_performance_cost(
    plant_config, ng_eaf_base_config, h2_feedstock_availability_costs, subtests
):
    ng_eaf_base_config["model_inputs"]["shared_parameters"][
        "steel_production_rate_tonnes_per_hr"
    ] = 838926.9489 / 8760
    expected_capex = 271492352.2740321
    expected_fixed_om = 37048005.00181486

    expected_steel_annual_production_tpd = 2298.43  # t/d

    prob = om.Problem()

    iron_dri_perf = HydrogenEAFPlantPerformanceComponent(
        plant_config=plant_config,
        tech_config=ng_eaf_base_config,
        driver_config={},
    )
    iron_dri_cost = HydrogenEAFPlantCostComponent(
        plant_config=plant_config,
        tech_config=ng_eaf_base_config,
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

    annual_steel = np.sum(prob.get_val("perf.steel_out", units="t/h"))
    with subtests.test("Annual Pig Iron"):
        assert pytest.approx(annual_steel / 365, rel=1e-3) == expected_steel_annual_production_tpd
    with subtests.test("CapEx"):
        # expected difference of 0.044534%
        assert pytest.approx(prob.get_val("cost.CapEx")[0], rel=1e-3) == expected_capex
    with subtests.test("OpEx"):
        assert (
            pytest.approx(prob.get_val("cost.OpEx")[0] + prob.get_val("cost.VarOpEx")[0], rel=1e-3)
            == expected_fixed_om
        )
