import numpy as np
import pytest
import openmdao.api as om
from pytest import fixture

from h2integrate.storage.generic_storage_pyo import StoragePerformanceModel
from h2integrate.control.control_strategies.heuristic_pyomo_controller import (
    HeuristicLoadFollowingController,
)
from h2integrate.control.control_rules.storage.pyomo_storage_rule_baseclass import (
    PyomoRuleStorageBaseclass,
)


@fixture
def plant_config():
    plant_config = {
        "plant": {
            "plant_life": 30,
            "simulation": {
                "dt": 3600,
                "n_timesteps": 8760,
            },
        },
        "tech_to_dispatch_connections": [
            ["h2_storage", "h2_storage"],
        ],
    }
    return plant_config


@fixture
def tech_config_generic():
    tech_config = {
        "technologies": {
            "h2_storage": {
                "dispatch_rule_set": {"model": "PyomoRuleStorageBaseclass"},
                "control_strategy": {"model": "HeuristicLoadFollowingController"},
                "performance_model": {"model": "StoragePerformanceModel"},
                "model_inputs": {
                    "shared_parameters": {
                        "max_charge_rate": 10.0,
                        "max_capacity": 40.0,
                        "n_control_window": 24,
                        "init_charge_fraction": 0.1,
                        "max_charge_fraction": 1.0,
                        "min_charge_fraction": 0.1,
                        "commodity": "hydrogen",
                        "commodity_rate_units": "kg/h",
                    },
                    "performance_parameters": {
                        "charge_equals_discharge": True,
                        "commodity_amount_units": "kg",
                        "charge_efficiency": 1.0,
                        "discharge_efficiency": 1.0,
                    },
                    "control_parameters": {
                        "tech_name": "h2_storage",
                        "system_commodity_interface_limit": 10.0,
                    },
                },
            }
        },
    }
    return tech_config


@pytest.mark.regression
def test_heuristic_load_following_dispatch_with_generic_storage(
    plant_config, tech_config_generic, subtests
):
    commodity_demand = np.full(8760, 5.0)
    commodity_in = np.tile(np.concat([np.zeros(3), np.cumsum(np.ones(15)), np.full(6, 4.0)]), 365)

    # Setup the OpenMDAO problem and add subsystems
    prob = om.Problem()

    prob.model.add_subsystem(
        "PyomoRuleStorageBaseclass",
        PyomoRuleStorageBaseclass(
            plant_config=plant_config, tech_config=tech_config_generic["technologies"]["h2_storage"]
        ),
        promotes=["*"],
    )

    prob.model.add_subsystem(
        "battery_heuristic_load_following_controller",
        HeuristicLoadFollowingController(
            plant_config=plant_config, tech_config=tech_config_generic["technologies"]["h2_storage"]
        ),
        promotes=["*"],
    )

    prob.model.add_subsystem(
        "storage",
        StoragePerformanceModel(
            plant_config=plant_config, tech_config=tech_config_generic["technologies"]["h2_storage"]
        ),
        promotes=["*"],
    )

    # Setup the system and required values
    prob.setup()
    prob.set_val("storage.hydrogen_in", commodity_in)
    prob.set_val("storage.hydrogen_demand", commodity_demand)

    # Run the model
    prob.run_model()

    charge_rate = prob.get_val("storage.max_charge_rate", units="kg/h")[0]
    discharge_rate = prob.get_val("storage.max_charge_rate", units="kg/h")[0]
    capacity = prob.get_val("storage.storage_capacity", units="kg")[0]

    # Test that discharge is always positive
    with subtests.test("Discharge is always positive"):
        assert np.all(prob.get_val("storage.storage_hydrogen_discharge", units="kg/h") >= 0)
    with subtests.test("Charge is always negative"):
        assert np.all(prob.get_val("storage.storage_hydrogen_charge", units="kg/h") <= 0)
    with subtests.test("Charge + Discharge == storage_hydrogen_out"):
        charge_plus_discharge = prob.get_val(
            "storage.storage_hydrogen_charge", units="kg/h"
        ) + prob.get_val("storage.storage_hydrogen_discharge", units="kg/h")
        np.testing.assert_allclose(
            charge_plus_discharge, prob.get_val("storage_hydrogen_out", units="kg/h"), rtol=1e-6
        )
    with subtests.test("Initial SOC is correct"):
        assert (
            pytest.approx(prob.model.get_val("storage.SOC", units="unitless")[0], rel=1e-6) == 0.1
        )

    indx_soc_increase = np.argwhere(
        np.diff(prob.model.get_val("storage.SOC", units="unitless"), prepend=True) > 0
    ).flatten()
    indx_soc_decrease = np.argwhere(
        np.diff(prob.model.get_val("storage.SOC", units="unitless"), prepend=False) < 0
    ).flatten()
    indx_soc_same = np.argwhere(
        np.diff(prob.model.get_val("storage.SOC", units="unitless"), prepend=True) == 0.0
    ).flatten()

    with subtests.test("SOC increases when charging"):
        assert np.all(
            prob.get_val("storage.storage_hydrogen_charge", units="kg/h")[indx_soc_increase] < 0
        )
        assert np.all(
            prob.get_val("storage.storage_hydrogen_charge", units="kg/h")[indx_soc_decrease] == 0
        )
        assert np.all(
            prob.get_val("storage.storage_hydrogen_charge", units="kg/h")[indx_soc_same] == 0
        )

    with subtests.test("SOC decreases when discharging"):
        assert np.all(
            prob.get_val("storage.storage_hydrogen_discharge", units="kg/h")[indx_soc_decrease] > 0
        )
        assert np.all(
            prob.get_val("storage.storage_hydrogen_discharge", units="kg/h")[indx_soc_increase] == 0
        )
        assert np.all(
            prob.get_val("storage.storage_hydrogen_discharge", units="kg/h")[indx_soc_same] == 0
        )

    with subtests.test("Max SOC <= Max storage percent"):
        assert prob.get_val("storage.SOC", units="unitless").max() <= 1.0

    with subtests.test("Min SOC >= Min storage percent"):
        assert prob.get_val("storage.SOC", units="unitless").min() >= 0.1

    with subtests.test("Charge never exceeds charge rate"):
        assert (
            prob.get_val("storage.storage_hydrogen_charge", units="kg/h").min() >= -1 * charge_rate
        )

    with subtests.test("Discharge never exceeds discharge rate"):
        assert (
            prob.get_val("storage.storage_hydrogen_discharge", units="kg/h").max() <= discharge_rate
        )

    with subtests.test("Discharge never exceeds demand"):
        assert np.all(
            prob.get_val("storage.storage_hydrogen_discharge", units="kg/h").max()
            <= commodity_demand
        )

    with subtests.test("Cumulative charge/discharge does not exceed storage capacity"):
        assert np.cumsum(prob.get_val("storage_hydrogen_out", units="kg/h")).max() <= capacity
        assert np.cumsum(prob.get_val("storage_hydrogen_out", units="kg/h")).min() >= -1 * capacity

    with subtests.test("Expected discharge from hour 10-30"):
        expected_discharge = np.concat(
            [np.zeros(8), np.ones(6), np.full(3, 5.0), np.array([4, 3, 2])]
        )
        np.testing.assert_allclose(
            prob.get_val("storage.storage_hydrogen_discharge", units="kg/h")[10:30],
            expected_discharge,
            rtol=1e-6,
        )

    with subtests.test("Expected charge hour 0-20"):
        expected_charge = np.concat([np.zeros(8), np.arange(-1, -9, -1), np.zeros(4)])
        np.testing.assert_allclose(
            prob.get_val("storage.storage_hydrogen_charge", units="kg/h")[0:20],
            expected_charge,
            rtol=1e-6,
        )
