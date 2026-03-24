import numpy as np
import pytest
import openmdao.api as om
from pytest import fixture

from h2integrate.storage.battery.pysam_battery import PySAMBatteryPerformanceModel
from h2integrate.control.control_strategies.optimized_pyomo_controller import (
    OptimizedDispatchController,
)


@fixture
def plant_config():
    plant_config = {
        "plant": {
            "plant_life": 1,
            "simulation": {
                "dt": 3600,
                "n_timesteps": 48,
            },
        },
        "tech_to_dispatch_connections": [
            ["combiner", "battery"],
            ["battery", "battery"],
        ],
    }
    return plant_config


@fixture
def tech_config_generic():
    tech_config = {
        "technologies": {
            "battery": {
                "control_strategy": {"model": "OptimizedDispatchController"},
                "performance_model": {"model": "PySAMBatteryPerformanceModel"},
                "model_inputs": {
                    "shared_parameters": {
                        "max_charge_rate": 50000,
                        "max_capacity": 200000,
                        "init_soc_fraction": 0.5,
                        "max_soc_fraction": 0.9,
                        "min_soc_fraction": 0.1,
                        "commodity": "electricity",
                        "commodity_rate_units": "kW",
                        "charge_efficiency": 0.95,
                        "discharge_efficiency": 0.95,
                    },
                    "performance_parameters": {
                        "system_model_source": "pysam",
                        "chemistry": "LFPGraphite",
                        "control_variable": "input_power",
                        "demand_profile": 0.0,
                    },
                    "control_parameters": {
                        "tech_name": "battery",
                        "system_commodity_interface_limit": 1e12,
                        "cost_per_charge": 0.004,
                        "cost_per_discharge": 0.005,
                        "cost_per_production": 0.0,
                        "commodity_met_value": 0.1,
                        "round_digits": 4,
                        "time_weighting_factor": 0.995,
                        "n_control_window": 24,
                    },
                },
            },
        },
    }
    return tech_config


@pytest.mark.regression
def test_min_operating_cost_load_following_battery_dispatch(
    plant_config, tech_config_generic, subtests
):
    # Fabricate some oscillating power generation data: 1000 kW for the first 12 hours, 10000 kW for
    # the second twelve hours, and repeat that daily cycle over a year.
    n_look_ahead_third = int(24 / 3)

    electricity_in = np.concatenate(
        (
            np.ones(n_look_ahead_third) * 6000,
            np.ones(n_look_ahead_third) * 1000,
            np.ones(n_look_ahead_third) * 10000,
        )
    )
    electricity_in = np.tile(electricity_in, 2)

    demand_in = np.ones(48) * 6000.0

    # Setup the OpenMDAO problem and add subsystems
    prob = om.Problem()

    prob.model.add_subsystem(
        "battery_optimized_load_following_controller",
        OptimizedDispatchController(
            plant_config=plant_config, tech_config=tech_config_generic["technologies"]["battery"]
        ),
        promotes=["*"],
    )

    prob.model.add_subsystem(
        "battery",
        PySAMBatteryPerformanceModel(
            plant_config=plant_config, tech_config=tech_config_generic["technologies"]["battery"]
        ),
        promotes=["*"],
    )

    # Setup the system and required values
    prob.setup()
    prob.set_val("battery.electricity_in", electricity_in)
    prob.set_val("battery.electricity_demand", demand_in)

    # Run the model
    prob.run_model()

    charge_rate = prob.get_val("battery.max_charge_rate", units="kW")[0]
    discharge_rate = prob.get_val("battery.max_charge_rate", units="kW")[0]
    capacity = prob.get_val("battery.storage_capacity", units="kW*h")[0]

    # Test that discharge is always positive
    with subtests.test("Discharge is always positive"):
        assert np.all(prob.get_val("battery.battery_electricity_discharge") >= 0)
    with subtests.test("Charge is always negative"):
        assert np.all(prob.get_val("battery.battery_electricity_charge") <= 0)
    # Set rtol lower b/c the values are in kW
    with subtests.test("Charge + Discharge == battery_electricity_out"):
        charge_plus_discharge = prob.get_val("battery.battery_electricity_charge") + prob.get_val(
            "battery.battery_electricity_discharge"
        )
        np.testing.assert_allclose(
            charge_plus_discharge, prob.get_val("battery_electricity_out"), rtol=1e-2
        )
    with subtests.test("Initial SOC is correct"):
        assert pytest.approx(prob.model.get_val("battery.SOC")[0], rel=1e-2) == 50

    # Find where the signal increases, decreases, and stays at zero
    print("SOC", prob.model.get_val("battery.SOC"))
    indx_soc_increase = np.argwhere(
        np.diff(prob.model.get_val("battery.SOC", units="unitless"), prepend=True) > 0
    ).flatten()
    indx_soc_decrease = np.argwhere(
        np.diff(prob.model.get_val("battery.SOC", units="unitless"), prepend=False) < 0
    ).flatten()
    indx_soc_same = np.argwhere(
        np.diff(prob.model.get_val("battery.SOC", units="unitless"), prepend=True) == 0.0
    ).flatten()

    with subtests.test("SOC increases when charging"):
        assert np.all(
            prob.get_val("battery.battery_electricity_charge", units="kW")[indx_soc_increase] <= 0
        )
        assert np.all(
            prob.get_val("battery.battery_electricity_charge", units="kW")[indx_soc_decrease] == 0
        )
        assert np.all(
            prob.get_val("battery.battery_electricity_charge", units="kW")[indx_soc_same] == 0
        )

    with subtests.test("SOC decreases when discharging"):
        assert np.all(
            prob.get_val("battery.battery_electricity_discharge", units="kW")[indx_soc_decrease] > 0
        )
        assert np.all(
            prob.get_val("battery.battery_electricity_discharge", units="kW")[indx_soc_increase]
            == 0
        )
        assert np.all(
            prob.get_val("battery.battery_electricity_discharge", units="kW")[indx_soc_same] == 0
        )

    with subtests.test("Max SOC <= Max storage percent"):
        assert prob.get_val("battery.SOC", units="unitless").max() <= 0.9

    with subtests.test("Min SOC >= Min storage percent"):
        assert prob.get_val("battery.SOC", units="unitless").min() >= 0.1

    with subtests.test("Charge never exceeds charge rate"):
        assert (
            prob.get_val("battery.battery_electricity_charge", units="kW").min() >= -1 * charge_rate
        )

    with subtests.test("Discharge never exceeds discharge rate"):
        assert (
            prob.get_val("battery.battery_electricity_discharge", units="kW").max()
            <= discharge_rate
        )

    with subtests.test("Discharge never exceeds demand"):
        assert np.all(
            prob.get_val("battery.battery_electricity_discharge", units="kW").max() <= demand_in
        )

    with subtests.test("Sometimes discharges"):
        assert any(
            k > 1e-3 for k in prob.get_val("battery.battery_electricity_discharge", units="kW")
        )

    with subtests.test("Sometimes charges"):
        assert any(
            k < -1e-3 for k in prob.get_val("battery.battery_electricity_charge", units="kW")
        )

    with subtests.test("Cumulative charge/discharge does not exceed storage capacity"):
        assert np.cumsum(charge_plus_discharge).max() <= capacity
        assert np.cumsum(charge_plus_discharge).min() >= -1 * capacity

    with subtests.test("Expected discharge from hour 10-30"):
        expected_discharge = np.concat([np.zeros(8), np.ones(8) * 5000, np.zeros(4)])
        np.testing.assert_allclose(
            prob.get_val("battery.battery_electricity_discharge", units="kW")[0:20],
            expected_discharge,
            rtol=1e-2,
        )

    with subtests.test("Expected charge hour 0-24"):
        expected_charge = -1 * np.concat([np.zeros(16), np.ones(8) * 4000])
        np.testing.assert_allclose(
            prob.get_val("battery.battery_electricity_charge", units="kW")[0:24],
            expected_charge,
            rtol=1e-2,
        )
