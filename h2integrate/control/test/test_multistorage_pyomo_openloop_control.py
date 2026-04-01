import numpy as np
import pytest
import openmdao.api as om
from pytest import fixture

from h2integrate.storage.battery.pysam_battery import PySAMBatteryPerformanceModel
from h2integrate.storage.storage_performance_model import StoragePerformanceModel
from h2integrate.control.control_strategies.heuristic_pyomo_controller import (
    HeuristicLoadFollowingController,
)
from h2integrate.control.control_rules.storage.pyomo_storage_rule_baseclass import (
    PyomoRuleStorageBaseclass,
)
from h2integrate.control.control_strategies.storage.demand_openloop_storage_controller import (
    DemandOpenLoopStorageController,
)


@fixture
def plant_config(pyo_controllers):
    plant_config_base = {
        "plant": {
            "plant_life": 30,
            "simulation": {
                "dt": 3600,
                "n_timesteps": 8760,
            },
        }
    }

    if pyo_controllers == "bat":
        tech_to_dispatch = {
            "tech_to_dispatch_connections": [
                ["combiner", "battery"],
                ["battery", "battery"],
            ]
        }
        plant_config = plant_config_base | tech_to_dispatch
        return plant_config

    if pyo_controllers == "h2s":
        tech_to_dispatch = {
            "tech_to_dispatch_connections": [
                ["combiner", "h2_storage"],
                ["h2_storage", "h2_storage"],
            ]
        }
        plant_config = plant_config_base | tech_to_dispatch
        return plant_config

    if pyo_controllers == "both":
        tech_to_dispatch = {
            "tech_to_dispatch_connections": [
                ["elec_combiner", "battery"],
                ["battery", "battery"],
                ["h2_combiner", "h2_storage"],
                ["h2_storage", "h2_storage"],
            ]
        }
        plant_config = plant_config_base | tech_to_dispatch
        return plant_config

    if pyo_controllers == "none":
        return plant_config_base


def make_battery_pyo_group(plant_config_bat):
    bat_tech_config = {
        "battery": {
            "dispatch_rule_set": {"model": "PyomoRuleStorageBaseclass"},
            "control_strategy": {"model": "HeuristicLoadFollowingController"},
            "performance_model": {"model": "PySAMBatteryPerformanceModel"},
            "model_inputs": {
                "shared_parameters": {
                    "max_charge_rate": 50000,
                    "max_capacity": 200000,
                    "n_control_window": 24,
                    "n_horizon_window": 48,
                    "init_soc_fraction": 0.5,
                    "max_soc_fraction": 0.9,
                    "min_soc_fraction": 0.1,
                },
                "performance_parameters": {
                    "chemistry": "LFPGraphite",
                    "control_variable": "input_power",
                    "demand_profile": 6000.0,
                },
                "control_parameters": {
                    "commodity": "electricity",
                    "commodity_rate_units": "kW",
                    "tech_name": "battery",
                    "system_commodity_interface_limit": 1e12,
                },
                "dispatch_rule_parameters": {
                    "commodity": "electricity",
                    "commodity_rate_units": "kW",
                },
            },
        }
    }
    rule_comp = PyomoRuleStorageBaseclass(
        plant_config=plant_config_bat, tech_config=bat_tech_config["battery"]
    )
    perf_comp = PySAMBatteryPerformanceModel(
        plant_config=plant_config_bat, tech_config=bat_tech_config["battery"]
    )
    control_comp = HeuristicLoadFollowingController(
        plant_config=plant_config_bat, tech_config=bat_tech_config["battery"]
    )

    electricity_in = np.concatenate((np.ones(12) * 0, np.ones(12) * 10000))
    electricity_in = np.tile(electricity_in, 365)
    ivc_comp = om.IndepVarComp(name="electricity_in", val=electricity_in, units="kW")

    return rule_comp, perf_comp, control_comp, ivc_comp


def make_h2_storage_pyo_group(plant_config_h2s):
    h2s_tech_config = {
        "h2_storage": {
            "dispatch_rule_set": {"model": "PyomoRuleStorageBaseclass"},
            "control_strategy": {"model": "HeuristicLoadFollowingController"},
            "performance_model": {"model": "StoragePerformanceModel"},
            "model_inputs": {
                "shared_parameters": {
                    "max_charge_rate": 10.0,
                    "max_capacity": 40.0,
                    "init_soc_fraction": 0.1,
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
                    "demand_profile": 5.0,
                },
                "control_parameters": {
                    "tech_name": "h2_storage",
                    "system_commodity_interface_limit": 10.0,
                    "n_control_window": 24,
                },
            },
        }
    }
    rule_comp = PyomoRuleStorageBaseclass(
        plant_config=plant_config_h2s, tech_config=h2s_tech_config["h2_storage"]
    )
    perf_comp = StoragePerformanceModel(
        plant_config=plant_config_h2s, tech_config=h2s_tech_config["h2_storage"]
    )
    control_comp = HeuristicLoadFollowingController(
        plant_config=plant_config_h2s, tech_config=h2s_tech_config["h2_storage"]
    )

    hydrogen_in = np.tile(np.concat([np.zeros(3), np.cumsum(np.ones(15)), np.full(6, 4.0)]), 365)

    ivc_comp = om.IndepVarComp(name="hydrogen_in", val=hydrogen_in, units="kg/h")

    return rule_comp, perf_comp, control_comp, ivc_comp


def make_h2_storage_openloop_group(plant_config_h2s):
    tech_config_h2s = {
        "shared_parameters": {
            "commodity": "hydrogen",
            "commodity_rate_units": "kg/h",
            "demand_profile": 5.0,
            "max_capacity": 40,
            "max_charge_rate": 10,
            "min_soc_fraction": 0.1,
            "max_soc_fraction": 1.0,
            "init_soc_fraction": 0.1,
            "charge_equals_discharge": True,
            "charge_efficiency": 1.0,
            "discharge_efficiency": 1.0,
        }
    }

    h2_in = np.concat([np.zeros(3), np.cumsum(np.ones(15)), np.full(6, 4.0)])
    commodity_in = np.tile(h2_in, 365)
    ivc_comp = om.IndepVarComp(name="hydrogen_in", val=commodity_in, units="kg/h")
    perf_comp = StoragePerformanceModel(
        plant_config=plant_config_h2s, tech_config={"model_inputs": tech_config_h2s}
    )
    control_comp = DemandOpenLoopStorageController(
        plant_config=plant_config_h2s, tech_config={"model_inputs": tech_config_h2s}
    )

    return ivc_comp, perf_comp, control_comp


def make_battery_openloop_group(plant_config_bat):
    tech_config_bat = {
        "shared_parameters": {
            "demand_profile": 5.0,
            "max_capacity": 40,
            "max_charge_rate": 10,
            "min_soc_fraction": 0.1,
            "max_soc_fraction": 1.0,
            "init_soc_fraction": 1.0,
        },
        "performance_parameters": {"chemistry": "LFPGraphite"},
        "control_parameters": {
            "commodity": "electricity",
            "commodity_rate_units": "kW",
            "charge_equals_discharge": True,
            "charge_efficiency": 1.0,
            "discharge_efficiency": 1.0,
        },
    }

    elec_in = np.concat([np.zeros(3), np.cumsum(np.ones(15)), np.full(6, 4.0)])
    commodity_in = np.tile(elec_in, 365)
    ivc_comp = om.IndepVarComp(name="electricity_in", val=commodity_in, units="kW")
    perf_comp = PySAMBatteryPerformanceModel(
        plant_config=plant_config_bat, tech_config={"model_inputs": tech_config_bat}
    )
    control_comp = DemandOpenLoopStorageController(
        plant_config=plant_config_bat, tech_config={"model_inputs": tech_config_bat}
    )

    return ivc_comp, perf_comp, control_comp


@pytest.mark.regression
@pytest.mark.parametrize("pyo_controllers", ["none"])
def test_h2s_openloop(subtests, plant_config):
    # these are the test values for the hydrogen storage that are used in
    # test_both_openloop_controllers and test_battery_pyomo_h2s_openloop
    h2s_expected_discharge = np.concat([np.zeros(18), np.ones(6)])
    h2s_expected_charge = np.concat([np.zeros(8), np.arange(-1, -9, -1), np.zeros(8)])
    prob = om.Problem()

    # make h2 storage group
    h2s_group = prob.model.add_subsystem("h2_storage", om.Group())
    h2s_ivc_comp, h2s_perf_comp, h2s_control_comp = make_h2_storage_openloop_group(plant_config)
    h2s_group.add_subsystem("IVC1", h2s_ivc_comp, promotes=["*"])
    h2s_group.add_subsystem("control", h2s_control_comp, promotes=["*"])
    h2s_group.add_subsystem("perf", h2s_perf_comp, promotes=["*"])

    prob.setup()
    prob.run_model()

    with subtests.test("H2 Storage: Expected charge"):
        np.testing.assert_allclose(
            prob.get_val("h2_storage.storage_hydrogen_charge", units="kg/h")[:24],
            h2s_expected_charge,
            rtol=1e-6,
        )
    with subtests.test("H2 Storage: Expected discharge"):
        np.testing.assert_allclose(
            prob.get_val("h2_storage.storage_hydrogen_discharge", units="kg/h")[:24],
            h2s_expected_discharge,
            rtol=1e-6,
        )


@pytest.mark.regression
@pytest.mark.parametrize("pyo_controllers", ["none"])
def test_battery_openloop(subtests, plant_config):
    # these are the test values for the battery that are used in
    # test_both_openloop_controllers and test_h2s_pyomo_batery_openloop
    bat_expected_discharge = np.concat(
        [
            np.array(
                [4.99483673, 4.99483511, 4.99403933, 3.99456736, 2.99545121, 1.99671242, 0.99828405]
            ),
            np.zeros(11),
            np.array([0.99907629, 0.9991349, 0.99911777, 0.99909762, 0.99907648, 0.99905434]),
        ]
    )
    bat_expected_charge = np.concat(
        [
            np.zeros(8),
            np.array(
                [
                    -0.99835716,
                    -1.9969656,
                    -2.99592019,
                    -3.9952197,
                    -4.99480988,
                    -5.99461958,
                    -3.70438813,
                ]
            ),
            np.zeros(9),
        ]
    )

    prob = om.Problem()

    # make battery group
    bat_group = prob.model.add_subsystem("battery", om.Group())
    bat_ivc_comp, bat_perf_comp, bat_control_comp = make_battery_openloop_group(plant_config)
    bat_group.add_subsystem("IVC2", bat_ivc_comp, promotes=["*"])
    bat_group.add_subsystem("control", bat_control_comp, promotes=["*"])
    bat_group.add_subsystem("perf", bat_perf_comp, promotes=["*"])

    prob.setup()
    prob.run_model()

    with subtests.test("Battery: Expected charge"):
        np.testing.assert_allclose(
            prob.get_val("battery.storage_electricity_charge", units="kW")[:24],
            bat_expected_charge,
            rtol=1e-6,
        )
    with subtests.test("Battery: Expected discharge"):
        np.testing.assert_allclose(
            prob.get_val("battery.storage_electricity_discharge", units="kW")[:24],
            bat_expected_discharge,
            rtol=1e-6,
        )


@pytest.mark.regression
@pytest.mark.parametrize("pyo_controllers", ["bat"])
def test_battery_pyo(subtests, plant_config):
    # these are the test values for the battery that are used in
    # test_both_pyomo_controllers and test_battery_pyomo_h2s_openloop
    bat_expected_charge = np.concat(
        [
            np.zeros(12),
            np.array(
                [
                    -3988.62235554,
                    -3989.2357847,
                    -3989.76832626,
                    -3990.26170521,
                    -3990.71676106,
                    -3991.13573086,
                    -3991.52143699,
                    -3991.87684905,
                    -3992.20485715,
                    -3992.50815603,
                    -3992.78920148,
                    -3993.05020268,
                ]
            ),
        ]
    )
    bat_expected_discharge = np.concat(
        [
            np.array(
                [
                    5999.99995059,
                    5990.56676743,
                    5990.138959,
                    5989.64831176,
                    5989.08548217,
                    5988.44193888,
                    5987.70577962,
                    5986.86071125,
                    5985.88493352,
                    5984.7496388,
                    5983.41717191,
                    5981.839478,
                ]
            ),
            np.zeros(12),
        ]
    )
    prob = om.Problem()

    # make battery group
    bat_group = prob.model.add_subsystem("battery", om.Group())
    bat_rule_comp, bat_perf_comp, bat_control_comp, electricity_in = make_battery_pyo_group(
        plant_config
    )
    bat_group.add_subsystem("IVC2", electricity_in, promotes=["*"])
    bat_group.add_subsystem("rule", bat_rule_comp, promotes=["*"])
    bat_group.add_subsystem("control", bat_control_comp, promotes=["*"])
    bat_group.add_subsystem("perf", bat_perf_comp, promotes=["*"])

    prob.setup()
    prob.run_model()

    with subtests.test("Battery: Expected charge"):
        np.testing.assert_allclose(
            prob.get_val("battery.storage_electricity_charge", units="kW")[:24],
            bat_expected_charge,
            rtol=1e-6,
        )
    with subtests.test("Battery: Expected discharge"):
        np.testing.assert_allclose(
            prob.get_val("battery.storage_electricity_discharge", units="kW")[:24],
            bat_expected_discharge,
            rtol=1e-6,
        )


@pytest.mark.regression
@pytest.mark.parametrize("pyo_controllers", ["h2s"])
def test_h2s_pyo(subtests, plant_config):
    # these are the test values for the hydrogen storage that are used in
    # test_both_pyomo_controllers and test_h2s_pyomo_battery_openloop

    h2s_expected_discharge = np.concat(
        [np.zeros(8), np.ones(6), np.full(3, 5.0), np.array([4, 3, 2])]
    )
    h2s_expected_charge = np.concat([np.zeros(8), np.arange(-1, -9, -1), np.zeros(8)])
    prob = om.Problem()

    # make hydrogen storage group
    h2s_group = prob.model.add_subsystem("h2_storage", om.Group())
    h2s_rule_comp, h2s_perf_comp, h2s_control_comp, hydrogen_in = make_h2_storage_pyo_group(
        plant_config
    )
    h2s_group.add_subsystem("IVC1", hydrogen_in, promotes=["*"])
    h2s_group.add_subsystem("rule", h2s_rule_comp, promotes=["*"])
    h2s_group.add_subsystem("control", h2s_control_comp, promotes=["*"])
    h2s_group.add_subsystem("perf", h2s_perf_comp, promotes=["*"])
    prob.setup()
    prob.run_model()

    with subtests.test("H2 Storage: Expected charge"):
        np.testing.assert_allclose(
            prob.get_val("h2_storage.storage_hydrogen_charge", units="kg/h")[:24],
            h2s_expected_charge,
            rtol=1e-6,
        )
    with subtests.test("H2 Storage: Expected discharge"):
        np.testing.assert_allclose(
            prob.get_val("h2_storage.storage_hydrogen_discharge", units="kg/h")[10:30],
            h2s_expected_discharge,
            rtol=1e-6,
        )


@pytest.mark.regression
@pytest.mark.parametrize("pyo_controllers", ["both"])
def test_both_pyomo_controllers(subtests, plant_config):
    bat_expected_charge = np.concat(
        [
            np.zeros(12),
            np.array(
                [
                    -3988.62235554,
                    -3989.2357847,
                    -3989.76832626,
                    -3990.26170521,
                    -3990.71676106,
                    -3991.13573086,
                    -3991.52143699,
                    -3991.87684905,
                    -3992.20485715,
                    -3992.50815603,
                    -3992.78920148,
                    -3993.05020268,
                ]
            ),
        ]
    )
    bat_expected_discharge = np.concat(
        [
            np.array(
                [
                    5999.99995059,
                    5990.56676743,
                    5990.138959,
                    5989.64831176,
                    5989.08548217,
                    5988.44193888,
                    5987.70577962,
                    5986.86071125,
                    5985.88493352,
                    5984.7496388,
                    5983.41717191,
                    5981.839478,
                ]
            ),
            np.zeros(12),
        ]
    )

    h2s_expected_discharge = np.concat(
        [np.zeros(8), np.ones(6), np.full(3, 5.0), np.array([4, 3, 2])]
    )
    h2s_expected_charge = np.concat([np.zeros(8), np.arange(-1, -9, -1), np.zeros(8)])
    prob = om.Problem()

    # make hydrogen storage group
    h2s_group = prob.model.add_subsystem("h2_storage", om.Group())
    h2s_rule_comp, h2s_perf_comp, h2s_control_comp, hydrogen_in = make_h2_storage_pyo_group(
        plant_config
    )
    h2s_group.add_subsystem("IVC1", hydrogen_in, promotes=["*"])
    h2s_group.add_subsystem("rule", h2s_rule_comp, promotes=["*"])
    h2s_group.add_subsystem("control", h2s_control_comp, promotes=["*"])
    h2s_group.add_subsystem("perf", h2s_perf_comp, promotes=["*"])

    # make battery group
    bat_group = prob.model.add_subsystem("battery", om.Group())
    bat_rule_comp, bat_perf_comp, bat_control_comp, electricity_in = make_battery_pyo_group(
        plant_config
    )
    bat_group.add_subsystem("IVC2", electricity_in, promotes=["*"])
    bat_group.add_subsystem("rule", bat_rule_comp, promotes=["*"])
    bat_group.add_subsystem("control", bat_control_comp, promotes=["*"])
    bat_group.add_subsystem("perf", bat_perf_comp, promotes=["*"])

    prob.setup()
    prob.run_model()

    with subtests.test("Battery: Expected charge"):
        np.testing.assert_allclose(
            prob.get_val("battery.storage_electricity_charge", units="kW")[:24],
            bat_expected_charge,
            rtol=1e-6,
        )
    with subtests.test("Battery: Expected discharge"):
        np.testing.assert_allclose(
            prob.get_val("battery.storage_electricity_discharge", units="kW")[:24],
            bat_expected_discharge,
            rtol=1e-6,
        )

    with subtests.test("H2 Storage: Expected charge"):
        np.testing.assert_allclose(
            prob.get_val("h2_storage.storage_hydrogen_charge", units="kg/h")[:24],
            h2s_expected_charge,
            rtol=1e-6,
        )
    with subtests.test("H2 Storage: Expected discharge"):
        np.testing.assert_allclose(
            prob.get_val("h2_storage.storage_hydrogen_discharge", units="kg/h")[10:30],
            h2s_expected_discharge,
            rtol=1e-6,
        )


@pytest.mark.regression
@pytest.mark.parametrize("pyo_controllers", ["none"])
def test_both_openloop_controllers(subtests, plant_config):
    h2s_expected_discharge = np.concat([np.zeros(18), np.ones(6)])
    h2s_expected_charge = np.concat([np.zeros(8), np.arange(-1, -9, -1), np.zeros(8)])
    bat_expected_discharge = np.concat(
        [
            np.array(
                [4.99483673, 4.99483511, 4.99403933, 3.99456736, 2.99545121, 1.99671242, 0.99828405]
            ),
            np.zeros(11),
            np.array([0.99907629, 0.9991349, 0.99911777, 0.99909762, 0.99907648, 0.99905434]),
        ]
    )
    bat_expected_charge = np.concat(
        [
            np.zeros(8),
            np.array(
                [
                    -0.99835716,
                    -1.9969656,
                    -2.99592019,
                    -3.9952197,
                    -4.99480988,
                    -5.99461958,
                    -3.70438813,
                ]
            ),
            np.zeros(9),
        ]
    )

    prob = om.Problem()

    # make h2 storage group
    h2s_group = prob.model.add_subsystem("h2_storage", om.Group())
    h2s_ivc_comp, h2s_perf_comp, h2s_control_comp = make_h2_storage_openloop_group(plant_config)
    h2s_group.add_subsystem("IVC1", h2s_ivc_comp, promotes=["*"])
    h2s_group.add_subsystem("control", h2s_control_comp, promotes=["*"])
    h2s_group.add_subsystem("perf", h2s_perf_comp, promotes=["*"])

    # make battery group
    bat_group = prob.model.add_subsystem("battery", om.Group())
    bat_ivc_comp, bat_perf_comp, bat_control_comp = make_battery_openloop_group(plant_config)
    bat_group.add_subsystem("IVC2", bat_ivc_comp, promotes=["*"])
    bat_group.add_subsystem("control", bat_control_comp, promotes=["*"])
    bat_group.add_subsystem("perf", bat_perf_comp, promotes=["*"])

    prob.setup()
    prob.run_model()

    with subtests.test("Battery: Expected charge"):
        np.testing.assert_allclose(
            prob.get_val("battery.storage_electricity_charge", units="kW")[:24],
            bat_expected_charge,
            rtol=1e-6,
        )
    with subtests.test("Battery: Expected discharge"):
        np.testing.assert_allclose(
            prob.get_val("battery.storage_electricity_discharge", units="kW")[:24],
            bat_expected_discharge,
            rtol=1e-6,
        )

    with subtests.test("H2 Storage: Expected charge"):
        np.testing.assert_allclose(
            prob.get_val("h2_storage.storage_hydrogen_charge", units="kg/h")[:24],
            h2s_expected_charge,
            rtol=1e-6,
        )
    with subtests.test("H2 Storage: Expected discharge"):
        np.testing.assert_allclose(
            prob.get_val("h2_storage.storage_hydrogen_discharge", units="kg/h")[:24],
            h2s_expected_discharge,
            rtol=1e-6,
        )


@pytest.mark.regression
@pytest.mark.parametrize("pyo_controllers", ["h2s"])
def test_h2s_pyomo_battery_openloop(subtests, plant_config):
    bat_expected_discharge = np.concat(
        [
            np.array(
                [4.99483673, 4.99483511, 4.99403933, 3.99456736, 2.99545121, 1.99671242, 0.99828405]
            ),
            np.zeros(11),
            np.array([0.99907629, 0.9991349, 0.99911777, 0.99909762, 0.99907648, 0.99905434]),
        ]
    )
    bat_expected_charge = np.concat(
        [
            np.zeros(8),
            np.array(
                [
                    -0.99835716,
                    -1.9969656,
                    -2.99592019,
                    -3.9952197,
                    -4.99480988,
                    -5.99461958,
                    -3.70438813,
                ]
            ),
            np.zeros(9),
        ]
    )
    h2s_expected_discharge = np.concat(
        [np.zeros(8), np.ones(6), np.full(3, 5.0), np.array([4, 3, 2])]
    )
    h2s_expected_charge = np.concat([np.zeros(8), np.arange(-1, -9, -1), np.zeros(8)])
    prob = om.Problem()

    # make hydrogen storage group
    h2s_group = prob.model.add_subsystem("h2_storage", om.Group())
    h2s_rule_comp, h2s_perf_comp, h2s_control_comp, hydrogen_in = make_h2_storage_pyo_group(
        plant_config
    )
    h2s_group.add_subsystem("IVC1", hydrogen_in, promotes=["*"])
    h2s_group.add_subsystem("rule", h2s_rule_comp, promotes=["*"])
    h2s_group.add_subsystem("control", h2s_control_comp, promotes=["*"])
    h2s_group.add_subsystem("perf", h2s_perf_comp, promotes=["*"])

    # make battery group
    bat_group = prob.model.add_subsystem("battery", om.Group())
    bat_ivc_comp, bat_perf_comp, bat_control_comp = make_battery_openloop_group(plant_config)
    bat_group.add_subsystem("IVC2", bat_ivc_comp, promotes=["*"])
    bat_group.add_subsystem("control", bat_control_comp, promotes=["*"])
    bat_group.add_subsystem("perf", bat_perf_comp, promotes=["*"])

    prob.setup()
    prob.run_model()

    with subtests.test("Battery: Expected charge"):
        np.testing.assert_allclose(
            prob.get_val("battery.storage_electricity_charge", units="kW")[:24],
            bat_expected_charge,
            rtol=1e-6,
        )
    with subtests.test("Battery: Expected discharge"):
        np.testing.assert_allclose(
            prob.get_val("battery.storage_electricity_discharge", units="kW")[:24],
            bat_expected_discharge,
            rtol=1e-6,
        )

    with subtests.test("H2 Storage: Expected charge"):
        np.testing.assert_allclose(
            prob.get_val("h2_storage.storage_hydrogen_charge", units="kg/h")[:24],
            h2s_expected_charge,
            rtol=1e-6,
        )
    with subtests.test("H2 Storage: Expected discharge"):
        np.testing.assert_allclose(
            prob.get_val("h2_storage.storage_hydrogen_discharge", units="kg/h")[10:30],
            h2s_expected_discharge,
            rtol=1e-6,
        )


@pytest.mark.regression
@pytest.mark.parametrize("pyo_controllers", ["bat"])
def test_battery_pyomo_h2s_openloop(subtests, plant_config):
    h2s_expected_discharge = np.concat([np.zeros(18), np.ones(6)])
    h2s_expected_charge = np.concat([np.zeros(8), np.arange(-1, -9, -1), np.zeros(8)])
    bat_expected_charge = np.concat(
        [
            np.zeros(12),
            np.array(
                [
                    -3988.62235554,
                    -3989.2357847,
                    -3989.76832626,
                    -3990.26170521,
                    -3990.71676106,
                    -3991.13573086,
                    -3991.52143699,
                    -3991.87684905,
                    -3992.20485715,
                    -3992.50815603,
                    -3992.78920148,
                    -3993.05020268,
                ]
            ),
        ]
    )
    bat_expected_discharge = np.concat(
        [
            np.array(
                [
                    5999.99995059,
                    5990.56676743,
                    5990.138959,
                    5989.64831176,
                    5989.08548217,
                    5988.44193888,
                    5987.70577962,
                    5986.86071125,
                    5985.88493352,
                    5984.7496388,
                    5983.41717191,
                    5981.839478,
                ]
            ),
            np.zeros(12),
        ]
    )

    prob = om.Problem()

    # make h2 storage group
    h2s_group = prob.model.add_subsystem("h2_storage", om.Group())
    h2s_ivc_comp, h2s_perf_comp, h2s_control_comp = make_h2_storage_openloop_group(plant_config)
    h2s_group.add_subsystem("IVC1", h2s_ivc_comp, promotes=["*"])
    h2s_group.add_subsystem("control", h2s_control_comp, promotes=["*"])
    h2s_group.add_subsystem("perf", h2s_perf_comp, promotes=["*"])

    # make battery group
    bat_rule_comp, bat_perf_comp, bat_control_comp, electricity_in = make_battery_pyo_group(
        plant_config
    )
    bat_group = prob.model.add_subsystem("battery", om.Group())
    bat_group.add_subsystem("IVC2", electricity_in, promotes=["*"])
    bat_group.add_subsystem("rule", bat_rule_comp, promotes=["*"])
    bat_group.add_subsystem("control", bat_control_comp, promotes=["*"])
    bat_group.add_subsystem("perf", bat_perf_comp, promotes=["*"])

    prob.setup()
    prob.run_model()

    with subtests.test("Battery: Expected charge"):
        np.testing.assert_allclose(
            prob.get_val("battery.storage_electricity_charge", units="kW")[:24],
            bat_expected_charge,
            rtol=1e-6,
        )
    with subtests.test("Battery: Expected discharge"):
        np.testing.assert_allclose(
            prob.get_val("battery.storage_electricity_discharge", units="kW")[:24],
            bat_expected_discharge,
            rtol=1e-6,
        )

    with subtests.test("H2 Storage: Expected charge"):
        np.testing.assert_allclose(
            prob.get_val("h2_storage.storage_hydrogen_charge", units="kg/h")[:24],
            h2s_expected_charge,
            rtol=1e-6,
        )
    with subtests.test("H2 Storage: Expected discharge"):
        np.testing.assert_allclose(
            prob.get_val("h2_storage.storage_hydrogen_discharge", units="kg/h")[:24],
            h2s_expected_discharge,
            rtol=1e-6,
        )
