from copy import deepcopy
from pathlib import Path

import yaml
import numpy as np
import pytest
import openmdao.api as om

from h2integrate.storage.battery.pysam_battery import (
    PySAMBatteryPerformanceModel,
    PySAMBatteryPerformanceModelConfig,
)


def test_pysam_battery_performance_model_without_controller(subtests):
    # Get the directory of the current script
    current_dir = Path(__file__).parent

    # Resolve the paths to the configuration files
    tech_config_path = current_dir / "inputs" / "tech_config.yaml"

    # Load the technology configuration
    with tech_config_path.open() as file:
        tech_config = yaml.safe_load(file)

    # Set up the OpenMDAO problem
    prob = om.Problem()

    n_control_window = tech_config["technologies"]["battery"]["model_inputs"]["shared_parameters"][
        "n_control_window"
    ]

    electricity_in = np.concatenate(
        (np.ones(int(n_control_window / 2)) * 1000.0, np.zeros(int(n_control_window / 2)))
    )

    electricity_demand = np.ones(int(n_control_window)) * 1000.0

    prob.model.add_subsystem(
        name="IVC1",
        subsys=om.IndepVarComp(name="electricity_in", val=electricity_in, units="kW*h"),
        promotes=["*"],
    )

    prob.model.add_subsystem(
        name="IVC2",
        subsys=om.IndepVarComp(name="time_step_duration", val=np.ones(n_control_window), units="h"),
        promotes=["*"],
    )

    prob.model.add_subsystem(
        name="IVC3",
        subsys=om.IndepVarComp(name="electricity_demand", val=electricity_demand, units="kW*h"),
        promotes=["*"],
    )

    prob.model.add_subsystem(
        "pysam_battery",
        PySAMBatteryPerformanceModel(
            plant_config={"plant": {"simulation": {"dt": 3600, "n_timesteps": 24}}},
            tech_config=tech_config["technologies"]["battery"],
        ),
        promotes=["*"],
    )

    prob.setup()

    prob.run_model()

    expected_battery_power = np.array(
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
            999.9999999703667,
            998.5371904178584,
            998.5263437993322,
            998.5152383436508,
            998.5038990519837,
            998.4923409910639,
            998.4805728240225,
            998.4685988497556,
            998.4564204119457,
            998.444036724444,
            998.4314456105915,
            998.4186438286721,
        ]
    )

    expected_battery_SOC = np.array(
        [
            50.07393113,
            50.07924536,
            50.08359418,
            50.08738059,
            50.09078403,
            50.09390401,
            50.09680279,
            50.0995225,
            50.1020933,
            50.10453765,
            50.10687283,
            50.10911249,
            51.82111663,
            51.35016991,
            50.87907361,
            50.40778871,
            49.93629139,
            49.46456699,
            48.99260672,
            48.52040546,
            48.04796035,
            47.57526987,
            47.10233318,
            46.62914982,
        ]
    )

    expected_unment_demand = np.array(
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
            2.963327006000327e-08,
            1.462809582141631,
            1.4736562006678469,
            1.4847616563491783,
            1.4961009480163057,
            1.5076590089361162,
            1.519427175977512,
            1.5314011502443918,
            1.5435795880542855,
            1.555963275555996,
            1.5685543894085185,
            1.5813561713279114,
        ]
    )
    expected_unused_electricity = np.zeros(n_control_window)

    with subtests.test("expected_battery_power"):
        np.testing.assert_allclose(
            prob.get_val("battery_electricity_discharge"), expected_battery_power, rtol=1e-2
        )

    with subtests.test("expected_battery_SOC"):
        np.testing.assert_allclose(prob.get_val("SOC"), expected_battery_SOC, rtol=1e-2)

    with subtests.test("expected_battery_unmet_demand"):
        np.testing.assert_allclose(
            prob.get_val("unmet_electricity_demand_out"), expected_unment_demand, rtol=1e-2
        )

    with subtests.test("expected_battery_unused_commodity"):
        np.testing.assert_allclose(
            prob.get_val("unused_electricity_out"), expected_unused_electricity, rtol=1e-2
        )


def test_battery_config(subtests):
    batt_kw = 5e3
    config_data = {
        "max_capacity": batt_kw * 4,
        "max_charge_rate": batt_kw,
        "chemistry": "LFPGraphite",
        "init_charge_percent": 0.1,
        "max_charge_percent": 0.9,
        "min_charge_percent": 0.1,
        "system_model_source": "pysam",
    }

    config = PySAMBatteryPerformanceModelConfig.from_dict(config_data)

    with subtests.test("with minimal params batt_kw"):
        assert config.max_charge_rate == batt_kw
    with subtests.test("with minimal params system_capacity_kwh"):
        assert config.max_capacity == batt_kw * 4
    with subtests.test("with minimal params minimum_SOC"):
        assert (
            config.min_charge_percent == 0.1
        )  # Decimal percent as compared to test_battery.py in HOPP 10%
    with subtests.test("with minimal params maximum_SOC"):
        assert (
            config.max_charge_percent == 0.9
        )  # Decimal percent as compared to test_battery.py in HOPP 90%
    with subtests.test("with minimal params initial_SOC"):
        assert (
            config.init_charge_percent == 0.1
        )  # Decimal percent as compared to test_battery.py in HOPP 10%
    with subtests.test("with minimal params system_model_source"):
        assert config.system_model_source == "pysam"
    with subtests.test("with minimal params n_control_window"):
        assert config.n_control_window == 24
    with subtests.test("with minimal params n_horizon_window"):
        assert config.n_horizon_window == 48

    with subtests.test("with invalid capacity"):
        with pytest.raises(ValueError):
            data = deepcopy(config_data)
            data["max_charge_rate"] = -1.0
            PySAMBatteryPerformanceModelConfig.from_dict(data)

        with pytest.raises(ValueError):
            data = deepcopy(config_data)
            data["max_capacity"] = -1.0
            PySAMBatteryPerformanceModelConfig.from_dict(data)

    with subtests.test("with invalid SOC"):
        # SOC values must be between 0-100
        with pytest.raises(ValueError):
            data = deepcopy(config_data)
            data["min_charge_percent"] = -1.0
            PySAMBatteryPerformanceModelConfig.from_dict(data)

        with pytest.raises(ValueError):
            data = deepcopy(config_data)
            data["max_charge_percent"] = 120.0
            PySAMBatteryPerformanceModelConfig.from_dict(data)

        with pytest.raises(ValueError):
            data = deepcopy(config_data)
            data["init_charge_percent"] = 120.0
            PySAMBatteryPerformanceModelConfig.from_dict(data)


def test_battery_initialization(subtests):
    # Get the directory of the current script
    current_dir = Path(__file__).parent

    # Resolve the paths to the configuration files
    tech_config_path = current_dir / "inputs" / "tech_config.yaml"

    # Load the technology configuration
    with tech_config_path.open() as file:
        tech_config = yaml.safe_load(file)

    battery = PySAMBatteryPerformanceModel(
        plant_config={"plant": {"simulation": {"dt": 3600, "n_timesteps": 24}}},
        tech_config=tech_config["technologies"]["battery"],
    )

    battery.setup()

    with subtests.test("battery attribute not None system_model"):
        assert battery.system_model is not None
    with subtests.test("battery attribute not None outputs"):
        assert battery.outputs is not None

    with subtests.test("battery mass"):
        # this test value does not match the value in test_battery.py in HOPP
        # this is because the mass is computed in compute function in H2I
        # and in HOPP it's in the attrs_post_init function
        # suggest removing this subtest
        assert battery.system_model.ParamsPack.mass * 20000 == pytest.approx(3044540.0, 1e-3)
