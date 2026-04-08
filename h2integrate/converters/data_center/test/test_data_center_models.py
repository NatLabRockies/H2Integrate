import numpy as np
import pytest
import openmdao.api as om
from pytest import fixture

from h2integrate.converters.data_center.data_center import (
    DataCenterCostModel,
    DataCenterPerformanceModel,
)


@fixture
def data_center_performance_params():
    """Data Center performance parameters."""
    tech_params = {
        "system_capacity_mw": 100,
        "compute_electrical_efficiency": 0.92,
        "cooling_load_ratio": 0.2,
        "water_use_per_mwh": 1200,  # galUS/MWh
    }
    return tech_params


@fixture
def data_center_cost_params():
    """Data Center cost parameters."""
    cost_params = {
        "capex_per_mw": 10E6,  # $/MW
        "fixed_opex_per_mw_per_year": 5.6E6,  # $/MW/year
        "variable_opex_per_mwh": 50,  # $/MWh
        "system_capacity_mw": 100,  # MW
        "cost_year": 2023,
    }
    return cost_params


@fixture
def plant_config():
    """Fixture to get plant configuration."""
    return {
        "plant": {
            "plant_life": 30,
            "simulation": {
                "n_timesteps": 8760,
                "dt": 3600,
            },
        },
    }


@pytest.mark.regression
def test_data_center_performance(plant_config, data_center_performance_params, subtests):
    """Test Data Center performance model with typical operating conditions."""
    tech_config_dict = {
        "model_inputs": {
            "performance_parameters": data_center_performance_params,
        }
    }

    system_capacity = data_center_performance_params["system_capacity_mw"]

    # Create a simple compute demand input profile (constant 100MW/h for 100 MW plant)
    compute_load_demand = np.full(8760, system_capacity)  # MW
    # MW, accounting for 92% efficiency (100 MW / 0.92) and 20% additional cooling load
    electrical_compute_load_demand = (
            compute_load_demand / data_center_performance_params["compute_electrical_efficiency"]
        )
    electricity_in = np.full(
        8760, (
            electrical_compute_load_demand
            + electrical_compute_load_demand
            * data_center_performance_params["cooling_load_ratio"]
        )
    )

    prob = om.Problem()
    perf_comp = DataCenterPerformanceModel(
        plant_config=plant_config,
        tech_config=tech_config_dict,
    )

    prob.model.add_subsystem("data_center_perf", perf_comp, promotes=["*"])
    prob.setup()

    # Set the compute load demand input
    prob.set_val("compute_load_demand", compute_load_demand)
    prob.set_val("electricity_in", electricity_in)
    prob.run_model()

    with subtests.test("Data Center Unmet Electricity Demand Output"):
        # Check that there is zero unmet electricity demand since the input is sufficient
        unmet_electricity_demand = prob.get_val("unmet_electricity_demand", units="MW")
        expected_output = [0.0] * plant_config["plant"]["simulation"]["n_timesteps"]
        assert pytest.approx(unmet_electricity_demand, rel=1e-6) == expected_output

    with subtests.test("Data Center Compute Load Output"):
        # Check compute load output is equal to the system capacity
        compute_load_out = prob.get_val("compute_load_out", units="MW")
        expected_output = [system_capacity] * plant_config["plant"]["simulation"]["n_timesteps"]
        assert pytest.approx(compute_load_out, rel=1e-6) == expected_output

    with subtests.test("Data Center Water usage"):
        # Check water usage
        water_consumed = prob.get_val("water_consumed", units="galUS/h")
        expected_output = (
            compute_load_demand
            / data_center_performance_params["compute_electrical_efficiency"]
            * data_center_performance_params["water_use_per_mwh"]
        )
        assert pytest.approx(water_consumed, rel=1e-6) == expected_output
