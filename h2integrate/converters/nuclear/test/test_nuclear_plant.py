import numpy as np
import pytest
import openmdao.api as om
from pytest import fixture

from h2integrate.converters.nuclear.nuclear_plant import NuclearCostModel, NuclearPerformanceModel


@fixture
def plant_config():
    return {
        "plant": {
            "plant_life": 30,
            "simulation": {
                "n_timesteps": 8760,
                "dt": 3600,
            },
        },
    }


@fixture
def nuclear_performance_params():
    return {
        "system_capacity_mw": 300.0,
    }


@fixture
def nuclear_cost_params():
    return {
        "system_capacity_mw": 450.0,
        "reactor_type": "smr_lwr",
        "type_costs": {
            "smr_lwr": {
                "capex_per_kw": 6000.0,
                "fixed_opex_per_kw_year": 120.0,
                "variable_opex_per_mwh": 2.5,
                "reference_capacity_mw": 300.0,
                "capex_scaling_exponent": 0.9,
            },
            "lwr": {
                "capex_per_kw": 4500.0,
                "fixed_opex_per_kw_year": 95.0,
                "variable_opex_per_mwh": 2.0,
                "reference_capacity_mw": 1000.0,
                "capex_scaling_exponent": 0.95,
            },
        },
        "cost_year": 2023,
    }


def test_nuclear_performance_demand(plant_config, nuclear_performance_params, subtests):
    tech_config_dict = {
        "model_inputs": {
            "performance_parameters": nuclear_performance_params,
        }
    }

    system_capacity = nuclear_performance_params["system_capacity_mw"]
    demand_section = np.linspace(0, 1.2 * system_capacity, 12)
    electricity_demand = np.tile(demand_section, 730)

    prob = om.Problem()
    perf_comp = NuclearPerformanceModel(
        plant_config=plant_config,
        tech_config=tech_config_dict,
        driver_config={},
    )

    prob.model.add_subsystem("nuc_perf", perf_comp, promotes=["*"])
    prob.setup()

    prob.set_val("electricity_demand", electricity_demand)
    prob.run_model()

    electricity_out = prob.get_val("electricity_out")

    expected_output = np.minimum(electricity_demand, system_capacity)

    with subtests.test("Nuclear output matches demand limit"):
        assert pytest.approx(electricity_out, rel=1e-6) == expected_output


def test_nuclear_cost_model(plant_config, nuclear_cost_params, subtests):
    tech_config_dict = {
        "model_inputs": {
            "cost_parameters": nuclear_cost_params,
        }
    }

    system_capacity = nuclear_cost_params["system_capacity_mw"]
    electricity_out = np.full(8760, 360.0)

    prob = om.Problem()
    cost_comp = NuclearCostModel(
        plant_config=plant_config,
        tech_config=tech_config_dict,
        driver_config={},
    )

    prob.model.add_subsystem("nuc_cost", cost_comp, promotes=["*"])
    prob.setup()

    prob.set_val("system_capacity", system_capacity)
    prob.set_val("electricity_out", electricity_out)
    prob.run_model()

    capex = prob.get_val("CapEx")[0]
    opex = prob.get_val("OpEx")[0]
    cost_year = prob.get_val("cost_year")

    type_costs = nuclear_cost_params["type_costs"][nuclear_cost_params["reactor_type"]]
    capex_per_kw = type_costs["capex_per_kw"]
    fixed_opex_per_kw_year = type_costs["fixed_opex_per_kw_year"]
    variable_opex_per_mwh = type_costs["variable_opex_per_mwh"]
    reference_capacity_mw = type_costs["reference_capacity_mw"]
    capex_scaling_exponent = type_costs["capex_scaling_exponent"]

    scale_ratio = system_capacity / reference_capacity_mw
    scaled_capex_per_kw = capex_per_kw * (scale_ratio ** (capex_scaling_exponent - 1.0))
    expected_capex = scaled_capex_per_kw * system_capacity * 1000.0

    dt = plant_config["plant"]["simulation"]["dt"]
    delivered_electricity_MWh = electricity_out.sum() * dt / 3600
    expected_fixed_om = fixed_opex_per_kw_year * system_capacity * 1000.0
    expected_variable_om = variable_opex_per_mwh * delivered_electricity_MWh
    expected_opex = expected_fixed_om
    expected_varopex = expected_variable_om

    with subtests.test("Nuclear capital cost"):
        assert pytest.approx(capex, rel=1e-6) == expected_capex

    with subtests.test("Nuclear operating cost"):
        assert pytest.approx(opex, rel=1e-6) == expected_opex

    with subtests.test("Nuclear variable operating cost"):
        assert pytest.approx(prob.get_val("VarOpEx")[0], rel=1e-6) == expected_varopex

    with subtests.test("Nuclear cost year"):
        assert cost_year == nuclear_cost_params["cost_year"]
