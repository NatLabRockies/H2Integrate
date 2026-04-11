from copy import deepcopy
from pathlib import Path

import numpy as np
import pytest
import openmdao.api as om
from pytest import fixture

from h2integrate.core.file_utils import load_yaml
from h2integrate.storage.storage_performance_model import StoragePerformanceModel
from h2integrate.control.control_strategies.storage.simple_openloop_controller import (
    SimpleStorageOpenLoopController,
)
from h2integrate.control.control_strategies.storage.demand_openloop_storage_controller import (
    DemandOpenLoopStorageController,
)


@fixture
def variable_h2_production_profile():
    end_use_rated_demand = 10.0  # kg/h
    ramp_up_rate_kg = 4.0
    ramp_down_rate_kg = 2.0
    slow_ramp_up = np.arange(0, end_use_rated_demand * 1.1, 0.5)
    slow_ramp_down = np.arange(end_use_rated_demand * 1.1, -0.5, -0.5)
    fast_ramp_up = np.arange(0, end_use_rated_demand, ramp_up_rate_kg * 1.2)
    fast_ramp_down = np.arange(end_use_rated_demand, 0.0, ramp_down_rate_kg * 1.1)
    variable_profile = np.concat(
        [slow_ramp_up, fast_ramp_down, slow_ramp_up, slow_ramp_down, fast_ramp_up]
    )
    variable_h2_profile = np.tile(variable_profile, 2)
    return variable_h2_profile


@pytest.mark.unit
def test_pass_through_controller(subtests):
    # Get the directory of the current script
    current_dir = Path(__file__).parent

    # Resolve the paths to the configuration files
    tech_config_path = current_dir / "inputs" / "tech_config.yaml"

    # Load the technology configuration
    tech_config = load_yaml(tech_config_path)

    tech_config["technologies"]["h2_storage"]["model_inputs"]["shared_parameters"].update(
        {"set_demand_as_avg_commodity_in": True}
    )
    # Set up the OpenMDAO problem
    prob = om.Problem()

    plant_config = {"plant": {"plant_life": 30, "simulation": {"n_timesteps": 10, "dt": 3600}}}

    prob.model.add_subsystem(
        name="IVC",
        subsys=om.IndepVarComp(name="hydrogen_in", val=np.arange(10)),
        promotes=["*"],
    )

    prob.model.add_subsystem(
        "pass_through_controller",
        SimpleStorageOpenLoopController(
            plant_config=plant_config, tech_config=tech_config["technologies"]["h2_storage"]
        ),
        promotes=["*"],
    )

    prob.setup()

    prob.run_model()

    # Run the test
    with subtests.test("Check output"):
        expected_set_point = np.mean(np.arange(10)) - np.arange(10)
        assert expected_set_point == (
            pytest.approx(prob.get_val("hydrogen_set_point", units="kg/h"), rel=1e-3)
        )


@pytest.mark.regression
def test_storage_demand_controller(subtests):
    # Get the directory of the current script
    current_dir = Path(__file__).parent

    # Resolve the paths to the configuration files
    tech_config_path = current_dir / "inputs" / "tech_config.yaml"

    # Load the technology configuration
    tech_config = load_yaml(tech_config_path)

    tech_config["technologies"]["h2_storage"]["model_inputs"]["shared_parameters"] = {
        "commodity": "hydrogen",
        "commodity_rate_units": "kg/h",
        "max_capacity": 10.0,  # kg
        "max_soc_fraction": 1.0,  # fraction (0-1)
        "min_soc_fraction": 0.0,  # fraction (0-1)
        "init_soc_fraction": 1.0,  # fraction (0-1)
        "max_charge_rate": 1.0,  # kg/time step
        "max_discharge_rate": 0.5,  # kg/time step
        "charge_equals_discharge": False,
        "charge_efficiency": 1.0,
        "discharge_efficiency": 1.0,
        "demand_profile": [1.0] * 10,  # Example: 10 time steps with 10 kg/time step demand
    }

    plant_config = {"plant": {"plant_life": 30, "simulation": {"n_timesteps": 10, "dt": 3600}}}

    # Set up the OpenMDAO problem
    prob = om.Problem()

    prob.model.add_subsystem(
        name="IVC",
        subsys=om.IndepVarComp(name="hydrogen_in", val=np.arange(10)),
        promotes=["*"],
    )

    prob.model.add_subsystem(
        "demand_open_loop_storage_controller",
        DemandOpenLoopStorageController(
            plant_config=plant_config, tech_config=tech_config["technologies"]["h2_storage"]
        ),
        promotes=["*"],
    )
    prob.model.add_subsystem(
        "storage",
        StoragePerformanceModel(
            plant_config=plant_config, tech_config=tech_config["technologies"]["h2_storage"]
        ),
        promotes=["*"],
    )

    prob.setup()

    prob.run_model()

    # Run the test
    with subtests.test("Check output"):
        assert prob.get_val("hydrogen_out", units="kg/h") == pytest.approx(
            [0.5, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0]
        )

    with subtests.test("Check curtailment"):
        assert prob.get_val("unused_hydrogen_out", units="kg/h") == pytest.approx(
            [0.0, 0.0, 0.5, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0]
        )

    with subtests.test("Check soc"):
        assert prob.get_val("SOC", units="unitless") == pytest.approx(
            [0.95, 0.95, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0]
        )

    with subtests.test("Check missed load"):
        assert prob.get_val("unmet_hydrogen_demand_out", units="kg/h") == pytest.approx(
            [0.5, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0]
        )


@pytest.mark.unit
def test_storage_demand_controller_round_trip_efficiency(subtests):
    # This tests the behavior of storage efficiencies when the storage is charging and discharging
    # Get the directory of the current script
    current_dir = Path(__file__).parent

    # Resolve the paths to the configuration files
    tech_config_path = current_dir / "inputs" / "tech_config.yaml"

    # Load the technology configuration
    tech_config = load_yaml(tech_config_path)

    tech_config["technologies"]["h2_storage"]["model_inputs"]["shared_parameters"] = {
        "commodity": "hydrogen",
        "commodity_rate_units": "kg/h",
        "max_capacity": 10.0,  # kg
        "max_soc_fraction": 1.0,  # fraction (0-1)
        "min_soc_fraction": 0.0,  # fraction (0-1)
        "init_soc_fraction": 1.0,  # fraction (0-1)
        "max_charge_rate": 1.0,  # kg/time step
        "max_discharge_rate": 0.5,  # kg/time step
        "charge_equals_discharge": False,
        "charge_efficiency": 1.0,
        "discharge_efficiency": 1.0,
        "demand_profile": [1.0] * 10,  # Example: 10 time steps with 10 kg/time step demand
    }

    tech_config_rte = deepcopy(tech_config)
    tech_config_rte["technologies"]["h2_storage"]["model_inputs"]["shared_parameters"] = {
        "commodity": "hydrogen",
        "commodity_rate_units": "kg/h",
        "max_capacity": 10.0,  # kg
        "max_soc_fraction": 1.0,  # fraction (0-1)
        "min_soc_fraction": 0.0,  # fraction (0-1)
        "init_soc_fraction": 1.0,  # fraction (0-1)
        "max_charge_rate": 1.0,  # kg/time step
        "max_discharge_rate": 0.5,  # kg/time step
        "charge_equals_discharge": False,
        "round_trip_efficiency": 1.0,
        "demand_profile": [1.0] * 10,  # Example: 10 time steps with 10 kg/time step demand
    }

    plant_config = {"plant": {"plant_life": 30, "simulation": {"n_timesteps": 10, "dt": 3600}}}

    def set_up_and_run_problem(config):
        # Set up the OpenMDAO problem
        prob = om.Problem()

        prob.model.add_subsystem(
            name="IVC",
            subsys=om.IndepVarComp(name="hydrogen_in", val=np.arange(10)),
            promotes=["*"],
        )

        prob.model.add_subsystem(
            "demand_openloop_controller",
            DemandOpenLoopStorageController(
                plant_config=plant_config, tech_config=config["technologies"]["h2_storage"]
            ),
            promotes=["*"],
        )
        prob.model.add_subsystem(
            "storage",
            StoragePerformanceModel(
                plant_config=plant_config, tech_config=tech_config["technologies"]["h2_storage"]
            ),
            promotes=["*"],
        )

        prob.setup()

        prob.run_model()

        return prob

    prob_ioe = set_up_and_run_problem(tech_config)
    prob_rte = set_up_and_run_problem(tech_config_rte)

    # Run the test
    with subtests.test("Check output"):
        assert prob_rte.get_val("hydrogen_out", units="kg/h") == pytest.approx(
            prob_ioe.get_val("hydrogen_out", units="kg/h")
        )

    with subtests.test("Check curtailment"):
        assert prob_rte.get_val("unused_hydrogen_out", units="kg/h") == pytest.approx(
            prob_ioe.get_val("unused_hydrogen_out", units="kg/h")
        )

    with subtests.test("Check soc"):
        assert prob_rte.get_val("SOC", units="unitless") == pytest.approx(
            prob_ioe.get_val("SOC", units="unitless")
        )

    with subtests.test("Check missed load"):
        assert prob_rte.get_val("unmet_hydrogen_demand_out", units="kg/h") == pytest.approx(
            prob_ioe.get_val("unmet_hydrogen_demand_out", units="kg/h")
        )


@pytest.mark.unit
def test_storage_demand_controller_round_trip_with_non_one_efficiencies(subtests):
    # Get the directory of the current script
    current_dir = Path(__file__).parent

    # Resolve the paths to the configuration files
    tech_config_path = current_dir / "inputs" / "tech_config.yaml"

    # Load the technology configuration
    tech_config = load_yaml(tech_config_path)

    tech_config["technologies"]["h2_storage"]["control_strategy"]["model"] = (
        "DemandOpenLoopStorageController"
    )

    tech_config["technologies"]["h2_storage"]["performance_model"]["model"] = (
        "StoragePerformanceModel"
    )

    tech_config["technologies"]["h2_storage"]["model_inputs"]["shared_parameters"] = {
        "commodity": "hydrogen",
        "commodity_rate_units": "kg/h",
        "max_capacity": 10.0,  # kg
        "max_soc_fraction": 1.0,  # fraction (0-1)
        "min_soc_fraction": 0.0,  # fraction (0-1)
        "init_soc_fraction": 0.75,  # fraction (0-1)
        "max_charge_rate": 1.0,  # kg/time step
        "max_discharge_rate": 1.0,  # kg/time step
        "charge_equals_discharge": False,
        "charge_efficiency": 0.5,
        "discharge_efficiency": 0.5,
        "demand_profile": [
            0.0,
            0.0,
            0.0,
            0.0,
            0.0,
            1.0,
            1.0,
            1.0,
            1.0,
            2.0,
        ],  # Example: 10 time steps
    }

    tech_config_rte = deepcopy(tech_config)
    tech_config_rte["technologies"]["h2_storage"]["model_inputs"]["shared_parameters"] = {
        "commodity": "hydrogen",
        "commodity_rate_units": "kg/h",
        "max_capacity": 10.0,  # kg
        "max_soc_fraction": 1.0,  # fraction (0-1)
        "min_soc_fraction": 0.0,  # fraction (0-1)
        "init_soc_fraction": 0.75,  # fraction (0-1)
        "max_charge_rate": 1.0,  # kg/time step
        "max_discharge_rate": 1.0,  # kg/time step
        "charge_equals_discharge": False,
        "round_trip_efficiency": 0.5**2,
        "demand_profile": [
            0.0,
            0.0,
            0.0,
            0.0,
            0.0,
            1.0,
            1.0,
            1.0,
            1.0,
            2.0,
        ],  # Example: 10 time steps with 10 kg/time step demand
    }

    plant_config = {"plant": {"plant_life": 30, "simulation": {"n_timesteps": 10, "dt": 3600}}}

    def set_up_and_run_problem(config):
        # Set up the OpenMDAO problem
        prob = om.Problem()

        prob.model.add_subsystem(
            name="IVC",
            subsys=om.IndepVarComp(
                name="hydrogen_in", val=[2.0, 1.0, 1.0, 1.0, 1.0, 0.0, 0.0, 0.0, 0.0, 0.0]
            ),
            promotes=["*"],
        )

        prob.model.add_subsystem(
            "demand_openloop_controller",
            DemandOpenLoopStorageController(
                plant_config=plant_config, tech_config=config["technologies"]["h2_storage"]
            ),
            promotes=["*"],
        )
        prob.model.add_subsystem(
            "storage",
            StoragePerformanceModel(
                plant_config=plant_config, tech_config=tech_config["technologies"]["h2_storage"]
            ),
            promotes=["*"],
        )

        prob.setup()

        prob.run_model()

        return prob

    prob_ioe = set_up_and_run_problem(tech_config)
    prob_rte = set_up_and_run_problem(tech_config_rte)

    # Run the comparison tests between charge/discharge and round trip efficiencies
    with subtests.test("Check output match"):
        assert prob_rte.get_val("hydrogen_out", units="kg/h") == pytest.approx(
            prob_ioe.get_val("hydrogen_out", units="kg/h")
        )

    with subtests.test("Check curtailment match"):
        assert prob_rte.get_val("unused_hydrogen_out", units="kg/h") == pytest.approx(
            prob_ioe.get_val("unused_hydrogen_out", units="kg/h")
        )

    with subtests.test("Check soc match"):
        assert prob_rte.get_val("SOC", units="unitless") == pytest.approx(
            prob_ioe.get_val("SOC", units="unitless")
        )

    with subtests.test("Check missed load match"):
        assert prob_rte.get_val("unmet_hydrogen_demand_out", units="kg/h") == pytest.approx(
            prob_ioe.get_val("unmet_hydrogen_demand_out", units="kg/h")
        )

    # Run the absolute value tests for charge/discharge and round trip efficiencies
    with subtests.test("Check output value"):
        assert prob_rte.get_val("hydrogen_out", units="kg/h") == pytest.approx(
            np.array([0.0, 0.0, 0.0, 0.0, 0.0, 1.0, 1.0, 1.0, 1.0, 1.0])
        )

    with subtests.test("Check curtailment value"):
        assert prob_rte.get_val("unused_hydrogen_out", units="kg/h") == pytest.approx(
            np.array([1.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0])
        )

    with subtests.test("Check soc value"):
        assert prob_rte.get_val("SOC", units="unitless") == pytest.approx(
            np.array([0.8, 0.85, 0.9, 0.95, 1.0, 0.8, 0.6, 0.4, 0.2, 0.0])
        )

    with subtests.test("Check missed load value"):
        assert prob_rte.get_val("unmet_hydrogen_demand_out", units="kg/h") == pytest.approx(
            np.array([0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 1.0])
        )


@pytest.mark.regression
def test_generic_storage_demand_controller(subtests):
    # Test is the same as the demand controller test test_demand_controller for the "h2_storage"
    # performance model but with the "StoragePerformanceModel" performance model

    # Get the directory of the current script
    current_dir = Path(__file__).parent

    # Resolve the paths to the configuration files
    tech_config_path = current_dir / "inputs" / "tech_config.yaml"

    # Load the technology configuration
    tech_config = load_yaml(tech_config_path)

    tech_config["technologies"]["h2_storage"] = {
        "performance_model": {
            "model": "StoragePerformanceModel",
        },
        "control_strategy": {
            "model": "DemandOpenLoopStorageController",
        },
        "model_inputs": {
            "shared_parameters": {
                "commodity": "hydrogen",
                "commodity_rate_units": "kg/h",
                "max_capacity": 10.0,  # kg
                "max_charge_rate": 1.0,  # fraction (0-1)
                "max_soc_fraction": 1.0,  # fraction (0-1)
                "min_soc_fraction": 0.0,  # fraction (0-1)
                "init_soc_fraction": 1.0,  # fraction (0-1)
                "max_discharge_rate": 0.5,  # kg/time step
                "charge_efficiency": 1.0,
                "charge_equals_discharge": False,
                "discharge_efficiency": 1.0,
                "demand_profile": [1.0] * 10,  # Example: 10 time steps with 10 kg/time step demand
            },
        },
    }

    plant_config = {"plant": {"plant_life": 30, "simulation": {"n_timesteps": 10, "dt": 3600}}}

    # Set up OpenMDAO problem
    prob = om.Problem()

    prob.model.add_subsystem(
        name="IVC",
        subsys=om.IndepVarComp(name="hydrogen_in", val=np.arange(10)),
        promotes=["*"],
    )

    prob.model.add_subsystem(
        "demand_open_loop_storage_controller",
        DemandOpenLoopStorageController(
            plant_config=plant_config, tech_config=tech_config["technologies"]["h2_storage"]
        ),
        promotes=["*"],
    )

    prob.model.add_subsystem(
        "storage",
        StoragePerformanceModel(
            plant_config=plant_config, tech_config=tech_config["technologies"]["h2_storage"]
        ),
        promotes=["*"],
    )

    prob.setup()

    prob.run_model()

    # # Run the test
    with subtests.test("Check output"):
        assert prob.get_val("hydrogen_out", units="kg/h") == pytest.approx(
            [0.5, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0]
        )

    with subtests.test("Check curtailment"):
        assert prob.get_val("unused_hydrogen_out", units="kg/h") == pytest.approx(
            [0.0, 0.0, 0.5, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0]
        )

    with subtests.test("Check soc"):
        assert prob.get_val("SOC", units="unitless") == pytest.approx(
            [0.95, 0.95, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0]
        )

    with subtests.test("Check missed load"):
        assert prob.get_val("unmet_hydrogen_demand_out", units="kg/h") == pytest.approx(
            [0.5, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0]
        )
