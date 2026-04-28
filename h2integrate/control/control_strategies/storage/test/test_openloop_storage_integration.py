import numpy as np
import pytest
import openmdao.api as om
from pytest import fixture

from h2integrate.storage.battery.pysam_battery import PySAMBatteryPerformanceModel
from h2integrate.storage.storage_performance_model import StoragePerformanceModel
from h2integrate.storage.simple_storage_auto_sizing import StorageAutoSizingModel
from h2integrate.control.control_strategies.storage.simple_openloop_controller import (
    SimpleStorageOpenLoopController,
)
from h2integrate.control.control_strategies.storage.demand_openloop_storage_controller import (
    DemandOpenLoopStorageController,
)


@fixture
def plant_config():
    plant = {
        "plant": {
            "plant_life": 30,
            "simulation": {
                "dt": 3600,
                "n_timesteps": 24,
            },
        },
    }
    return plant


@fixture
def storage_perf_params(storage_model_name):
    if storage_model_name == "StoragePerformanceModel":
        return {
            "max_capacity": 40,
            "max_charge_rate": 10,
            "min_soc_fraction": 0.1,
            "max_soc_fraction": 1.0,
            "init_soc_fraction": 0.1,
            "charge_equals_discharge": True,
            "charge_efficiency": 1.0,
            "discharge_efficiency": 1.0,
        }
    if storage_model_name == "PySAMBatteryPerformanceModel":
        return {
            "max_capacity": 40,
            "max_charge_rate": 10,
            "min_soc_fraction": 0.1,
            "max_soc_fraction": 1.0,
            "init_soc_fraction": 1.0,
            "chemistry": "LFPGraphite",
        }
    if storage_model_name == "StorageAutoSizingModel":
        return {
            "min_soc_fraction": 0.1,
            "max_soc_fraction": 1.0,
            "charge_efficiency": 1.0,
            "discharge_efficiency": 1.0,
        }


@pytest.mark.integration
@pytest.mark.parametrize("storage_model_name", ["StoragePerformanceModel"])
def test_generic_storage_with_demand_openloop(plant_config, storage_perf_params, subtests):
    commodity_in = np.concat([np.zeros(3), np.cumsum(np.ones(15)), np.full(6, 4.0)])
    commodity_demand = np.full(24, 5.0)

    shared_params = {
        "commodity": "hydrogen",
        "commodity_rate_units": "kg/h",
        "demand_profile": commodity_demand,
    }

    model_inputs = {"shared_parameters": storage_perf_params | shared_params}

    prob = om.Problem()
    prob.model.add_subsystem(
        name="IVC1",
        subsys=om.IndepVarComp(name="hydrogen_in", val=commodity_in, units="kg/h"),
        promotes=["*"],
    )

    prob.model.add_subsystem(
        "h2_storage_control",
        DemandOpenLoopStorageController(
            plant_config=plant_config,
            tech_config={"model_inputs": model_inputs},
        ),
        promotes=["*"],
    )

    prob.model.add_subsystem(
        "h2_storage",
        StoragePerformanceModel(
            plant_config=plant_config,
            tech_config={"model_inputs": model_inputs},
        ),
        promotes=["*"],
    )

    prob.setup()

    prob.run_model()

    with subtests.test("Expected discharge"):
        expected_discharge = np.concat([np.zeros(18), np.ones(6)])
        np.testing.assert_allclose(
            prob.get_val("h2_storage.storage_hydrogen_discharge", units="kg/h"),
            expected_discharge,
            rtol=1e-6,
        )

    with subtests.test("Expected charge"):
        expected_charge = np.concat([np.zeros(8), np.arange(-1, -9, -1), np.zeros(8)])
        np.testing.assert_allclose(
            prob.get_val("h2_storage.storage_hydrogen_charge", units="kg/h"),
            expected_charge,
            rtol=1e-6,
        )


@pytest.mark.integration
@pytest.mark.parametrize("storage_model_name", ["StoragePerformanceModel"])
def test_generic_storage_with_simple_openloop(plant_config, storage_perf_params, subtests):
    commodity_in = np.concat([np.zeros(3), np.cumsum(np.ones(15)), np.full(6, 4.0)])
    commodity_demand = np.full(24, 5.0)

    shared_params = {
        "commodity": "hydrogen",
        "commodity_rate_units": "kg/h",
        "demand_profile": commodity_demand,
    }

    model_inputs = {
        "shared_parameters": shared_params,
        "performance_parameters": storage_perf_params,
        "control_parameters": {"set_demand_as_avg_commodity_in": False},
    }

    prob = om.Problem()
    prob.model.add_subsystem(
        name="IVC1",
        subsys=om.IndepVarComp(name="hydrogen_in", val=commodity_in, units="kg/h"),
        promotes=["*"],
    )

    prob.model.add_subsystem(
        "h2_storage_control",
        SimpleStorageOpenLoopController(
            plant_config=plant_config,
            tech_config={"model_inputs": model_inputs},
        ),
        promotes=["*"],
    )

    prob.model.add_subsystem(
        "h2_storage",
        StoragePerformanceModel(
            plant_config=plant_config,
            tech_config={"model_inputs": model_inputs},
        ),
        promotes=["*"],
    )

    prob.setup()

    prob.run_model()

    with subtests.test("Expected discharge"):
        expected_discharge = np.concat([np.zeros(18), np.ones(6)])
        np.testing.assert_allclose(
            prob.get_val("h2_storage.storage_hydrogen_discharge", units="kg/h"),
            expected_discharge,
            rtol=1e-6,
        )

    with subtests.test("Expected charge"):
        expected_charge = np.concat([np.zeros(8), np.arange(-1, -9, -1), np.zeros(8)])
        np.testing.assert_allclose(
            prob.get_val("h2_storage.storage_hydrogen_charge", units="kg/h"),
            expected_charge,
            rtol=1e-6,
        )


@pytest.mark.integration
@pytest.mark.parametrize("storage_model_name", ["PySAMBatteryPerformanceModel"])
def test_pysam_battery_with_demand_openloop(plant_config, storage_perf_params, subtests):
    commodity_in = np.concat([np.zeros(3), np.cumsum(np.ones(15)), np.full(6, 4.0)])
    commodity_demand = np.full(24, 5.0)

    shared_params = {"demand_profile": commodity_demand} | {
        k: v for k, v in storage_perf_params.items() if k != "chemistry"
    }

    model_inputs = {
        "shared_parameters": shared_params,
        "performance_parameters": {"chemistry": storage_perf_params["chemistry"]},
        "control_parameters": {
            "commodity": "electricity",
            "commodity_rate_units": "kW",
            "charge_equals_discharge": True,
            "charge_efficiency": 1.0,
            "discharge_efficiency": 1.0,
        },
    }

    prob = om.Problem()
    prob.model.add_subsystem(
        name="IVC1",
        subsys=om.IndepVarComp(name="electricity_in", val=commodity_in, units="kW"),
        promotes=["*"],
    )

    prob.model.add_subsystem(
        "battery_control",
        DemandOpenLoopStorageController(
            plant_config=plant_config,
            tech_config={"model_inputs": model_inputs},
        ),
        promotes=["*"],
    )

    prob.model.add_subsystem(
        "battery",
        PySAMBatteryPerformanceModel(
            plant_config=plant_config,
            tech_config={"model_inputs": model_inputs},
        ),
        promotes=["*"],
    )

    prob.setup()

    prob.run_model()
    expected_discharge = np.array(
        [
            4.99483673,
            4.99483511,
            4.99403933,
            3.99456736,
            2.99545121,
            1.99671242,
            0.99828405,
            0.0,
            0.0,
            0.0,
            0.0,
            0.0,
            0.0,
            0.0,
            0.0,
            0.0,
            0.0,
            0.0,
            0.99907629,
            0.9991349,
            0.99911777,
            0.99909762,
            0.99907648,
            0.99905434,
        ]
    )
    with subtests.test("Expected discharge"):
        np.testing.assert_allclose(
            prob.get_val("battery.storage_electricity_discharge", units="kW"),
            expected_discharge,
            rtol=1e-6,
        )

    expected_charge = np.array(
        [
            0.0,
            0.0,
            0.0,
            0.0,
            0.0,
            0.0,
            0.0,
            0.0,
            -0.99835716,
            -1.9969656,
            -2.99592019,
            -3.9952197,
            -4.99480988,
            -5.99461958,
            -3.70438813,
            0.0,
            0.0,
            0.0,
            0.0,
            0.0,
            0.0,
            0.0,
            0.0,
            0.0,
        ]
    )
    with subtests.test("Expected charge"):
        np.testing.assert_allclose(
            prob.get_val("battery.storage_electricity_charge", units="kW"),
            expected_charge,
            rtol=1e-6,
        )


@pytest.mark.integration
@pytest.mark.parametrize("storage_model_name", ["PySAMBatteryPerformanceModel"])
def test_pysam_battery_with_simple_openloop(plant_config, storage_perf_params, subtests):
    commodity_in = np.concat([np.zeros(3), np.cumsum(np.ones(15)), np.full(6, 4.0)])
    commodity_demand = np.full(24, 5.0)

    control_params = {
        "commodity": "electricity",
        "commodity_rate_units": "kW",
        "set_demand_as_avg_commodity_in": False,
    }

    model_inputs = {
        "shared_parameters": {"demand_profile": commodity_demand},
        "performance_parameters": storage_perf_params,
        "control_parameters": control_params,
    }

    prob = om.Problem()
    prob.model.add_subsystem(
        name="IVC1",
        subsys=om.IndepVarComp(name="electricity_in", val=commodity_in, units="kW"),
        promotes=["*"],
    )

    prob.model.add_subsystem(
        "battery_control",
        SimpleStorageOpenLoopController(
            plant_config=plant_config,
            tech_config={"model_inputs": model_inputs},
        ),
        promotes=["*"],
    )

    prob.model.add_subsystem(
        "battery",
        PySAMBatteryPerformanceModel(
            plant_config=plant_config,
            tech_config={"model_inputs": model_inputs},
        ),
        promotes=["*"],
    )

    prob.setup()

    prob.run_model()
    expected_discharge = np.array(
        [
            4.99483673,
            4.99483511,
            4.99403933,
            3.99456736,
            2.99545121,
            1.99671242,
            0.99828405,
            0.0,
            0.0,
            0.0,
            0.0,
            0.0,
            0.0,
            0.0,
            0.0,
            0.0,
            0.0,
            0.0,
            0.99885513,
            0.99913572,
            0.99912398,
            0.99910425,
            0.99908343,
            0.99906162,
        ]
    )
    with subtests.test("Expected discharge"):
        np.testing.assert_allclose(
            prob.get_val("battery.storage_electricity_discharge", units="kW"),
            expected_discharge,
            rtol=1e-6,
        )

    expected_charge = np.array(
        [
            0.0,
            0.0,
            0.0,
            0.0,
            0.0,
            0.0,
            0.0,
            0.0,
            -0.99835716,
            -1.9969656,
            -2.99592019,
            -3.9952197,
            -4.99480988,
            -5.99461958,
            -3.70438813,
            -0.31010625,
            -0.02143906,
            0.0,
            0.0,
            0.0,
            0.0,
            0.0,
            0.0,
            0.0,
        ]
    )
    with subtests.test("Expected charge"):
        np.testing.assert_allclose(
            prob.get_val("battery.storage_electricity_charge", units="kW"),
            expected_charge,
            rtol=1e-6,
        )


@pytest.mark.integration
@pytest.mark.parametrize("storage_model_name", ["StorageAutoSizingModel"])
def test_storage_autosizing_with_demand_openloop(plant_config, storage_perf_params, subtests):
    commodity_in = np.concat([np.zeros(3), np.cumsum(np.ones(15)), np.full(6, 4.0)])
    commodity_demand = np.full(24, 5.0)
    shared_params = {
        "commodity": "hydrogen",
        "commodity_rate_units": "kg/h",
        "demand_profile": commodity_demand,
        "charge_efficiency": storage_perf_params.pop("charge_efficiency"),
        "discharge_efficiency": storage_perf_params.pop("discharge_efficiency"),
        "min_soc_fraction": storage_perf_params.pop("min_soc_fraction"),
        "max_soc_fraction": storage_perf_params.pop("max_soc_fraction"),
    }

    perf_params = storage_perf_params | {"set_demand_as_avg_commodity_in": False}
    model_inputs = {
        "shared_parameters": shared_params,
        "performance_parameters": perf_params,
        "control_parameters": {
            "max_capacity": 100.0,
            "max_charge_rate": 400.0,
            "init_soc_fraction": 0.1,
        },
    }

    prob = om.Problem()
    prob.model.add_subsystem(
        name="IVC1",
        subsys=om.IndepVarComp(name="hydrogen_in", val=commodity_in, units="kg/h"),
        promotes=["*"],
    )

    # NOTE: when these are used together, the controller is not taking
    # the charge/discharge rate info output from the performance model

    prob.model.add_subsystem(
        "h2_storage_control",
        DemandOpenLoopStorageController(
            plant_config=plant_config,
            tech_config={"model_inputs": model_inputs},
        ),
        promotes=["*"],
    )

    prob.model.add_subsystem(
        "h2_storage",
        StorageAutoSizingModel(
            plant_config=plant_config,
            tech_config={"model_inputs": model_inputs},
        ),
        promotes=["*"],
    )

    prob.setup()

    # NOTE: with these combinations, we have to set these values
    # or else the 0 value initialized in the storage performance model
    # is passed to the demand openloop controller
    prob.set_val("h2_storage_control.storage_capacity", 400.0, units="kg")
    prob.set_val("h2_storage_control.max_charge_rate", 100.0, units="kg/h")

    prob.run_model()
    with subtests.test("Expected discharge"):
        expected_discharge = np.concat([np.zeros(18), np.ones(6)])
        np.testing.assert_allclose(
            prob.get_val("h2_storage.storage_hydrogen_discharge", units="kg/h"),
            expected_discharge,
            rtol=1e-6,
        )

    with subtests.test("Expected charge"):
        expected_charge = np.concat([np.zeros(8), np.arange(-1, -11, -1), np.zeros(6)])
        np.testing.assert_allclose(
            prob.get_val("h2_storage.storage_hydrogen_charge", units="kg/h"),
            expected_charge,
            rtol=1e-6,
        )

    with subtests.test("Expected Capacity"):
        assert (
            pytest.approx(prob.get_val("h2_storage.storage_capacity", units="kg"), rel=1e-6)
            == 61.11111111111111
        )

    with subtests.test("Expected Charge Rate"):
        assert pytest.approx(
            prob.get_val("h2_storage.max_charge_rate", units="kg/h"), rel=1e-6
        ) == np.max(commodity_in)


@pytest.mark.integration
@pytest.mark.parametrize("storage_model_name", ["StorageAutoSizingModel"])
def test_storage_autosizing_with_simple_openloop(plant_config, storage_perf_params, subtests):
    commodity_in = np.concat([np.zeros(3), np.cumsum(np.ones(15)), np.full(6, 4.0)])
    commodity_demand = np.full(24, 5.0)
    shared_params = {
        "commodity": "hydrogen",
        "commodity_rate_units": "kg/h",
        "demand_profile": commodity_demand,
        "set_demand_as_avg_commodity_in": False,
    }

    model_inputs = {
        "shared_parameters": shared_params,
        "performance_parameters": storage_perf_params,
    }

    prob = om.Problem()
    prob.model.add_subsystem(
        name="IVC1",
        subsys=om.IndepVarComp(name="hydrogen_in", val=commodity_in, units="kg/h"),
        promotes=["*"],
    )

    prob.model.add_subsystem(
        "h2_storage_control",
        SimpleStorageOpenLoopController(
            plant_config=plant_config,
            tech_config={"model_inputs": model_inputs},
        ),
        promotes=["*"],
    )

    prob.model.add_subsystem(
        "h2_storage",
        StorageAutoSizingModel(
            plant_config=plant_config,
            tech_config={"model_inputs": model_inputs},
        ),
        promotes=["*"],
    )

    prob.setup()

    prob.run_model()

    with subtests.test("Expected discharge"):
        expected_discharge = np.concat([np.array([5.0, 5.0, 3.88889]), np.zeros(15), np.ones(6)])
        np.testing.assert_allclose(
            prob.get_val("h2_storage.storage_hydrogen_discharge", units="kg/h"),
            expected_discharge,
            rtol=1e-6,
        )

    with subtests.test("Expected charge"):
        expected_charge = np.concat([np.zeros(8), np.arange(-1, -11, -1), np.zeros(6)])
        np.testing.assert_allclose(
            prob.get_val("h2_storage.storage_hydrogen_charge", units="kg/h"),
            expected_charge,
            rtol=1e-6,
        )
