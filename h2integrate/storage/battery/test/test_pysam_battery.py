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


@pytest.mark.regression
@pytest.mark.parametrize("n_timesteps", [24])
def test_pysam_battery_performance_model_without_controller(plant_config, subtests):
    # Get the directory of the current script
    current_dir = Path(__file__).parent

    # Resolve the paths to the configuration files
    tech_config_path = current_dir / "inputs" / "tech_config.yaml"

    # Load the technology configuration
    with tech_config_path.open() as file:
        tech_config = yaml.safe_load(file)

    # Set up the OpenMDAO problem
    prob = om.Problem()

    n_control_window = tech_config["technologies"]["battery"]["model_inputs"]["control_parameters"][
        "n_control_window"
    ]

    electricity_in = np.concatenate(
        (np.ones(int(n_control_window / 2)) * 1000.0, np.zeros(int(n_control_window / 2)))
    )

    electricity_demand = np.ones(int(n_control_window)) * 1000.0

    prob.model.add_subsystem(
        name="IVC1",
        subsys=om.IndepVarComp(name="electricity_in", val=electricity_in, units="kW"),
        promotes=["*"],
    )

    prob.model.add_subsystem(
        name="IVC2",
        subsys=om.IndepVarComp(name="time_step_duration", val=np.ones(n_control_window), units="h"),
        promotes=["*"],
    )

    prob.model.add_subsystem(
        name="IVC3",
        subsys=om.IndepVarComp(name="electricity_demand", val=electricity_demand, units="kW"),
        promotes=["*"],
    )

    prob.model.add_subsystem(
        name="IVC4",
        subsys=om.IndepVarComp(
            name="electricity_set_point", val=electricity_demand - electricity_in, units="kW"
        ),
        promotes=["*"],
    )

    prob.model.add_subsystem(
        "pysam_battery",
        PySAMBatteryPerformanceModel(
            plant_config=plant_config,
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
            prob.get_val("battery_electricity_out", units="kW"),
            expected_battery_power,
            rtol=1e-2,
        )

    with subtests.test("expected_battery_SOC"):
        np.testing.assert_allclose(
            prob.get_val("SOC", units="percent"), expected_battery_SOC, rtol=1e-2
        )

    with subtests.test("expected_battery_unmet_demand"):
        np.testing.assert_allclose(
            prob.get_val("unmet_electricity_demand_out", units="kW"),
            expected_unment_demand,
            rtol=1e-2,
        )

    with subtests.test("expected_battery_unused_commodity"):
        np.testing.assert_allclose(
            prob.get_val("unused_electricity_out", units="kW"),
            expected_unused_electricity,
            rtol=1e-2,
        )


@pytest.mark.regression
def test_battery_config(subtests):
    batt_kw = 5e3
    config_data = {
        "max_capacity": batt_kw * 4,
        "max_charge_rate": batt_kw,
        "chemistry": "LFPGraphite",
        "init_soc_fraction": 0.1,
        "max_soc_fraction": 0.9,
        "min_soc_fraction": 0.1,
        "demand_profile": 0.0,
    }

    config = PySAMBatteryPerformanceModelConfig.from_dict(config_data)

    with subtests.test("with minimal params batt_kw"):
        assert config.max_charge_rate == batt_kw
    with subtests.test("with minimal params system_capacity_kwh"):
        assert config.max_capacity == batt_kw * 4
    with subtests.test("with minimal params minimum_SOC"):
        assert (
            config.min_soc_fraction == 0.1
        )  # Decimal percent as compared to test_battery.py in HOPP 10%
    with subtests.test("with minimal params maximum_SOC"):
        assert (
            config.max_soc_fraction == 0.9
        )  # Decimal percent as compared to test_battery.py in HOPP 90%
    with subtests.test("with minimal params initial_SOC"):
        assert (
            config.init_soc_fraction == 0.1
        )  # Decimal percent as compared to test_battery.py in HOPP 10%

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
            data["min_soc_fraction"] = -1.0
            PySAMBatteryPerformanceModelConfig.from_dict(data)

        with pytest.raises(ValueError):
            data = deepcopy(config_data)
            data["max_soc_fraction"] = 120.0
            PySAMBatteryPerformanceModelConfig.from_dict(data)

        with pytest.raises(ValueError):
            data = deepcopy(config_data)
            data["init_soc_fraction"] = 120.0
            PySAMBatteryPerformanceModelConfig.from_dict(data)


@pytest.mark.unit
@pytest.mark.parametrize("n_timesteps", [24])
def test_battery_initialization(plant_config, subtests):
    # Get the directory of the current script
    current_dir = Path(__file__).parent

    # Resolve the paths to the configuration files
    tech_config_path = current_dir / "inputs" / "tech_config.yaml"

    # Load the technology configuration
    with tech_config_path.open() as file:
        tech_config = yaml.safe_load(file)

    battery = PySAMBatteryPerformanceModel(
        plant_config=plant_config,
        tech_config=tech_config["technologies"]["battery"],
    )

    battery.setup()

    with subtests.test("battery attribute not None system_model"):
        assert battery.system_model is not None

    with subtests.test("battery mass"):
        # this test value does not match the value in test_battery.py in HOPP
        # this is because the mass is computed in compute function in H2I
        # and in HOPP it's in the attrs_post_init function
        # suggest removing this subtest
        assert battery.system_model.ParamsPack.mass * 20000 == pytest.approx(3044540.0, 1e-3)


@pytest.mark.regression
@pytest.mark.parametrize("n_timesteps", [48])
def test_pysam_battery_no_controller_change_capacity(plant_config, subtests):
    prob = om.Problem()
    # Get the directory of the current script
    current_dir = Path(__file__).parent

    # Resolve the paths to the configuration files
    tech_config_path = current_dir / "inputs" / "tech_config.yaml"

    # Load the technology configuration
    with tech_config_path.open() as file:
        tech_config = yaml.safe_load(file)

    init_charge_rate = 5 * 1e3  # 5 MW
    init_capacity = 20 * 1e3  # 20 MW

    electricity_demand = np.full(48, 15.0 * 1e3)  # demand is 15 MW
    electricity_in = np.tile(
        np.concat([np.arange(0, 25, 2.5), np.arange(25, 0, -2.5), np.full(4, 5)]), 2
    )

    tech_config = {
        "model_inputs": {
            "shared_parameters": {
                "max_charge_rate": init_charge_rate,
                "max_capacity": init_capacity,
                "n_control_window": 48,
                "init_soc_fraction": 0.1,
                "max_soc_fraction": 1.0,
                "min_soc_fraction": 0.1,
            },
            "performance_parameters": {"chemistry": "LFPGraphite", "demand_profile": 0.0},
        }
    }
    # Set up the OpenMDAO problem
    prob_init = om.Problem()
    prob_init.model.add_subsystem(
        name="IVC1",
        subsys=om.IndepVarComp(name="electricity_demand", val=electricity_demand, units="kW"),
        promotes=["*"],
    )

    prob_init.model.add_subsystem(
        name="IVC2",
        subsys=om.IndepVarComp(name="electricity_in", val=electricity_in, units="MW"),
        promotes=["*"],
    )

    prob_init.model.add_subsystem(
        name="IVC3",
        subsys=om.IndepVarComp(
            name="electricity_set_point", val=electricity_demand - electricity_in, units="kW"
        ),
        promotes=["*"],
    )

    prob_init.model.add_subsystem(
        "pysam_battery",
        PySAMBatteryPerformanceModel(
            plant_config=plant_config,
            tech_config=tech_config,
        ),
        promotes=["*"],
    )

    prob_init.setup()

    prob_init.run_model()

    with subtests.test("5 MW battery discharge profile within charge rate bounds"):
        assert (
            prob_init.get_val("pysam_battery.battery_electricity_discharge", units="kW").max()
            < init_charge_rate
        )
        assert (
            prob_init.get_val("pysam_battery.battery_electricity_discharge", units="kW").min()
            >= 0.0
        )

    with subtests.test("5 MW battery charge profile within charge rate bounds"):
        assert (
            prob_init.get_val("pysam_battery.battery_electricity_charge", units="kW").min()
            > -1 * init_charge_rate
        )
        assert (
            prob_init.get_val("pysam_battery.battery_electricity_charge", units="kW").max() <= 0.0
        )

    with subtests.test("5 MW battery rated production == charge rate"):
        assert (
            pytest.approx(
                prob_init.get_val("pysam_battery.rated_electricity_production", units="kW").max(),
                rel=1e-6,
            )
            == init_charge_rate
        )

    # Re-run and set the charge rate as half of what it was before
    prob = om.Problem()
    prob.model.add_subsystem(
        name="IVC1",
        subsys=om.IndepVarComp(name="electricity_demand", val=electricity_demand, units="kW"),
        promotes=["*"],
    )

    prob.model.add_subsystem(
        name="IVC2",
        subsys=om.IndepVarComp(name="electricity_in", val=electricity_in, units="MW"),
        promotes=["*"],
    )

    prob.model.add_subsystem(
        name="IVC3",
        subsys=om.IndepVarComp(
            name="electricity_set_point", val=electricity_demand - electricity_in, units="kW"
        ),
        promotes=["*"],
    )

    prob.model.add_subsystem(
        "pysam_battery",
        PySAMBatteryPerformanceModel(
            plant_config=plant_config,
            tech_config=tech_config,
        ),
        promotes=["*"],
    )

    prob.setup()

    prob.set_val("pysam_battery.max_charge_rate", init_charge_rate / 2, units="kW")

    prob.run_model()

    with subtests.test("2.5 MW battery discharge profile within charge rate bounds"):
        assert (
            prob.get_val("pysam_battery.battery_electricity_discharge", units="kW").max()
            < init_charge_rate / 2
        )
        assert prob.get_val("pysam_battery.battery_electricity_discharge", units="kW").min() >= 0.0

    with subtests.test("2.5 MW battery charge profile within charge rate bounds"):
        assert (
            prob.get_val("pysam_battery.battery_electricity_charge", units="kW").min()
            > -1 * init_charge_rate / 2
        )
        assert prob.get_val("pysam_battery.battery_electricity_charge", units="kW").max() <= 0.0

    with subtests.test("2.5 MW battery discharge < charge rate"):
        assert prob.get_val(
            "pysam_battery.battery_electricity_discharge", units="MW"
        ).max() < init_charge_rate / (2 * 1e3)

    with subtests.test("2.5 MW battery discharge <= 5 MW battery discharge"):
        assert (
            prob.get_val("pysam_battery.battery_electricity_discharge", units="MW").max()
            < prob_init.get_val("pysam_battery.battery_electricity_discharge", units="MW").max()
        )

    with subtests.test("5 MW battery charge <= 2.5 MW battery charge"):
        assert (
            prob.get_val("pysam_battery.battery_electricity_discharge", units="MW").min()
            <= prob_init.get_val("pysam_battery.battery_electricity_discharge", units="MW").min()
        )

    with subtests.test("2.5 MW battery rated production == charge rate"):
        assert (
            pytest.approx(
                prob.get_val("pysam_battery.rated_electricity_production", units="MW").max(),
                rel=1e-6,
            )
            == 2.5
        )
