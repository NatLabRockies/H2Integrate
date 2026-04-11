import numpy as np
import pytest
import openmdao.api as om
from pytest import fixture

from h2integrate.demand.generic_demand import GenericDemandComponent
from h2integrate.demand.flexible_demand import FlexibleDemandComponent


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


@pytest.mark.regression
def test_demand_converter_controller(subtests):
    # Test is the same as the demand controller test test_demand_controller for the "h2_storage"
    # performance model but with the "StoragePerformanceModel" performance model

    # Define the technology configuration
    tech_config = {"technologies": {}}

    tech_config["technologies"]["load"] = {
        "performance_model": {
            "model": "GenericDemandComponent",
        },
        "model_inputs": {
            "performance_parameters": {
                "commodity": "hydrogen",
                "commodity_rate_units": "kg",
                "demand_profile": [5.0] * 10,  # Example: 10 time steps with 5 kg/time step demand
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
        GenericDemandComponent(
            plant_config=plant_config, tech_config=tech_config["technologies"]["load"]
        ),
        promotes=["*"],
    )

    prob.setup()

    prob.run_model()

    # # Run the test
    with subtests.test("Check output"):
        assert prob.get_val("hydrogen_out") == pytest.approx(
            [0.0, 1.0, 2.0, 3.0, 4.0, 5.0, 5.0, 5.0, 5.0, 5.0]
        )

    with subtests.test("Check curtailment"):
        assert prob.get_val("unused_hydrogen_out") == pytest.approx(
            [0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 1.0, 2.0, 3.0, 4.0]
        )

    with subtests.test("Check missed load"):
        assert prob.get_val("unmet_hydrogen_demand_out") == pytest.approx(
            [5.0, 4.0, 3.0, 2.0, 1.0, 0.0, 0.0, 0.0, 0.0, 0.0]
        )


@pytest.mark.unit
def test_flexible_demand_converter_controller(subtests, variable_h2_production_profile):
    # Define the technology configuration
    tech_config = {"technologies": {}}

    end_use_rated_demand = 10.0  # kg/h
    ramp_up_rate_kg = 4.0
    ramp_down_rate_kg = 2.0
    min_demand_kg = 2.5
    tech_config["technologies"]["load"] = {
        "performance_model": {
            "model": "FlexibleDemandComponent",
        },
        "model_inputs": {
            "performance_parameters": {
                "commodity": "hydrogen",
                "commodity_rate_units": "kg",
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
            "simulation": {"n_timesteps": len(variable_h2_production_profile), "dt": 3600},
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
        "flexible_demand_open_loop_converter_controller",
        FlexibleDemandComponent(
            plant_config=plant_config, tech_config=tech_config["technologies"]["load"]
        ),
        promotes=["*"],
    )

    prob.setup()

    prob.run_model()

    flexible_total_demand = prob.get_val("hydrogen_flexible_demand_profile", units="kg")

    rated_production = end_use_rated_demand * len(variable_h2_production_profile)

    with subtests.test("Check that total demand profile is less than rated"):
        assert np.all(flexible_total_demand <= end_use_rated_demand)

    with subtests.test("Check curtailment"):  # failed
        assert np.sum(prob.get_val("unused_hydrogen_out", units="kg")) == pytest.approx(6.6)

    # check ramping constraints and turndown constraints are met
    with subtests.test("Check turndown ratio constraint"):
        assert np.all(flexible_total_demand >= min_demand_kg)

    ramping_down = np.where(
        np.diff(flexible_total_demand) < 0, -1 * np.diff(flexible_total_demand), 0
    )
    ramping_up = np.where(np.diff(flexible_total_demand) > 0, np.diff(flexible_total_demand), 0)

    with subtests.test("Check ramping down constraint"):
        assert np.max(ramping_down) == pytest.approx(ramp_down_rate_kg, rel=1e-6)

    with subtests.test("Check ramping up constraint"):  # failed
        assert np.max(ramping_up) == pytest.approx(ramp_up_rate_kg, rel=1e-6)

    with subtests.test("Check min utilization constraint"):
        assert np.sum(flexible_total_demand) / rated_production >= 0.1

    with subtests.test("Check min utilization value"):
        flexible_demand_utilization = np.sum(flexible_total_demand) / rated_production
        assert flexible_demand_utilization == pytest.approx(0.5822142857142857, rel=1e-6)

    # flexible_demand_profile[i] >= commodity_in[i] (as long as you are not curtailing
    # any commodity in)
    with subtests.test("Check that flexible demand is greater than hydrogen_in"):
        hydrogen_available = variable_h2_production_profile - prob.get_val(
            "unused_hydrogen_out", units="kg"
        )
        assert np.all(flexible_total_demand >= hydrogen_available)

    with subtests.test("Check that remaining demand was calculated properly"):
        unmet_demand = flexible_total_demand - hydrogen_available
        assert np.all(unmet_demand == prob.get_val("unmet_hydrogen_demand_out", units="kg"))


@pytest.mark.regression
def test_flexible_demand_converter_controller_min_utilization(
    subtests, variable_h2_production_profile
):
    # give it a min utilization larger than utilization resulting from above test

    # Define the technology configuration
    tech_config = {"technologies": {}}

    end_use_rated_demand = 10.0  # kg/h
    ramp_up_rate_kg = 4.0
    ramp_down_rate_kg = 2.0
    min_demand_kg = 2.5
    tech_config["technologies"]["load"] = {
        "performance_model": {
            "model": "FlexibleDemandComponent",
        },
        "model_inputs": {
            "performance_parameters": {
                "commodity": "hydrogen",
                "commodity_rate_units": "kg",
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
            "simulation": {"n_timesteps": len(variable_h2_production_profile), "dt": 3600},
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
        "DemandOpenLoopStorageController",
        FlexibleDemandComponent(
            plant_config=plant_config, tech_config=tech_config["technologies"]["load"]
        ),
        promotes=["*"],
    )

    prob.setup()

    prob.run_model()

    flexible_total_demand = prob.get_val("hydrogen_flexible_demand_profile", units="kg")

    rated_production = end_use_rated_demand * len(variable_h2_production_profile)

    flexible_demand_utilization = np.sum(flexible_total_demand) / rated_production

    with subtests.test("Check min utilization constraint"):
        assert flexible_demand_utilization >= 0.8

    with subtests.test("Check min utilization value"):
        assert flexible_demand_utilization == pytest.approx(0.8010612244, rel=1e-6)
