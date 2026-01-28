from copy import deepcopy
from pathlib import Path

import yaml
import numpy as np
import pytest
import openmdao.api as om
from pytest import fixture
from openmdao.utils.assert_utils import assert_check_totals

from h2integrate.control.control_strategies.passthrough_openloop_controller import (
    PassThroughOpenLoopController,
)
from h2integrate.control.control_strategies.storage.demand_openloop_controller import (
    DemandOpenLoopStorageController,
)
from h2integrate.control.control_strategies.converters.demand_openloop_controller import (
    DemandOpenLoopConverterController,
)
from h2integrate.control.control_strategies.converters.flexible_demand_openloop_controller import (
    FlexibleDemandOpenLoopConverterController,
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


def test_pass_through_controller(subtests):
    # Get the directory of the current script
    current_dir = Path(__file__).parent

    # Resolve the paths to the configuration files
    tech_config_path = current_dir / "inputs" / "tech_config.yaml"

    # Load the technology configuration
    with tech_config_path.open() as file:
        tech_config = yaml.safe_load(file)

    # Set up the OpenMDAO problem
    prob = om.Problem()

    prob.model.add_subsystem(
        name="IVC",
        subsys=om.IndepVarComp(name="hydrogen_in", val=np.arange(10)),
        promotes=["*"],
    )

    prob.model.add_subsystem(
        "pass_through_controller",
        PassThroughOpenLoopController(
            plant_config={}, tech_config=tech_config["technologies"]["h2_storage"]
        ),
        promotes=["*"],
    )

    prob.setup()

    prob.run_model()

    # Run the test
    with subtests.test("Check output"):
        assert pytest.approx(prob.get_val("hydrogen_out"), rel=1e-3) == np.arange(10)

    # Run the test
    with subtests.test("Check derivatives"):
        # check total derivatives using OpenMDAO's check_totals and assert tools
        assert_check_totals(
            prob.check_totals(
                of=[
                    "hydrogen_out",
                ],
                wrt=[
                    "hydrogen_in",
                ],
                step=1e-6,
                form="central",
                show_only_incorrect=False,
                out_stream=None,
            )
        )


def test_storage_demand_controller(subtests):
    # Get the directory of the current script
    current_dir = Path(__file__).parent

    # Resolve the paths to the configuration files
    tech_config_path = current_dir / "inputs" / "tech_config.yaml"

    # Load the technology configuration
    with tech_config_path.open() as file:
        tech_config = yaml.safe_load(file)

    plant_config = {"plant": {"simulation": {"n_timesteps": 10}}}

    tech_config["technologies"]["h2_storage"]["control_strategy"]["model"] = (
        "demand_open_loop_storage_controller"
    )

    tech_config["technologies"]["h2_storage"]["model_inputs"]["control_parameters"] = {
        "max_capacity": 10.0,  # kg
        "max_charge_percent": 1.0,  # percent as decimal
        "min_charge_percent": 0.0,  # percent as decimal
        "init_charge_percent": 1.0,  # percent as decimal
        "max_charge_rate": 1.0,  # kg/time step
        "max_discharge_rate": 0.5,  # kg/time step
        "charge_equals_discharge": False,
        "charge_efficiency": 1.0,
        "discharge_efficiency": 1.0,
        "demand_profile": [1.0] * 10,  # Example: 10 time steps with 10 kg/time step demand
    }

    plant_config = {"plant": {"plant_life": 30, "simulation": {"n_timesteps": 10}}}

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

    prob.setup()

    prob.run_model()

    # Run the test
    with subtests.test("Check output"):
        assert pytest.approx([0.5, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0]) == prob.get_val(
            "hydrogen_out"
        )

    with subtests.test("Check curtailment"):
        assert pytest.approx([0.0, 0.0, 0.5, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0]) == prob.get_val(
            "hydrogen_unused_commodity"
        )

    with subtests.test("Check soc"):
        assert pytest.approx([0.95, 0.95, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0]) == prob.get_val(
            "hydrogen_soc"
        )

    with subtests.test("Check missed load"):
        assert pytest.approx([0.5, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0]) == prob.get_val(
            "hydrogen_unmet_demand"
        )


def test_storage_demand_controller_round_trip_efficiency(subtests):
    # Get the directory of the current script
    current_dir = Path(__file__).parent

    # Resolve the paths to the configuration files
    tech_config_path = current_dir / "inputs" / "tech_config.yaml"

    # Load the technology configuration
    with tech_config_path.open() as file:
        tech_config = yaml.safe_load(file)

    plant_config = {"plant": {"simulation": {"n_timesteps": 10}}}

    tech_config["technologies"]["h2_storage"]["control_strategy"]["model"] = (
        "demand_open_loop_storage_controller"
    )
    tech_config["technologies"]["h2_storage"]["model_inputs"]["control_parameters"] = {
        "max_capacity": 10.0,  # kg
        "max_charge_percent": 1.0,  # percent as decimal
        "min_charge_percent": 0.0,  # percent as decimal
        "init_charge_percent": 1.0,  # percent as decimal
        "max_charge_rate": 1.0,  # kg/time step
        "max_discharge_rate": 0.5,  # kg/time step
        "charge_equals_discharge": False,
        "charge_efficiency": 1.0,
        "discharge_efficiency": 1.0,
        "demand_profile": [1.0] * 10,  # Example: 10 time steps with 10 kg/time step demand
    }

    tech_config_rte = deepcopy(tech_config)
    tech_config_rte["technologies"]["h2_storage"]["model_inputs"]["control_parameters"] = {
        "max_capacity": 10.0,  # kg
        "max_charge_percent": 1.0,  # percent as decimal
        "min_charge_percent": 0.0,  # percent as decimal
        "init_charge_percent": 1.0,  # percent as decimal
        "max_charge_rate": 1.0,  # kg/time step
        "max_discharge_rate": 0.5,  # kg/time step
        "charge_equals_discharge": False,
        "round_trip_efficiency": 1.0,
        "demand_profile": [1.0] * 10,  # Example: 10 time steps with 10 kg/time step demand
    }

    plant_config = {"plant": {"plant_life": 30, "simulation": {"n_timesteps": 10}}}

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

        prob.setup()

        prob.run_model()

        return prob

    prob_ioe = set_up_and_run_problem(tech_config)
    prob_rte = set_up_and_run_problem(tech_config_rte)

    # Run the test
    with subtests.test("Check output"):
        assert pytest.approx(prob_ioe.get_val("hydrogen_out")) == prob_rte.get_val("hydrogen_out")

    with subtests.test("Check curtailment"):
        assert pytest.approx(prob_ioe.get_val("hydrogen_unused_commodity")) == prob_rte.get_val(
            "hydrogen_unused_commodity"
        )

    with subtests.test("Check soc"):
        assert pytest.approx(prob_ioe.get_val("hydrogen_soc")) == prob_rte.get_val("hydrogen_soc")

    with subtests.test("Check missed load"):
        assert pytest.approx(prob_ioe.get_val("hydrogen_unmet_demand")) == prob_rte.get_val(
            "hydrogen_unmet_demand"
        )


def test_generic_storage_demand_controller(subtests):
    # Test is the same as the demand controller test test_demand_controller for the "h2_storage"
    # performance model but with the "simple_generic_storage" performance model

    # Get the directory of the current script
    current_dir = Path(__file__).parent

    # Resolve the paths to the configuration files
    tech_config_path = current_dir / "inputs" / "tech_config.yaml"

    # Load the technology configuration
    with tech_config_path.open() as file:
        tech_config = yaml.safe_load(file)

    tech_config["technologies"]["h2_storage"] = {
        "performance_model": {
            "model": "simple_generic_storage",
        },
        "control_strategy": {
            "model": "demand_open_loop_storage_controller",
        },
        "model_inputs": {
            "shared_parameters": {
                "commodity_name": "hydrogen",
                "commodity_units": "kg",
                "max_capacity": 10.0,  # kg
                "max_charge_rate": 1.0,  # percent as decimal
            },
            "control_parameters": {
                "max_charge_percent": 1.0,  # percent as decimal
                "min_charge_percent": 0.0,  # percent as decimal
                "init_charge_percent": 1.0,  # percent as decimal
                "max_discharge_rate": 0.5,  # kg/time step
                "charge_efficiency": 1.0,
                "charge_equals_discharge": False,
                "discharge_efficiency": 1.0,
                "demand_profile": [1.0] * 10,  # Example: 10 time steps with 10 kg/time step demand
            },
        },
    }

    plant_config = {"plant": {"plant_life": 30, "simulation": {"n_timesteps": 10}}}

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

    prob.setup()

    prob.run_model()

    # # Run the test
    with subtests.test("Check output"):
        assert pytest.approx([0.5, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0]) == prob.get_val(
            "hydrogen_out"
        )

    with subtests.test("Check curtailment"):
        assert pytest.approx([0.0, 0.0, 0.5, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0]) == prob.get_val(
            "hydrogen_unused_commodity"
        )

    with subtests.test("Check soc"):
        assert pytest.approx([0.95, 0.95, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0]) == prob.get_val(
            "hydrogen_soc"
        )

    with subtests.test("Check missed load"):
        assert pytest.approx([0.5, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0]) == prob.get_val(
            "hydrogen_unmet_demand"
        )


def test_demand_converter_controller(subtests):
    # Test is the same as the demand controller test test_demand_controller for the "h2_storage"
    # performance model but with the "simple_generic_storage" performance model

    # Get the directory of the current script
    current_dir = Path(__file__).parent

    # Resolve the paths to the configuration files
    tech_config_path = current_dir / "inputs" / "tech_config.yaml"

    # Load the technology configuration
    with tech_config_path.open() as file:
        tech_config = yaml.safe_load(file)

    tech_config["technologies"]["load"] = {
        "control_strategy": {
            "model": "demand_open_loop_converter_controller",
        },
        "model_inputs": {
            "control_parameters": {
                "commodity_name": "hydrogen",
                "commodity_units": "kg",
                "demand_profile": [5.0] * 10,  # Example: 10 time steps with 5 kg/time step demand
            },
        },
    }

    plant_config = {"plant": {"plant_life": 30, "simulation": {"n_timesteps": 10}}}

    # Set up OpenMDAO problem
    prob = om.Problem()

    prob.model.add_subsystem(
        name="IVC",
        subsys=om.IndepVarComp(name="hydrogen_in", val=np.arange(10)),
        promotes=["*"],
    )

    prob.model.add_subsystem(
        "demand_open_loop_storage_controller",
        DemandOpenLoopConverterController(
            plant_config=plant_config, tech_config=tech_config["technologies"]["load"]
        ),
        promotes=["*"],
    )

    prob.setup()

    prob.run_model()

    # # Run the test
    with subtests.test("Check output"):
        assert pytest.approx([0.0, 1.0, 2.0, 3.0, 4.0, 5.0, 5.0, 5.0, 5.0, 5.0]) == prob.get_val(
            "hydrogen_out"
        )

    with subtests.test("Check curtailment"):
        assert pytest.approx([0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 1.0, 2.0, 3.0, 4.0]) == prob.get_val(
            "hydrogen_unused_commodity"
        )

    with subtests.test("Check missed load"):
        assert pytest.approx([5.0, 4.0, 3.0, 2.0, 1.0, 0.0, 0.0, 0.0, 0.0, 0.0]) == prob.get_val(
            "hydrogen_unmet_demand"
        )


### Add test for flexible load demand controller here


def test_flexible_demand_converter_controller(subtests, variable_h2_production_profile):
    # Get the directory of the current script
    current_dir = Path(__file__).parent

    # Resolve the paths to the configuration files
    tech_config_path = current_dir / "inputs" / "tech_config.yaml"

    # Load the technology configuration
    with tech_config_path.open() as file:
        tech_config = yaml.safe_load(file)

    end_use_rated_demand = 10.0  # kg/h
    ramp_up_rate_kg = 4.0
    ramp_down_rate_kg = 2.0
    min_demand_kg = 2.5
    tech_config["technologies"]["load"] = {
        "control_strategy": {
            "model": "flexible_demand_open_loop_converter_controller",
        },
        "model_inputs": {
            "control_parameters": {
                "commodity_name": "hydrogen",
                "commodity_units": "kg",
                "rated_demand": end_use_rated_demand,
                "demand_profile": end_use_rated_demand,  # flat demand profile
                "turndown_ratio": min_demand_kg / end_use_rated_demand,
                "ramp_down_rate_fraction": ramp_down_rate_kg / end_use_rated_demand,
                "ramp_up_rate_fraction": ramp_up_rate_kg / end_use_rated_demand,
                "min_utilization": 0.1,
            },
        },
    }

    plant_config = {
        "plant": {
            "plant_life": 30,
            "simulation": {"n_timesteps": len(variable_h2_production_profile)},
        }
    }

    # Set up OpenMDAO problem
    prob = om.Problem()

    prob.model.add_subsystem(
        name="IVC",
        subsys=om.IndepVarComp(name="hydrogen_in", val=variable_h2_production_profile),
        promotes=["*"],
    )

    prob.model.add_subsystem(
        "demand_open_loop_storage_controller",
        FlexibleDemandOpenLoopConverterController(
            plant_config=plant_config, tech_config=tech_config["technologies"]["load"]
        ),
        promotes=["*"],
    )

    prob.setup()

    prob.run_model()

    flexible_total_demand = prob.get_val("hydrogen_flexible_demand_profile")

    rated_production = end_use_rated_demand * len(variable_h2_production_profile)

    with subtests.test("Check that total demand profile is less than rated"):
        assert np.all(flexible_total_demand <= end_use_rated_demand)

    with subtests.test("Check curtailment"):  # failed
        assert pytest.approx(np.sum(prob.get_val("hydrogen_unused_commodity")), rel=1e-3) == 6.6

    # check ramping constraints and turndown constraints are met
    with subtests.test("Check turndown ratio constraint"):
        assert np.all(flexible_total_demand >= min_demand_kg)

    ramping_down = np.where(
        np.diff(flexible_total_demand) < 0, -1 * np.diff(flexible_total_demand), 0
    )
    ramping_up = np.where(np.diff(flexible_total_demand) > 0, np.diff(flexible_total_demand), 0)

    with subtests.test("Check ramping down constraint"):
        assert pytest.approx(np.max(ramping_down), rel=1e-6) == ramp_down_rate_kg

    with subtests.test("Check ramping up constraint"):  # failed
        assert pytest.approx(np.max(ramping_up), rel=1e-6) == ramp_up_rate_kg

    with subtests.test("Check min utilization constraint"):
        assert np.sum(flexible_total_demand) / rated_production >= 0.1

    with subtests.test("Check min utilization value"):
        flexible_demand_utilization = np.sum(flexible_total_demand) / rated_production
        assert pytest.approx(flexible_demand_utilization, rel=1e-6) == 0.5822142857142857

    # flexible_demand_profile[i] >= commodity_in[i] (as long as you are not curtailing
    # any commodity in)
    with subtests.test("Check that flexible demand is greater than hydrogen_in"):
        hydrogen_available = variable_h2_production_profile - prob.get_val(
            "hydrogen_unused_commodity"
        )
        assert np.all(flexible_total_demand >= hydrogen_available)

    with subtests.test("Check that remaining demand was calculated properly"):
        unmet_demand = flexible_total_demand - hydrogen_available
        assert np.all(unmet_demand == prob.get_val("hydrogen_unmet_demand"))


def test_flexible_demand_converter_controller_min_utilization(
    subtests, variable_h2_production_profile
):
    # give it a min utilization larger than utilization resulting from above test

    # Get the directory of the current script
    current_dir = Path(__file__).parent

    # Resolve the paths to the configuration files
    tech_config_path = current_dir / "inputs" / "tech_config.yaml"

    # Load the technology configuration
    with tech_config_path.open() as file:
        tech_config = yaml.safe_load(file)

    end_use_rated_demand = 10.0  # kg/h
    ramp_up_rate_kg = 4.0
    ramp_down_rate_kg = 2.0
    min_demand_kg = 2.5
    tech_config["technologies"]["load"] = {
        "control_strategy": {
            "model": "flexible_demand_open_loop_converter_controller",
        },
        "model_inputs": {
            "control_parameters": {
                "commodity_name": "hydrogen",
                "commodity_units": "kg",
                "rated_demand": end_use_rated_demand,
                "demand_profile": end_use_rated_demand,  # flat demand profile
                "turndown_ratio": min_demand_kg / end_use_rated_demand,
                "ramp_down_rate_fraction": ramp_down_rate_kg / end_use_rated_demand,
                "ramp_up_rate_fraction": ramp_up_rate_kg / end_use_rated_demand,
                "min_utilization": 0.8,
            },
        },
    }

    plant_config = {
        "plant": {
            "plant_life": 30,
            "simulation": {"n_timesteps": len(variable_h2_production_profile)},
        }
    }

    # Set up OpenMDAO problem
    prob = om.Problem()

    prob.model.add_subsystem(
        name="IVC",
        subsys=om.IndepVarComp(name="hydrogen_in", val=variable_h2_production_profile),
        promotes=["*"],
    )

    prob.model.add_subsystem(
        "demand_open_loop_storage_controller",
        FlexibleDemandOpenLoopConverterController(
            plant_config=plant_config, tech_config=tech_config["technologies"]["load"]
        ),
        promotes=["*"],
    )

    prob.setup()

    prob.run_model()

    flexible_total_demand = prob.get_val("hydrogen_flexible_demand_profile")

    rated_production = end_use_rated_demand * len(variable_h2_production_profile)

    flexible_demand_utilization = np.sum(flexible_total_demand) / rated_production

    with subtests.test("Check min utilization constraint"):
        assert flexible_demand_utilization >= 0.8

    with subtests.test("Check min utilization value"):
        assert pytest.approx(flexible_demand_utilization, rel=1e-6) == 0.8010612244
