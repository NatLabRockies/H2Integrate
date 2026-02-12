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
            "units": "MMBtu/h",
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
            "units": "MMBtu/h",
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


def test_ng_dri_performance_outputs(
    plant_config, ng_dri_base_config, ng_feedstock_availability_costs, subtests
):
    prob = om.Problem()

    iron_dri_perf = NaturalGasIronReductionPlantPerformanceComponent(
        plant_config=plant_config,
        tech_config=ng_dri_base_config,
        driver_config={},
    )
    prob.model.add_subsystem("comp", iron_dri_perf, promotes=["*"])
    prob.setup()

    for feedstock_name, feedstock_info in ng_feedstock_availability_costs.items():
        prob.set_val(
            f"comp.{feedstock_name}_in",
            feedstock_info["rated_capacity"],
            units=feedstock_info["units"],
        )
    prob.run_model()
    commodity = "pig_iron"
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
