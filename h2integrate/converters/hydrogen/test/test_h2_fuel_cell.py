import numpy as np
import pytest
import openmdao.api as om
from pytest import fixture

from h2integrate.converters.hydrogen.h2_fuel_cell import (
    H2FuelCellCostModel,
    LinearH2FuelCellPerformanceModel,
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
    config = {
        "model_inputs": {
            "performance_parameters": {
                "system_capacity_kw": 1000.0,
                "fuel_cell_efficiency_hhv": 0.50,
            }
        }
    }
    return config


@fixture
def cost_config():
    config = {
        "model_inputs": {
            "cost_parameters": {
                "system_capacity_kw": 1000.0,
                "capex_per_kw": 200.0,
                "fixed_opex_per_kw_per_year": 10.0,
                "cost_year": 2018,
            }
        }
    }
    return config


def test_fuel_cell_performance(tech_config, plant_config, subtests):
    n_timesteps = int(plant_config["plant"]["simulation"]["n_timesteps"])

    prob = om.Problem()

    fuel_cell = LinearH2FuelCellPerformanceModel(
        plant_config=plant_config, tech_config=tech_config, driver_config={}
    )

    prob.model.add_subsystem("fuel_cell", fuel_cell, promotes=["*"])

    prob.setup()

    hydrogen_input = np.ones(n_timesteps) * 20.0  # kg/h
    hydrogen_input[0] = (
        500000000.0  # test extreme case of very high hydrogen input to check system capacity limit
    )

    prob.set_val("fuel_cell.hydrogen_in", hydrogen_input, units="kg/h")

    prob.run_model()

    # Check that electricity output is less than or equal to system capacity
    electricity_output = prob.get_val("fuel_cell.electricity_out", units="kW")

    with subtests.test("max electricity output"):
        assert max(electricity_output) == 1000.0

    with subtests.test("electricity output non-negative"):
        assert np.all(electricity_output >= 0)

    with subtests.test("electricity out"):
        assert pytest.approx(np.sum(electricity_output), rel=1e-6) == 3452532.6111

    with subtests.test("capacity_factor"):
        assert (
            pytest.approx(prob.get_val("fuel_cell.capacity_factor", units="unitless"), rel=1e-6)
            == 0.39412473
        )

    with subtests.test("annual_electricity_production"):
        assert (
            pytest.approx(
                prob.get_val("fuel_cell.annual_electricity_produced", units="kW*h/year"), rel=1e-6
            )
            == 3452532.6111
        )

    with subtests.test("rated_electricity_production"):
        assert (
            pytest.approx(
                prob.get_val("fuel_cell.rated_electricity_production", units="kW"), rel=1e-6
            )
            == 1000.0
        )

    with subtests.test("total_electricity_produced"):
        assert (
            pytest.approx(
                prob.get_val("fuel_cell.total_electricity_produced", units="kW*h"), rel=1e-6
            )
            == 3452532.6111
        )

    with subtests.test("hydrogen consumed"):
        assert (
            pytest.approx(
                np.sum(prob.get_val("fuel_cell.hydrogen_consumed", units="kg/h")), rel=1e-6
            )
            == 175230.7542647681
        )


def test_fuel_cell_cost(cost_config, plant_config, subtests):
    int(plant_config["plant"]["simulation"]["n_timesteps"])

    prob = om.Problem()

    fuel_cell_cost = H2FuelCellCostModel(
        plant_config=plant_config, tech_config=cost_config, driver_config={}
    )

    prob.model.add_subsystem("fuel_cell_cost", fuel_cell_cost, promotes=["*"])

    prob.setup()

    prob.run_model()

    with subtests.test("capex value"):
        assert prob.get_val("fuel_cell_cost.CapEx", units="USD") == 200000.0

    with subtests.test("opex value"):
        assert prob.get_val("fuel_cell_cost.OpEx", units="USD/year") == 10000.0
