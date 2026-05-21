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
    with subtests.test(f"Electricity consumption loss for first {n_timesteps_test} timesteps"):
        elec_losses = (elec_in[:n_timesteps_test] - elec_consumed[:n_timesteps_test]).sum()
        assert pytest.approx(expected_off_time_losses_per_sequence, rel=1e-6) == elec_losses


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

    with subtests.test(f"Electricity consumption loss for first {n_timesteps_test} timesteps"):
        elec_losses = (elec_in[:n_timesteps_test] - elec_consumed[:n_timesteps_test]).sum()
        assert pytest.approx(expected_off_time_losses_per_sequence, rel=1e-6) == elec_losses


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
    with subtests.test(f"Electricity consumption loss for first {n_timesteps_test} timesteps"):
        elec_losses = (elec_in[:n_timesteps_test] - elec_consumed[:n_timesteps_test]).sum()
        assert pytest.approx(expected_off_time_losses_per_sequence, rel=1e-6) == elec_losses


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
    with subtests.test(f"Electricity consumption loss for first {n_timesteps_test} timesteps"):
        elec_losses = (elec_in[:n_timesteps_test] - elec_consumed[:n_timesteps_test]).sum()
        assert pytest.approx(expected_off_time_losses_per_sequence, rel=1e-6) == elec_losses


@pytest.mark.regression
@pytest.mark.parametrize("dt,n_timesteps", [(3600, 40)])
def test_ammonia_moms_cold_soss_warm_start(
    plant_config, synloop_config, dynamics_config, n_timesteps, subtests
):
    # Test when theres both cold start and warm start
    # TODO: add test in
    # cold start params, off time of 4 hours, delay time of 2
    # cold start is multi_offtime_multi_startup (moms)
    dynamics_config["include_cold_start"] = True
    dynamics_config["off_hours_cold_start"] = 4
    dynamics_config["cold_start_delay_hours"] = 2
    # warm start: off time of 0.5 hrs, delay time of 0.5
    # warm start is subdt_offtime_subdt_startup (soss)
    dynamics_config["include_warm_start"] = True
    dynamics_config["off_hours_warm_start"] = 0.25
    dynamics_config["warm_start_delay_hours"] = 0.5

    dynamics_config["turndown_ratio"] = 0.1
    pass


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
        f"Electricity consumption loss for first {n_timesteps_test} timesteps  (multidt offtime)"
    ):
        elec_losses = (elec_in[:n_timesteps_test] - elec_consumed[:n_timesteps_test]).sum()
        assert pytest.approx(expected_off_time_losses_per_sequence, rel=1e-6) == elec_losses

    # Re-run model but for subdt_offtime_multidt_delay case
    # Change the offtime to subdt
    # Then re-run
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

    elec_consumed_subdtofftime = prob.get_val("comp.electricity_consumed", units="kW")
    with subtests.test(
        f"Electricity consumption loss for first {n_timesteps_test} timesteps (subdt offtime)"
    ):
        elec_losses = (
            elec_in[:n_timesteps_test] - elec_consumed_subdtofftime[:n_timesteps_test]
        ).sum()
        assert pytest.approx(expected_off_time_losses_per_sequence, rel=1e-6) == elec_losses


@pytest.mark.regression
@pytest.mark.parametrize("dt,n_timesteps", [(3600, 40)])
def test_ammonia_multidt_offtime_fraction(
    plant_config, synloop_config, dynamics_config, n_timesteps, subtests
):
    # TODO: add test in similar to test_ammonia_multidt_offtime_multidt_delay
    # and test_ammonia_multidt_offtime_subdt_delay but with
    # off_hours_cold_start of 2.5 hrs
    # should have to be off for 3 hrs to trigger start-up delay

    pass


@pytest.mark.regression
@pytest.mark.parametrize("dt,n_timesteps", [(3600, 40)])
def test_ammonia_subdt_offtime_start_off(
    plant_config, synloop_config, dynamics_config, n_timesteps, subtests
):
    # TODO: add test(s) similar to test_ammonia_subdt_offtime_subdt_delay
    # and test_ammonia_subdt_offtime_multidt_delay but start with off

    # nh3_no_dynamics = make_production_sequence(
    #     min_nh3, rated_capacity, on_off_sequence, n_timesteps, start_on=False
    # )
    pass


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

    with subtests.test("Check ramping up constraint"):  # failed
        assert np.max(ramping_up) == pytest.approx(ramp_up_rate_kg, rel=1e-6)


@pytest.mark.regression
@pytest.mark.parametrize("dt,n_timesteps", [(3600, 40)])
def test_ammonia_ramping_and_startup_losses(
    plant_config, synloop_config, dynamics_config, n_timesteps, subtests
):
    # TODO: add a test with ramping constraints and start-up losses
    # bonus points if the ramping constraint would result in additional
    # start-up delay losses
    pass


@pytest.mark.unit
def test_ammonia_config(synloop_config, dynamics_config, subtests):
    # TODO: add tests to check error raising in synloop config
    pass


@pytest.mark.regression
@pytest.mark.parametrize("dt,n_timesteps", [(3600, 40)])
def test_edge_cases(plant_config, synloop_config, dynamics_config, n_timesteps, subtests):
    # TODO: add test in with ramping constraints

    pass
