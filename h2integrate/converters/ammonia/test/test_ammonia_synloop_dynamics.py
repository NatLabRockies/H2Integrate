import numpy as np
import pytest
import openmdao.api as om
from pytest import fixture

from h2integrate.converters.ammonia.ammonia_synloop import AmmoniaSynLoopPerformanceModel


@pytest.fixture
def plant_config(dt, n_timesteps):
    plant = {
        "plant": {
            "plant_life": 30,
            "simulation": {
                "dt": dt,
                "n_timesteps": n_timesteps,
            },
        },
    }
    return plant


@fixture
def synloop_config():
    return {
        "model_inputs": {
            "shared_parameters": {
                "production_capacity": 50.0,
                "catalyst_consumption_rate": 0.000091295354067341,
                "catalyst_replacement_interval": 3,
            },
            "performance_parameters": {
                "size_mode": "normal",
                "capacity_factor": 0.9,
                "energy_demand": 1.0,  # kWh/kg
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


@fixture
def dynamics_config():
    params = {
        "turndown_ratio": 0.0,
        "ramp_up_rate_fraction": 1.0,
        "ramp_down_rate_fraction": 1.0,
        "include_cold_start": False,
        "off_hours_cold_start": None,
        "cold_start_delay_hours": None,
        "include_warm_start": False,
        "off_hours_warm_start": None,
        "warm_start_delay_hours": None,
    }
    return params


# def create_status_profile_for_delays(dt, n_timesteps, offtime_hrs, delay_hrs, start_on=True):
#     dt_hr = dt/3600

#     if offtime_hrs<=dt_hr:
#         offtime_dt = 1.0 # offtime in dt
#     else:
#         # check that this is right
#         offtime_dt = offtime_hrs/dt_hr

#     # delay time
#     delay_dt = delay_hrs/dt_hr
#     production_multiplier = np.zeros(n_timesteps)
#     i = 0
#     if start_on:
#         production_multiplier[0] = 1.0
#         i +=1


def make_production_sequence(min_prod, max_prod, onoff_sequence, n_timesteps, start_on=True):
    if isinstance(onoff_sequence, list):
        onoff_sequence = np.array(onoff_sequence)
    production_sequence = np.zeros(len(onoff_sequence))
    production_sequence[np.argwhere(onoff_sequence < 0.99).flatten()] = min_prod / 2
    production_sequence[np.argwhere(onoff_sequence >= 0.99).flatten()] = max_prod

    n_repeats = 1 + (n_timesteps // len(onoff_sequence))

    production0 = max_prod if start_on else 0

    production = np.concat([production0, np.tile(production_sequence, n_repeats)])[:n_timesteps]

    return production


@pytest.mark.unit
def test_ammonia_config(synloop_config, dynamics_config, subtests):
    # TODO: add tests to check error raising in synloop config
    pass


@pytest.mark.regression
@pytest.mark.parametrize("dt,n_timesteps", [(3600, 40)])
def test_ammonia_subdt_offtime_subdt_delay(
    plant_config, synloop_config, dynamics_config, n_timesteps, subtests
):
    rated_capacity = synloop_config["model_inputs"]["shared_parameters"]["production_capacity"]

    dynamics_config["include_cold_start"] = True
    dynamics_config["off_hours_cold_start"] = 0.5
    dynamics_config["cold_start_delay_hours"] = 0.25
    dynamics_config["turndown_ratio"] = 0.1

    synloop_config["model_inputs"].update({"performance_parameters": dynamics_config})

    min_nh3 = dynamics_config["turndown_ratio"] * rated_capacity

    # test when its off and when its on
    # off for 1 hour, on for 3 hours, off for two, on for 1
    on_off_sequence = [0, 1, 1, 1, 0, 0, 1]
    # starts on

    nh3_no_dynamics = make_production_sequence(
        min_nh3, rated_capacity, on_off_sequence, n_timesteps, start_on=True
    )
    elec_in = (
        nh3_no_dynamics * synloop_config["model_inputs"]["performance_parameters"]["energy_demand"]
    )

    # only electricity is a limiting input
    cap_mult = 10.0e3
    n2 = np.full(n_timesteps, 5.0 * cap_mult)
    h2 = np.full(n_timesteps, 2.0 * cap_mult)

    prob = om.Problem()

    comp = AmmoniaSynLoopPerformanceModel(
        plant_config=plant_config,
        tech_config=synloop_config,
        driver_config={},
    )
    prob.model.add_subsystem("comp", comp, promotes=["*"])
    prob.setup()
    prob.set_val("comp.hydrogen_in", h2, units="kg/h")
    prob.set_val("comp.nitrogen_in", n2, units="kg/h")
    prob.set_val("comp.electricity_in", elec_in, units="kW")

    prob.run_model()

    nh3_out = prob.get_val("comp.ammonia_out", units="kg/h")

    # 2 hours with losses from delay per on/off sequence
    # 3 hours of off-time per on/off sequence
    expected_delay_losses_per_sequence = 0.25 * rated_capacity * 2
    expected_off_time_losses_per_sequence = (min_nh3 / 2) * 3
    # checking the first timesteps to include starting on
    n_timesteps_test = int(len(on_off_sequence) + 1)

    with subtests.test(f"Losses for first {n_timesteps_test} timesteps"):
        nh3_produced = nh3_out[:n_timesteps_test].sum()
        nh3_without_losses = nh3_no_dynamics[:n_timesteps_test].sum()
        expected_nh3 = nh3_without_losses - (
            expected_delay_losses_per_sequence + expected_off_time_losses_per_sequence
        )
        assert pytest.approx(nh3_produced, rel=1e-6) == expected_nh3


@pytest.mark.regression
@pytest.mark.parametrize("dt,n_timesteps", [(3600, 40)])
def test_ammonia_subdt_offtime_multidt_delay(
    plant_config, synloop_config, dynamics_config, n_timesteps, subtests
):
    rated_capacity = synloop_config["model_inputs"]["shared_parameters"]["production_capacity"]

    dynamics_config["include_cold_start"] = True
    dynamics_config["off_hours_cold_start"] = 0.5  # off for 1 hour to trigger off
    dynamics_config["cold_start_delay_hours"] = 3.0  # 3 hours to start-up
    dynamics_config["turndown_ratio"] = 0.1

    synloop_config["model_inputs"].update({"performance_parameters": dynamics_config})

    min_nh3 = dynamics_config["turndown_ratio"] * rated_capacity

    # test when its off and when its on
    # off for 1 hour, on for 5 hours, off for 2, on for 3
    on_off_sequence = np.concat([np.zeros(1), np.ones(5), np.zeros(2), np.ones(3)])
    # starts on
    nh3_no_dynamics = make_production_sequence(
        min_nh3, rated_capacity, on_off_sequence, n_timesteps, start_on=True
    )
    elec_in = (
        nh3_no_dynamics * synloop_config["model_inputs"]["performance_parameters"]["energy_demand"]
    )

    # only electricity is a limiting input
    cap_mult = 10.0e3
    n2 = np.full(n_timesteps, 5.0 * cap_mult)
    h2 = np.full(n_timesteps, 2.0 * cap_mult)

    prob = om.Problem()

    comp = AmmoniaSynLoopPerformanceModel(
        plant_config=plant_config,
        tech_config=synloop_config,
        driver_config={},
    )
    prob.model.add_subsystem("comp", comp, promotes=["*"])
    prob.setup()
    prob.set_val("comp.hydrogen_in", h2, units="kg/h")
    prob.set_val("comp.nitrogen_in", n2, units="kg/h")
    prob.set_val("comp.electricity_in", elec_in, units="kW")

    prob.run_model()

    nh3_out = prob.get_val("comp.ammonia_out", units="kg/h")
    # 6 hours with no production (from delay) per on/off sequence
    # 3 hours of off-time per on/off sequence
    expected_delay_losses_per_sequence = rated_capacity * 6
    expected_off_time_losses_per_sequence = (min_nh3 / 2) * 3
    # checking the first timesteps to include starting on
    n_timesteps_test = int(len(on_off_sequence) + 1)

    with subtests.test(f"Losses for first {n_timesteps_test} timesteps"):
        nh3_produced = nh3_out[:n_timesteps_test].sum()
        nh3_without_losses = nh3_no_dynamics[:n_timesteps_test].sum()
        expected_nh3 = nh3_without_losses - (
            expected_delay_losses_per_sequence + expected_off_time_losses_per_sequence
        )
        assert pytest.approx(nh3_produced, rel=1e-6) == expected_nh3


@pytest.mark.regression
@pytest.mark.parametrize("dt,n_timesteps", [(3600, 40)])
def test_ammonia_multidt_offtime_multidt_delay(
    plant_config, synloop_config, dynamics_config, n_timesteps, subtests
):
    rated_capacity = synloop_config["model_inputs"]["shared_parameters"]["production_capacity"]

    dynamics_config["include_cold_start"] = True
    dynamics_config["off_hours_cold_start"] = 4  # off for 4 hours to trigger delay
    dynamics_config["cold_start_delay_hours"] = 2  # 2 hours to turn on
    dynamics_config["turndown_ratio"] = 0.1

    synloop_config["model_inputs"].update({"performance_parameters": dynamics_config})

    min_nh3 = dynamics_config["turndown_ratio"] * rated_capacity

    # test when its off and when its on
    # off for 3 hour, on for 3 hours, off for 4, on for 3, off for 5, on for 3
    on_off_sequence = np.concat(
        [np.zeros(3), np.ones(3), np.zeros(4), np.ones(3), np.zeros(5), np.ones(3)]
    )
    # starts on
    nh3_no_dynamics = make_production_sequence(
        min_nh3, rated_capacity, on_off_sequence, n_timesteps, start_on=True
    )
    elec_in = (
        nh3_no_dynamics * synloop_config["model_inputs"]["performance_parameters"]["energy_demand"]
    )

    # only electricity is a limiting input
    cap_mult = 10.0e3
    n2 = np.full(n_timesteps, 5.0 * cap_mult)
    h2 = np.full(n_timesteps, 2.0 * cap_mult)

    prob = om.Problem()

    comp = AmmoniaSynLoopPerformanceModel(
        plant_config=plant_config,
        tech_config=synloop_config,
        driver_config={},
    )
    prob.model.add_subsystem("comp", comp, promotes=["*"])
    prob.setup()
    prob.set_val("comp.hydrogen_in", h2, units="kg/h")
    prob.set_val("comp.nitrogen_in", n2, units="kg/h")
    prob.set_val("comp.electricity_in", elec_in, units="kW")

    prob.run_model()

    nh3_out = prob.get_val("comp.ammonia_out", units="kg/h")
    # 6 hours with no production (from delay) per on/off sequence
    # 12 hours of off-time per on/off sequence
    expected_delay_losses_per_sequence = rated_capacity * 6
    expected_off_time_losses_per_sequence = (min_nh3 / 2) * 12
    # checking the first timesteps to include starting on
    n_timesteps_test = int(len(on_off_sequence) + 1)

    with subtests.test(f"Losses for first {n_timesteps_test} timesteps"):
        nh3_produced = nh3_out[:n_timesteps_test].sum()
        nh3_without_losses = nh3_no_dynamics[:n_timesteps_test].sum()
        expected_nh3 = nh3_without_losses - (
            expected_delay_losses_per_sequence + expected_off_time_losses_per_sequence
        )
        assert pytest.approx(nh3_produced, rel=1e-6) == expected_nh3
