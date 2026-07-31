import numpy as np
import pytest
import openmdao.api as om
from pytest import fixture

from h2integrate.converters.nuclear.nuclear_plant_thermal import (
    SimpleThermalNuclearReactorCostModel,
    SimpleThermalNuclearReactorPerformanceModel,
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
def thermal_performance_params():
    return {
        "operating_mode": "heat",
        "electricity_command_value": 500.0,
        "high_pressure_electrical_efficiency": 0.2,
        "low_pressure_electrical_efficiency": 0.5,
        "rated_capacity": 600.0,
        "minimum_heat_extract": 0.0,
    }


@fixture
def thermal_cost_params():
    return {
        "rated_capacity": 600.0,
        "upfront_cost": 5750000.0,
        "fixed_om_cost": 2640,
        "variable_om_cost": 145.0,
        "cost_year": 2022,
    }


def _build_performance_problem(plant_config, performance_params):
    tech_config_dict = {
        "model_inputs": {
            "performance_parameters": performance_params,
        }
    }

    prob = om.Problem()
    perf_comp = SimpleThermalNuclearReactorPerformanceModel(
        plant_config=plant_config,
        tech_config=tech_config_dict,
        driver_config={},
    )
    prob.model.add_subsystem("nuc_thermal_perf", perf_comp, promotes=["*"])
    prob.setup()
    return prob


@pytest.mark.unit
def test_thermal_performance_heat_mode(plant_config, thermal_performance_params, subtests):
    n_timesteps = plant_config["plant"]["simulation"]["n_timesteps"]
    plant_life = plant_config["plant"]["plant_life"]

    prob = _build_performance_problem(plant_config, thermal_performance_params)
    prob.set_val("heat_command_value", np.full(n_timesteps, 400.0), units="MW")
    prob.run_model()

    # thermal_capacity = 600 / (0.2 + 0.8 * 0.5) = 1000 MW
    # available process heat = 1000 * 0.8 = 800 MW
    # heat_out = min(400, 800) = 400 MW
    # electricity_out = 200 (HP) + (800 - 400) * 0.5 = 400 MW
    with subtests.test("Delivered process heat matches demand"):
        assert pytest.approx(prob.get_val("heat_out", units="kW")) == np.full(n_timesteps, 400000.0)

    with subtests.test("Electricity output in heat mode"):
        assert pytest.approx(prob.get_val("electricity_out", units="kW")) == (
            np.full(n_timesteps, 400000.0)
        )

    with subtests.test("High-pressure heat stream"):
        assert pytest.approx(prob.get_val("high_pressure_heat", units="kW")) == (
            np.full(n_timesteps, 800000.0)
        )

    with subtests.test("Low-pressure heat remaining"):
        assert pytest.approx(prob.get_val("low_pressure_heat", units="kW")) == (
            np.full(n_timesteps, 400000.0)
        )

    with subtests.test("Thermal split is conserved"):
        hp_heat = prob.get_val("high_pressure_heat", units="kW")
        lp_heat = prob.get_val("low_pressure_heat", units="kW")
        heat_out = prob.get_val("heat_out", units="kW")
        assert np.allclose(hp_heat, lp_heat + heat_out, rtol=1e-6)

    with subtests.test("Rated electricity production"):
        assert (
            pytest.approx(prob.get_val("rated_electricity_production", units="kW")[0]) == 600000.0
        )

    with subtests.test("Capacity factor in heat mode"):
        assert pytest.approx(prob.get_val("capacity_factor"), rel=1e-6) == np.full(
            plant_life, 400.0 / 600.0
        )

    with subtests.test("Annual electricity production"):
        assert pytest.approx(
            prob.get_val("annual_electricity_produced", units="MW*h/year")
        ) == np.full(plant_life, 400.0 * n_timesteps)


@pytest.mark.unit
def test_thermal_performance_electricity_mode(plant_config, thermal_performance_params, subtests):
    n_timesteps = plant_config["plant"]["simulation"]["n_timesteps"]
    plant_life = plant_config["plant"]["plant_life"]

    performance_params = dict(thermal_performance_params)
    performance_params["operating_mode"] = "electricity"

    prob = _build_performance_problem(plant_config, performance_params)
    prob.set_val("electricity_command_value", np.full(n_timesteps, 500000.0), units="kW")
    prob.run_model()

    # electricity_out = min(500, 600) = 500 MW
    # heat_out = 800 - (500 - 200) / 0.5 = 200 MW
    with subtests.test("Electricity output tracks command"):
        assert pytest.approx(prob.get_val("electricity_out", units="kW")) == (
            np.full(n_timesteps, 500000.0)
        )

    with subtests.test("Process heat after electricity dispatch"):
        assert pytest.approx(prob.get_val("heat_out", units="kW")) == np.full(n_timesteps, 200000.0)

    with subtests.test("Thermal split is conserved"):
        hp_heat = prob.get_val("high_pressure_heat", units="kW")
        lp_heat = prob.get_val("low_pressure_heat", units="kW")
        heat_out = prob.get_val("heat_out", units="kW")
        assert np.allclose(hp_heat, lp_heat + heat_out, rtol=1e-6)

    with subtests.test("Capacity factor in electricity mode"):
        assert pytest.approx(prob.get_val("capacity_factor"), rel=1e-6) == np.full(
            plant_life, 500.0 / 600.0
        )


@pytest.mark.unit
def test_thermal_performance_electricity_capped_at_capacity(
    plant_config, thermal_performance_params, subtests
):
    n_timesteps = plant_config["plant"]["simulation"]["n_timesteps"]

    performance_params = dict(thermal_performance_params)
    performance_params["operating_mode"] = "electricity"

    prob = _build_performance_problem(plant_config, performance_params)
    # Command more than the rated electrical capacity (600 MW)
    prob.set_val("electricity_command_value", np.full(n_timesteps, 900000.0), units="kW")
    prob.run_model()

    with subtests.test("Electricity output clipped to rated capacity"):
        assert pytest.approx(prob.get_val("electricity_out", units="kW")) == (
            np.full(n_timesteps, 600000.0)
        )


@pytest.mark.unit
def test_thermal_cost_model(plant_config, thermal_cost_params, subtests):
    plant_life = plant_config["plant"]["plant_life"]

    half_year_plant_config = {
        **plant_config,
        "plant": {
            **plant_config["plant"],
            "simulation": {
                **plant_config["plant"]["simulation"],
                "n_timesteps": 4380,
            },
        },
    }
    n_timesteps = half_year_plant_config["plant"]["simulation"]["n_timesteps"]

    tech_config_dict = {
        "model_inputs": {
            "cost_parameters": thermal_cost_params,
        }
    }

    electricity_out = np.full(n_timesteps, 400.0)

    prob = om.Problem()
    cost_comp = SimpleThermalNuclearReactorCostModel(
        plant_config=half_year_plant_config,
        tech_config=tech_config_dict,
        driver_config={},
    )
    prob.model.add_subsystem("nuc_thermal_cost", cost_comp, promotes=["*"])
    prob.setup()

    prob.set_val("electricity_out", electricity_out, units="kW")
    prob.run_model()

    rated_capacity_mw = thermal_cost_params["rated_capacity"]
    upfront_cost_per_mw = thermal_cost_params["upfront_cost"]
    fixed_om_per_mw_year = thermal_cost_params["fixed_om_cost"]
    variable_om_per_mwh = thermal_cost_params["variable_om_cost"]

    dt = half_year_plant_config["plant"]["simulation"]["dt"]
    delivered_electricity_mwh = electricity_out.sum() * (dt / 3600.0)
    fraction_of_year_simulated = (dt * n_timesteps / 3600.0) / 8760.0

    with subtests.test("Thermal reactor capital cost"):
        assert pytest.approx(prob.get_val("CapEx", units="USD")[0], rel=1e-6) == (
            rated_capacity_mw * upfront_cost_per_mw
        )

    with subtests.test("Thermal reactor fixed operating cost"):
        assert pytest.approx(prob.get_val("OpEx", units="USD/year")[0], rel=1e-6) == (
            fixed_om_per_mw_year * rated_capacity_mw
        )

    with subtests.test("Thermal reactor variable operating cost"):
        expected_varopex = (
            variable_om_per_mwh * delivered_electricity_mwh / fraction_of_year_simulated
        )
        assert pytest.approx(prob.get_val("VarOpEx", units="USD/year"), rel=1e-6) == np.full(
            plant_life, expected_varopex
        )

    with subtests.test("Thermal reactor cost year"):
        assert prob.get_val("cost_year") == thermal_cost_params["cost_year"]
