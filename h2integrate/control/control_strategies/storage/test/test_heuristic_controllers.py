import numpy as np
import pytest
import openmdao.api as om
from pytest import fixture

from h2integrate.storage.battery.pysam_battery import PySAMBatteryPerformanceModel
from h2integrate.storage.storage_performance_model import StoragePerformanceModel
from h2integrate.storage.simple_storage_auto_sizing import StorageAutoSizingModel
from h2integrate.control.control_rules.storage.pyomo_storage_rule_baseclass import (
    PyomoRuleStorageBaseclass,
)
from h2integrate.control.control_strategies.storage.heuristic_pyomo_controller import (
    HeuristicLoadFollowingStorageController,
)


@fixture
def plant_config_battery():
    plant_config_dict = {
        "plant": {
            "plant_life": 30,
            "simulation": {
                "dt": 3600,
                "n_timesteps": 8760,
            },
        },
        "tech_to_dispatch_connections": [
            ["battery", "battery"],
        ],
    }
    return plant_config_dict


@fixture
def tech_config_battery():
    tech_config_dict = {
        "name": "technology_config",
        "description": "...",
        "technologies": {
            "battery": {
                "dispatch_rule_set": {"model": "PyomoRuleStorageBaseclass"},
                "control_strategy": {"model": "HeuristicLoadFollowingStorageController"},
                "performance_model": {"model": "PySAMBatteryPerformanceModel"},
                "model_inputs": {
                    "shared_parameters": {
                        "max_charge_rate": 50000,
                        "max_capacity": 200000,
                        "n_control_window_hours": 24,
                        "n_horizon_window": 48,
                        "init_soc_fraction": 0.5,
                        "max_soc_fraction": 0.9,
                        "min_soc_fraction": 0.1,
                    },
                    "performance_parameters": {
                        "chemistry": "LFPGraphite",
                        "control_variable": "input_power",
                        "demand_profile": 0.0,
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
        },
    }
    return tech_config_dict


@fixture
def plant_config_h2_storage():
    plant_config = {
        "plant": {
            "plant_life": 30,
            "simulation": {
                "dt": 3600,
                "n_timesteps": 8760,
            },
        },
        "tech_to_dispatch_connections": [
            ["combiner", "h2_storage"],
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
                "control_strategy": {"model": "HeuristicLoadFollowingStorageController"},
                "performance_model": {"model": "StoragePerformanceModel"},
                "model_inputs": {
                    "shared_parameters": {
                        "max_charge_rate": 10.0,
                        "max_capacity": 40.0,
                        "n_control_window_hours": 24,
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
                        "demand_profile": 0.0,
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


@fixture
def tech_config_autosizing():
    tech_config = {
        "technologies": {
            "h2_storage": {
                "dispatch_rule_set": {"model": "PyomoRuleStorageBaseclass"},
                "control_strategy": {"model": "HeuristicLoadFollowingStorageController"},
                "performance_model": {"model": "StorageAutoSizingModel"},
                "model_inputs": {
                    "shared_parameters": {
                        "max_soc_fraction": 1.0,
                        "min_soc_fraction": 0.0,
                        "commodity": "hydrogen",
                        "commodity_rate_units": "kg/h",
                        "charge_efficiency": 1.0,
                        "discharge_efficiency": 1.0,
                        "max_capacity": 5.0,  # shared between control and dispatch rules
                    },
                    "performance_parameters": {
                        "charge_equals_discharge": True,
                        "commodity_amount_units": "kg",
                        "demand_profile": 0.0,
                        "set_demand_as_avg_commodity_in": False,
                    },
                    "control_parameters": {
                        "n_control_window_hours": 24,
                        "tech_name": "h2_storage",
                        "system_commodity_interface_limit": 10.0,
                        "init_soc_fraction": 0.1,
                    },
                },
            }
        },
    }
    return tech_config


def calculate_combined_outputs(storage_charge_discharge, commodity_in, commodity_demand):
    combined_commodity_in = commodity_in + storage_charge_discharge
    remaining_demand = commodity_demand - combined_commodity_in
    unmet_demand = np.where(remaining_demand > 0, remaining_demand, 0)
    unused_commodity = np.where(remaining_demand < 0, -1 * remaining_demand, 0)
    combined_out_for_demand = combined_commodity_in - unused_commodity

    return unmet_demand, unused_commodity, combined_out_for_demand


@pytest.mark.regression
def test_heuristic_load_following_battery_dispatch(
    plant_config_battery, tech_config_battery, subtests
):
    # Fabricate some oscillating power generation data: 0 kW for the first 12 hours, 10000 kW for
    # the second twelve hours, and repeat that daily cycle over a year.
    n_look_ahead_half = int(24 / 2)

    electricity_in = np.concatenate(
        (np.ones(n_look_ahead_half) * 0, np.ones(n_look_ahead_half) * 10000)
    )
    electricity_in = np.tile(electricity_in, 365)

    demand_in = np.ones(8760) * 6000.0

    # Setup the OpenMDAO problem and add subsystems
    prob = om.Problem()

    prob.model.add_subsystem(
        "PyomoRuleStorageBaseclass",
        PyomoRuleStorageBaseclass(
            plant_config=plant_config_battery,
            tech_config=tech_config_battery["technologies"]["battery"],
        ),
        promotes=["*"],
    )

    prob.model.add_subsystem(
        "battery_heuristic_load_following_controller",
        HeuristicLoadFollowingStorageController(
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

    # Test the case where the charging/discharging cycle remains within the max and min SOC limits
    # Check the expected outputs to actual outputs
    expected_electricity_out = [
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
        6000.0,
        6000.0,
        6000.0,
        6000.0,
        6000.0,
        6000.0,
        6000.0,
        6000.0,
        6000.0,
        6000.0,
        6000.0,
        6000.0,
    ]

    expected_battery_electricity = [
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

    expected_SOC = [
        49.39724571,
        46.54631833,
        43.69133882,
        40.83119769,
        37.96394628,
        35.08762294,
        32.20015974,
        29.29919751,
        26.38184809,
        23.44436442,
        20.48162855,
        17.48627159,
        19.47067094,
        21.44466462,
        23.40741401,
        25.36052712,
        27.30530573,
        29.24281439,
        31.17393198,
        33.09939078,
        35.01980641,
        36.93570091,
        38.84752069,
        40.75565055,
    ]

    expected_unmet_demand_out = np.array(
        [
            4.93562475e-05,
            9.43323257e00,
            9.86104099e00,
            1.03516883e01,
            1.09145178e01,
            1.15580611e01,
            1.22942204e01,
            1.31392889e01,
            1.41150664e01,
            1.52503612e01,
            1.65828282e01,
            1.81605218e01,
            0.00000000e00,
            0.00000000e00,
            0.00000000e00,
            0.00000000e00,
            0.00000000e00,
            0.00000000e00,
            0.00000000e00,
            0.00000000e00,
            0.00000000e00,
            0.00000000e00,
            0.00000000e00,
            0.00000000e00,
        ]
    )

    expected_unused_commodity_out = np.array(
        [
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
            0.0,
            11.37764445,
            10.76421514,
            10.23167373,
            9.73829458,
            9.28323883,
            8.86426912,
            8.47856327,
            8.12315078,
            7.79514283,
            7.49184426,
            7.21079852,
            6.94979705,
        ]
    )

    unmet_demand, unused_commodity, combined_out_for_demand = calculate_combined_outputs(
        prob.get_val("battery.electricity_out", units="kW"), electricity_in, demand_in
    )

    with subtests.test("Check electricity_out"):
        assert pytest.approx(expected_electricity_out) == combined_out_for_demand[0:24]

    with subtests.test("Check battery_electricity"):
        assert (
            pytest.approx(expected_battery_electricity)
            == prob.get_val("battery.electricity_out", units="kW")[0:24]
        )

    with subtests.test("Check SOC"):
        assert pytest.approx(expected_SOC) == prob.get_val("battery.SOC", units="percent")[0:24]

    with subtests.test("Check unmet_demand"):
        assert pytest.approx(expected_unmet_demand_out, abs=1e-4) == unmet_demand[0:24]

    with subtests.test("Check unused_electricity_out"):
        assert pytest.approx(expected_unused_commodity_out) == unused_commodity[0:24]

    # Test the case where the battery is discharged to its lower SOC limit
    electricity_in = np.zeros(8760)
    demand_in = np.ones(8760) * 30000

    # Setup the system and required values
    prob.setup()

    prob.set_val("battery.electricity_in", electricity_in)
    prob.set_val("battery.electricity_demand", demand_in)

    # Run the model
    prob.run_model()

    expected_electricity_out = np.array(
        [3.00000000e04, 2.99305601e04, 2.48145097e04, 4.97901621e00, 3.04065390e01]
    )
    expected_battery_electricity = expected_electricity_out
    expected_SOC = np.array([37.69010284, 22.89921133, 10.00249593, 10.01524461, 10.03556385])
    expected_unmet_demand_out = np.array(
        [
            9.43691703e-09,
            6.94398578e01,
            5.18549025244965e03,
            2.999502098378662e04,
            2.9969593461021406e04,
        ]
    )
    expected_unused_commodity_out = np.zeros(5)

    unmet_demand, unused_commodity, combined_out_for_demand = calculate_combined_outputs(
        prob.get_val("battery.electricity_out", units="kW"), electricity_in, demand_in
    )

    with subtests.test("Check electricity_out for min SOC"):
        assert pytest.approx(expected_electricity_out) == combined_out_for_demand[:5]

    with subtests.test("Check battery_electricity for min SOC"):
        assert (
            pytest.approx(expected_battery_electricity)
            == prob.get_val("battery.electricity_out", units="kW")[:5]
        )

    with subtests.test("Check SOC for min SOC"):
        assert pytest.approx(expected_SOC) == prob.get_val("battery.SOC", units="percent")[:5]

    with subtests.test("Check unmet_demand for min SOC"):
        assert pytest.approx(expected_unmet_demand_out, abs=1e-6) == unmet_demand[:5]

    with subtests.test("Check unused_commodity_out for min SOC"):
        assert pytest.approx(expected_unused_commodity_out) == unused_commodity[:5]

    # Test the case where the battery is charged to its upper SOC limit
    electricity_in = np.ones(8760) * 30000.0
    demand_in = np.zeros(8760)

    # Setup the system and required values
    prob.setup()
    prob.set_val("battery.electricity_in", electricity_in)
    prob.set_val("battery.electricity_demand", demand_in)

    # Run the model
    prob.run_model()

    expected_electricity_out = [-0.008477085, 0.0, 0.0, 0.0, 0.0]

    # TODO reevaluate the output here
    expected_battery_electricity = np.array(
        [-30000.00847709, -29973.58679719, -21109.22734423, 0.0, 0.0]
    )

    # expected_SOC = [66.00200558, 79.43840635, 90.0, 90.0, 90.0]
    expected_SOC = np.array([66.00200558, 79.43840635, 89.02326413, 89.02326413, 89.02326413])
    expected_unmet_demand_out = np.array([0.00847709, 0.0, 0.0, 0.0, 0.0])
    expected_unused_commodity_out = np.array(
        [0.00000000e00, 2.64132028e01, 8.89077266e03, 3.04088135e04, 3.00564087e04]
    )
    # I think this is the right expected_electricity_out since the battery won't
    # be discharging in this instance
    # expected_electricity_out = [0.0, 0.0, 0.0, 0.0, 0.0]
    # # expected_electricity_out = [0.0, 0.0, 6150.14483911, 30000.0, 30000.0]
    # expected_battery_electricity = [-30000.00847705, -29973.58679681,
    # -23310.54620182, 0.0, 0.0]
    # expected_SOC = [66.00200558, 79.43840635, 90.0, 90.0, 90.0]
    # expected_unmet_demand_out = np.zeros(5)
    # expected_unused_commodity_out = [0.0, 0.0, 6150.14483911, 30000.0, 30000.0]

    abs_tol = 1e-6
    rel_tol = 1e-1

    unmet_demand, unused_commodity, combined_out_for_demand = calculate_combined_outputs(
        prob.get_val("battery.electricity_out", units="kW"), electricity_in, demand_in
    )

    with subtests.test("Check electricity_out for max SOC"):
        assert (
            pytest.approx(expected_electricity_out, abs=abs_tol, rel=rel_tol)
            == combined_out_for_demand[:5]
        )

    with subtests.test("Check battery_electricity for max SOC"):
        assert (
            pytest.approx(expected_battery_electricity, abs=abs_tol, rel=rel_tol)
            == prob.get_val("battery.electricity_out", units="kW")[:5]
        )

    with subtests.test("Check SOC for max SOC"):
        assert (
            pytest.approx(expected_SOC, abs=abs_tol)
            == prob.get_val("battery.SOC", units="percent")[:5]
        )

    with subtests.test("Check unmet_demand for max SOC"):
        assert pytest.approx(expected_unmet_demand_out, abs=abs_tol) == unmet_demand[:5]

    with subtests.test("Check unused_commodity_out for max SOC"):
        assert (
            pytest.approx(expected_unused_commodity_out, abs=abs_tol, rel=rel_tol)
            == unused_commodity[:5]
        )


@pytest.mark.regression
def test_heuristic_load_following_battery_dispatch_change_capacities(
    plant_config_battery, tech_config_battery, subtests
):
    # update the battery capacity to be very small in the config

    tech_config_battery["technologies"]["battery"]["model_inputs"]["shared_parameters"].update(
        {"max_charge_rate": 1000}
    )
    tech_config_battery["technologies"]["battery"]["model_inputs"]["shared_parameters"].update(
        {"max_capacity": 1000}
    )

    # Fabricate some oscillating power generation data: 0 kW for the first 12 hours, 10000 kW for
    # the second twelve hours, and repeat that daily cycle over a year.

    n_look_ahead_half = int(24 / 2)

    electricity_in = np.concatenate(
        (np.ones(n_look_ahead_half) * 0, np.ones(n_look_ahead_half) * 10000)
    )
    electricity_in = np.tile(electricity_in, 365)

    demand_in = np.ones(8760) * 6000.0

    # Setup the OpenMDAO problem and add subsystems
    prob = om.Problem()

    prob.model.add_subsystem(
        name="IVC1",
        subsys=om.IndepVarComp(name="max_charge_rate", val=1000, units="kW"),
        promotes=["*"],
    )

    prob.model.add_subsystem(
        name="IVC2",
        subsys=om.IndepVarComp(name="storage_capacity", val=1000, units="kW*h"),
        promotes=["*"],
    )

    prob.model.add_subsystem(
        "PyomoRuleStorageBaseclass",
        PyomoRuleStorageBaseclass(
            plant_config=plant_config_battery,
            tech_config=tech_config_battery["technologies"]["battery"],
        ),
        promotes=["*"],
    )

    prob.model.add_subsystem(
        "battery_heuristic_load_following_controller",
        HeuristicLoadFollowingStorageController(
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

    prob.set_val("IVC1.max_charge_rate", 50000, units="kW")
    prob.set_val("IVC2.storage_capacity", 200000, units="kW*h")

    prob.set_val("battery.electricity_in", electricity_in)
    prob.set_val("battery.electricity_demand", demand_in)

    # Run the model
    prob.run_model()

    # Test the case where the charging/discharging cycle remains within the max and min SOC limits
    # Check the expected outputs to actual outputs
    expected_electricity_out = [
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
        6000.0,
        6000.0,
        6000.0,
        6000.0,
        6000.0,
        6000.0,
        6000.0,
        6000.0,
        6000.0,
        6000.0,
        6000.0,
        6000.0,
    ]

    expected_battery_electricity = [
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

    expected_SOC = [
        49.39724571,
        46.54631833,
        43.69133882,
        40.83119769,
        37.96394628,
        35.08762294,
        32.20015974,
        29.29919751,
        26.38184809,
        23.44436442,
        20.48162855,
        17.48627159,
        19.47067094,
        21.44466462,
        23.40741401,
        25.36052712,
        27.30530573,
        29.24281439,
        31.17393198,
        33.09939078,
        35.01980641,
        36.93570091,
        38.84752069,
        40.75565055,
    ]

    expected_unmet_demand_out = np.array(
        [
            4.93562475e-05,
            9.43323257e00,
            9.86104099e00,
            1.03516883e01,
            1.09145178e01,
            1.15580611e01,
            1.22942204e01,
            1.31392889e01,
            1.41150664e01,
            1.52503612e01,
            1.65828282e01,
            1.81605218e01,
            0.00000000e00,
            0.00000000e00,
            0.00000000e00,
            0.00000000e00,
            0.00000000e00,
            0.00000000e00,
            0.00000000e00,
            0.00000000e00,
            0.00000000e00,
            0.00000000e00,
            0.00000000e00,
            0.00000000e00,
        ]
    )

    expected_unused_commodity_out = np.array(
        [
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
            0.0,
            11.37764445,
            10.76421514,
            10.23167373,
            9.73829458,
            9.28323883,
            8.86426912,
            8.47856327,
            8.12315078,
            7.79514283,
            7.49184426,
            7.21079852,
            6.94979705,
        ]
    )

    unmet_demand, unused_commodity, combined_out_for_demand = calculate_combined_outputs(
        prob.get_val("battery.electricity_out", units="kW"), electricity_in, demand_in
    )

    with subtests.test("Battery output capacity"):
        assert (
            pytest.approx(
                prob.get_val("battery.rated_electricity_production", units="MW"), rel=1e-6
            )
            == 50.0
        )

    with subtests.test("Check electricity_out"):
        assert (
            pytest.approx(expected_electricity_out)  # TODO: update
            == combined_out_for_demand[0:24]
        )

    with subtests.test("Check battery_electricity"):
        assert (
            pytest.approx(expected_battery_electricity)
            == prob.get_val("battery.electricity_out", units="kW")[0:24]
        )

    with subtests.test("Check SOC"):
        assert pytest.approx(expected_SOC) == prob.get_val("battery.SOC", units="percent")[0:24]

    with subtests.test("Check unmet_demand"):
        assert pytest.approx(expected_unmet_demand_out, abs=1e-4) == unmet_demand[0:24]

    with subtests.test("Check unused_electricity_out"):
        assert pytest.approx(expected_unused_commodity_out) == unused_commodity[0:24]


@pytest.mark.regression
def test_heuristic_load_following_dispatch_with_generic_storage(
    plant_config_h2_storage, tech_config_generic, subtests
):
    commodity_demand = np.full(8760, 5.0)
    commodity_in = np.tile(np.concat([np.zeros(3), np.cumsum(np.ones(15)), np.full(6, 4.0)]), 365)

    # Setup the OpenMDAO problem and add subsystems
    prob = om.Problem()

    prob.model.add_subsystem(
        "PyomoRuleStorageBaseclass",
        PyomoRuleStorageBaseclass(
            plant_config=plant_config_h2_storage,
            tech_config=tech_config_generic["technologies"]["h2_storage"],
        ),
        promotes=["*"],
    )

    prob.model.add_subsystem(
        "h2_storage_heuristic_load_following_controller",
        HeuristicLoadFollowingStorageController(
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
def test_heuristic_dispatch_with_autosizing_storage_demand_less_than_avg_in(
    plant_config_h2_storage, tech_config_autosizing, subtests
):
    commodity_demand = np.full(8760, 5.0)
    commodity_in = np.tile(np.concat([np.zeros(3), np.cumsum(np.ones(15)), np.full(6, 4.0)]), 365)

    # Setup the OpenMDAO problem and add subsystems
    prob = om.Problem()

    prob.model.add_subsystem(
        "PyomoRuleStorageBaseclass",
        PyomoRuleStorageBaseclass(
            plant_config=plant_config_h2_storage,
            tech_config=tech_config_autosizing["technologies"]["h2_storage"],
        ),
        promotes=["*"],
    )

    prob.model.add_subsystem(
        "h2_storage_controller",
        HeuristicLoadFollowingStorageController(
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
def test_heuristic_dispatch_with_autosizing_storage_demand_is_avg_in(
    plant_config_h2_storage, tech_config_autosizing, subtests
):
    commodity_in = np.tile(np.concat([np.zeros(3), np.cumsum(np.ones(15)), np.full(6, 4.0)]), 365)
    commodity_demand = np.full(8760, np.mean(commodity_in))
    tech_config_autosizing["technologies"]["h2_storage"]["model_inputs"]["performance_parameters"][
        "set_demand_as_avg_commodity_in"
    ] = True
    tech_config_autosizing["technologies"]["h2_storage"]["model_inputs"]["performance_parameters"][
        "demand_profile"
    ] = 0.0

    # Setup the OpenMDAO problem and add subsystems
    prob = om.Problem()

    prob.model.add_subsystem(
        "PyomoRuleStorageBaseclass",
        PyomoRuleStorageBaseclass(
            plant_config=plant_config_h2_storage,
            tech_config=tech_config_autosizing["technologies"]["h2_storage"],
        ),
        promotes=["*"],
    )

    prob.model.add_subsystem(
        "h2_storage_controller",
        HeuristicLoadFollowingStorageController(
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
        expected_charge = np.concat([np.zeros(9), np.arange(-1, -10, -1), np.zeros(2)])
        np.testing.assert_allclose(
            prob.get_val("h2_storage.storage_hydrogen_charge", units="kg/h")[0:20],
            expected_charge,
            rtol=1e-6,
        )
