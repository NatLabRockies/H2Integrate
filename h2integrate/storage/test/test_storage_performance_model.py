import numpy as np
import pytest
import openmdao.api as om

from h2integrate.storage.storage_performance_model import StoragePerformanceModel
from h2integrate.control.control_strategies.storage.simple_openloop_controller import (
    SimpleStorageOpenLoopController,
)


@pytest.mark.regression
@pytest.mark.parametrize("n_timesteps", [24])
def test_generic_storage_with_simple_control_dmd_lessthan_charge_rate(plant_config, subtests):
    # this tests a case where the demand < charge rate and charge_rate=discharge_rate
    model_inputs = {
        "shared_parameters": {
            "commodity": "hydrogen",
            "commodity_rate_units": "kg/h",
        },
        "performance_parameters": {
            "max_capacity": 40,
            "max_charge_rate": 10,
            "min_soc_fraction": 0.1,
            "max_soc_fraction": 1.0,
            "init_soc_fraction": 0.1,
            "commodity_amount_units": "kg",
            "charge_equals_discharge": True,
            "charge_efficiency": 1.0,
            "discharge_efficiency": 1.0,
            "demand_profile": 0.0,
        },
        "control_parameters": {"set_demand_as_avg_commodity_in": False},
    }

    prob = om.Problem()

    commodity_demand = np.full(24, 5.0)
    commodity_in = np.concat([np.zeros(3), np.cumsum(np.ones(15)), np.full(6, 4.0)])

    prob.model.add_subsystem(
        name="IVC1",
        subsys=om.IndepVarComp(name="hydrogen_in", val=commodity_in, units="kg/h"),
        promotes=["*"],
    )

    prob.model.add_subsystem(
        name="IVC2",
        subsys=om.IndepVarComp(name="hydrogen_demand", val=commodity_demand, units="kg/h"),
        promotes=["*"],
    )

    prob.model.add_subsystem(
        "control",
        SimpleStorageOpenLoopController(
            plant_config=plant_config,
            tech_config={"model_inputs": model_inputs},
        ),
        promotes=["*"],
    )

    prob.model.add_subsystem(
        "storage",
        StoragePerformanceModel(
            plant_config=plant_config,
            tech_config={"model_inputs": model_inputs},
        ),
        promotes=["*"],
    )

    prob.setup()

    prob.run_model()

    performance_model_config = model_inputs["performance_parameters"]

    charge_rate = prob.get_val("storage.max_charge_rate", units="kg/h")[0]
    discharge_rate = prob.get_val("storage.max_charge_rate", units="kg/h")[0]
    capacity = prob.get_val("storage.storage_capacity", units="kg")[0]

    with subtests.test("Charge rate = charge rate from config"):
        assert pytest.approx(charge_rate, rel=1e-6) == performance_model_config["max_charge_rate"]
    with subtests.test("Capacity = capacity from config"):
        assert pytest.approx(capacity, rel=1e-6) == performance_model_config["max_capacity"]
    with subtests.test("Charge rate = discharge rate"):
        assert pytest.approx(charge_rate, rel=1e-6) == discharge_rate

    # Test that discharge is always positive
    with subtests.test("Discharge is always positive"):
        assert np.all(prob.get_val("storage.storage_hydrogen_discharge", units="kg/h") >= 0)

    with subtests.test("Charge is always negative"):
        assert np.all(prob.get_val("storage.storage_hydrogen_charge", units="kg/h") <= 0)

    with subtests.test("Charge + Discharge == hydrogen_out"):
        charge_plus_discharge = prob.get_val(
            "storage.storage_hydrogen_charge", units="kg/h"
        ) + prob.get_val("storage.storage_hydrogen_discharge", units="kg/h")
        np.testing.assert_allclose(
            charge_plus_discharge, prob.get_val("hydrogen_out", units="kg/h"), rtol=1e-6
        )
    with subtests.test("Initial SOC is correct"):
        assert (
            pytest.approx(prob.model.get_val("storage.SOC", units="unitless")[0], rel=1e-6)
            == performance_model_config["init_soc_fraction"]
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
        assert (
            prob.get_val("storage.SOC", units="unitless").max()
            <= performance_model_config["max_soc_fraction"]
        )

    with subtests.test("Min SOC >= Min storage percent"):
        assert (
            prob.get_val("storage.SOC", units="unitless").min()
            >= performance_model_config["min_soc_fraction"]
        )

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
        assert np.cumsum(prob.get_val("hydrogen_out", units="kg/h")).max() <= capacity
        assert np.cumsum(prob.get_val("hydrogen_out", units="kg/h")).min() >= -1 * capacity

    with subtests.test("Expected discharge"):
        expected_discharge = np.concat([np.zeros(18), np.ones(6)])
        np.testing.assert_allclose(
            prob.get_val("storage.storage_hydrogen_discharge", units="kg/h"),
            expected_discharge,
            rtol=1e-6,
        )

    with subtests.test("Expected charge"):
        expected_charge = np.concat([np.zeros(8), np.arange(-1, -9, -1), np.zeros(8)])
        np.testing.assert_allclose(
            prob.get_val("storage.storage_hydrogen_charge", units="kg/h"),
            expected_charge,
            rtol=1e-6,
        )

    with subtests.test("Expected capacity factor"):
        assert (
            pytest.approx(-12.5, rel=1e-6)
            == prob.get_val("storage.capacity_factor", units="percent")[0]
        )

    with subtests.test("Expected standard capacity factor"):
        assert (
            pytest.approx(2.5, rel=1e-6)
            == prob.get_val("storage.standard_capacity_factor", units="percent")[0]
        )


@pytest.mark.regression
@pytest.mark.parametrize("n_timesteps", [24])
def test_generic_storage_with_simple_control_charge_rate_lessthan_demand(plant_config, subtests):
    # this tests a case where the charge_rate < demand and charge_rate=discharge_rate
    model_inputs = {
        "shared_parameters": {
            "commodity": "hydrogen",
            "commodity_rate_units": "kg/h",
        },
        "performance_parameters": {
            "max_capacity": 400,
            "max_charge_rate": 100,
            "min_soc_fraction": 0.1,
            "max_soc_fraction": 1.0,
            "init_soc_fraction": 0.1,
            "n_control_window": 24,
            "commodity_amount_units": "kg",
            "charge_equals_discharge": True,
            "charge_efficiency": 1.0,
            "discharge_efficiency": 1.0,
            "demand_profile": 0.0,
        },
        "control_parameters": {"set_demand_as_avg_commodity_in": False},
    }

    prob = om.Problem()

    commodity_demand = np.full(24, 11.0)
    commodity_in = np.concat([np.full(3, 20.0), np.cumsum(np.ones(15)), np.full(6, 4.0)])

    prob.model.add_subsystem(
        name="IVC1",
        subsys=om.IndepVarComp(name="hydrogen_in", val=commodity_in, units="kg/h"),
        promotes=["*"],
    )

    prob.model.add_subsystem(
        name="IVC2",
        subsys=om.IndepVarComp(name="hydrogen_demand", val=commodity_demand, units="kg/h"),
        promotes=["*"],
    )

    prob.model.add_subsystem(
        "control",
        SimpleStorageOpenLoopController(
            plant_config=plant_config,
            tech_config={"model_inputs": model_inputs},
        ),
        promotes=["*"],
    )

    prob.model.add_subsystem(
        "storage",
        StoragePerformanceModel(
            plant_config=plant_config,
            tech_config={"model_inputs": model_inputs},
        ),
        promotes=["*"],
    )

    prob.setup()

    new_charge_rate = 10.0
    new_storage_capacity = 40.0
    prob.set_val("storage.max_charge_rate", new_charge_rate, units="kg/h")
    prob.set_val("storage.storage_capacity", new_storage_capacity, units="kg")

    prob.run_model()

    performance_model_config = model_inputs["performance_parameters"]

    charge_rate = prob.get_val("storage.max_charge_rate", units="kg/h")[0]
    discharge_rate = prob.get_val("storage.max_charge_rate", units="kg/h")[0]
    capacity = prob.get_val("storage.storage_capacity", units="kg")[0]

    with subtests.test("Charge rate = charge rate from set_val"):
        assert pytest.approx(charge_rate, rel=1e-6) == new_charge_rate
    with subtests.test("Capacity = capacity from set_val"):
        assert pytest.approx(capacity, rel=1e-6) == new_storage_capacity
    with subtests.test("Charge rate = discharge rate"):
        assert pytest.approx(charge_rate, rel=1e-6) == discharge_rate

    # Test that discharge is always positive
    with subtests.test("Discharge is always positive"):
        assert np.all(prob.get_val("storage.storage_hydrogen_discharge", units="kg/h") >= 0)

    with subtests.test("Charge is always negative"):
        assert np.all(prob.get_val("storage.storage_hydrogen_charge", units="kg/h") <= 0)

    with subtests.test("Charge + Discharge == hydrogen_out"):
        charge_plus_discharge = prob.get_val(
            "storage.storage_hydrogen_charge", units="kg/h"
        ) + prob.get_val("storage.storage_hydrogen_discharge", units="kg/h")
        np.testing.assert_allclose(
            charge_plus_discharge, prob.get_val("hydrogen_out", units="kg/h"), rtol=1e-6
        )
    with subtests.test("Initial SOC is correct"):
        init_soc_expected = (
            performance_model_config["init_soc_fraction"]
            - prob.get_val("hydrogen_out", units="kg/h")[0] / capacity
        )
        assert (
            pytest.approx(prob.model.get_val("storage.SOC", units="unitless")[0], rel=1e-6)
            == init_soc_expected
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
        assert (
            prob.get_val("storage.SOC", units="unitless").max()
            <= performance_model_config["max_soc_fraction"]
        )

    with subtests.test("Min SOC >= Min storage percent"):
        assert (
            prob.get_val("storage.SOC", units="unitless").min()
            >= performance_model_config["min_soc_fraction"]
        )

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
        assert np.cumsum(prob.get_val("hydrogen_out", units="kg/h")).max() <= capacity
        assert np.cumsum(prob.get_val("hydrogen_out", units="kg/h")).min() >= -1 * capacity

    with subtests.test("Expected discharge"):
        expected_discharge = np.concat(
            [np.zeros(3), np.array([10, 9, 8]), np.zeros(12), np.array([7, 3]), np.zeros(4)]
        )
        np.testing.assert_allclose(
            prob.get_val("storage.storage_hydrogen_discharge", units="kg/h"),
            expected_discharge,
            rtol=1e-6,
            atol=1e-10,
        )

    with subtests.test("Expected charge"):
        expected_charge = np.concat(
            [np.full(3, -9), np.zeros(11), np.arange(-1, -5, -1), np.zeros(6)]
        )
        np.testing.assert_allclose(
            prob.get_val("storage.storage_hydrogen_charge", units="kg/h"),
            expected_charge,
            rtol=1e-6,
        )

    with subtests.test("Total charge = total discharge"):
        assert (
            pytest.approx(
                -1 * prob.get_val("storage.storage_hydrogen_charge", units="kg/h").sum(), rel=1e-6
            )
            == prob.get_val("storage.storage_hydrogen_discharge", units="kg/h").sum()
        )

    with subtests.test("Expected capacity factor"):
        assert (
            pytest.approx(0.0, rel=1e-6)
            == prob.get_val("storage.capacity_factor", units="percent")[0]
        )

    with subtests.test("Expected standard capacity factor"):
        assert (
            pytest.approx(15.416666, rel=1e-6)
            == prob.get_val("storage.standard_capacity_factor", units="percent")[0]
        )


@pytest.mark.regression
@pytest.mark.parametrize("n_timesteps", [24])
def test_generic_storage_with_simple_control_zero_size(plant_config, subtests):
    # this tests a case where the charge_rate < demand and charge_rate=discharge_rate
    model_inputs = {
        "shared_parameters": {
            "commodity": "hydrogen",
            "commodity_rate_units": "kg/h",
        },
        "performance_parameters": {
            "max_capacity": 40,
            "max_charge_rate": 10,
            "max_discharge_rate": 10,
            "min_soc_fraction": 0.1,
            "max_soc_fraction": 1.0,
            "init_soc_fraction": 0.1,
            "n_control_window": 24,
            "commodity_amount_units": "kg",
            "charge_equals_discharge": False,
            "charge_efficiency": 1.0,
            "discharge_efficiency": 1.0,
            "demand_profile": 0.0,
        },
        "control_parameters": {"set_demand_as_avg_commodity_in": False},
    }

    prob = om.Problem()

    commodity_demand = np.full(24, 11.0)
    commodity_in = np.concat([np.full(3, 20.0), np.cumsum(np.ones(15)), np.full(6, 4.0)])

    prob.model.add_subsystem(
        name="IVC1",
        subsys=om.IndepVarComp(name="hydrogen_in", val=commodity_in, units="kg/h"),
        promotes=["*"],
    )

    prob.model.add_subsystem(
        name="IVC2",
        subsys=om.IndepVarComp(name="hydrogen_demand", val=commodity_demand, units="kg/h"),
        promotes=["*"],
    )

    prob.model.add_subsystem(
        "control",
        SimpleStorageOpenLoopController(
            plant_config=plant_config,
            tech_config={"model_inputs": model_inputs},
        ),
        promotes=["*"],
    )

    prob.model.add_subsystem(
        "storage",
        StoragePerformanceModel(
            plant_config=plant_config,
            tech_config={"model_inputs": model_inputs},
        ),
        promotes=["*"],
    )

    prob.setup()

    new_charge_rate = 10.0
    new_storage_capacity = 40.0
    new_discharge_rate = 0.0
    prob.set_val("storage.max_charge_rate", new_charge_rate, units="kg/h")
    prob.set_val("storage.max_discharge_rate", new_discharge_rate, units="kg/h")
    prob.set_val("storage.storage_capacity", new_storage_capacity, units="kg")

    prob.run_model()

    performance_model_config = model_inputs["performance_parameters"]

    charge_rate = prob.get_val("storage.max_charge_rate", units="kg/h")[0]
    discharge_rate = prob.get_val("storage.max_discharge_rate", units="kg/h")[0]
    capacity = prob.get_val("storage.storage_capacity", units="kg")[0]

    with subtests.test("Charge rate = charge rate from set_val"):
        assert pytest.approx(charge_rate, rel=1e-6) == new_charge_rate
    with subtests.test("Capacity = capacity from set_val"):
        assert pytest.approx(capacity, rel=1e-6) == new_storage_capacity
    with subtests.test("Discharge rate = discharge rate from set_val"):
        assert pytest.approx(discharge_rate, rel=1e-6) == new_discharge_rate

    # Test that discharge is always zero since discharge rate is zero
    with subtests.test("Discharge is always zero"):
        assert np.all(prob.get_val("storage.storage_hydrogen_discharge", units="kg/h") == 0)

    with subtests.test("Charge is always negative"):
        assert np.all(prob.get_val("storage.storage_hydrogen_charge", units="kg/h") <= 0)

    # Test when charge rate and discharge rate are zero
    new_charge_rate = 0.0
    new_storage_capacity = 40.0
    new_discharge_rate = 0.0
    prob.set_val("storage.max_charge_rate", new_charge_rate, units="kg/h")
    prob.set_val("storage.max_discharge_rate", new_discharge_rate, units="kg/h")
    prob.set_val("storage.storage_capacity", new_storage_capacity, units="kg")

    prob.run_model()

    charge_rate = prob.get_val("storage.max_charge_rate", units="kg/h")[0]
    discharge_rate = prob.get_val("storage.max_discharge_rate", units="kg/h")[0]
    capacity = prob.get_val("storage.storage_capacity", units="kg")[0]

    with subtests.test("Charge rate = 0"):
        assert pytest.approx(charge_rate, rel=1e-6) == new_charge_rate
    with subtests.test("Capacity > 0"):
        assert pytest.approx(capacity, rel=1e-6) == new_storage_capacity
    with subtests.test("Discharge rate = 0"):
        assert pytest.approx(discharge_rate, rel=1e-6) == new_discharge_rate

    # Test that discharge is always zero since discharge rate is zero
    with subtests.test("Discharge is always zero"):
        assert np.all(prob.get_val("storage.storage_hydrogen_discharge", units="kg/h") == 0)

    with subtests.test("Charge is always zero"):
        assert np.all(prob.get_val("storage.storage_hydrogen_charge", units="kg/h") == 0)

    with subtests.test("SOC never changes"):
        assert np.all(
            prob.get_val("storage.SOC", units="unitless")
            == performance_model_config["init_soc_fraction"]
        )

    # Test when capacity is zero
    new_charge_rate = 10.0
    new_storage_capacity = 0.0
    new_discharge_rate = 10.0
    prob.set_val("storage.max_charge_rate", new_charge_rate, units="kg/h")
    prob.set_val("storage.max_discharge_rate", new_discharge_rate, units="kg/h")
    prob.set_val("storage.storage_capacity", new_storage_capacity, units="kg")

    prob.run_model()

    charge_rate = prob.get_val("storage.max_charge_rate", units="kg/h")[0]
    discharge_rate = prob.get_val("storage.max_discharge_rate", units="kg/h")[0]
    capacity = prob.get_val("storage.storage_capacity", units="kg")[0]

    with subtests.test("Charge rate = 10"):
        assert pytest.approx(charge_rate, rel=1e-6) == new_charge_rate
    with subtests.test("Capacity = 0"):
        assert pytest.approx(capacity, rel=1e-6) == new_storage_capacity
    with subtests.test("Discharge rate = 10"):
        assert pytest.approx(discharge_rate, rel=1e-6) == new_discharge_rate

    # Test that discharge is always zero since capacity is zero
    with subtests.test("Discharge is always zero"):
        assert np.all(prob.get_val("storage.storage_hydrogen_discharge", units="kg/h") == 0)

    with subtests.test("Charge is always zero"):
        assert np.all(prob.get_val("storage.storage_hydrogen_charge", units="kg/h") == 0)

    with subtests.test("SOC never changes"):
        assert np.all(
            prob.get_val("storage.SOC", units="unitless")
            == performance_model_config["init_soc_fraction"]
        )

    with subtests.test("Expected capacity factor"):
        assert (
            pytest.approx(0.0, rel=1e-6)
            == prob.get_val("storage.capacity_factor", units="percent")[0]
        )

    with subtests.test("Expected standard capacity factor"):
        assert (
            pytest.approx(0.0, rel=1e-6)
            == prob.get_val("storage.standard_capacity_factor", units="percent")[0]
        )


@pytest.mark.regression
@pytest.mark.parametrize("n_timesteps", [24])
def test_generic_storage_with_simple_control_with_losses(plant_config, subtests):
    # this tests a case where the demand < charge rate and charge_rate=discharge_rate
    charge_eff = 0.80
    discharge_eff = 0.75
    model_inputs = {
        "shared_parameters": {
            "commodity": "hydrogen",
            "commodity_rate_units": "kg/h",
        },
        "performance_parameters": {
            "max_capacity": 40,
            "max_charge_rate": 10,
            "min_soc_fraction": 0.1,
            "max_soc_fraction": 1.0,
            "init_soc_fraction": 0.1,
            "n_control_window": 24,
            "commodity_amount_units": "kg",
            "charge_equals_discharge": True,
            "charge_efficiency": charge_eff,
            "discharge_efficiency": discharge_eff,
            "demand_profile": 0.0,
        },
        "control_parameters": {"set_demand_as_avg_commodity_in": False},
    }

    prob = om.Problem()

    # demand is below then above the charge rate
    commodity_demand = np.concat([np.full(12, 5.0), np.full(12, 20.0)])
    # start with charging for first 3 hours (in>demand),
    # then discharging at last 6 hours (in<demand)
    commodity_in = np.concat([np.full(3, 8.0), np.arange(1, 16, 1), np.full(6, 4.0)])

    prob.model.add_subsystem(
        name="IVC1",
        subsys=om.IndepVarComp(name="hydrogen_in", val=commodity_in, units="kg/h"),
        promotes=["*"],
    )

    prob.model.add_subsystem(
        name="IVC2",
        subsys=om.IndepVarComp(name="hydrogen_demand", val=commodity_demand, units="kg/h"),
        promotes=["*"],
    )

    prob.model.add_subsystem(
        "control",
        SimpleStorageOpenLoopController(
            plant_config=plant_config,
            tech_config={"model_inputs": model_inputs},
        ),
        promotes=["*"],
    )

    prob.model.add_subsystem(
        "storage",
        StoragePerformanceModel(
            plant_config=plant_config,
            tech_config={"model_inputs": model_inputs},
        ),
        promotes=["*"],
    )

    prob.setup()

    prob.run_model()

    performance_model_config = model_inputs["performance_parameters"]

    charge_rate = prob.get_val("storage.max_charge_rate", units="kg/h")[0]
    discharge_rate = prob.get_val("storage.max_charge_rate", units="kg/h")[0]
    capacity = prob.get_val("storage.storage_capacity", units="kg")[0]

    with subtests.test("Charge rate = charge rate from config"):
        assert pytest.approx(charge_rate, rel=1e-6) == performance_model_config["max_charge_rate"]
    with subtests.test("Capacity = capacity from config"):
        assert pytest.approx(capacity, rel=1e-6) == performance_model_config["max_capacity"]
    with subtests.test("Charge rate = discharge rate"):
        assert pytest.approx(charge_rate, rel=1e-6) == discharge_rate

    # Test that discharge is always positive
    with subtests.test("Discharge is always positive"):
        assert np.all(prob.get_val("storage.storage_hydrogen_discharge", units="kg/h") >= 0)

    with subtests.test("Charge is always negative"):
        assert np.all(prob.get_val("storage.storage_hydrogen_charge", units="kg/h") <= 0)

    with subtests.test("Charge + Discharge == hydrogen_out"):
        charge_plus_discharge = prob.get_val(
            "storage.storage_hydrogen_charge", units="kg/h"
        ) + prob.get_val("storage.storage_hydrogen_discharge", units="kg/h")
        np.testing.assert_allclose(
            charge_plus_discharge, prob.get_val("hydrogen_out", units="kg/h"), rtol=1e-6
        )
    with subtests.test("Initial SOC is correct"):
        init_soc_expected = (
            performance_model_config["init_soc_fraction"]
            - (prob.get_val("hydrogen_out", units="kg/h")[0] * charge_eff) / capacity
        )

        assert (
            pytest.approx(prob.model.get_val("storage.SOC", units="unitless")[0], rel=1e-6)
            == init_soc_expected
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
        assert (
            prob.get_val("storage.SOC", units="unitless").max()
            <= performance_model_config["max_soc_fraction"]
        )

    with subtests.test("Min SOC >= Min storage percent"):
        assert (
            prob.get_val("storage.SOC", units="unitless").min()
            >= performance_model_config["min_soc_fraction"]
        )

    with subtests.test("Charge never exceeds charge rate"):
        assert (
            prob.get_val("storage.storage_hydrogen_charge", units="kg/h").min()
            >= -1 * charge_rate / charge_eff
        )

    with subtests.test("Discharge never exceeds discharge rate"):
        assert (
            prob.get_val("storage.storage_hydrogen_discharge", units="kg/h").max() <= discharge_rate
        )

    with subtests.test("Discharge never exceeds demand"):
        assert np.all(
            prob.get_val("storage.storage_hydrogen_discharge", units="kg/h") <= commodity_demand
        )

    with subtests.test("Cumulative charge/discharge does not exceed storage capacity"):
        assert (
            np.cumsum(prob.get_val("hydrogen_out", units="kg/h")).max() <= capacity * discharge_eff
        )
        assert (
            np.cumsum(prob.get_val("hydrogen_out", units="kg/h")).min()
            >= -1 * capacity / charge_eff
        )

    # When charging, the increase in the SOC (in kg) should be less than the commodity taken
    # from the available commodity to charge
    soc_kg = prob.model.get_val("storage.SOC", units="unitless") * capacity
    commodity_to_soc_when_charging = np.diff(soc_kg, prepend=True)[indx_soc_increase]
    commodity_from_instream_when_charging = (
        -1 * prob.get_val("storage.storage_hydrogen_charge", units="kg/h")[indx_soc_increase]
    )
    charge_losses = 1 - (commodity_to_soc_when_charging / commodity_from_instream_when_charging)

    with subtests.test(
        "Charge efficiency: commodity from available > commodity to storage when charging"
    ):
        assert np.allclose(charge_losses, 1 - charge_eff, rtol=1e-6, atol=1e-10)

    # When discharging, the decrease in the SOC (in kg) should be more than the commodity added
    # to the available commodity from discharging
    commodity_from_soc_when_discharging = -1 * np.diff(soc_kg, prepend=False)[indx_soc_decrease]
    commodity_to_outstream_when_discharging = prob.get_val(
        "storage.storage_hydrogen_discharge", units="kg/h"
    )[indx_soc_decrease]
    discharge_losses = 1 - (
        commodity_to_outstream_when_discharging / commodity_from_soc_when_discharging
    )

    with subtests.test(
        "Discharge efficiency: commodity to available < commodity from storage when discharging"
    ):
        assert np.allclose(discharge_losses, 1 - discharge_eff, rtol=1e-6, atol=1e-10)

    with subtests.test("Expected discharge"):
        expected_discharge = np.concat(
            [np.zeros(3), np.array([4, 1.4]), np.zeros(7), np.array([6]), np.zeros(11)]
        )
        np.testing.assert_allclose(
            prob.get_val("storage.storage_hydrogen_discharge", units="kg/h"),
            expected_discharge,
            rtol=1e-6,
        )

    with subtests.test("Expected charge"):
        expected_charge = np.concat(
            [np.full(3, -3.0), np.zeros(5), np.arange(-1, -5, -1), np.zeros(12)]
        )
        np.testing.assert_allclose(
            prob.get_val("storage.storage_hydrogen_charge", units="kg/h"),
            expected_charge,
            rtol=1e-6,
        )

    with subtests.test("Expected capacity factor"):
        assert (
            pytest.approx(-3.16666666, rel=1e-6)
            == prob.get_val("storage.capacity_factor", units="percent")[0]
        )

    with subtests.test("Expected standard capacity factor"):
        assert (
            pytest.approx(4.750, rel=1e-6)
            == prob.get_val("storage.standard_capacity_factor", units="percent")[0]
        )


@pytest.mark.regression
@pytest.mark.parametrize("n_timesteps", [24])
def test_generic_storage_with_simple_control_with_losses_round_trip(plant_config, subtests):
    # this tests a case where the demand < charge rate and charge_rate=discharge_rate
    charge_eff = 0.75
    discharge_eff = 0.75
    round_trip_eff = charge_eff * discharge_eff
    model_inputs = {
        "shared_parameters": {
            "commodity": "hydrogen",
            "commodity_rate_units": "kg/h",
        },
        "performance_parameters": {
            "max_capacity": 40,
            "max_charge_rate": 10,
            "min_soc_fraction": 0.1,
            "max_soc_fraction": 1.0,
            "init_soc_fraction": 0.1,
            "n_control_window": 24,
            "commodity_amount_units": "kg",
            "charge_equals_discharge": True,
            "round_trip_efficiency": round_trip_eff,
            "demand_profile": 0.0,
        },
        "control_parameters": {"set_demand_as_avg_commodity_in": False},
    }

    prob = om.Problem()

    commodity_demand = np.full(24, 5.0)
    commodity_in = np.concat([np.zeros(3), np.cumsum(np.ones(15)), np.full(6, 4.0)])

    prob.model.add_subsystem(
        name="IVC1",
        subsys=om.IndepVarComp(name="hydrogen_in", val=commodity_in, units="kg/h"),
        promotes=["*"],
    )

    prob.model.add_subsystem(
        name="IVC2",
        subsys=om.IndepVarComp(name="hydrogen_demand", val=commodity_demand, units="kg/h"),
        promotes=["*"],
    )

    prob.model.add_subsystem(
        "control",
        SimpleStorageOpenLoopController(
            plant_config=plant_config,
            tech_config={"model_inputs": model_inputs},
        ),
        promotes=["*"],
    )

    prob.model.add_subsystem(
        "storage",
        StoragePerformanceModel(
            plant_config=plant_config,
            tech_config={"model_inputs": model_inputs},
        ),
        promotes=["*"],
    )

    prob.setup()

    prob.run_model()

    performance_model_config = model_inputs["performance_parameters"]

    charge_rate = prob.get_val("storage.max_charge_rate", units="kg/h")[0]
    discharge_rate = prob.get_val("storage.max_charge_rate", units="kg/h")[0]
    capacity = prob.get_val("storage.storage_capacity", units="kg")[0]

    with subtests.test("Charge rate = charge rate from config"):
        assert pytest.approx(charge_rate, rel=1e-6) == performance_model_config["max_charge_rate"]
    with subtests.test("Capacity = capacity from config"):
        assert pytest.approx(capacity, rel=1e-6) == performance_model_config["max_capacity"]
    with subtests.test("Charge rate = discharge rate"):
        assert pytest.approx(charge_rate, rel=1e-6) == discharge_rate

    # Test that discharge is always positive
    with subtests.test("Discharge is always positive"):
        assert np.all(prob.get_val("storage.storage_hydrogen_discharge", units="kg/h") >= 0)

    with subtests.test("Charge is always negative"):
        assert np.all(prob.get_val("storage.storage_hydrogen_charge", units="kg/h") <= 0)

    with subtests.test("Charge + Discharge == hydrogen_out"):
        charge_plus_discharge = prob.get_val(
            "storage.storage_hydrogen_charge", units="kg/h"
        ) + prob.get_val("storage.storage_hydrogen_discharge", units="kg/h")
        np.testing.assert_allclose(
            charge_plus_discharge, prob.get_val("hydrogen_out", units="kg/h"), rtol=1e-6
        )
    with subtests.test("Initial SOC is correct"):
        assert (
            pytest.approx(prob.model.get_val("storage.SOC", units="unitless")[0], rel=1e-6)
            == performance_model_config["init_soc_fraction"]
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
        assert (
            prob.get_val("storage.SOC", units="unitless").max()
            <= performance_model_config["max_soc_fraction"]
        )

    with subtests.test("Min SOC >= Min storage percent"):
        assert (
            prob.get_val("storage.SOC", units="unitless").min()
            >= performance_model_config["min_soc_fraction"]
        )

    with subtests.test("Charge never exceeds charge rate"):
        assert (
            prob.get_val("storage.storage_hydrogen_charge", units="kg/h").min()
            >= -1 * charge_rate / charge_eff
        )

    with subtests.test("Discharge never exceeds discharge rate"):
        assert prob.get_val(
            "storage.storage_hydrogen_discharge", units="kg/h"
        ).max() <= discharge_rate * np.sqrt(performance_model_config["round_trip_efficiency"])

    with subtests.test("Discharge never exceeds demand"):
        assert np.all(
            prob.get_val("storage.storage_hydrogen_discharge", units="kg/h").max()
            <= commodity_demand
        )

    with subtests.test("Cumulative charge/discharge does not exceed storage capacity"):
        assert (
            np.cumsum(prob.get_val("hydrogen_out", units="kg/h")).max() <= capacity * discharge_eff
        )
        assert (
            np.cumsum(prob.get_val("hydrogen_out", units="kg/h")).min()
            >= -1 * capacity / charge_eff
        )

    with subtests.test("Expected discharge"):
        expected_discharge = np.concat([np.zeros(18), np.ones(6)])
        np.testing.assert_allclose(
            prob.get_val("storage.storage_hydrogen_discharge", units="kg/h"),
            expected_discharge,
            rtol=1e-6,
        )

    with subtests.test("Expected charge"):
        expected_charge = np.concat(
            [
                np.zeros(8),
                np.arange(-1, -10, -1),
                np.array([-3]),
                np.zeros(6),
            ]
        )
        np.testing.assert_allclose(
            prob.get_val("storage.storage_hydrogen_charge", units="kg/h"),
            expected_charge,
            rtol=1e-6,
        )

    with subtests.test("Expected capacity factor"):
        assert (
            pytest.approx(-17.5, rel=1e-6)
            == prob.get_val("storage.capacity_factor", units="percent")[0]
        )

    with subtests.test("Expected standard capacity factor"):
        assert (
            pytest.approx(2.5, rel=1e-6)
            == prob.get_val("storage.standard_capacity_factor", units="percent")[0]
        )


@pytest.mark.unit
def test_round_trip_efficiency_preserved_in_config(subtests):
    """Test that round_trip_efficiency is preserved in the config's as_dict() output.

    This is a regression test for a bug where round_trip_efficiency was set to None
    after computing charge/discharge efficiencies in __attrs_post_init__. This caused
    check_inputs() to raise an AttributeError because round_trip_efficiency appeared
    in the user input but was missing from the config's as_dict() output.
    """
    from h2integrate.storage.storage_performance_model import StoragePerformanceModelConfig

    round_trip_eff = 0.81

    with subtests.test("StoragePerformanceModelConfig preserves round_trip_efficiency"):
        config = StoragePerformanceModelConfig(
            commodity="hydrogen",
            commodity_rate_units="kg/h",
            max_capacity=40,
            max_charge_rate=10,
            min_soc_fraction=0.1,
            max_soc_fraction=1.0,
            init_soc_fraction=0.5,
            demand_profile=0.0,
            round_trip_efficiency=round_trip_eff,
        )
        config_dict = config.as_dict()
        assert "round_trip_efficiency" in config_dict
        assert config_dict["round_trip_efficiency"] == round_trip_eff
        assert config_dict["charge_efficiency"] == pytest.approx(np.sqrt(round_trip_eff))
        assert config_dict["discharge_efficiency"] == pytest.approx(np.sqrt(round_trip_eff))
