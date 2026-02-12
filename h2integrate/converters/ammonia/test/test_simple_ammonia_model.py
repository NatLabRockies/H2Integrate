import numpy as np
import pytest
import openmdao.api as om
from pytest import fixture

from h2integrate.converters.ammonia.simple_ammonia_model import (
    SimpleAmmoniaCostModel,
    SimpleAmmoniaPerformanceModel,
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
    }
    return plant_config


@fixture
def tech_config():
    tech_config_dict = {
        "model_inputs": {
            "shared_parameters": {
                "plant_capacity_kgpy": 1000000.0,
                "plant_capacity_factor": 0.9,
            },
            "cost_parameters": {
                "electricity_cost": 91,
                # "hydrogen_cost": 4.023963541079105,
                "cooling_water_cost": 0.00516275276753,
                "iron_based_catalyst_cost": 25,
                "oxygen_cost": 0,
                "electricity_consumption": 0.0001207,
                "hydrogen_consumption": 0.197284403,
                "cooling_water_consumption": 0.049236824,
                "iron_based_catalyst_consumption": 0.000091295354067341,
                "oxygen_byproduct": 0.29405077250145,
                "capex_scaling_exponent": 0.6,
                "cost_year": 2022,
            },
        }
    }
    return tech_config_dict


def test_simple_ammonia_performance_model_outputs(plant_config, tech_config, subtests):
    prob = om.Problem()
    comp = SimpleAmmoniaPerformanceModel(
        plant_config=plant_config,
        tech_config=tech_config,
    )

    plant_life = int(plant_config["plant"]["plant_life"])
    n_timesteps = int(plant_config["plant"]["simulation"]["n_timesteps"])

    prob.model.add_subsystem("comp", comp)
    prob.setup()
    # Set dummy hydrogen input (array of n_timesteps for shape test)
    prob.set_val("comp.hydrogen_in", [10.0] * n_timesteps, units="kg/h")
    prob.run_model()
    commodity = "ammonia"
    commodity_amount_units = "kg"
    commodity_rate_units = "kg/h"

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


def test_simple_ammonia_performance_model(tech_config, subtests):
    plant_info = {
        "plant_life": 30,
        "simulation": {
            "n_timesteps": 2,
            "dt": 3600,
        },
    }

    prob = om.Problem()
    comp = SimpleAmmoniaPerformanceModel(
        plant_config={"plant": plant_info},
        tech_config=tech_config,
    )
    prob.model.add_subsystem("ammonia_perf", comp)
    prob.setup()
    # Set dummy hydrogen input (array of n_timesteps for shape test)
    prob.set_val("ammonia_perf.hydrogen_in", [10.0] * 2, units="kg/h")
    prob.run_model()
    # Dummy expected values
    expected_total = 1000000.0 * 0.9
    expected_out = expected_total / 2

    with subtests.test("total ammonia produced"):
        assert pytest.approx(prob.get_val("ammonia_perf.total_ammonia_produced")) == expected_total

    with subtests.test("performance output"):
        assert all(
            pytest.approx(x) == expected_out for x in prob.get_val("ammonia_perf.ammonia_out")
        )


def test_simple_ammonia_cost_model(plant_config, tech_config, subtests):
    plant_config["plant"]["simulation"]

    prob = om.Problem()
    comp = SimpleAmmoniaCostModel(
        plant_config=plant_config,
        tech_config=tech_config,
    )

    prob.model.add_subsystem("ammonia_cost", comp)
    prob.setup()

    # Set required inputs
    prob.set_val("ammonia_cost.plant_capacity_kgpy", 1000000.0, units="kg/year")
    prob.set_val("ammonia_cost.plant_capacity_factor", 0.9)
    prob.set_val("ammonia_cost.LCOH", 2.0, units="USD/kg")
    prob.run_model()

    expected_outputs = {
        "capex_air_separation_cryogenic": [853619.36456877],
        "capex_haber_bosch": [707090.74827636],
        "capex_boiler": [268119.3387603],
        "capex_cooling_tower": [182025.76432338],
        "capex_direct": [2010855.21592881],
        "capex_depreciable_nonequipment": [853454.92310814],
        "CapEx": [2864310.13903695],
        "land_cost": [62946.66128355],
        "labor_cost": [1278414.87818485],
        "general_administration_cost": [255682.97563697],
        "property_tax_insurance": [57286.20278074],
        "maintenance_cost": [253.15324433],
        "OpEx": [1654583.87113044],
        "H2_cost_in_startup_year": [355111.9254],
        "energy_cost_in_startup_year": [9885.33],
        "non_energy_cost_in_startup_year": [2282.92326095],
        "variable_cost_in_startup_year": [12168.25326095],
        "credits_byproduct": [0.0],
    }

    for out, expected in expected_outputs.items():
        with subtests.test(out):
            val = prob.get_val(f"ammonia_cost.{out}")
            assert pytest.approx(val, rel=1e-6) == expected[0]
