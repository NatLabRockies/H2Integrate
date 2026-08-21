import numpy as np
import pytest
import openmdao.api as om
from pytest import fixture

from h2integrate.converters.hydrogen.PEM_h2_fuel_cell import PEMH2FuelCellPerformanceModel


@fixture
def plant_config():
    plant_config = {
        "plant": {
            "plant_life": 30,
            "simulation": {
                "n_timesteps": 48,
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
                "system_capacity_kw": 1500.0,
                "n_stacks": 60,
                "stack_temperature_K": 278.0,
                "hhv": 39.4,  # kWh/kg
            }
        }
    }
    return config


@pytest.mark.regression
def test_fuel_cell_performance(tech_config, plant_config, subtests):
    n_timesteps = int(plant_config["plant"]["simulation"]["n_timesteps"])

    prob = om.Problem()

    fuel_cell = PEMH2FuelCellPerformanceModel(
        plant_config=plant_config, tech_config=tech_config, driver_config={}
    )

    prob.model.add_subsystem("fuel_cell", fuel_cell, promotes=["*"])

    prob.setup()

    # Provide ample hydrogen and oxygen to run at the default command (rated capacity)
    hydrogen_input = np.ones(n_timesteps) * 200.0  # kg/h
    oxygen_input = np.ones(n_timesteps) * 2000.0  # kg/h

    prob.set_val("fuel_cell.hydrogen_in", hydrogen_input, units="kg/h")
    prob.set_val("fuel_cell.oxygen_in", oxygen_input, units="kg/h")
    prob.set_val("fuel_cell.electricity_command_value", np.ones(n_timesteps) * 1000.0, units="kW")

    prob.run_model()

    electricity_output = prob.get_val("fuel_cell.electricity_out", units="kW")
    prob.get_val("fuel_cell.hydrogen_consumed", units="kg/h")
    prob.get_val("fuel_cell.oxygen_consumed", units="kg/h")
    prob.get_val("fuel_cell.water_out", units="kg/h")

    with subtests.test("max electricity output bounded by system capacity"):
        assert np.max(electricity_output) <= 1500.0 + 1e-6

    with subtests.test("electricity output is non-negative"):
        assert np.min(electricity_output) >= 0.0

    with subtests.test("total_electricity_produced matches sum of output"):
        assert pytest.approx(
            prob.get_val("fuel_cell.total_electricity_produced", units="kW*h"), rel=1e-6
        ) == np.sum(electricity_output)

    with subtests.test("electricity out"):
        assert (
            pytest.approx(np.sum(prob.get_val("fuel_cell.electricity_out", units="kW")), rel=1e-6)
            == 48209.20157
        )

    with subtests.test("capacity_factor"):
        assert (
            pytest.approx(prob.get_val("fuel_cell.capacity_factor", units="unitless"), rel=1e-2)
            == 0.669
        )

    with subtests.test("annual_electricity_production"):
        assert (
            pytest.approx(
                prob.get_val("fuel_cell.annual_electricity_produced", units="kW*h/year"), rel=1e-2
            )
            == 8760000.86
        )

    with subtests.test("rated_electricity_production"):
        assert (
            pytest.approx(
                prob.get_val("fuel_cell.rated_electricity_production", units="kW"), rel=1e-4
            )
            == 1498.9
        )

    with subtests.test("total_electricity_produced"):
        assert (
            pytest.approx(
                prob.get_val("fuel_cell.total_electricity_produced", units="kW*h"), rel=1e-6
            )
            == 48209.20157
        )

    with subtests.test("hydrogen consumed"):
        assert (
            pytest.approx(
                np.sum(prob.get_val("fuel_cell.hydrogen_consumed", units="kg/h")), rel=1e-6
            )
            == 2291.481556
        )

    with subtests.test("oxygen consumed"):
        assert (
            pytest.approx(np.sum(prob.get_val("fuel_cell.oxygen_consumed", units="kg/h")), rel=1e-6)
            == 18185.22451853
        )

    with subtests.test("water out"):
        assert (
            pytest.approx(np.sum(prob.get_val("fuel_cell.water_out", units="kg/h")), rel=1e-6)
            == 20476.70602546
        )

    with subtests.test("rated h2 consumed"):
        assert (
            pytest.approx(prob.get_val("fuel_cell.rated_h2_consumed", units="kg/h"), rel=1e-6)
            == 76.5012465
        )

    with subtests.test("rated o2 consumed"):
        assert (
            pytest.approx(prob.get_val("fuel_cell.rated_o2_consumed", units="kg/h"), rel=1e-6)
            == 607.11480
        )

    with subtests.test("rated water out"):
        assert (
            pytest.approx(prob.get_val("fuel_cell.rated_water_out", units="kg/h"), rel=1e-6)
            == 683.6160498
        )

    with subtests.test("rated heat out"):
        assert (
            pytest.approx(prob.get_val("fuel_cell.rated_heat_out", units="kW"), rel=1e-6)
            == 1515.1571138
        )


@pytest.mark.unit
def test_fuel_cell_demand(tech_config, plant_config, subtests):
    n_timesteps = int(plant_config["plant"]["simulation"]["n_timesteps"])

    prob = om.Problem()

    fuel_cell = PEMH2FuelCellPerformanceModel(
        plant_config=plant_config, tech_config=tech_config, driver_config={}
    )

    prob.model.add_subsystem("fuel_cell", fuel_cell, promotes=["*"])

    prob.setup()

    # Provide ample feedstock for most timesteps; constrain a few to test edge cases
    hydrogen_input = np.ones(n_timesteps) * 200.0  # kg/h
    oxygen_input = np.ones(n_timesteps) * 2000.0  # kg/h

    # Edge cases for feedstock supply at the first 6 timesteps
    hydrogen_input[:6] = (
        500000000.0,  # very high H2 supply
        500000000.0,  # very high H2 supply with low set point
        200.0,  # ample
        0.0,  # zero hydrogen supply
        1.0,  # very limited hydrogen supply
        200.0,  # ample
    )
    oxygen_input[:6] = (
        2000.0,
        2000.0,
        2000.0,
        2000.0,
        2000.0,
        0.0,  # zero oxygen supply
    )

    prob.set_val("fuel_cell.hydrogen_in", hydrogen_input, units="kg/h")
    prob.set_val("fuel_cell.oxygen_in", oxygen_input, units="kg/h")

    elec_set_point = np.ones(n_timesteps) * 1500.0  # kW
    elec_set_point[:6] = (
        1500.0,  # set point equal to system capacity
        500.0,  # set point below system capacity
        1500.0,  # set point equal to system capacity
        1500.0,  # set point equal to system capacity, no H2 supply
        1500.0,  # set point equal to system capacity, limited H2 supply
        0.0,  # zero set point
    )

    prob.set_val("fuel_cell.electricity_command_value", elec_set_point, units="kW")

    prob.run_model()

    electricity_output = prob.get_val("fuel_cell.electricity_out", units="kW")
    hydrogen_consumed = prob.get_val("fuel_cell.hydrogen_consumed", units="kg/h")
    oxygen_consumed = prob.get_val("fuel_cell.oxygen_consumed", units="kg/h")
    water_out = prob.get_val("fuel_cell.water_out", units="kg/h")

    with subtests.test("output clipped to system capacity"):
        assert electricity_output[0] == pytest.approx(1500.0, rel=1e-3)

    with subtests.test("output follows reduced set point"):
        # When set point is below capacity and feedstock is ample, output tracks set point
        assert electricity_output[1] == pytest.approx(500.0, rel=1e-2)

    with subtests.test("output non-negative when ample supply"):
        assert electricity_output[2] >= 0.0
        assert electricity_output[2] <= 1500.0 + 1e-6

    with subtests.test("zero hydrogen feedstock supply yields zero output"):
        assert electricity_output[3] == pytest.approx(0.0, abs=1e-6)

    with subtests.test("limited hydrogen feedstock supply yields reduced output"):
        assert electricity_output[4] < 30.0
        assert electricity_output[4] > 0.0

    with subtests.test("zero set point yields zero output"):
        assert electricity_output[5] == pytest.approx(0.0, abs=1e-6)

    # Test hydrogen_consumed, oxygen_consumed, and water_out for the first 6 timesteps
    with subtests.test("hydrogen consumed"):
        expected_h2_consumed = [76.501247, 22.920501, 76.501247, 0, 1, 0.0]
        np.testing.assert_allclose(hydrogen_consumed[:6], expected_h2_consumed, rtol=1e-4)

    with subtests.test("oxygen consumed"):
        expected_o2_consumed = [607.114803, 181.897366, 607.114803, 0, 7.936012, 0.0]
        np.testing.assert_allclose(oxygen_consumed[:6], expected_o2_consumed, rtol=1e-4)

    with subtests.test("water out"):
        expected_water_out = [683.61605, 204.817867, 683.61605, 0.0, 8.936012, 0.0]
        np.testing.assert_allclose(water_out[:6], expected_water_out, rtol=1e-4)
