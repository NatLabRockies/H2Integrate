import numpy as np
import pytest
import openmdao.api as om

from h2integrate.storage.battery.pysam_battery import PySAMBatteryPerformanceModel
from h2integrate.control.control_strategies.pyomo_controllers import (
    HeuristicLoadFollowingController,
)
from h2integrate.control.control_rules.storage.pyomo_storage_rule_baseclass import (
    PyomoRuleStorageBaseclass,
)


plant_config = {
    "name": "plant_config",
    "description": "...",
    "plant": {
        "plant_life": 30,
        "grid_connection": False,
        "ppa_price": 0.025,
        "hybrid_electricity_estimated_cf": 0.492,
        "simulation": {
            "dt": 3600,
            "n_timesteps": 8760,
        },
    },
    "tech_to_dispatch_connections": [
        ["battery", "battery"],
    ],
}

tech_config = {
    "name": "technology_config",
    "description": "...",
    "technologies": {
        "battery": {
            "dispatch_rule_set": {"model": "pyomo_dispatch_generic_storage"},
            "control_strategy": {"model": "heuristic_load_following_controller"},
            "performance_model": {"model": "pysam_battery"},
            "model_inputs": {
                "shared_parameters": {
                    "max_charge_rate": 50000,
                    "max_capacity": 200000,
                    "n_control_window": 24,
                    "n_horizon_window": 48,
                    "init_charge_percent": 0.5,
                    "max_charge_percent": 0.9,
                    "min_charge_percent": 0.1,
                },
                "performance_parameters": {
                    "system_model_source": "pysam",
                    "chemistry": "LFPGraphite",
                    "control_variable": "input_power",
                },
                "control_parameters": {
                    "commodity_name": "electricity",
                    "commodity_storage_units": "kW",
                    "tech_name": "battery",
                    "system_commodity_interface_limit": 1e12,
                },
                "dispatch_rule_parameters": {
                    "commodity_name": "electricity",
                    "commodity_storage_units": "kW",
                },
            },
        }
    },
}


def test_heuristic_load_following_battery_dispatch(subtests):
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
        "pyomo_dispatch_generic_storage",
        PyomoRuleStorageBaseclass(
            plant_config=plant_config, tech_config=tech_config["technologies"]["battery"]
        ),
        promotes=["*"],
    )

    prob.model.add_subsystem(
        "battery_heuristic_load_following_controller",
        HeuristicLoadFollowingController(
            plant_config=plant_config, tech_config=tech_config["technologies"]["battery"]
        ),
        promotes=["*"],
    )

    prob.model.add_subsystem(
        "battery",
        PySAMBatteryPerformanceModel(
            plant_config=plant_config, tech_config=tech_config["technologies"]["battery"]
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

    expected_battery_electricity_discharge = [
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

    with subtests.test("Check electricity_out"):
        assert (
            pytest.approx(expected_electricity_out) == prob.get_val("battery.electricity_out")[0:24]
        )

    with subtests.test("Check battery_electricity_discharge"):
        assert (
            pytest.approx(expected_battery_electricity_discharge)
            == prob.get_val("battery.battery_electricity_discharge")[0:24]
        )

    with subtests.test("Check SOC"):
        assert pytest.approx(expected_SOC) == prob.get_val("battery.SOC")[0:24]

    with subtests.test("Check unmet_demand"):
        assert (
            pytest.approx(expected_unmet_demand_out, abs=1e-4)
            == prob.get_val("battery.unmet_electricity_demand_out")[0:24]
        )

    with subtests.test("Check unused_electricity_out"):
        assert (
            pytest.approx(expected_unused_commodity_out)
            == prob.get_val("battery.unused_electricity_out")[0:24]
        )

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
    expected_battery_electricity_discharge = expected_electricity_out
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

    with subtests.test("Check electricity_out for min SOC"):
        assert (
            pytest.approx(expected_electricity_out) == prob.get_val("battery.electricity_out")[:5]
        )

    with subtests.test("Check battery_electricity_discharge for min SOC"):
        assert (
            pytest.approx(expected_battery_electricity_discharge)
            == prob.get_val("battery.battery_electricity_discharge")[:5]
        )

    with subtests.test("Check SOC for min SOC"):
        assert pytest.approx(expected_SOC) == prob.get_val("battery.SOC")[:5]

    with subtests.test("Check unmet_demand for min SOC"):
        assert (
            pytest.approx(expected_unmet_demand_out, abs=1e-6)
            == prob.get_val("battery.unmet_electricity_demand_out")[:5]
        )

    with subtests.test("Check unused_commodity_out for min SOC"):
        assert (
            pytest.approx(expected_unused_commodity_out)
            == prob.get_val("battery.unused_electricity_out")[:5]
        )

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
    expected_battery_electricity_discharge = np.array(
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
    # expected_battery_electricity_discharge = [-30000.00847705, -29973.58679681,
    # -23310.54620182, 0.0, 0.0]
    # expected_SOC = [66.00200558, 79.43840635, 90.0, 90.0, 90.0]
    # expected_unmet_demand_out = np.zeros(5)
    # expected_unused_commodity_out = [0.0, 0.0, 6150.14483911, 30000.0, 30000.0]

    abs_tol = 1e-6
    rel_tol = 1e-1
    with subtests.test("Check electricity_out for max SOC"):
        assert (
            pytest.approx(expected_electricity_out, abs=abs_tol, rel=rel_tol)
            == prob.get_val("battery.electricity_out")[:5]
        )

    with subtests.test("Check battery_electricity_discharge for max SOC"):
        assert (
            pytest.approx(expected_battery_electricity_discharge, abs=abs_tol, rel=rel_tol)
            == prob.get_val("battery.battery_electricity_discharge")[:5]
        )

    with subtests.test("Check SOC for max SOC"):
        assert pytest.approx(expected_SOC, abs=abs_tol) == prob.get_val("battery.SOC")[:5]

    with subtests.test("Check unmet_demand for max SOC"):
        assert (
            pytest.approx(expected_unmet_demand_out, abs=abs_tol)
            == prob.get_val("battery.unmet_electricity_demand_out")[:5]
        )

    with subtests.test("Check unused_commodity_out for max SOC"):
        assert (
            pytest.approx(expected_unused_commodity_out, abs=abs_tol, rel=rel_tol)
            == prob.get_val("battery.unused_electricity_out")[:5]
        )
