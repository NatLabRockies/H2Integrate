import numpy as np
import pytest
import openmdao.api as om
from pytest import fixture

from h2integrate.converters.natural_gas.SO_NG_fuel_cell import SONGFuelCellPerformanceModel


@fixture
def plant_config():
    plant_config = {
        "plant": {
            "plant_life": 1,
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
                "stack_temperature_K": 1073.0,
                "hhv": 15.4,  # kWh/kg --> based on methane
            }
        }
    }
    return config


@pytest.mark.regression
def test_fuel_cell_performance(tech_config, plant_config, subtests):
    n_timesteps = int(plant_config["plant"]["simulation"]["n_timesteps"])

    prob = om.Problem()

    fuel_cell = SONGFuelCellPerformanceModel(
        plant_config=plant_config, tech_config=tech_config, driver_config={}
    )

    prob.model.add_subsystem("fuel_cell", fuel_cell, promotes=["*"])

    prob.setup()

    # Provide ample natural gas and oxygen to run at the default command (rated capacity)
    natural_gas_input = np.ones(n_timesteps) * 10.0  # MMBtu/h
    oxygen_input = np.ones(n_timesteps) * 2000.0  # kg/h

    prob.set_val("fuel_cell.natural_gas_in", natural_gas_input, units="MMBtu/h")
    prob.set_val("fuel_cell.oxygen_in", oxygen_input, units="kg/h")
    prob.set_val("fuel_cell.electricity_command_value", np.ones(n_timesteps) * 1000.0, units="kW")

    prob.run_model()

    with subtests.test("max electricity output"):
        assert (
            pytest.approx(np.max(prob.get_val("fuel_cell.electricity_out", units="kW")), rel=1e-2)
            == 1000.0
        )

    with subtests.test("electricity out"):
        assert (
            pytest.approx(np.sum(prob.get_val("fuel_cell.electricity_out", units="kW")), rel=1e-6)
            == 48209.2
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
            == 48209.2
        )

    with subtests.test("natural gas consumed"):
        assert (
            pytest.approx(
                np.sum(prob.get_val("fuel_cell.natural_gas_consumed", units="MMBtu/h")), rel=1e-6
            )
            == 216.00547288
        )

    with subtests.test("oxygen consumed"):
        assert (
            pytest.approx(np.sum(prob.get_val("fuel_cell.oxygen_consumed", units="kg/h")), rel=1e-6)
            == 18185.2245185
        )

    with subtests.test("water out"):
        assert (
            pytest.approx(np.sum(prob.get_val("fuel_cell.water_out", units="kg/h")), rel=1e-6)
            == 20476.7060254
        )

    with subtests.test("co2 out"):
        assert (
            pytest.approx(np.sum(prob.get_val("fuel_cell.co2_out", units="kg/h")), rel=1e-6)
            == 12505.9649206
        )

    with subtests.test("rated natural gas consumed"):
        assert (
            pytest.approx(
                prob.get_val("fuel_cell.rated_natural_gas_consumed", units="MMBtu/h"), rel=1e-6
            )
            == 7.2113556
        )

    with subtests.test("rated oxygen consumed"):
        assert (
            pytest.approx(prob.get_val("fuel_cell.rated_oxygen_consumed", units="kg/h"), rel=1e-6)
            == 607.11480
        )

    with subtests.test("rated water out"):
        assert (
            pytest.approx(prob.get_val("fuel_cell.rated_water_out", units="kg/h"), rel=1e-6)
            == 683.61604984
        )

    with subtests.test("rated co2 out"):
        assert (
            pytest.approx(prob.get_val("fuel_cell.rated_co2_out", units="kg/h"), rel=1e-6)
            == 417.512383
        )

    with subtests.test("rated heat out"):
        assert (
            pytest.approx(prob.get_val("fuel_cell.rated_heat_out", units="kW"), rel=1e-6)
            == 844.389934  # TODO: update expected value
        )


@pytest.mark.unit
def test_fuel_cell_demand(tech_config, plant_config, subtests):
    n_timesteps = int(plant_config["plant"]["simulation"]["n_timesteps"])

    prob = om.Problem()

    fuel_cell = SONGFuelCellPerformanceModel(
        plant_config=plant_config, tech_config=tech_config, driver_config={}
    )

    prob.model.add_subsystem("fuel_cell", fuel_cell, promotes=["*"])

    prob.setup()

    # Provide ample feedstock supply for most timesteps; constrain a few to test
    # feedstock-limited dynamics.
    natural_gas_input = np.ones(n_timesteps) * 30.0  # MMBtu/h
    oxygen_input = np.ones(n_timesteps) * 2000.0  # kg/h

    # Edge cases for feedstock supply at timesteps 5-7
    natural_gas_input[5:8] = (
        0.0,  # zero NG supply -> output should collapse to zero
        1,  # severely limited NG supply -> output reduced
        20.0,  # ample NG supply, but O2 will be limited below
    )
    oxygen_input[5:8] = (
        2000.0,
        2000.0,
        0.0,  # zero O2 supply -> output should collapse to zero
    )

    prob.set_val("fuel_cell.natural_gas_in", natural_gas_input, units="MMBtu/h")
    prob.set_val("fuel_cell.oxygen_in", oxygen_input, units="kg/h")

    elec_set_point = np.ones(n_timesteps) * 1500.0  # kW

    # First 5 timesteps test set-point edge cases (with ample feedstock).
    # Timesteps 5-7 test feedstock-limited dynamics at rated set point.
    elec_set_point[:5] = (
        1500.0,  # set point equal to system capacity
        500.0,  # set point below system capacity
        2500.0,  # very high set point (should be clipped to system capacity)
        0.0,  # zero set point
        750.0,  # set point at half of system capacity
    )

    prob.set_val("fuel_cell.electricity_command_value", elec_set_point, units="kW")

    prob.run_model()

    electricity_output = prob.get_val("fuel_cell.electricity_out", units="kW")
    ng_consumed = prob.get_val("fuel_cell.natural_gas_consumed", units="MMBtu/h")
    o2_consumed = prob.get_val("fuel_cell.oxygen_consumed", units="kg/h")
    water_out = prob.get_val("fuel_cell.water_out", units="kg/h")
    co2_out = prob.get_val("fuel_cell.co2_out", units="kg/h")

    with subtests.test("output bounded by system capacity"):
        assert np.max(electricity_output) <= 1500.0 + 1e-6

    with subtests.test("output non-negative"):
        assert np.min(electricity_output) >= 0.0

    with subtests.test("output clipped to system capacity at rated set point"):
        assert electricity_output[0] == pytest.approx(1500.0, rel=1e-2)

    with subtests.test("output follows reduced set point"):
        assert electricity_output[1] == pytest.approx(500.0, rel=1e-2)

    with subtests.test("very high set point clipped to system capacity"):
        assert electricity_output[2] == pytest.approx(1500.0, rel=1e-2)

    with subtests.test("zero set point yields zero output"):
        assert electricity_output[3] == pytest.approx(0.0, abs=1e-6)

    with subtests.test("half-rated set point yields ~half output"):
        assert electricity_output[4] == pytest.approx(750.0, rel=5e-2)

    with subtests.test("natural gas consumed non-negative"):
        assert np.min(ng_consumed) >= 0.0

    with subtests.test("oxygen consumed non-negative"):
        assert np.min(o2_consumed) >= 0.0

    with subtests.test("water produced non-negative"):
        assert np.min(water_out) >= 0.0

    with subtests.test("CO2 produced non-negative"):
        assert np.min(co2_out) >= 0.0

    with subtests.test("zero set point yields zero consumption and byproducts"):
        assert ng_consumed[3] == pytest.approx(0.0, abs=1e-6)
        assert o2_consumed[3] == pytest.approx(0.0, abs=1e-6)
        assert water_out[3] == pytest.approx(0.0, abs=1e-6)
        assert co2_out[3] == pytest.approx(0.0, abs=1e-6)

    # Feedstock-limited dynamics:

    with subtests.test("zero NG supply collapses output to zero"):
        assert electricity_output[5] == pytest.approx(0.0, abs=1e-6)
        assert ng_consumed[5] == pytest.approx(0.0, abs=1e-6)
        assert o2_consumed[5] == pytest.approx(0.0, abs=1e-6)
        assert water_out[5] == pytest.approx(0.0, abs=1e-6)
        assert co2_out[5] == pytest.approx(0.0, abs=1e-6)

    with subtests.test("limited NG supply reduces electricity output and byproducts"):
        assert electricity_output[6] == pytest.approx(258.4037579, rel=1e-2)
        assert ng_consumed[6] == pytest.approx(1.0, rel=1e-2)
        assert o2_consumed[6] == pytest.approx(84.18872, rel=1e-2)
        assert water_out[6] == pytest.approx(94.7971630, rel=1e-2)
        assert co2_out[6] == pytest.approx(57.8965188, rel=1e-2)

    with subtests.test("zero O2 supply collapses output to zero"):
        assert electricity_output[7] == pytest.approx(0.0, abs=1e-6)
        assert ng_consumed[7] == pytest.approx(0.0, abs=1e-6)
        assert o2_consumed[7] == pytest.approx(0.0, abs=1e-6)
        assert water_out[7] == pytest.approx(0.0, abs=1e-6)
        assert co2_out[7] == pytest.approx(0.0, abs=1e-6)
