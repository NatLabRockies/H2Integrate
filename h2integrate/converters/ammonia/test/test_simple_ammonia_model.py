import pytest
import openmdao.api as om

from h2integrate.converters.ammonia.simple_ammonia_model import (
    SimpleAmmoniaCostModel,
    SimpleAmmoniaPerformanceModel,
)


plant_config = {
    "plant": {
        "plant_life": 30,
        "simulation": {
            "n_timesteps": 8760,
            "dt": 3600,
        },
    },
}

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


def test_simple_ammonia_performance_model():
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
        tech_config=tech_config_dict,
    )
    prob.model.add_subsystem("ammonia_perf", comp)
    prob.setup()
    # Set dummy hydrogen input (array of n_timesteps for shape test)
    prob.set_val("ammonia_perf.hydrogen_in", [10.0] * 2, units="kg/h")
    prob.run_model()
    # Dummy expected values
    expected_total = 1000000.0 * 0.9
    expected_out = expected_total / 2
    assert pytest.approx(prob.get_val("ammonia_perf.total_ammonia_produced")) == expected_total
    assert all(pytest.approx(x) == expected_out for x in prob.get_val("ammonia_perf.ammonia_out"))


def test_simple_ammonia_cost_model(subtests):
    plant_info = {
        "plant_life": 30,
        "simulation": {
            "n_timesteps": 8760,
            "dt": 3600,
        },
    }

    prob = om.Problem()
    comp = SimpleAmmoniaCostModel(
        plant_config={"plant": plant_info},
        tech_config=tech_config_dict,
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
