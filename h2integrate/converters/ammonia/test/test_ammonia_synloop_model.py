import os

import numpy as np
import pytest
import openmdao.api as om

from h2integrate import EXAMPLE_DIR
from h2integrate.core.h2integrate_model import H2IntegrateModel
from h2integrate.core.inputs.validation import load_tech_yaml, load_plant_yaml, load_driver_yaml
from h2integrate.converters.ammonia.ammonia_synloop import AmmoniaSynLoopPerformanceModel


def make_synloop_config():
    return {
        "model_inputs": {
            "shared_parameters": {
                "production_capacity": 52777.6,
                "catalyst_consumption_rate": 0.000091295354067341,
                "catalyst_replacement_interval": 3,
            },
            "performance_parameters": {
                "size_mode": "normal",
                "capacity_factor": 0.9,
                "energy_demand": 0.530645243,
                "heat_output": 0.8299956,
                "feed_gas_t": 25.8,
                "feed_gas_p": 20,
                "feed_gas_x_n2": 0.25,
                "feed_gas_x_h2": 0.75,
                "feed_gas_mass_ratio": 1.13,
                "purge_gas_t": 7.5,
                "purge_gas_p": 275,
                "purge_gas_x_n2": 0.26,
                "purge_gas_x_h2": 0.68,
                "purge_gas_x_ar": 0.02,
                "purge_gas_x_nh3": 0.04,
                "purge_gas_mass_ratio": 0.07,
            },
        }
    }


def test_ammonia_synloop_limiting_cases(subtests):
    config = make_synloop_config()
    plant_info = {
        "simulation": {
            "n_timesteps": 4,  # Using 4 timesteps for this test
            "dt": 3600,
        }
    }

    # Each test is a single array of 4 hours, each with a different limiting case
    # Case 1: N2 limiting
    cap_mult = 10.0e3
    n2 = np.array([2.0, 5.0, 5.0, 5.0]) * cap_mult  # Only first entry is N2 limiting
    h2 = np.array([2.0, 1.0, 2.0, 2.0]) * cap_mult  # Second entry is H2 limiting
    elec = np.array([0.006, 0.006, 0.001, 0.006]) * cap_mult  # Third entry is electricity limiting
    # Fourth entry is capacity-limited

    expected_nh3 = np.array(
        [
            21520.21334466,  # N2 limiting
            49840.21632252,  # H2 limiting
            18844.98190065,  # Electricity limiting
            52777.6,  # Capacity limiting
        ]
    )

    prob = om.Problem()
    comp = AmmoniaSynLoopPerformanceModel(plant_config={"plant": plant_info}, tech_config=config)
    prob.model.add_subsystem("synloop", comp)
    prob.setup()
    prob.set_val("synloop.hydrogen_in", h2, units="kg/h")
    prob.set_val("synloop.nitrogen_in", n2, units="kg/h")
    prob.set_val("synloop.electricity_in", elec, units="MW")
    prob.run_model()
    nh3 = prob.get_val("synloop.ammonia_out")
    total = prob.get_val("synloop.total_ammonia_produced")

    # Check individual NH3 output values
    with subtests.test("N2 limiting"):
        assert pytest.approx(nh3[0], rel=1e-6) == 21520.21334466
        assert pytest.approx(prob.get_val("synloop.limiting_input")[0]) == 0

    with subtests.test("H2 limiting"):
        assert pytest.approx(nh3[1], rel=1e-6) == 49840.21632252
        assert pytest.approx(prob.get_val("synloop.limiting_input")[1]) == 1

    with subtests.test("Electricity limiting"):
        assert pytest.approx(nh3[2], rel=1e-6) == 18844.98190065
        assert pytest.approx(prob.get_val("synloop.limiting_input")[2]) == 2

    with subtests.test("Capacity limiting"):
        assert pytest.approx(nh3[3], rel=1e-6) == 52777.6
        assert pytest.approx(prob.get_val("synloop.limiting_input")[3]) == 3

    # Check total NH3 output
    with subtests.test("Total ammonia"):
        assert np.allclose(total, np.sum(expected_nh3), rtol=1e-6)


def test_size_mode_outputs(subtests):
    # Change the current working directory to the example's directory
    os.chdir(EXAMPLE_DIR / "25_sizing_modes")

    # Load the 'base' configs needed to create the H2I model
    driver_config = load_driver_yaml(EXAMPLE_DIR / "25_sizing_modes" / "driver_config.yaml")
    plant_config = load_plant_yaml(EXAMPLE_DIR / "25_sizing_modes" / "plant_config.yaml")
    tech_config = load_tech_yaml(EXAMPLE_DIR / "25_sizing_modes" / "tech_config.yaml")
    input_config = {
        "name": "H2Integrate_config",
        "system_summary": "hybrid plant containing ammonia plant and electrolyzer",
        "driver_config": driver_config,
        "plant_config": plant_config,
        "technology_config": tech_config,
    }

    # Create a H2Integrate model, modifying tech_config as necessary
    tech_config["technologies"]["ammonia"]["model_inputs"]["performance_parameters"][
        "size_mode"
    ] = "resize_by_max_feedstock"
    tech_config["technologies"]["ammonia"]["model_inputs"]["performance_parameters"][
        "flow_used_for_sizing"
    ] = "hydrogen"
    tech_config["technologies"]["ammonia"]["model_inputs"]["performance_parameters"][
        "max_feedstock_ratio"
    ] = 1.0
    input_config["technology_config"] = tech_config
    model = H2IntegrateModel(input_config)

    model.run()

    with subtests.test("Test `resize_by_max_feedstock` mode"):
        assert (
            pytest.approx(model.prob.get_val("ammonia.max_hydrogen_capacity")[0], rel=1e-3)
            == 12543.68246215831
        )
