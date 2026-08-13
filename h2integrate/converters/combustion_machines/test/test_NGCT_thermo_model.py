import numpy as np
import pytest
import pyfluids

from h2integrate.converters.combustion_machines.thermo_tools import (
    ThermodynamicCycleResult,
    compute_heat_transfer,
    make_humid_air_mixture,
    compute_turbine_work_rate,
    compute_compressor_work_rate,
    humidity_ratio_to_water_mass_fraction,
    compute_isentropic_expansion_outlet_state,
    compute_isentropic_compression_outlet_state,
)
from h2integrate.converters.combustion_machines.NGCT_thermo_model import (
    NGCT,
    GE_7FA05_NGCT,
    GE_7EA_NGCT_2014,
)


@pytest.fixture(scope="module")
def iso_conditions():
    return {
        "pressure": 101325.0,
        "temperature": 15.0,
        "relative_humidity": 60.0,
    }


@pytest.fixture(scope="module")
def iso_ambient_state(iso_conditions):
    working_fluid = make_humid_air_mixture(
        iso_conditions["pressure"],
        iso_conditions["temperature"],
        iso_conditions["relative_humidity"],
    )
    return working_fluid.with_state(
        pyfluids.Input.pressure(iso_conditions["pressure"]),
        pyfluids.Input.temperature(iso_conditions["temperature"]),
    )


@pytest.fixture(scope="module")
def basic_ngct():
    return NGCT(
        ratio_P=15.0,
        Trel_firing=1300.0,
        isentropic_efficiency_compressor=0.85,
        isentropic_efficiency_turbine=0.90,
        Q_fluid_max=1.0,
    )


@pytest.fixture(scope="module")
def ge_7fa05():
    return GE_7FA05_NGCT()


@pytest.fixture(scope="module")
def ge_7ea_2014():
    return GE_7EA_NGCT_2014()


@pytest.fixture(
    params=[
        {"pressure": 101325.0, "temperature": 0.0, "relative_humidity": 40.0},
        {"pressure": 101325.0, "temperature": 35.0, "relative_humidity": 80.0},
        {"pressure": 80000.0, "temperature": 15.0, "relative_humidity": 60.0},
    ]
)
def varied_ambient_state(request):
    conditions = request.param
    working_fluid = make_humid_air_mixture(
        conditions["pressure"],
        conditions["temperature"],
        conditions["relative_humidity"],
    )
    return working_fluid.with_state(
        pyfluids.Input.pressure(conditions["pressure"]),
        pyfluids.Input.temperature(conditions["temperature"]),
    )


@pytest.mark.unit
def test_humidity_ratio_to_water_mass_fraction_roundtrip():
    humidity_ratio = 0.015
    water_mass_fraction = humidity_ratio_to_water_mass_fraction(humidity_ratio)
    recovered_humidity_ratio = water_mass_fraction / (1.0 - water_mass_fraction)

    assert water_mass_fraction == pytest.approx(0.014778325123152709)
    assert recovered_humidity_ratio == pytest.approx(humidity_ratio)


@pytest.mark.unit
def test_make_humid_air_mixture_builds_valid_state(iso_conditions):
    working_fluid = make_humid_air_mixture(
        iso_conditions["pressure"],
        iso_conditions["temperature"],
        iso_conditions["relative_humidity"],
    )
    fluid_ambient = working_fluid.with_state(
        pyfluids.Input.pressure(iso_conditions["pressure"]),
        pyfluids.Input.temperature(iso_conditions["temperature"]),
    )

    assert np.isfinite(fluid_ambient.density)
    assert np.isfinite(fluid_ambient.enthalpy)
    assert np.isfinite(fluid_ambient.entropy)
    assert fluid_ambient.density > 0.0
    assert fluid_ambient.pressure == pytest.approx(iso_conditions["pressure"])
    assert fluid_ambient.temperature == pytest.approx(iso_conditions["temperature"])


@pytest.mark.unit
def test_compressor_outlet_state_isentropic_preserves_entropy(iso_ambient_state):
    ratio_p = 12.6
    compressed = compute_isentropic_compression_outlet_state(iso_ambient_state, ratio_p)

    assert compressed.pressure == pytest.approx(iso_ambient_state.pressure * ratio_p)
    assert compressed.entropy == pytest.approx(iso_ambient_state.entropy, rel=1e-6, abs=1e-3)
    assert compressed.temperature > iso_ambient_state.temperature


@pytest.mark.unit
def test_turbine_outlet_state_isentropic_preserves_entropy(iso_ambient_state):
    combusted = iso_ambient_state.with_state(
        pyfluids.Input.pressure(iso_ambient_state.pressure * 12.6),
        pyfluids.Input.temperature(1300.0),
    )
    exhaust = compute_isentropic_expansion_outlet_state(combusted, 12.6)

    assert exhaust.pressure == pytest.approx(combusted.pressure / 12.6)
    assert exhaust.entropy == pytest.approx(combusted.entropy, rel=1e-6, abs=1e-3)
    assert exhaust.temperature < combusted.temperature


@pytest.mark.unit
def test_helper_sign_conventions(iso_ambient_state):
    compressed = compute_isentropic_compression_outlet_state(iso_ambient_state, 10.0)
    combusted = compressed.with_state(
        pyfluids.Input.pressure(compressed.pressure),
        pyfluids.Input.temperature(1300.0),
    )
    exhaust = compute_isentropic_expansion_outlet_state(combusted, 10.0)

    wdot_compressor = compute_compressor_work_rate(
        iso_ambient_state, compressed, isentropic_efficiency=0.85
    )
    wdot_turbine = compute_turbine_work_rate(combusted, exhaust, isentropic_efficiency=0.90)
    qdot_combustor = compute_heat_transfer(compressed, combusted)
    qdot_exhaust = compute_heat_transfer(exhaust, iso_ambient_state)

    assert wdot_compressor < 0.0
    assert wdot_turbine > 0.0
    assert qdot_combustor > 0.0
    assert qdot_exhaust < 0.0


@pytest.mark.unit
def test_ngct_result_aggregates_cycle_quantities(iso_ambient_state):
    result = ThermodynamicCycleResult(desc="synthetic cycle")
    for index in range(1, 5):
        result.add_state(index, iso_ambient_state, f"state {index}")

    result.mass_flowrate = 5.0
    result.add_process(1, 2, -10.0, 0.0, "compressor")
    result.add_process(2, 3, 0.0, 30.0, "combustor")
    result.add_process(3, 4, 20.0, 0.0, "turbine")
    result.add_process(4, 1, 0.0, -5.0, "cooler")

    assert result.get_net_work() == pytest.approx(50.0)
    assert result.get_net_heat_input() == pytest.approx(150.0)
    assert result.get_net_heat_rejection() == pytest.approx(-25.0)
    assert result.get_back_work_ratio() == pytest.approx(0.5)
    assert result.get_efficiency() == pytest.approx(1.0 / 3.0)


@pytest.mark.integration
def test_run_turbine_model_singleton_matches_batch_result(ge_7ea_2014, iso_ambient_state):
    result_single = ge_7ea_2014.run_turbine_model(iso_ambient_state)
    result_batch = ge_7ea_2014.run_turbine_model([iso_ambient_state])[0]

    assert result_single.mass_flowrate == pytest.approx(result_batch.mass_flowrate)
    assert result_single.get_net_work() == pytest.approx(result_batch.get_net_work())
    assert result_single.get_efficiency() == pytest.approx(result_batch.get_efficiency())
    assert result_single.states[4].temperature == pytest.approx(result_batch.states[4].temperature)


@pytest.mark.regression
def test_run_turbine_model_applies_minimum_mass_flow_constraint(basic_ngct, iso_ambient_state):
    unconstrained = basic_ngct.run_turbine_model(iso_ambient_state)
    specific_net_work = unconstrained.get_net_work() / unconstrained.mass_flowrate
    specific_heat_input = unconstrained.process_heat_unit[(2, 3)]

    power_limit = 0.75 * unconstrained.get_net_work()
    heat_limit = 0.60 * unconstrained.get_net_heat_input()

    constrained = basic_ngct.run_turbine_model(
        iso_ambient_state,
        power_rated=power_limit,
        heatrate_fuel_capacity=heat_limit,
    )

    expected_mass_flowrate = min(
        unconstrained.mass_flowrate,
        power_limit / specific_net_work,
        heat_limit / specific_heat_input,
    )

    assert constrained.mass_flowrate == pytest.approx(expected_mass_flowrate)


@pytest.mark.regression
def test_ge_7fa05_iso_design_point_regression(ge_7fa05, iso_ambient_state):
    result = ge_7fa05.run_turbine_model(iso_ambient_state)

    assert result.get_efficiency() == pytest.approx(
        ge_7fa05.design_conditions["eta_th_ISO"],
        rel=0.05,
    )
    assert result.get_net_work() == pytest.approx(
        ge_7fa05.design_conditions["W_net_ISO"],
        rel=0.08,
    )
    assert result.states[4].temperature > iso_ambient_state.temperature


# @pytest.mark.regression
# def test_ge_7ea_2014_iso_design_point_regression(ge_7ea_2014, iso_ambient_state):
# 	result = ge_7ea_2014.run_turbine_model(iso_ambient_state)
#
# 	assert result.get_efficiency() == pytest.approx(
# 		ge_7ea_2014.design_conditions["eta_th_ISO"],
# 		rel=0.05,
# 	)
# 	assert result.get_net_work() == pytest.approx(
# 		ge_7ea_2014.design_conditions["W_net_ISO"],
# 		rel=0.08,
# 	)
# 	assert result.states[4].temperature > iso_ambient_state.temperature


@pytest.mark.integration
def test_ideal_brayton_cycle_energy_balance(iso_ambient_state):
    ideal_ngct = NGCT(
        ratio_P=15.0,
        Trel_firing=1300.0,
        isentropic_efficiency_compressor=1.0,
        isentropic_efficiency_turbine=1.0,
        Q_fluid_max=1.0,
    )
    result = ideal_ngct.run_turbine_model(iso_ambient_state)
    net_heat = result.get_net_heat_input() + result.get_net_heat_rejection()

    assert result.get_net_work() == pytest.approx(net_heat, rel=1e-9)


@pytest.mark.integration
def test_varied_ambient_conditions_produce_finite_outputs(ge_7ea_2014, varied_ambient_state):
    result = ge_7ea_2014.run_turbine_model(varied_ambient_state)

    assert np.isfinite(result.mass_flowrate)
    assert np.isfinite(result.get_net_work())
    assert np.isfinite(result.get_efficiency())
    assert 0.0 < result.get_efficiency() < 1.0
