import numpy as np
import pytest
import openmdao.api as om
from pytest import fixture

from h2integrate.converters.ammonia.ammonia_synloop_performance import (
    AmmoniaSynLoopPerformanceModel,
)


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


def make_production_sequence(min_prod, max_prod, onoff_sequence, n_timesteps, start_on=True):
    if isinstance(onoff_sequence, list):
        onoff_sequence = np.array(onoff_sequence)
    production_sequence = np.zeros(len(onoff_sequence))
    production_sequence[np.argwhere(onoff_sequence < 0.99).flatten()] = min_prod / 2
    production_sequence[np.argwhere(onoff_sequence >= 0.99).flatten()] = max_prod

    n_repeats = 1 + (n_timesteps // len(onoff_sequence))

    production0 = max_prod if start_on else 0

    production = np.concat([np.array([production0]), np.tile(production_sequence, n_repeats)])[
        :n_timesteps
    ]

    return production


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

    synloop_config["model_inputs"]["performance_parameters"] = (
        synloop_config["model_inputs"]["performance_parameters"] | dynamics_config
    )

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

    elec_consumed = prob.get_val("comp.electricity_consumed", units="kW")
    with subtests.test(f"Electricity consumption for first {n_timesteps_test} timesteps"):
        total_elec_consumed = elec_consumed[:n_timesteps_test].sum()
        nh3_produced = nh3_out[:n_timesteps_test].sum()
        assert pytest.approx(nh3_produced, rel=1e-6) == total_elec_consumed

    # Confirm losses repeat consistently across all full sequence repeats in the sim
    n_repeats = (n_timesteps - 1) // len(on_off_sequence)
    n_check = 1 + n_repeats * len(on_off_sequence)
    with subtests.test(f"Losses over {n_repeats} full sequence repeats ({n_check} timesteps)"):
        nh3_produced_full = nh3_out[:n_check].sum()
        nh3_without_losses_full = nh3_no_dynamics[:n_check].sum()
        expected_full = nh3_without_losses_full - n_repeats * (
            expected_delay_losses_per_sequence + expected_off_time_losses_per_sequence
        )
        assert pytest.approx(nh3_produced_full, rel=1e-6) == expected_full


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

    synloop_config["model_inputs"]["performance_parameters"] = (
        synloop_config["model_inputs"]["performance_parameters"] | dynamics_config
    )

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
    expected_delay_losses_per_sequence = rated_capacity * 6
    # 3 hours of off-time per on/off sequence
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

    # h2_consumed = prob.get_val("comp.hydrogen_consumed", units="kg/h")
    # n2_consumed = prob.get_val("comp.nitrogen_consumed", units="kg/h")
    elec_consumed = prob.get_val("comp.electricity_consumed", units="kW")

    with subtests.test(f"Electricity consumption for first {n_timesteps_test} timesteps"):
        total_elec_consumed = elec_consumed[:n_timesteps_test].sum()
        nh3_produced = nh3_out[:n_timesteps_test].sum()
        assert pytest.approx(nh3_produced, rel=1e-6) == total_elec_consumed

    # Confirm losses repeat consistently across all full sequence repeats in the sim
    n_repeats = (n_timesteps - 1) // len(on_off_sequence)
    n_check = 1 + n_repeats * len(on_off_sequence)
    with subtests.test(f"Losses over {n_repeats} full sequence repeats ({n_check} timesteps)"):
        nh3_produced_full = nh3_out[:n_check].sum()
        nh3_without_losses_full = nh3_no_dynamics[:n_check].sum()
        expected_full = nh3_without_losses_full - n_repeats * (
            expected_delay_losses_per_sequence + expected_off_time_losses_per_sequence
        )
        assert pytest.approx(nh3_produced_full, rel=1e-6) == expected_full


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

    synloop_config["model_inputs"]["performance_parameters"] = (
        synloop_config["model_inputs"]["performance_parameters"] | dynamics_config
    )

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
    # 4 hours with no production (from delay) per on/off sequence
    # 12 hours of off-time per on/off sequence
    expected_delay_losses_per_sequence = rated_capacity * 4
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

    elec_consumed = prob.get_val("comp.electricity_consumed", units="kW")
    with subtests.test(f"Electricity consumption for first {n_timesteps_test} timesteps"):
        total_elec_consumed = elec_consumed[:n_timesteps_test].sum()
        nh3_produced = nh3_out[:n_timesteps_test].sum()
        assert pytest.approx(nh3_produced, rel=1e-6) == total_elec_consumed

    # Confirm losses repeat consistently across all full sequence repeats in the sim
    n_repeats = (n_timesteps - 1) // len(on_off_sequence)
    n_check = 1 + n_repeats * len(on_off_sequence)
    with subtests.test(f"Losses over {n_repeats} full sequence repeats ({n_check} timesteps)"):
        nh3_produced_full = nh3_out[:n_check].sum()
        nh3_without_losses_full = nh3_no_dynamics[:n_check].sum()
        expected_full = nh3_without_losses_full - n_repeats * (
            expected_delay_losses_per_sequence + expected_off_time_losses_per_sequence
        )
        assert pytest.approx(nh3_produced_full, rel=1e-6) == expected_full


@pytest.mark.regression
@pytest.mark.parametrize("dt,n_timesteps", [(3600, 40)])
def test_ammonia_multidt_offtime_subdt_startup(
    plant_config, synloop_config, dynamics_config, n_timesteps, subtests
):
    rated_capacity = synloop_config["model_inputs"]["shared_parameters"]["production_capacity"]

    dynamics_config["include_cold_start"] = True
    dynamics_config["off_hours_cold_start"] = 4  # off for 4 hours to trigger delay
    dynamics_config["cold_start_delay_hours"] = 0.25  # 1/4 hour to turn on
    dynamics_config["turndown_ratio"] = 0.1

    synloop_config["model_inputs"]["performance_parameters"] = (
        synloop_config["model_inputs"]["performance_parameters"] | dynamics_config
    )

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
    # 2 hours with partial production (from delay) per on/off sequence
    # 12 hours of off-time per on/off sequence
    expected_delay_losses_per_sequence = rated_capacity * 2 * 0.25
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

    elec_consumed = prob.get_val("comp.electricity_consumed", units="kW")
    with subtests.test(f"Electricity consumption for first {n_timesteps_test} timesteps"):
        total_elec_consumed = elec_consumed[:n_timesteps_test].sum()
        nh3_produced = nh3_out[:n_timesteps_test].sum()
        assert pytest.approx(nh3_produced, rel=1e-6) == total_elec_consumed

    # Confirm losses repeat consistently across all full sequence repeats in the sim
    n_repeats = (n_timesteps - 1) // len(on_off_sequence)
    n_check = 1 + n_repeats * len(on_off_sequence)
    with subtests.test(f"Losses over {n_repeats} full sequence repeats ({n_check} timesteps)"):
        nh3_produced_full = nh3_out[:n_check].sum()
        nh3_without_losses_full = nh3_no_dynamics[:n_check].sum()
        expected_full = nh3_without_losses_full - n_repeats * (
            expected_delay_losses_per_sequence + expected_off_time_losses_per_sequence
        )
        assert pytest.approx(nh3_produced_full, rel=1e-6) == expected_full


@pytest.mark.regression
@pytest.mark.parametrize("dt,n_timesteps", [(3600, 40)])
def test_ammonia_moms_cold_soss_warm_start(
    plant_config, synloop_config, dynamics_config, n_timesteps, subtests
):
    # Test when theres both cold start and warm start
    # cold start params, off time of 4 hours, delay time of 2
    # cold start is multidt_offtime_multidt_startup (moms)
    dynamics_config["include_cold_start"] = True
    dynamics_config["off_hours_cold_start"] = 4
    dynamics_config["cold_start_delay_hours"] = 2
    # warm start: off time of 0.5 hrs, delay time of 0.5
    # warm start is subdt_offtime_subdt_startup (soss)
    dynamics_config["include_warm_start"] = True
    dynamics_config["off_hours_warm_start"] = 0.25
    dynamics_config["warm_start_delay_hours"] = 0.5

    dynamics_config["turndown_ratio"] = 0.1

    # NOTE:
    # Both warm and cold start multipliers are derived from the pre-startup reference profile
    # and combined via element-wise multiplication, so the apparent ordering of warm vs cold
    # does not matter. A long cold-start delay no longer creates a "fake" off-event that
    # incorrectly triggers an additional warm-start delay further downstream.
    rated_capacity = synloop_config["model_inputs"]["shared_parameters"]["production_capacity"]

    # Override the defaults set above with values that clearly distinguish the bug.
    dynamics_config["off_hours_cold_start"] = 4
    dynamics_config["cold_start_delay_hours"] = 4
    dynamics_config["off_hours_warm_start"] = 0.5
    dynamics_config["warm_start_delay_hours"] = 1

    synloop_config["model_inputs"]["performance_parameters"] = (
        synloop_config["model_inputs"]["performance_parameters"] | dynamics_config
    )

    min_nh3 = dynamics_config["turndown_ratio"] * rated_capacity

    # 5 hours off, 8 hours on -- long enough for the 4-hr cold delay to fully
    # cover 4 'on' hours and leave 4 'on' hours of full production at the end.
    on_off_sequence = np.concat([np.zeros(5), np.ones(8)])

    nh3_no_dynamics = make_production_sequence(
        min_nh3, rated_capacity, on_off_sequence, n_timesteps, start_on=True
    )
    elec_in = (
        nh3_no_dynamics * synloop_config["model_inputs"]["performance_parameters"]["energy_demand"]
    )

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

    # Expected pattern over first 14 timesteps (t=0..13). Note: off hours are zeroed
    # by the startup multiplier (the model treats below-min_prod input as "off" and
    # forces 0 output during those hours), and the first 4 on-hours after the long off
    # are also zeroed by the 4-hr cold delay:
    #   t=0    : rated (initial 'on')
    #   t=1..5 : 0 (off, multiplier=0)
    #   t=6..9 : 0 (cold delay)
    #   t=10..13: rated
    expected_first = np.concat(
        [np.array([rated_capacity]), np.zeros(9), np.full(4, rated_capacity)]
    )
    with subtests.test("Combined warm+cold start uses original reference profile"):
        assert nh3_out[:14] == pytest.approx(expected_first, abs=1e-9)

    with subtests.test("Only one cold-start delay zone occurs after the long off"):
        # If the bug were present, the cold pass would re-trigger after the warm pass zeroed
        # t=6, producing 5 (not 4) zero on-hours and only 3 (not 4) hours of full production.
        assert (nh3_out[6:14] == 0).sum() == 4
        assert pytest.approx(nh3_out[10:14].sum(), rel=1e-6) == 4 * rated_capacity


@pytest.mark.regression
@pytest.mark.parametrize("dt,n_timesteps", [(3600, 40)])
def test_ammonia_multidt_delay_fraction(
    plant_config, synloop_config, dynamics_config, n_timesteps, subtests
):
    # Similar test to test_ammonia_multidt_offtime_multidt_delay
    # and test_ammonia_subdt_offtime_multidt_delay but with
    # cold_start_delay_hours of 3.25
    # Aka - delay causes full loss for 3 hours and partial loss at hour 4
    rated_capacity = synloop_config["model_inputs"]["shared_parameters"]["production_capacity"]

    dynamics_config["include_cold_start"] = True
    dynamics_config["off_hours_cold_start"] = 2
    dynamics_config["cold_start_delay_hours"] = 3.25
    dynamics_config["turndown_ratio"] = 0.1

    synloop_config["model_inputs"]["performance_parameters"] = (
        synloop_config["model_inputs"]["performance_parameters"] | dynamics_config
    )

    min_nh3 = dynamics_config["turndown_ratio"] * rated_capacity

    # test when its off and when its on
    # off for 2 hours, on for 5 hours, off for 2, on for 3, off for 3, on for 4
    # all shut-offs trigger a start-up delay
    # first start-up has 3 hours without production, 1 hr with partial, fully on for 1 hr
    # second start-up has all 3 hours without production
    # last start-up has 3 hours without production, 1 hr with partial
    # has 7 hours off, 9 hours with zero production due to delay, 2 hours with partial production

    on_off_sequence = np.concat(
        [np.zeros(2), np.ones(5), np.zeros(2), np.ones(3), np.zeros(3), np.ones(4)]
    )

    # starts on
    nh3_no_dynamics = make_production_sequence(
        min_nh3, rated_capacity, on_off_sequence, n_timesteps, start_on=True
    )
    elec_in = (
        nh3_no_dynamics * synloop_config["model_inputs"]["performance_parameters"]["energy_demand"]
    )

    cap_mult = 10.0e3
    n2 = np.full(n_timesteps, 5.0 * cap_mult)
    h2 = np.full(n_timesteps, 2.0 * cap_mult)

    # Create model
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

    # each sequench has:
    # 7 hours off
    expected_off_time_losses_per_sequence = (min_nh3 / 2) * 7
    # 9 hours with zero production due to delay
    expected_full_delay_losses_per_sequence = rated_capacity * 9
    # 2 hours with partial production
    expected_partial_delay_losses_per_sequence = rated_capacity * 2 * 0.25

    nh3_out = prob.get_val("comp.ammonia_out", units="kg/h")

    # checking the first sequence
    n_timesteps_test = int(len(on_off_sequence) + 1)

    with subtests.test(f"Losses for first {n_timesteps_test} timesteps (multidt offtime)"):
        nh3_produced = nh3_out[:n_timesteps_test].sum()
        nh3_without_losses = nh3_no_dynamics[:n_timesteps_test].sum()
        expected_nh3 = nh3_without_losses - (
            expected_full_delay_losses_per_sequence
            + expected_partial_delay_losses_per_sequence
            + expected_off_time_losses_per_sequence
        )
        assert pytest.approx(nh3_produced, rel=1e-6) == expected_nh3

    elec_consumed = prob.get_val("comp.electricity_consumed", units="kW")
    with subtests.test(
        f"Electricity consumption for first {n_timesteps_test} timesteps  (multidt offtime)"
    ):
        total_elec_consumed = elec_consumed[:n_timesteps_test].sum()
        nh3_produced = nh3_out[:n_timesteps_test].sum()
        assert pytest.approx(nh3_produced, rel=1e-6) == total_elec_consumed

    # Confirm losses repeat consistently across full sequence repeats in the multidt-offtime sim
    n_repeats = (n_timesteps - 1) // len(on_off_sequence)
    n_check = 1 + n_repeats * len(on_off_sequence)
    with subtests.test(
        f"Losses over {n_repeats} full sequence repeats ({n_check} timesteps) (multidt offtime)"
    ):
        nh3_produced_full = nh3_out[:n_check].sum()
        nh3_without_losses_full = nh3_no_dynamics[:n_check].sum()
        expected_full = nh3_without_losses_full - n_repeats * (
            expected_full_delay_losses_per_sequence
            + expected_partial_delay_losses_per_sequence
            + expected_off_time_losses_per_sequence
        )
        assert pytest.approx(nh3_produced_full, rel=1e-6) == expected_full

    # Re-run model but for subdt_offtime_multidt_delay case
    # Change the offtime to subdt
    prob.set_val("comp.off_time_cold_start", 0.5, units="h")
    prob.run_model()

    nh3_out_subdtofftime = prob.get_val("comp.ammonia_out", units="kg/h")

    with subtests.test(f"Losses for first {n_timesteps_test} timesteps (subdt offtime)"):
        nh3_produced = nh3_out_subdtofftime[:n_timesteps_test].sum()
        nh3_without_losses = nh3_no_dynamics[:n_timesteps_test].sum()
        expected_nh3 = nh3_without_losses - (
            expected_full_delay_losses_per_sequence
            + expected_partial_delay_losses_per_sequence
            + expected_off_time_losses_per_sequence
        )
        assert pytest.approx(nh3_produced, rel=1e-6) == expected_nh3

    prob.get_val("comp.electricity_consumed", units="kW")
    with subtests.test(
        f"Electricity consumption for first {n_timesteps_test} timesteps (subdt offtime)"
    ):
        total_elec_consumed = elec_consumed[:n_timesteps_test].sum()
        nh3_produced = nh3_out[:n_timesteps_test].sum()
        assert pytest.approx(nh3_produced, rel=1e-6) == total_elec_consumed

    # Confirm losses repeat consistently across full sequence repeats in the sub-dt-offtime sim
    n_repeats = (n_timesteps - 1) // len(on_off_sequence)
    n_check = 1 + n_repeats * len(on_off_sequence)
    with subtests.test(
        f"Losses over {n_repeats} full sequence repeats ({n_check} timesteps) (subdt offtime)"
    ):
        nh3_produced_full = nh3_out_subdtofftime[:n_check].sum()
        nh3_without_losses_full = nh3_no_dynamics[:n_check].sum()
        expected_full = nh3_without_losses_full - n_repeats * (
            expected_full_delay_losses_per_sequence
            + expected_partial_delay_losses_per_sequence
            + expected_off_time_losses_per_sequence
        )
        assert pytest.approx(nh3_produced_full, rel=1e-6) == expected_full


@pytest.mark.regression
@pytest.mark.parametrize("dt,n_timesteps", [(3600, 40)])
def test_ammonia_multidt_offtime_fraction(
    plant_config, synloop_config, dynamics_config, n_timesteps, subtests
):
    # off_hours_cold_start=2.5 with dt=1h means an off-block must be > 2.5 hrs (i.e. >=3 timesteps)
    # to trigger a cold start delay. A 2-hr off block should not.
    rated_capacity = synloop_config["model_inputs"]["shared_parameters"]["production_capacity"]

    dynamics_config["include_cold_start"] = True
    dynamics_config["off_hours_cold_start"] = 2.5
    dynamics_config["cold_start_delay_hours"] = 1
    dynamics_config["turndown_ratio"] = 0.1

    synloop_config["model_inputs"]["performance_parameters"] = (
        synloop_config["model_inputs"]["performance_parameters"] | dynamics_config
    )

    min_nh3 = dynamics_config["turndown_ratio"] * rated_capacity

    # off for 2 (sub-threshold, no startup), on for 3, off for 3 (triggers), on for 4
    on_off_sequence = np.concat([np.zeros(2), np.ones(3), np.zeros(3), np.ones(4)])
    nh3_no_dynamics = make_production_sequence(
        min_nh3, rated_capacity, on_off_sequence, n_timesteps, start_on=True
    )
    elec_in = (
        nh3_no_dynamics * synloop_config["model_inputs"]["performance_parameters"]["energy_demand"]
    )
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

    # Sequence offset by initial 'on' timestep: indices 1..12 carry the first sequence.
    # Off block 1: t=1..2 (2hr, < 2.5hr) -> no startup delay; t=3..5 should be fully on.
    # Off block 2: t=6..8 (3hr, > 2.5hr) -> 1 hr startup delay; t=9 zeroed, t=10..12 fully on.
    with subtests.test("Sub-threshold off block does not trigger cold start delay"):
        assert nh3_out[3:6] == pytest.approx(np.full(3, rated_capacity), rel=1e-6)

    with subtests.test("Over-threshold off block triggers cold start delay"):
        assert nh3_out[9] == pytest.approx(0.0, abs=1e-9)
        assert nh3_out[10:13] == pytest.approx(np.full(3, rated_capacity), rel=1e-6)


@pytest.mark.regression
@pytest.mark.parametrize("dt,n_timesteps", [(3600, 40)])
def test_ammonia_subdt_offtime_start_off(
    plant_config, synloop_config, dynamics_config, n_timesteps, subtests
):
    # Same as test_ammonia_subdt_offtime_subdt_delay but the simulation starts in the 'off' state.
    # The startup delay must still apply on the very first transition from off->on.
    rated_capacity = synloop_config["model_inputs"]["shared_parameters"]["production_capacity"]

    dynamics_config["include_cold_start"] = True
    dynamics_config["off_hours_cold_start"] = 0.5
    dynamics_config["cold_start_delay_hours"] = 0.25
    dynamics_config["turndown_ratio"] = 0.1

    synloop_config["model_inputs"]["performance_parameters"] = (
        synloop_config["model_inputs"]["performance_parameters"] | dynamics_config
    )

    min_nh3 = dynamics_config["turndown_ratio"] * rated_capacity

    on_off_sequence = np.array([0, 1, 1, 1, 0, 0, 1])
    nh3_no_dynamics = make_production_sequence(
        min_nh3, rated_capacity, on_off_sequence, n_timesteps, start_on=False
    )
    elec_in = (
        nh3_no_dynamics * synloop_config["model_inputs"]["performance_parameters"]["energy_demand"]
    )
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

    with subtests.test("Simulation starts in 'off' state (t=0 below min)"):
        assert nh3_out[0] < min_nh3

    with subtests.test("Startup delay applied to first on-transition out of off state"):
        # First on-transition is at t=2 (t=0 starts off, t=1 is also off=min/2).
        # Sub-dt delay of 0.25 hr -> partial loss: rated * (1 - 0.25) = 0.75 * rated.
        expected_partial = rated_capacity * (1.0 - 0.25)
        assert nh3_out[2] == pytest.approx(expected_partial, rel=1e-6)


@pytest.mark.regression
@pytest.mark.parametrize("dt,n_timesteps", [(3600, 40)])
def test_ammonia_ramp_constraints(
    plant_config, synloop_config, dynamics_config, n_timesteps, subtests
):
    rated_capacity = synloop_config["model_inputs"]["shared_parameters"]["production_capacity"]
    # 2 hours to go from 0% to 100%, 1 hr to go from 50% to 100%
    dynamics_config["ramp_up_rate_fraction"] = 0.50
    # 4 hours to go from 100% to 0% or 2 hrs to go from 50% to 0%
    dynamics_config["ramp_down_rate_fraction"] = 0.25

    dynamics_config["include_cold_start"] = False
    dynamics_config["turndown_ratio"] = 0.1

    synloop_config["model_inputs"]["performance_parameters"] = (
        synloop_config["model_inputs"]["performance_parameters"] | dynamics_config
    )

    min_nh3 = dynamics_config["turndown_ratio"] * rated_capacity
    ramp_up_rate_kg = dynamics_config["ramp_up_rate_fraction"] * rated_capacity
    ramp_down_rate_kg = dynamics_config["ramp_down_rate_fraction"] * rated_capacity

    # Make variable profile
    slow_ramp_up = np.arange(0, rated_capacity + ramp_up_rate_kg / 2, ramp_up_rate_kg / 2)
    slow_ramp_down = np.arange(
        rated_capacity, min_nh3 - ramp_down_rate_kg / 2, -1 * ramp_down_rate_kg / 2
    )
    ramp_up = np.arange(0, rated_capacity + ramp_up_rate_kg, ramp_up_rate_kg)
    ramp_down = np.arange(rated_capacity, min_nh3 - ramp_down_rate_kg, -1 * ramp_down_rate_kg)
    quick_ramp_up = np.arange(0, rated_capacity + ramp_up_rate_kg, 2 * ramp_up_rate_kg)
    quick_ramp_down = np.arange(rated_capacity, min_nh3 - ramp_down_rate_kg, -2 * ramp_down_rate_kg)
    nh3_no_dynamics = np.concat(
        [
            slow_ramp_up,
            slow_ramp_down,
            quick_ramp_up,
            quick_ramp_down,
            ramp_up,
            ramp_down,
            quick_ramp_up,
            quick_ramp_down,
            slow_ramp_up,
            quick_ramp_down,
        ]
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
    # check that ramping constraints happen during "quick" ramp-ups and downs
    ramping_down = np.where(np.diff(nh3_out) < 0, -1 * np.diff(nh3_out), 0)
    ramping_up = np.where(np.diff(nh3_out) > 0, np.diff(nh3_out), 0)

    with subtests.test("Check ramping down constraint"):
        assert np.max(ramping_down) == pytest.approx(ramp_down_rate_kg, rel=1e-6)

    with subtests.test("Check ramping up constraint"):
        assert np.max(ramping_up) == pytest.approx(ramp_up_rate_kg, rel=1e-6)

    # No startup events are configured here, so per-step changes must respect the ramp caps
    # over the *entire* simulation -- not just the slow/quick blocks examined above.
    with subtests.test("Ramping constraints respected over full 40 timesteps"):
        diffs = np.diff(nh3_out)
        assert np.max(diffs) <= ramp_up_rate_kg + 1e-6
        assert np.min(diffs) >= -ramp_down_rate_kg - 1e-6


@pytest.mark.regression
@pytest.mark.parametrize("dt,n_timesteps", [(3600, 40)])
def test_ammonia_ramping_and_startup_losses(
    plant_config, synloop_config, dynamics_config, n_timesteps, subtests
):
    # Combined ramping + cold-start losses applied in sequence.
    rated_capacity = synloop_config["model_inputs"]["shared_parameters"]["production_capacity"]

    dynamics_config["include_cold_start"] = True
    dynamics_config["off_hours_cold_start"] = 2
    dynamics_config["cold_start_delay_hours"] = 1
    dynamics_config["turndown_ratio"] = 0.1
    dynamics_config["ramp_up_rate_fraction"] = 0.5
    dynamics_config["ramp_down_rate_fraction"] = 0.5

    synloop_config["model_inputs"]["performance_parameters"] = (
        synloop_config["model_inputs"]["performance_parameters"] | dynamics_config
    )

    min_nh3 = dynamics_config["turndown_ratio"] * rated_capacity
    dynamics_config["ramp_up_rate_fraction"] * rated_capacity

    # off for 3 hours then on for 6 hours -- triggers cold start; ramping caps step changes.
    on_off_sequence = np.concat([np.zeros(3), np.ones(6)])
    nh3_no_dynamics = make_production_sequence(
        min_nh3, rated_capacity, on_off_sequence, n_timesteps, start_on=True
    )
    elec_in = (
        nh3_no_dynamics * synloop_config["model_inputs"]["performance_parameters"]["energy_demand"]
    )
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
    np.abs(np.diff(nh3_out))

    with subtests.test("Cold-start delay observed after off-block"):
        # First on-hour after the 3-hr off block (t=4) should be zeroed by the 1-hr cold delay.
        assert nh3_out[4] == pytest.approx(0.0, abs=1e-9)

    with subtests.test("Ramping cap respected on smooth (no-startup-event) transitions"):
        # NOTE: ramping is applied before start-up losses in the model, so the abrupt
        # transition from a zeroed start-up window back to full production can exceed
        # the per-step ramp cap. Check the ramp cap on the post-startup-recovery region
        # (after the cold delay completes, the profile holds rated for the remaining on-hours).
        # Pick a sub-range that does not span a startup zeroing edge: t=5..8 (all rated post-delay).
        assert pytest.approx(np.max(np.abs(np.diff(nh3_out[5:9]))), 1e-6) == 25.0


@pytest.mark.unit
def test_ammonia_config(synloop_config, dynamics_config, subtests):
    from h2integrate.converters.ammonia.ammonia_synloop_performance import (
        AmmoniaSynLoopPerformanceConfig,
    )

    base = {
        **synloop_config["model_inputs"]["shared_parameters"],
        **synloop_config["model_inputs"]["performance_parameters"],
    }

    with subtests.test("include_cold_start=True without required params raises"):
        bad = base | {
            "include_cold_start": True,
            "off_hours_cold_start": None,
            "cold_start_delay_hours": None,
        }
        with pytest.raises(AttributeError, match="include_cold_start") as excinfo:
            AmmoniaSynLoopPerformanceConfig(**bad)
        # Both missing param names should appear in the error message so a user knows
        # exactly what to add to their tech config.
        assert "off_hours_cold_start" in str(excinfo.value)
        assert "cold_start_delay_hours" in str(excinfo.value)

    with subtests.test("include_cold_start=True with only one missing param lists only that one"):
        bad = base | {
            "include_cold_start": True,
            "off_hours_cold_start": 4.0,
            "cold_start_delay_hours": None,
        }
        with pytest.raises(AttributeError, match="include_cold_start") as excinfo:
            AmmoniaSynLoopPerformanceConfig(**bad)
        assert "cold_start_delay_hours" in str(excinfo.value)
        assert "off_hours_cold_start" not in str(excinfo.value)

    with subtests.test("include_warm_start=True without required params raises"):
        bad = base | {
            "include_warm_start": True,
            "off_hours_warm_start": None,
            "warm_start_delay_hours": None,
        }
        with pytest.raises(AttributeError, match="include_warm_start") as excinfo:
            AmmoniaSynLoopPerformanceConfig(**bad)
        assert "off_hours_warm_start" in str(excinfo.value)
        assert "warm_start_delay_hours" in str(excinfo.value)

    with subtests.test("include_warm_start=True with only one missing param lists only that one"):
        bad = base | {
            "include_warm_start": True,
            "off_hours_warm_start": None,
            "warm_start_delay_hours": 0.5,
        }
        with pytest.raises(AttributeError, match="include_warm_start") as excinfo:
            AmmoniaSynLoopPerformanceConfig(**bad)
        assert "off_hours_warm_start" in str(excinfo.value)
        assert "warm_start_delay_hours" not in str(excinfo.value)

    with subtests.test("turndown_ratio outside [0, 1] is rejected"):
        bad = base | {"turndown_ratio": 1.5}
        with pytest.raises(ValueError):
            AmmoniaSynLoopPerformanceConfig(**bad)

    with subtests.test("ramp_up_rate_fraction outside [0, 1] is rejected"):
        bad = base | {"ramp_up_rate_fraction": -0.1}
        with pytest.raises(ValueError):
            AmmoniaSynLoopPerformanceConfig(**bad)

    with subtests.test("non-positive cold start hours rejected by validator"):
        bad = base | {
            "include_cold_start": True,
            "off_hours_cold_start": -1.0,
            "cold_start_delay_hours": 1.0,
        }
        with pytest.raises(ValueError):
            AmmoniaSynLoopPerformanceConfig(**bad)


@pytest.mark.regression
@pytest.mark.parametrize("dt,n_timesteps", [(3600, 40)])
def test_edge_cases(plant_config, synloop_config, dynamics_config, n_timesteps, subtests):
    rated_capacity = synloop_config["model_inputs"]["shared_parameters"]["production_capacity"]

    # Edge case: dynamics enabled but inputs are always above min_prod -> no losses ever applied.
    dynamics_config["include_cold_start"] = True
    dynamics_config["off_hours_cold_start"] = 2
    dynamics_config["cold_start_delay_hours"] = 1
    dynamics_config["turndown_ratio"] = 0.1
    dynamics_config["ramp_up_rate_fraction"] = 1.0
    dynamics_config["ramp_down_rate_fraction"] = 1.0

    synloop_config["model_inputs"]["performance_parameters"] = (
        synloop_config["model_inputs"]["performance_parameters"] | dynamics_config
    )

    elec_in = np.full(
        n_timesteps,
        rated_capacity * synloop_config["model_inputs"]["performance_parameters"]["energy_demand"],
    )
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
    with subtests.test("Always-on profile incurs no startup losses"):
        assert nh3_out == pytest.approx(np.full(n_timesteps, rated_capacity), rel=1e-6)


@pytest.mark.regression
@pytest.mark.parametrize("dt,n_timesteps", [(1800, 40)])
def test_ammonia_ramping_dt_flexibility(
    plant_config, synloop_config, dynamics_config, n_timesteps, subtests
):
    # With dt=1800s (0.5 h), the per-timestep ramp delta must equal (rate_kg_per_hr * 0.5).
    rated_capacity = synloop_config["model_inputs"]["shared_parameters"]["production_capacity"]

    dynamics_config["ramp_up_rate_fraction"] = 0.5
    dynamics_config["ramp_down_rate_fraction"] = 0.5
    dynamics_config["turndown_ratio"] = 0.1

    synloop_config["model_inputs"]["performance_parameters"] = (
        synloop_config["model_inputs"]["performance_parameters"] | dynamics_config
    )

    dt_hrs = 1800 / 3600
    ramp_rate_per_step = dynamics_config["ramp_up_rate_fraction"] * rated_capacity * dt_hrs

    # Demand a 0 -> rated step change so ramping caps the response.
    elec_in = np.zeros(n_timesteps)
    elec_in[1:] = (
        rated_capacity * synloop_config["model_inputs"]["performance_parameters"]["energy_demand"]
    )
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

    nh3_out = prob.get_val("comp.ammonia_out", units=f"kg/({dt_hrs}*h)")
    step_changes = np.abs(np.diff(nh3_out))

    with subtests.test("Per-timestep ramp delta scales with dt (dt=1800s -> half hourly rate)"):
        assert np.max(step_changes) <= ramp_rate_per_step + 1e-6


@pytest.mark.regression
@pytest.mark.parametrize("dt,n_timesteps", [(3600, 20)])
def test_ammonia_turndown_enforced_without_startup(
    plant_config, synloop_config, dynamics_config, n_timesteps, subtests
):
    # Turndown should function as a hard "minimum production while on" floor even
    # when no start-up dynamics are configured: any demand below the floor must
    # cause the plant to shut off (output=0) rather than passing through as
    # sub-turndown production.
    rated_capacity = synloop_config["model_inputs"]["shared_parameters"]["production_capacity"]

    dynamics_config["turndown_ratio"] = 0.3
    dynamics_config["ramp_up_rate_fraction"] = 1.0
    dynamics_config["ramp_down_rate_fraction"] = 1.0
    # Explicitly leave include_cold_start / include_warm_start False.

    synloop_config["model_inputs"]["performance_parameters"] = (
        synloop_config["model_inputs"]["performance_parameters"] | dynamics_config
    )

    dynamics_config["turndown_ratio"] * rated_capacity

    # Build a profile that holds steady at a sub-turndown level for several hours,
    # bracketed by full-rated production.
    sub_floor = 0.1 * rated_capacity  # below the 0.3 turndown floor
    demand = np.concat(
        [
            np.full(3, rated_capacity),
            np.full(4, sub_floor),
            np.full(n_timesteps - 7, rated_capacity),
        ]
    )
    elec_in = demand * synloop_config["model_inputs"]["performance_parameters"]["energy_demand"]
    cap_mult = 10.0e3
    n2 = np.full(n_timesteps, 5.0 * cap_mult)
    h2 = np.full(n_timesteps, 2.0 * cap_mult)

    prob = om.Problem()
    comp = AmmoniaSynLoopPerformanceModel(
        plant_config=plant_config, tech_config=synloop_config, driver_config={}
    )
    prob.model.add_subsystem("comp", comp, promotes=["*"])
    prob.setup()
    prob.set_val("comp.hydrogen_in", h2, units="kg/h")
    prob.set_val("comp.nitrogen_in", n2, units="kg/h")
    prob.set_val("comp.electricity_in", elec_in, units="kW")
    prob.run_model()

    nh3_out = prob.get_val("comp.ammonia_out", units="kg/h")

    with subtests.test("Sub-turndown demand is forced to 0 (plant shuts off)"):
        assert np.all(nh3_out[3:7] == pytest.approx(0.0, abs=1e-9))

    with subtests.test("Above-turndown demand passes through unchanged"):
        assert np.all(nh3_out[:3] == pytest.approx(rated_capacity, abs=1e-9))
        assert np.all(nh3_out[7:] == pytest.approx(rated_capacity, abs=1e-9))

    with subtests.test("Feedstock consumption is also zero during sub-turndown shutoff"):
        elec_consumed = prob.get_val("comp.electricity_consumed", units="kW")
        assert np.all(elec_consumed[3:7] == pytest.approx(0.0, abs=1e-9))


@pytest.mark.regression
@pytest.mark.parametrize("dt,n_timesteps", [(3600, 20)])
def test_ammonia_warm_cold_mutual_exclusion(
    plant_config, synloop_config, dynamics_config, n_timesteps, subtests
):
    # When both warm and cold are configured and a single off-block qualifies for
    # both, only the cold-start delay should apply -- the warm-start pass must not
    # extend the penalty downstream when its delay is longer than cold's.
    rated_capacity = synloop_config["model_inputs"]["shared_parameters"]["production_capacity"]

    # Cold delay (1 hr) is shorter than the warm delay (3 hrs) here, so the bug
    # before mutual exclusion would cause the long off-block to be penalized for
    # the longer warm delay (max(cold, warm) = 3 hrs of zero) instead of the
    # cold-start-only delay (1 hr of zero).
    dynamics_config["include_cold_start"] = True
    dynamics_config["off_hours_cold_start"] = 4
    dynamics_config["cold_start_delay_hours"] = 1
    dynamics_config["include_warm_start"] = True
    dynamics_config["off_hours_warm_start"] = 0.5
    dynamics_config["warm_start_delay_hours"] = 3
    dynamics_config["turndown_ratio"] = 0.1

    synloop_config["model_inputs"]["performance_parameters"] = (
        synloop_config["model_inputs"]["performance_parameters"] | dynamics_config
    )

    # 5-hr off block (qualifies as cold), then 8-hr on. With mutual exclusion the
    # off-block is claimed by cold so only the 1-hr cold delay applies.
    on_off_sequence = np.concat([np.zeros(5), np.ones(8)])
    min_nh3 = dynamics_config["turndown_ratio"] * rated_capacity
    nh3_no_dynamics = make_production_sequence(
        min_nh3, rated_capacity, on_off_sequence, n_timesteps, start_on=True
    )
    elec_in = (
        nh3_no_dynamics * synloop_config["model_inputs"]["performance_parameters"]["energy_demand"]
    )
    cap_mult = 10.0e3
    n2 = np.full(n_timesteps, 5.0 * cap_mult)
    h2 = np.full(n_timesteps, 2.0 * cap_mult)

    prob = om.Problem()
    comp = AmmoniaSynLoopPerformanceModel(
        plant_config=plant_config, tech_config=synloop_config, driver_config={}
    )
    prob.model.add_subsystem("comp", comp, promotes=["*"])
    prob.setup()
    prob.set_val("comp.hydrogen_in", h2, units="kg/h")
    prob.set_val("comp.nitrogen_in", n2, units="kg/h")
    prob.set_val("comp.electricity_in", elec_in, units="kW")
    prob.run_model()

    nh3_out = prob.get_val("comp.ammonia_out", units="kg/h")

    # Layout: t=0 rated (initial on), t=1..5 off (zero), t=6 cold delay (zero),
    # t=7..13 rated. If the warm pass had also claimed the long off-block, we would
    # see zeros at t=6,7,8 instead of just t=6.
    with subtests.test("Long off-block is penalized only by cold delay (1 hr zero)"):
        assert nh3_out[6] == pytest.approx(0.0, abs=1e-9)
        assert nh3_out[7] == pytest.approx(rated_capacity, abs=1e-9)
        assert nh3_out[8] == pytest.approx(rated_capacity, abs=1e-9)

    with subtests.test("Off-steps stay zero"):
        assert np.all(nh3_out[1:6] == pytest.approx(0.0, abs=1e-9))


@pytest.mark.regression
@pytest.mark.parametrize("dt,n_timesteps", [(3600, 20)])
def test_ammonia_warm_start_still_applies_to_short_off_blocks(
    plant_config, synloop_config, dynamics_config, n_timesteps, subtests
):
    # Mutual exclusion should not silence the warm-start pass for off-blocks that
    # are shorter than the cold-start threshold. A 1-hr off-block should still
    # trigger the warm-start delay when warm is configured.
    rated_capacity = synloop_config["model_inputs"]["shared_parameters"]["production_capacity"]

    dynamics_config["include_cold_start"] = True
    dynamics_config["off_hours_cold_start"] = 4
    dynamics_config["cold_start_delay_hours"] = 2
    dynamics_config["include_warm_start"] = True
    dynamics_config["off_hours_warm_start"] = 0.5
    dynamics_config["warm_start_delay_hours"] = 1
    dynamics_config["turndown_ratio"] = 0.1

    synloop_config["model_inputs"]["performance_parameters"] = (
        synloop_config["model_inputs"]["performance_parameters"] | dynamics_config
    )

    # Single 1-hr off-block (warm-qualifying, sub-cold-threshold) embedded in a
    # mostly-on profile.
    demand = np.full(n_timesteps, rated_capacity)
    demand[5] = 0.0
    elec_in = demand * synloop_config["model_inputs"]["performance_parameters"]["energy_demand"]
    cap_mult = 10.0e3
    n2 = np.full(n_timesteps, 5.0 * cap_mult)
    h2 = np.full(n_timesteps, 2.0 * cap_mult)

    prob = om.Problem()
    comp = AmmoniaSynLoopPerformanceModel(
        plant_config=plant_config, tech_config=synloop_config, driver_config={}
    )
    prob.model.add_subsystem("comp", comp, promotes=["*"])
    prob.setup()
    prob.set_val("comp.hydrogen_in", h2, units="kg/h")
    prob.set_val("comp.nitrogen_in", n2, units="kg/h")
    prob.set_val("comp.electricity_in", elec_in, units="kW")
    prob.run_model()

    nh3_out = prob.get_val("comp.ammonia_out", units="kg/h")

    with subtests.test("Short off-block triggers warm-start delay (1 hr zero)"):
        assert nh3_out[5] == pytest.approx(0.0, abs=1e-9)
        assert nh3_out[6] == pytest.approx(0.0, abs=1e-9)
        assert nh3_out[7] == pytest.approx(rated_capacity, abs=1e-9)
