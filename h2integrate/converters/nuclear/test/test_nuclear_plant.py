import numpy as np
import pytest
import openmdao.api as om
from pytest import fixture

from h2integrate.converters.nuclear.nuclear_plant import (
    QuinnNuclearCostModel,
    QuinnNuclearPerformanceModel,
)


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
        "system_capacity_kw": 300000.0,
    }


@fixture
def nuclear_cost_params():
    return {
        "system_capacity_kw": 450000.0,
        "capex_per_kw": 6000.0,
        "fixed_opex_per_kw_year": 120.0,
        "variable_opex_per_mwh": 2.5,
        "reference_capacity_kw": 300000.0,
        "capex_scaling_exponent": 0.9,
        "cost_year": 2023,
    }


@pytest.mark.unit
def test_nuclear_performance_demand(plant_config, nuclear_performance_params, subtests):
    tech_config_dict = {
        "model_inputs": {
            "performance_parameters": nuclear_performance_params,
        }
    }

    system_capacity = nuclear_performance_params["system_capacity_kw"]
    demand_section = np.linspace(0, 1.2 * system_capacity, 12)
    electricity_demand = np.tile(demand_section, 730)

    prob = om.Problem()
    perf_comp = QuinnNuclearPerformanceModel(
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


@pytest.mark.unit
def test_nuclear_cost_model(plant_config, nuclear_cost_params, subtests):
    tech_config_dict = {
        "model_inputs": {
            "cost_parameters": nuclear_cost_params,
        }
    }

    system_capacity = nuclear_cost_params["system_capacity_kw"]
    electricity_out = np.full(8760, 360000.0)

    prob = om.Problem()
    cost_comp = QuinnNuclearCostModel(
        plant_config=plant_config,
        tech_config=tech_config_dict,
        driver_config={},
    )

    prob.model.add_subsystem("nuc_cost", cost_comp, promotes=["*"])
    prob.setup()

    prob.set_val("system_capacity", system_capacity)
    prob.set_val("electricity_out", electricity_out)
    prob.run_model()

    capex = prob.get_val("CapEx", units="USD")[0]
    opex = prob.get_val("OpEx", units="USD/yr")[0]
    cost_year = prob.get_val("cost_year")

    capex_per_kw = nuclear_cost_params["capex_per_kw"]
    fixed_opex_per_kw_year = nuclear_cost_params["fixed_opex_per_kw_year"]
    variable_opex_per_mwh = nuclear_cost_params["variable_opex_per_mwh"]
    reference_capacity_kw = nuclear_cost_params["reference_capacity_kw"]
    capex_scaling_exponent = nuclear_cost_params["capex_scaling_exponent"]

    scale_ratio = system_capacity / reference_capacity_kw
    scaled_capex_per_kw = capex_per_kw * (scale_ratio ** (capex_scaling_exponent - 1.0))
    expected_capex = scaled_capex_per_kw * system_capacity

    dt = plant_config["plant"]["simulation"]["dt"]
    delivered_electricity_mwh = electricity_out.sum() * dt / 3600 / 1000.0
    expected_fixed_om = fixed_opex_per_kw_year * system_capacity
    expected_variable_om = variable_opex_per_mwh * delivered_electricity_mwh
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
