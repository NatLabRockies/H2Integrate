import numpy as np
import pytest

from h2integrate.core.h2integrate_model import H2IntegrateModel


plant_config = {
    "name": "plant_config",
    "description": "...",
    "sites": {
        "site": {"latitude": 35.2018863, "longitude": -101.945027},
    },
    "plant": {
        "plant_life": 1,
        "grid_connection": False,
        "ppa_price": 0.025,
        "hybrid_electricity_estimated_cf": 0.492,
        "simulation": {
            "dt": 3600,
            "n_timesteps": 8760,
        },
    },
    "technology_interconnections": [["combiner", "battery", "electricity", "cable"]],
    "tech_to_dispatch_connections": [
        ["combiner", "battery"],
        ["battery", "battery"],
    ],
}

driver_config = {
    "name": "driver_config",
    "description": "Pyomo optimal min operating cost test",
    "general": {},
}

tech_config = {
    "name": "technology_config",
    "description": "...",
    "technologies": {
        "battery": {
            "dispatch_rule_set": {"model": "PyomoRuleStorageBaseclass"},
            "control_strategy": {"model": "OptimizedDispatchController"},
            "performance_model": {"model": "PySAMBatteryPerformanceModel"},
            "model_inputs": {
                "shared_parameters": {
                    "max_charge_rate": 50000,
                    "max_capacity": 200000,
                    "n_control_window": 24,
                    "n_horizon_window": 48,
                    "init_charge_percent": 0.5,
                    "max_charge_percent": 0.9,
                    "min_charge_percent": 0.1,
                    "commodity": "electricity",
                    "commodity_rate_units": "kW",
                    "time_weighting_factor": 0.995,
                    "charge_efficiency": 0.95,
                    "discharge_efficiency": 0.95,
                    "cost_per_charge": 0.004,
                    "cost_per_discharge": 0.005,
                    "cost_per_production": 0.0,
                    "commodity_met_value": 0.1,
                    "round_digits": 4,
                },
                "performance_parameters": {
                    "system_model_source": "pysam",
                    "chemistry": "LFPGraphite",
                    "control_variable": "input_power",
                },
                "control_parameters": {
                    "tech_name": "battery",
                    "system_commodity_interface_limit": 1e12,
                },
            },
        },
        "combiner": {
            "performance_model": {"model": "GenericCombinerPerformanceModel"},
            "dispatch_rule_set": {"model": "PyomoDispatchGenericConverter"},
            "model_inputs": {
                "performance_parameters": {
                    "commodity": "electricity",
                    "commodity_units": "kW",
                    "in_streams": 1,
                },
                "dispatch_rule_parameters": {
                    "commodity": "electricity",
                    "commodity_rate_units": "kW",
                },
            },
        },
    },
}


def test_min_operating_cost_load_following_battery_dispatch(subtests):
    # Fabricate some oscillating power generation data: 1000 kW for the first 12 hours, 10000 kW for
    # the second twelve hours, and repeat that daily cycle over a year.
    n_look_ahead_half = int(24 / 2)

    electricity_in = np.concatenate(
        (np.ones(n_look_ahead_half) * 1000, np.ones(n_look_ahead_half) * 10000)
    )
    electricity_in = np.tile(electricity_in, 365)

    demand_in = np.ones(8760) * 6000.0

    # Create an H2Integrate model
    model = H2IntegrateModel(
        {
            "driver_config": driver_config,
            "technology_config": tech_config,
            "plant_config": plant_config,
        }
    )

    # Setup the system and required values
    model.setup()
    model.prob.set_val("combiner.electricity_in1", electricity_in)
    model.prob.set_val("battery.electricity_demand", demand_in)

    # Run the model
    model.prob.run_model()

    # Test the case where the charging/discharging cycle remains within the max and min SOC limits
    # Check the expected outputs to actual outputs
    expected_electricity_out = [
        5999.99997732,
        5992.25494845,
        5991.96052468,
        5991.63342842,
        5991.26824325,
        5990.86174194,
        5990.40961477,
        5989.90607785,
        5989.34362595,
        5988.71271658,
        5988.00134229,
        5987.19448473,
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
        4999.99997732,
        4992.25494845,
        4991.96052468,
        4991.63342842,
        4991.26824325,
        4990.86174194,
        4990.40961477,
        4989.90607785,
        4989.34362595,
        4988.71271658,
        4988.00134229,
        4987.19448473,
        -3990.28117686,
        -3990.74350731,
        -3991.15657455,
        -3991.53821244,
        -3991.89075932,
        -3992.21669822,
        -3992.51846124,
        -3992.79833559,
        -3993.05841677,
        -3993.30060036,
        -3993.52658465,
        -3993.73788536,
    ]

    expected_battery_soc = [
        49.87479765,
        47.50390223,
        45.12932011,
        42.75108798,
        40.3682277,
        37.9797332,
        35.58459541,
        33.18174418,
        30.76997461,
        28.34786178,
        25.91365422,
        23.4651282,
        25.4168656,
        27.36180226,
        29.29938411,
        31.23051435,
        33.15594392,
        35.07630244,
        36.99212221,
        38.90385706,
        40.81189705,
        42.71658006,
        44.61820098,
        46.517019,
        44.14026872,
        41.75708657,
        39.3692475,
        36.97562686,
        34.57512794,
        32.16658699,
        29.7486839,
        27.31984419,
        24.87811568,
        22.42099596,
        19.94517118,
        17.44609219,
    ]

    expected_unmet_demand = np.array(
        [
            2.26821512e-05,
            7.74505155,
            8.03947532,
            8.36657158,
            8.73175675,
            9.13825806,
            9.59038523,
            1.00939222e01,
            1.06563740e01,
            1.12872834e01,
            1.19986577e01,
            1.28055153e01,
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

    expected_unused_electricity = np.array(
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
            9.71882314,
            9.25649269,
            8.84342545,
            8.46178756,
            8.10924068,
            7.78330178,
            7.48153876,
            7.20166441,
            6.94158323,
            6.69939964,
            6.47341535,
            6.26211464,
        ]
    )

    with subtests.test("Check battery.electricity_out"):
        assert (
            pytest.approx(expected_electricity_out)
            == model.prob.get_val("battery.electricity_out")[0:24]
        )

    with subtests.test("Check battery_electricity_discharge"):
        assert (
            pytest.approx(expected_battery_electricity_discharge)
            == model.prob.get_val("battery.battery_electricity_discharge")[0:24]
        )

    # Check a longer portion of SOC to make sure SOC is getting linked between optimization periods
    with subtests.test("Check SOC"):
        assert pytest.approx(expected_battery_soc) == model.prob.get_val("battery.SOC")[0:36]

    with subtests.test("Check unmet_demand"):
        assert (
            pytest.approx(expected_unmet_demand, abs=1e-4)
            == model.prob.get_val("battery.unmet_electricity_demand_out")[0:24]
        )

    with subtests.test("Check unused_electricity_out"):
        assert (
            pytest.approx(expected_unused_electricity)
            == model.prob.get_val("battery.unused_electricity_out")[0:24]
        )

    # Test the case where the battery efficiency is lower
    tech_config["technologies"]["battery"]["model_inputs"]["shared_parameters"][
        "charge_efficiency"
    ] = 0.632
    tech_config["technologies"]["battery"]["model_inputs"]["shared_parameters"][
        "discharge_efficiency"
    ] = 0.632

    model = H2IntegrateModel(
        {
            "driver_config": driver_config,
            "technology_config": tech_config,
            "plant_config": plant_config,
        }
    )

    # Setup the system and required values
    model.setup()
    model.prob.set_val("combiner.electricity_in1", electricity_in)
    model.prob.set_val("battery.electricity_demand", demand_in)

    # Run the model
    model.prob.run_model()

    expected_electricity_out = [
        5999.99997732,
        5992.25494845,
        5991.96052468,
        5991.63342842,
        5991.26824325,
        5990.86174194,
        5990.40961477,
        5989.90607785,
        5989.34362595,
        5988.71271658,
        1558.72773849,
        1000.0,
    ]

    # Make sure output changes if efficiency is changed
    with subtests.test("Check electricity_out for different efficiency"):
        assert (
            pytest.approx(expected_electricity_out)
            == model.prob.get_val("battery.electricity_out")[:12]
        )
