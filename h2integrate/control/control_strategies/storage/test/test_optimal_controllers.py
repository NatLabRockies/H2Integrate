from copy import deepcopy

import numpy as np
import pytest
import openmdao.api as om
from pytest import fixture

from h2integrate.storage.battery.pysam_battery import PySAMBatteryPerformanceModel
from h2integrate.storage.storage_performance_model import StoragePerformanceModel
from h2integrate.storage.simple_storage_auto_sizing import StorageAutoSizingModel
from h2integrate.control.control_strategies.storage.optimized_pyomo_controller import (
    OptimizedDispatchStorageController,
    OptimizedDispatchStorageControllerConfig,
)


@fixture
def plant_config_battery():
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
def tech_config_battery():
    tech_config = {
        "technologies": {
            "battery": {
                "control_strategy": {"model": "OptimizedDispatchStorageController"},
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
                        "demand_met_value": 0.1,
                        "round_digits": 4,
                        "time_weighting_factor": 0.995,
                        "n_control_window": 24,
                        "allow_commodity_buying": False,
                    },
                },
            },
        },
    }
    return tech_config


@fixture
def plant_config_h2_storage():
    plant_config = {
        "plant": {
            "plant_life": 30,
            "simulation": {
                "dt": 3600,
                "n_timesteps": 48,
            },
        },
        "tech_to_dispatch_connections": [
            ["converter", "h2_storage"],
            ["h2_storage", "h2_storage"],
        ],
    }
    return plant_config


@fixture
def tech_config_generic():
    tech_config = {
        "technologies": {
            "h2_storage": {
                "control_strategy": {"model": "OptimizedDispatchStorageController"},
                "performance_model": {"model": "StoragePerformanceModel"},
                "model_inputs": {
                    "shared_parameters": {
                        "max_charge_rate": 10.0,
                        "max_capacity": 40.0,
                        "init_soc_fraction": 0.2,
                        "max_soc_fraction": 1.0,
                        "min_soc_fraction": 0.1,
                        "commodity": "hydrogen",
                        "commodity_rate_units": "kg/h",
                        "charge_efficiency": 1.0,
                        "discharge_efficiency": 1.0,
                    },
                    "performance_parameters": {
                        "charge_equals_discharge": True,
                        "commodity_amount_units": "kg",
                        "demand_profile": 0.0,
                    },
                    "control_parameters": {
                        "tech_name": "h2_storage",
                        "cost_per_charge": 0.03,  # USD/kg
                        "cost_per_discharge": 0.05,  # USD/kg
                        "demand_met_value": 0.1,  # USD/kg
                        "cost_per_production": 0.0,  # USD/kg
                        "time_weighting_factor": 0.995,
                        "system_commodity_interface_limit": 10.0,
                        "n_control_window": 24,
                        "allow_commodity_buying": False,
                    },
                },
            }
        },
    }
    return tech_config


@fixture
def tech_config_autosizing():
    tech_config = {
        "technologies": {
            "h2_storage": {
                "control_strategy": {"model": "OptimizedDispatchStorageController"},
                "performance_model": {"model": "StorageAutoSizingModel"},
                "model_inputs": {
                    "shared_parameters": {
                        "max_soc_fraction": 1.0,
                        "min_soc_fraction": 0.0,
                        "commodity": "hydrogen",
                        "commodity_rate_units": "kg/h",
                        "charge_efficiency": 1.0,
                        "discharge_efficiency": 1.0,
                    },
                    "performance_parameters": {
                        "charge_equals_discharge": True,
                        "demand_profile": 0.0,
                        "commodity_amount_units": "kg",
                        "set_demand_as_avg_commodity_in": False,
                    },
                    "control_parameters": {
                        "tech_name": "h2_storage",
                        "cost_per_charge": 0.03,  # USD/kg
                        "cost_per_discharge": 0.05,  # USD/kg
                        "demand_met_value": 0.1,  # USD/kg
                        "cost_per_production": 0.0,  # USD/kg
                        "time_weighting_factor": 0.995,
                        "system_commodity_interface_limit": 10.0,
                        "n_control_window": 24,
                        "max_charge_rate": 5.0,
                        "max_capacity": 5.0,
                        "init_soc_fraction": 0.1,
                        "allow_commodity_buying": False,
                    },
                },
            }
        },
    }
    return tech_config


@pytest.mark.regression
def test_min_operating_cost_load_following_battery_dispatch(
    plant_config_battery, tech_config_battery, subtests
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
        OptimizedDispatchStorageController(
            plant_config=plant_config_battery,
            tech_config=tech_config_battery["technologies"]["battery"],
        ),
        promotes=["*"],
    )

    prob.model.add_subsystem(
        "battery",
        PySAMBatteryPerformanceModel(
            plant_config=plant_config_battery,
            tech_config=tech_config_battery["technologies"]["battery"],
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
        assert np.all(prob.get_val("battery.storage_electricity_discharge") >= 0)
    with subtests.test("Charge is always negative"):
        assert np.all(prob.get_val("battery.storage_electricity_charge") <= 0)
    # Set rtol lower b/c the values are in kW
    with subtests.test("Charge + Discharge == battery_electricity_out"):
        charge_plus_discharge = prob.get_val("battery.storage_electricity_charge") + prob.get_val(
            "battery.storage_electricity_discharge"
        )
        np.testing.assert_allclose(
            charge_plus_discharge, prob.get_val("electricity_out"), rtol=1e-2
        )
    with subtests.test("Initial SOC is correct"):
        assert pytest.approx(prob.model.get_val("battery.SOC")[0], rel=1e-2) == 50

    # Find where the signal increases, decreases, and stays at zero
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
            prob.get_val("battery.storage_electricity_charge", units="kW")[indx_soc_increase] <= 0
        )
        assert np.all(
            prob.get_val("battery.storage_electricity_charge", units="kW")[indx_soc_decrease] == 0
        )
        assert np.all(
            prob.get_val("battery.storage_electricity_charge", units="kW")[indx_soc_same] == 0
        )

    with subtests.test("SOC decreases when discharging"):
        assert np.all(
            prob.get_val("battery.storage_electricity_discharge", units="kW")[indx_soc_decrease] > 0
        )
        assert np.all(
            prob.get_val("battery.storage_electricity_discharge", units="kW")[indx_soc_increase]
            == 0
        )
        assert np.all(
            prob.get_val("battery.storage_electricity_discharge", units="kW")[indx_soc_same] == 0
        )

    with subtests.test("Max SOC <= Max storage percent"):
        assert prob.get_val("battery.SOC", units="unitless").max() <= 0.9

    with subtests.test("Min SOC >= Min storage percent"):
        assert prob.get_val("battery.SOC", units="unitless").min() >= 0.1

    with subtests.test("Charge never exceeds charge rate"):
        assert (
            prob.get_val("battery.storage_electricity_charge", units="kW").min() >= -1 * charge_rate
        )

    with subtests.test("Discharge never exceeds discharge rate"):
        assert (
            prob.get_val("battery.storage_electricity_discharge", units="kW").max()
            <= discharge_rate
        )

    with subtests.test("Discharge never exceeds demand"):
        assert np.all(
            prob.get_val("battery.storage_electricity_discharge", units="kW").max() <= demand_in
        )

    with subtests.test("Sometimes discharges"):
        assert any(
            k > 1e-3 for k in prob.get_val("battery.storage_electricity_discharge", units="kW")
        )

    with subtests.test("Sometimes charges"):
        assert any(
            k < -1e-3 for k in prob.get_val("battery.storage_electricity_charge", units="kW")
        )

    with subtests.test("Cumulative charge/discharge does not exceed storage capacity"):
        assert np.cumsum(charge_plus_discharge).max() <= capacity
        assert np.cumsum(charge_plus_discharge).min() >= -1 * capacity

    with subtests.test("Expected discharge from hour 10-30"):
        expected_discharge = np.concat([np.zeros(8), np.ones(8) * 5000, np.zeros(4)])
        np.testing.assert_allclose(
            prob.get_val("battery.storage_electricity_discharge", units="kW")[0:20],
            expected_discharge,
            rtol=1e-2,
        )

    with subtests.test("Expected charge hour 0-24"):
        expected_charge = -1 * np.concat([np.zeros(16), np.ones(8) * 4000])
        np.testing.assert_allclose(
            prob.get_val("battery.storage_electricity_charge", units="kW")[0:24],
            expected_charge,
            rtol=1e-2,
        )


@pytest.mark.regression
def test_optimal_control_with_generic_storage(
    plant_config_h2_storage, tech_config_generic, subtests
):
    commodity_demand = np.full(48, 5.0)
    commodity_in = np.tile(np.concat([np.zeros(3), np.cumsum(np.ones(15)), np.full(6, 4.0)]), 2)

    # Setup the OpenMDAO problem and add subsystems
    prob = om.Problem()

    prob.model.add_subsystem(
        "h2_storage_optimized_load_following_controller",
        OptimizedDispatchStorageController(
            plant_config=plant_config_h2_storage,
            tech_config=tech_config_generic["technologies"]["h2_storage"],
        ),
        promotes=["*"],
    )

    prob.model.add_subsystem(
        "h2_storage",
        StoragePerformanceModel(
            plant_config=plant_config_h2_storage,
            tech_config=tech_config_generic["technologies"]["h2_storage"],
        ),
        promotes=["*"],
    )

    # Setup the system and required values
    prob.setup()
    prob.set_val("h2_storage.hydrogen_in", commodity_in)
    prob.set_val("h2_storage.hydrogen_demand", commodity_demand)

    # Run the model
    prob.run_model()

    charge_rate = prob.get_val("h2_storage.max_charge_rate", units="kg/h")[0]
    discharge_rate = prob.get_val("h2_storage.max_charge_rate", units="kg/h")[0]
    capacity = prob.get_val("h2_storage.storage_capacity", units="kg")[0]

    # Test that discharge is always positive
    with subtests.test("Discharge is always positive"):
        assert np.all(prob.get_val("h2_storage.storage_hydrogen_discharge", units="kg/h") >= 0)
    with subtests.test("Charge is always negative"):
        assert np.all(prob.get_val("h2_storage.storage_hydrogen_charge", units="kg/h") <= 0)
    with subtests.test("Charge + Discharge == hydrogen_out"):
        charge_plus_discharge = prob.get_val(
            "h2_storage.storage_hydrogen_charge", units="kg/h"
        ) + prob.get_val("h2_storage.storage_hydrogen_discharge", units="kg/h")
        np.testing.assert_allclose(
            charge_plus_discharge, prob.get_val("hydrogen_out", units="kg/h"), rtol=1e-6
        )
    with subtests.test("Initial SOC is correct"):
        assert (
            pytest.approx(prob.model.get_val("h2_storage.SOC", units="unitless")[0], rel=1e-6)
            == 0.1
        )

    indx_soc_increase = np.argwhere(
        np.diff(prob.model.get_val("h2_storage.SOC", units="unitless"), prepend=True) > 0
    ).flatten()
    indx_soc_decrease = np.argwhere(
        np.diff(prob.model.get_val("h2_storage.SOC", units="unitless"), prepend=False) < 0
    ).flatten()
    indx_soc_same = np.argwhere(
        np.diff(prob.model.get_val("h2_storage.SOC", units="unitless"), prepend=True) == 0.0
    ).flatten()

    with subtests.test("SOC increases when charging"):
        assert np.all(
            prob.get_val("h2_storage.storage_hydrogen_charge", units="kg/h")[indx_soc_increase] < 0
        )
        assert np.all(
            prob.get_val("h2_storage.storage_hydrogen_charge", units="kg/h")[indx_soc_decrease] == 0
        )
        assert np.all(
            prob.get_val("h2_storage.storage_hydrogen_charge", units="kg/h")[indx_soc_same] == 0
        )

    with subtests.test("SOC decreases when discharging"):
        assert np.all(
            prob.get_val("h2_storage.storage_hydrogen_discharge", units="kg/h")[indx_soc_decrease]
            > 0
        )
        assert np.all(
            prob.get_val("h2_storage.storage_hydrogen_discharge", units="kg/h")[indx_soc_increase]
            == 0
        )
        assert np.all(
            prob.get_val("h2_storage.storage_hydrogen_discharge", units="kg/h")[indx_soc_same] == 0
        )

    with subtests.test("Max SOC <= Max storage percent"):
        assert prob.get_val("h2_storage.SOC", units="unitless").max() <= 1.0

    with subtests.test("Min SOC >= Min storage percent"):
        assert prob.get_val("h2_storage.SOC", units="unitless").min() >= 0.1

    with subtests.test("Charge never exceeds charge rate"):
        assert (
            prob.get_val("h2_storage.storage_hydrogen_charge", units="kg/h").min()
            >= -1 * charge_rate
        )

    with subtests.test("Discharge never exceeds discharge rate"):
        assert (
            prob.get_val("h2_storage.storage_hydrogen_discharge", units="kg/h").max()
            <= discharge_rate
        )

    with subtests.test("Discharge never exceeds demand"):
        assert np.all(
            prob.get_val("h2_storage.storage_hydrogen_discharge", units="kg/h").max()
            <= commodity_demand
        )

    with subtests.test("Sometimes discharges"):
        assert any(
            k > 1e-3 for k in prob.get_val("h2_storage.storage_hydrogen_discharge", units="kg/h")
        )

    with subtests.test("Sometimes charges"):
        assert any(
            k < -1e-3 for k in prob.get_val("h2_storage.storage_hydrogen_charge", units="kg/h")
        )

    with subtests.test("Cumulative charge/discharge does not exceed storage capacity"):
        assert np.cumsum(prob.get_val("hydrogen_out", units="kg/h")).max() <= capacity
        assert np.cumsum(prob.get_val("hydrogen_out", units="kg/h")).min() >= -1 * capacity

    with subtests.test("Expected discharge from hour 10-30"):
        expected_discharge = np.concat(
            [np.zeros(8), np.ones(6), np.full(3, 5.0), np.array([4, 3, 2])]
        )
        np.testing.assert_allclose(
            prob.get_val("h2_storage.storage_hydrogen_discharge", units="kg/h")[10:30],
            expected_discharge,
            rtol=1e-6,
        )

    with subtests.test("Expected charge hour 0-20"):
        expected_charge = np.concat([np.zeros(8), np.arange(-1, -9, -1), np.zeros(4)])
        np.testing.assert_allclose(
            prob.get_val("h2_storage.storage_hydrogen_charge", units="kg/h")[0:20],
            expected_charge,
            rtol=1e-6,
        )


@pytest.mark.regression
def test_optimal_dispatch_with_autosizing_storage_demand_less_than_avg_in(
    plant_config_h2_storage, tech_config_autosizing, subtests
):
    commodity_demand = np.full(48, 5.0)
    commodity_in = np.tile(np.concat([np.zeros(3), np.cumsum(np.ones(15)), np.full(6, 4.0)]), 2)
    # Setup the OpenMDAO problem and add subsystems
    prob = om.Problem()

    prob.model.add_subsystem(
        "h2_storage_controller",
        OptimizedDispatchStorageController(
            plant_config=plant_config_h2_storage,
            tech_config=tech_config_autosizing["technologies"]["h2_storage"],
        ),
        promotes=["*"],
    )

    prob.model.add_subsystem(
        "h2_storage",
        StorageAutoSizingModel(
            plant_config=plant_config_h2_storage,
            tech_config=tech_config_autosizing["technologies"]["h2_storage"],
        ),
        promotes=["*"],
    )

    # Setup the system and required values
    prob.setup()
    prob.set_val("h2_storage.hydrogen_in", commodity_in)
    prob.set_val("h2_storage.hydrogen_demand", commodity_demand)

    # Run the model
    prob.run_model()

    charge_rate = prob.get_val("h2_storage.max_charge_rate", units="kg/h")[0]
    discharge_rate = prob.get_val("h2_storage.max_discharge_rate", units="kg/h")[0]
    capacity = prob.get_val("h2_storage.storage_capacity", units="kg")[0]

    with subtests.test("Capacity is correct"):
        soc_kg = np.cumsum(commodity_demand - commodity_in)
        soc_kg_adj = soc_kg + np.abs(np.min(soc_kg))
        expected_usable_capacity = np.max(soc_kg_adj) - np.min(soc_kg_adj)

        assert pytest.approx(capacity, rel=1e-6) == expected_usable_capacity

    with subtests.test("Charge rate is correct"):
        assert pytest.approx(charge_rate, rel=1e-6) == max(commodity_in)
    with subtests.test("Discharge rate is correct"):
        assert pytest.approx(discharge_rate, rel=1e-6) == max(commodity_in)

    with subtests.test("Expected discharge from hour 10-30"):
        expected_discharge = np.concat(
            [np.zeros(8), np.ones(6), np.full(3, 5.0), np.array([4, 3, 2])]
        )
        np.testing.assert_allclose(
            prob.get_val("h2_storage.storage_hydrogen_discharge", units="kg/h")[10:30],
            expected_discharge,
            rtol=1e-6,
        )

    with subtests.test("Expected charge hour 0-20"):
        expected_charge = np.concat([np.zeros(8), np.arange(-1, -11, -1), np.zeros(2)])
        np.testing.assert_allclose(
            prob.get_val("h2_storage.storage_hydrogen_charge", units="kg/h")[0:20],
            expected_charge,
            rtol=1e-6,
        )


@pytest.mark.regression
def test_optimal_dispatch_with_autosizing_storage_demand_is_avg_in(
    plant_config_h2_storage, tech_config_autosizing, subtests
):
    commodity_in = np.tile(np.concat([np.zeros(3), np.cumsum(np.ones(15)), np.full(6, 4.0)]), 2)
    commodity_demand = np.full(48, np.mean(commodity_in))
    tech_config_autosizing["technologies"]["h2_storage"]["model_inputs"]["performance_parameters"][
        "set_demand_as_avg_commodity_in"
    ] = True
    tech_config_autosizing["technologies"]["h2_storage"]["model_inputs"]["performance_parameters"][
        "demand_profile"
    ] = 0.0

    # Setup the OpenMDAO problem and add subsystems
    prob = om.Problem()

    prob.model.add_subsystem(
        "h2_storage_controller",
        OptimizedDispatchStorageController(
            plant_config=plant_config_h2_storage,
            tech_config=tech_config_autosizing["technologies"]["h2_storage"],
        ),
        promotes=["*"],
    )

    prob.model.add_subsystem(
        "h2_storage",
        StorageAutoSizingModel(
            plant_config=plant_config_h2_storage,
            tech_config=tech_config_autosizing["technologies"]["h2_storage"],
        ),
        promotes=["*"],
    )

    # Setup the system and required values
    prob.setup()
    prob.set_val("h2_storage.hydrogen_in", commodity_in)

    # Run the model
    prob.run_model()

    charge_rate = prob.get_val("h2_storage.max_charge_rate", units="kg/h")[0]
    discharge_rate = prob.get_val("h2_storage.max_discharge_rate", units="kg/h")[0]
    capacity = prob.get_val("h2_storage.storage_capacity", units="kg")[0]

    with subtests.test("Capacity is correct"):
        soc_kg = np.cumsum(commodity_demand - commodity_in)
        soc_kg_adj = soc_kg + np.abs(np.min(soc_kg))
        expected_usable_capacity = np.max(soc_kg_adj) - np.min(soc_kg_adj)

        assert pytest.approx(capacity, rel=1e-6) == expected_usable_capacity

    with subtests.test("Charge rate is correct"):
        assert pytest.approx(charge_rate, rel=1e-6) == max(commodity_in)
    with subtests.test("Discharge rate is correct"):
        assert pytest.approx(discharge_rate, rel=1e-6) == max(commodity_in)

    with subtests.test("Expected discharge from hour 10-30"):
        expected_discharge = np.concat(
            [np.zeros(8), np.full(6, 2.0), np.full(3, 6.0), np.array([5, 4, 3])]
        )
        np.testing.assert_allclose(
            prob.get_val("h2_storage.storage_hydrogen_discharge", units="kg/h")[10:30],
            expected_discharge,
            rtol=1e-6,
        )

    with subtests.test("Expected charge hour 0-20"):
        expected_charge = np.concat(
            [np.zeros(9), np.arange(-1, -7, -1), np.array([-1.5]), np.zeros(4)]
        )
        np.testing.assert_allclose(
            prob.get_val("h2_storage.storage_hydrogen_charge", units="kg/h")[0:20],
            expected_charge,
            rtol=1e-6,
        )


@pytest.mark.regression
def test_optimal_control_config_with_commodity_buying(subtests):
    config_data = {
        "tech_name": "h2_storage",
        "max_charge_rate": 10.0,
        "charge_efficiency": 1.0,
        "discharge_efficiency": 1.0,
        "commodity": "hydrogen",
        "commodity_rate_units": "kg/h",
        "max_capacity": 40.0,
        "init_soc_fraction": 0.2,
        "max_soc_fraction": 1.0,
        "min_soc_fraction": 0.1,
        "cost_per_charge": 0.03,  # USD/kg
        "cost_per_discharge": 0.05,  # USD/kg
        "demand_met_value": 0.1,  # USD/kg
        "cost_per_production": 0.0,  # USD/kg
        "time_weighting_factor": 0.995,
        "system_commodity_interface_limit": 10.0,
        "n_control_window": 24,
        "allow_commodity_buying": False,
    }

    config = OptimizedDispatchStorageControllerConfig.from_dict(config_data)

    with subtests.test("check commodity_buy_price is None"):
        assert config.commodity_buy_price is None
    with subtests.test("check commodity_import_limit is None"):
        assert config.commodity_import_limit is None

    config_data["allow_commodity_buying"] = True

    with subtests.test("with invalid commodity_buy_price"):
        with pytest.raises(ValueError):
            data = deepcopy(config_data)
            data["allow_commodity_buying"] = True
            OptimizedDispatchStorageControllerConfig.from_dict(data)

        with pytest.raises(ValueError):
            data = deepcopy(config_data)
            data["allow_commodity_buying"] = True
            data["commodity_buy_price"] = 0.4
            OptimizedDispatchStorageControllerConfig.from_dict(data)

        with pytest.raises(ValueError):
            data = deepcopy(config_data)
            data["allow_commodity_buying"] = True
            data["commodity_buy_price"] = 0.4
            data["commodity_import_limit"] = 0.0
            OptimizedDispatchStorageControllerConfig.from_dict(data)


@pytest.mark.regression
def test_optimal_control_with_commodity_buying_generic_storage(
    plant_config_h2_storage, tech_config_generic, subtests
):
    commodity_demand = np.full(48, 5.0)
    commodity_in = np.tile(np.concat([np.zeros(3), np.cumsum(np.ones(15)), np.full(6, 4.0)]), 2)
    commodity_buy_price = np.tile(np.concat([np.arange(-3, 9), np.arange(8, -4, -1)]), 2)
    commodity_import_limit = 7

    # Set grid charging parameters
    tech_config_generic["technologies"]["h2_storage"]["model_inputs"]["control_parameters"] = {
        "tech_name": "h2_storage",
        "cost_per_charge": 0.03,  # USD/kg
        "cost_per_discharge": 0.05,  # USD/kg
        "demand_met_value": 0.1,  # USD/kg
        "cost_per_production": 0.0,  # USD/kg
        "time_weighting_factor": 0.995,
        "system_commodity_interface_limit": 10.0,
        "n_control_window": 24,
        "allow_commodity_buying": True,
        "commodity_buy_price": 1,
        "commodity_import_limit": commodity_import_limit,
    }

    # Setup the OpenMDAO problem and add subsystems
    prob = om.Problem()

    prob.model.add_subsystem(
        "h2_storage_optimized_load_following_controller",
        OptimizedDispatchStorageController(
            plant_config=plant_config_h2_storage,
            tech_config=tech_config_generic["technologies"]["h2_storage"],
        ),
        promotes=["*"],
    )

    prob.model.add_subsystem(
        "h2_storage",
        StoragePerformanceModel(
            plant_config=plant_config_h2_storage,
            tech_config=tech_config_generic["technologies"]["h2_storage"],
        ),
        promotes=["*"],
    )

    # Setup the system and required values
    prob.setup()
    prob.set_val("h2_storage.hydrogen_in", commodity_in)
    prob.set_val("h2_storage.hydrogen_demand", commodity_demand)
    prob.set_val("hydrogen_buy_price", commodity_buy_price)

    # Run the model
    prob.run_model()

    charge_rate = prob.get_val("h2_storage.max_charge_rate", units="kg/h")[0]
    discharge_rate = prob.get_val("h2_storage.max_charge_rate", units="kg/h")[0]
    capacity = prob.get_val("h2_storage.storage_capacity", units="kg")[0]

    print("outputs: ", prob.get_val("hydrogen_out"))
    print("discharge: ", prob.get_val("h2_storage.storage_hydrogen_discharge"))
    print("charge: ", prob.get_val("h2_storage.storage_hydrogen_charge"))
    print("commodity in: ", prob.get_val("h2_storage.hydrogen_in"))
    print("demand: ", prob.get_val("h2_storage.hydrogen_demand"))
    print("commodity_buy: ", prob.get_val("hydrogen_buy_price"))
    print("hydrogen_out: ", prob.get_val("hydrogen_out"))
    print("hydrogen bought: ", prob.get_val("hydrogen_bought_for_storage"))

    # Test that discharge is always positive
    with subtests.test("Discharge is always positive"):
        assert np.all(prob.get_val("h2_storage.storage_hydrogen_discharge", units="kg/h") >= 0)
    with subtests.test("Charge is always negative"):
        assert np.all(prob.get_val("h2_storage.storage_hydrogen_charge", units="kg/h") <= 0)
    with subtests.test("Charge + Discharge == hydrogen_out"):
        charge_plus_discharge = prob.get_val(
            "h2_storage.storage_hydrogen_charge", units="kg/h"
        ) + prob.get_val("h2_storage.storage_hydrogen_discharge", units="kg/h")
        np.testing.assert_allclose(
            charge_plus_discharge, prob.get_val("hydrogen_out", units="kg/h"), rtol=1e-6
        )
    with subtests.test("Initial SOC is correct"):
        assert (
            pytest.approx(prob.model.get_val("h2_storage.SOC", units="unitless")[0], rel=1e-6)
            == 0.375
        )

    indx_soc_increase = np.argwhere(
        np.diff(prob.model.get_val("h2_storage.SOC", units="unitless"), prepend=True) > 0
    ).flatten()
    indx_soc_decrease = np.argwhere(
        np.diff(prob.model.get_val("h2_storage.SOC", units="unitless"), prepend=False) < 0
    ).flatten()
    indx_soc_same = np.argwhere(
        np.diff(prob.model.get_val("h2_storage.SOC", units="unitless"), prepend=True) == 0.0
    ).flatten()

    with subtests.test("SOC increases when charging"):
        assert np.all(
            prob.get_val("h2_storage.storage_hydrogen_charge", units="kg/h")[indx_soc_increase] < 0
        )
        assert np.all(
            prob.get_val("h2_storage.storage_hydrogen_charge", units="kg/h")[indx_soc_decrease] == 0
        )
        assert np.all(
            prob.get_val("h2_storage.storage_hydrogen_charge", units="kg/h")[indx_soc_same] == 0
        )

    with subtests.test("SOC decreases when discharging"):
        assert np.all(
            prob.get_val("h2_storage.storage_hydrogen_discharge", units="kg/h")[indx_soc_decrease]
            > 0
        )
        assert np.all(
            prob.get_val("h2_storage.storage_hydrogen_discharge", units="kg/h")[indx_soc_increase]
            == 0
        )
        assert np.all(
            prob.get_val("h2_storage.storage_hydrogen_discharge", units="kg/h")[indx_soc_same] == 0
        )

    with subtests.test("Max SOC <= Max storage percent"):
        assert prob.get_val("h2_storage.SOC", units="unitless").max() <= 1.0

    with subtests.test("Min SOC >= Min storage percent"):
        assert prob.get_val("h2_storage.SOC", units="unitless").min() >= 0.1

    with subtests.test("Charge never exceeds charge rate"):
        assert (
            prob.get_val("h2_storage.storage_hydrogen_charge", units="kg/h").min()
            >= -1 * charge_rate
        )

    with subtests.test("Discharge never exceeds discharge rate"):
        assert (
            prob.get_val("h2_storage.storage_hydrogen_discharge", units="kg/h").max()
            <= discharge_rate
        )

    with subtests.test("Discharge never exceeds demand"):
        np.testing.assert_allclose(
            prob.get_val("h2_storage.storage_hydrogen_discharge", units="kg/h").max(),
            commodity_demand,
            rtol=1e-6,
        )

    with subtests.test("Sometimes discharges"):
        assert any(
            k > 1e-3 for k in prob.get_val("h2_storage.storage_hydrogen_discharge", units="kg/h")
        )

    with subtests.test("Sometimes charges"):
        assert any(
            k < -1e-3 for k in prob.get_val("h2_storage.storage_hydrogen_charge", units="kg/h")
        )

    with subtests.test("Cumulative charge/discharge does not exceed storage capacity"):
        assert np.cumsum(prob.get_val("hydrogen_out", units="kg/h")).max() <= capacity
        assert np.cumsum(prob.get_val("hydrogen_out", units="kg/h")).min() >= -1 * capacity

    with subtests.test("Expected discharge from hour 10-30"):
        expected_discharge = np.concat(
            [np.zeros(8), np.ones(3), np.zeros(3), [5, 0], np.arange(5, 1, -1)]
        )
        np.testing.assert_allclose(
            prob.get_val("h2_storage.storage_hydrogen_discharge", units="kg/h")[10:30],
            expected_discharge,
            rtol=1e-6,
            atol=1e-6,
        )

    with subtests.test("Expected charge hour 0-20"):
        expected_charge = np.concat([np.ones(3) * -7, np.zeros(5), [-1, -2], np.zeros(10)])
        np.testing.assert_allclose(
            prob.get_val("h2_storage.storage_hydrogen_charge", units="kg/h")[0:20],
            expected_charge,
            rtol=1e-6,
        )

    with subtests.test("Output never exceeds system commodity draw limit"):
        np.testing.assert_allclose(
            prob.get_val("h2_storage.storage_hydrogen_charge", units="kg/h").min(),
            -commodity_import_limit,
            rtol=1e-6,
        )

    with subtests.test("Expected bought commodity"):
        expected_commodity_bought = np.concat(
            [np.ones(3) * 7, np.zeros(18), np.ones(3) * 7, [0], [5], np.zeros(19), np.ones(3) * 7]
        )
        np.testing.assert_allclose(
            prob.get_val("hydrogen_bought_for_storage", units="kg/h"),
            expected_commodity_bought,
            rtol=1e-6,
            atol=1e-6,
        )


def _setup_commodity_buying_problem(
    plant_config, tech_config, commodity_buy_price_timeseries, commodity_import_limit=7
):
    """Helper to set up an OptimizedDispatchStorageController problem with commodity buying enabled.

    Args:
        plant_config: Plant configuration dictionary.
        tech_config: Technology configuration dictionary (will be modified in-place).
        commodity_buy_price_timeseries: Numpy array of buy prices per timestep.
        commodity_import_limit: Maximum commodity import rate (default: 7 kg/h).

    Returns:
        tuple: (prob, commodity_in, commodity_demand) - the configured OpenMDAO problem
               and the input arrays used.
    """
    commodity_demand = np.full(48, 5.0)
    commodity_in = np.tile(np.concat([np.zeros(3), np.cumsum(np.ones(15)), np.full(6, 4.0)]), 2)

    tech_config["technologies"]["h2_storage"]["model_inputs"]["control_parameters"] = {
        "tech_name": "h2_storage",
        "cost_per_charge": 0.03,
        "cost_per_discharge": 0.05,
        "demand_met_value": 0.1,
        "cost_per_production": 0.0,
        "time_weighting_factor": 0.995,
        "system_commodity_interface_limit": 10.0,
        "n_control_window": 24,
        "allow_commodity_buying": True,
        "commodity_buy_price": 1,
        "commodity_import_limit": commodity_import_limit,
    }

    prob = om.Problem()

    prob.model.add_subsystem(
        "h2_storage_optimized_load_following_controller",
        OptimizedDispatchStorageController(
            plant_config=plant_config,
            tech_config=tech_config["technologies"]["h2_storage"],
        ),
        promotes=["*"],
    )

    prob.model.add_subsystem(
        "h2_storage",
        StoragePerformanceModel(
            plant_config=plant_config,
            tech_config=tech_config["technologies"]["h2_storage"],
        ),
        promotes=["*"],
    )

    prob.setup()
    prob.set_val("h2_storage.hydrogen_in", commodity_in)
    prob.set_val("h2_storage.hydrogen_demand", commodity_demand)
    prob.set_val("hydrogen_buy_price", commodity_buy_price_timeseries)

    prob.run_model()

    return prob, commodity_in, commodity_demand


def _run_standard_commodity_buying_assertions(prob, commodity_demand, subtests):
    """Run standard physical constraint checks for commodity buying tests.

    Args:
        prob: The solved OpenMDAO problem.
        commodity_demand: The demand profile array.
        subtests: pytest subtests fixture.
    """
    charge_rate = prob.get_val("h2_storage.max_charge_rate", units="kg/h")[0]
    discharge_rate = prob.get_val("h2_storage.max_charge_rate", units="kg/h")[0]
    capacity = prob.get_val("h2_storage.storage_capacity", units="kg")[0]

    with subtests.test("Discharge is always positive"):
        assert np.all(prob.get_val("h2_storage.storage_hydrogen_discharge", units="kg/h") >= 0)
    with subtests.test("Charge is always negative"):
        assert np.all(prob.get_val("h2_storage.storage_hydrogen_charge", units="kg/h") <= 0)
    with subtests.test("Charge + Discharge == hydrogen_out"):
        charge_plus_discharge = prob.get_val(
            "h2_storage.storage_hydrogen_charge", units="kg/h"
        ) + prob.get_val("h2_storage.storage_hydrogen_discharge", units="kg/h")
        np.testing.assert_allclose(
            charge_plus_discharge, prob.get_val("hydrogen_out", units="kg/h"), rtol=1e-6
        )
    with subtests.test("Max SOC <= Max storage percent"):
        assert prob.get_val("h2_storage.SOC", units="unitless").max() <= 1.0
    with subtests.test("Min SOC >= Min storage percent"):
        assert prob.get_val("h2_storage.SOC", units="unitless").min() >= 0.1
    with subtests.test("Charge never exceeds charge rate"):
        assert (
            prob.get_val("h2_storage.storage_hydrogen_charge", units="kg/h").min()
            >= -1 * charge_rate
        )
    with subtests.test("Discharge never exceeds discharge rate"):
        assert (
            prob.get_val("h2_storage.storage_hydrogen_discharge", units="kg/h").max()
            <= discharge_rate
        )
    with subtests.test("Commodity bought is non-negative"):
        assert np.all(prob.get_val("hydrogen_bought_for_storage", units="kg/h") >= -1e-6)
    with subtests.test("Cumulative charge/discharge does not exceed storage capacity"):
        assert np.cumsum(prob.get_val("hydrogen_out", units="kg/h")).max() <= capacity
        assert np.cumsum(prob.get_val("hydrogen_out", units="kg/h")).min() >= -1 * capacity


@pytest.mark.regression
def test_optimal_control_commodity_buying_all_positive_prices(
    plant_config_h2_storage, tech_config_generic, subtests
):
    """Test commodity buying with all positive prices.

    When all prices are positive, buying commodity adds to the operating cost.
    The optimizer should only buy when the cost of buying is less than the
    penalty for not meeting demand (demand_met_value=0.1 $/kg).
    With a high buy price (5.0 $/kg >> demand_met_value), buying is expensive
    and the optimizer should prefer to not buy.
    """
    commodity_buy_price = np.full(48, 5.0)
    commodity_import_limit = 7

    prob, commodity_in, commodity_demand = _setup_commodity_buying_problem(
        plant_config_h2_storage,
        tech_config_generic,
        commodity_buy_price,
        commodity_import_limit,
    )

    _run_standard_commodity_buying_assertions(prob, commodity_demand, subtests)

    commodity_bought = prob.get_val("hydrogen_bought_for_storage", units="kg/h")

    # With high positive prices (5.0 >> demand_met_value of 0.1), buying is too expensive
    # relative to the penalty for unmet demand, so the optimizer should not buy any commodity.
    with subtests.test("No commodity bought when price exceeds demand met value"):
        np.testing.assert_allclose(commodity_bought, 0.0, atol=1e-6)


@pytest.mark.regression
def test_optimal_control_commodity_buying_all_negative_prices(
    plant_config_h2_storage, tech_config_generic, subtests
):
    """Test commodity buying with all negative prices.

    When all prices are negative, buying commodity *reduces* the operating cost
    (the optimizer gets paid to buy). The optimizer should buy as much as
    possible up to the import limit whenever it can.
    """
    commodity_buy_price = np.full(48, -5.0)
    commodity_import_limit = 7

    prob, commodity_in, commodity_demand = _setup_commodity_buying_problem(
        plant_config_h2_storage,
        tech_config_generic,
        commodity_buy_price,
        commodity_import_limit,
    )

    _run_standard_commodity_buying_assertions(prob, commodity_demand, subtests)

    commodity_bought = prob.get_val("hydrogen_bought_for_storage", units="kg/h")

    # With negative prices, buying reduces cost. The optimizer should buy aggressively.
    with subtests.test("Commodity is bought when prices are negative"):
        assert np.sum(commodity_bought) > 0

    # The purchase_limit constraint prevents buying when is_generating=1, but
    # whenever the system is not generating, it should buy the maximum.
    with subtests.test("Bought commodity never exceeds import limit"):
        assert np.all(commodity_bought <= commodity_import_limit + 1e-6)

    # With strong negative prices, the optimizer should buy at the import limit
    # whenever it is allowed (i.e. when not generating). Check that it buys at
    # the maximum for at least some timesteps.
    with subtests.test("Buys at import limit for some timesteps"):
        assert np.any(np.isclose(commodity_bought, commodity_import_limit, atol=1e-4))


@pytest.mark.regression
def test_optimal_control_commodity_buying_zero_prices(
    plant_config_h2_storage, tech_config_generic, subtests
):
    """Test commodity buying with zero prices.

    When the buy price is zero, buying commodity has no direct cost. The
    optimizer should buy freely to help charge storage and meet demand since
    there is no cost penalty for doing so.
    """
    commodity_buy_price = np.full(48, 0.0)
    commodity_import_limit = 7

    prob, commodity_in, commodity_demand = _setup_commodity_buying_problem(
        plant_config_h2_storage,
        tech_config_generic,
        commodity_buy_price,
        commodity_import_limit,
    )

    _run_standard_commodity_buying_assertions(prob, commodity_demand, subtests)

    commodity_bought = prob.get_val("hydrogen_bought_for_storage", units="kg/h")

    # With zero prices, buying is free. The optimizer should buy commodity to help
    # meet demand, especially during periods when commodity_in is insufficient.
    with subtests.test("Commodity is bought when prices are zero"):
        assert np.sum(commodity_bought) > 0

    with subtests.test("Bought commodity never exceeds import limit"):
        assert np.all(commodity_bought <= commodity_import_limit + 1e-6)
