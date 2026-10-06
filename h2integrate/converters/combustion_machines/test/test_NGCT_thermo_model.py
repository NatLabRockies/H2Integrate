import importlib

import numpy as np
import pytest


try:
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
    from h2integrate.converters.combustion_machines.NGCT_thermo_model import NGCT
except ModuleNotFoundError:
    pass


# GE 7FA.05 in simple-cycle operation. Values come from a mix of fact- and
# data-sheet performance descriptions, textbook assumptions, and
# reverse-engineering targeting the ISO performance at the design conditions.
GE_7FA05_NGCT_INPUTS = {
    "ratio_P": 18.712850988834695,  # -, by reverse-engineering from datasheet
    "Trel_firing": 1300.0,  # deg C, by textbook assumption
    "isentropic_efficiency_compressor": 0.85,  # -, by textbook assumption
    "isentropic_efficiency_turbine": 0.90,  # -, by textbook assumption
    "Q_fluid_max": 477.78734437019483,  # m**3/s, by reverse-engineering from datasheet
}
GE_7FA05_NGCT_DESIGN_CONDITIONS = {
    "P_ISO": 101325.0,  # Pa, ISO conditions
    "T_ISO": 288.15,  # K, ISO conditions
    "rel_humidity_ISO": 60.0,  # %, ISO conditions
    "eta_th_ISO": 0.385,  # -, from GE factsheet for 7F.05
    "W_net_ISO": 239.0e3,  # kW, from GE factsheet for 7F.05
}

# GE 7EA in simple-cycle operation. Matching is middling and the information on
# the turbine is very old.
GE_7EA_NGCT_2014_INPUTS = {
    "ratio_P": 12.6,  # -, from NYISO GE factsheet
    "Trel_firing": 1300.0,  # deg C, by textbook assumption
    "isentropic_efficiency_compressor": 0.85,  # -, by textbook assumption
    "isentropic_efficiency_turbine": 0.90,  # -, by textbook assumption
    "Q_fluid_max": 238.3673469388,  # m**3/s, from NYISO GE factsheet
}
GE_7EA_NGCT_2014_DESIGN_CONDITIONS = {
    "P_ISO": 101325.0,  # Pa, ISO conditions
    "T_ISO": 288.15,  # K, ISO conditions
    "rel_humidity_ISO": 60.0,  # %, ISO conditions
    "eta_th_ISO": 0.3275,  # -, from GE factsheet for 7EA
    "W_net_ISO": 85.4e3,  # kW, from GE factsheet for 7EA
}


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
    return NGCT(**GE_7FA05_NGCT_INPUTS)


@pytest.fixture(scope="module")
def ge_7ea_2014():
    return NGCT(**GE_7EA_NGCT_2014_INPUTS)


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
@pytest.mark.skipif(
    importlib.util.find_spec("pyfluids") is None, reason="thermo modules are not installed"
)
def test_humidity_ratio_to_water_mass_fraction_roundtrip():
    humidity_ratio = 0.015
    water_mass_fraction = humidity_ratio_to_water_mass_fraction(humidity_ratio)
    recovered_humidity_ratio = water_mass_fraction / (1.0 - water_mass_fraction)

    assert water_mass_fraction == pytest.approx(0.014778325123152709)
    assert recovered_humidity_ratio == pytest.approx(humidity_ratio)


@pytest.mark.unit
@pytest.mark.skipif(
    importlib.util.find_spec("pyfluids") is None, reason="thermo modules are not installed"
)
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
@pytest.mark.skipif(
    importlib.util.find_spec("pyfluids") is None, reason="thermo modules are not installed"
)
def test_compressor_outlet_state_isentropic_preserves_entropy(iso_ambient_state):
    ratio_p = 12.6
    compressed = compute_isentropic_compression_outlet_state(iso_ambient_state, ratio_p)

    assert compressed.pressure == pytest.approx(iso_ambient_state.pressure * ratio_p)
    assert compressed.entropy == pytest.approx(iso_ambient_state.entropy, rel=1e-6, abs=1e-3)
    assert compressed.temperature > iso_ambient_state.temperature


@pytest.mark.unit
@pytest.mark.skipif(
    importlib.util.find_spec("pyfluids") is None, reason="thermo modules are not installed"
)
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
@pytest.mark.skipif(
    importlib.util.find_spec("pyfluids") is None, reason="thermo modules are not installed"
)
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
@pytest.mark.skipif(
    importlib.util.find_spec("pyfluids") is None, reason="thermo modules are not installed"
)
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
@pytest.mark.skipif(
    importlib.util.find_spec("pyfluids") is None, reason="thermo modules are not installed"
)
def test_run_turbine_model_returns_one_result_per_ambient_state(ge_7ea_2014, iso_ambient_state):
    results = ge_7ea_2014.run_turbine_model([iso_ambient_state, iso_ambient_state])

    assert isinstance(results, list)
    assert len(results) == 2
    assert results[0].mass_flowrate == pytest.approx(results[1].mass_flowrate)
    assert results[0].get_net_work() == pytest.approx(results[1].get_net_work())
    assert results[0].get_efficiency() == pytest.approx(results[1].get_efficiency())
    assert results[0].states[4].temperature == pytest.approx(results[1].states[4].temperature)


@pytest.mark.regression
@pytest.mark.skipif(
    importlib.util.find_spec("pyfluids") is None, reason="thermo modules are not installed"
)
def test_run_turbine_model_applies_minimum_mass_flow_constraint(basic_ngct, iso_ambient_state):
    unconstrained = basic_ngct.run_turbine_model([iso_ambient_state])[0]
    specific_net_work = unconstrained.get_net_work() / unconstrained.mass_flowrate
    specific_heat_input = unconstrained.process_heat_unit[(2, 3)]

    power_limit = 0.75 * unconstrained.get_net_work()
    heat_limit = 0.60 * unconstrained.get_net_heat_input()

    constrained = basic_ngct.run_turbine_model(
        [iso_ambient_state],
        power_rated=power_limit,
        heatrate_fuel_capacity=heat_limit,
    )[0]

    expected_mass_flowrate = min(
        unconstrained.mass_flowrate,
        power_limit / specific_net_work,
        heat_limit / specific_heat_input,
    )

    assert constrained.mass_flowrate == pytest.approx(expected_mass_flowrate)


@pytest.mark.regression
@pytest.mark.skipif(
    importlib.util.find_spec("pyfluids") is None, reason="thermo modules are not installed"
)
def test_ge_7fa05_iso_design_point_regression(ge_7fa05, iso_ambient_state):
    result = ge_7fa05.run_turbine_model([iso_ambient_state])[0]

    assert result.get_efficiency() == pytest.approx(
        GE_7FA05_NGCT_DESIGN_CONDITIONS["eta_th_ISO"],
        rel=0.05,
    )
    assert result.get_net_work() == pytest.approx(
        GE_7FA05_NGCT_DESIGN_CONDITIONS["W_net_ISO"],
        rel=0.08,
    )
    assert result.states[4].temperature > iso_ambient_state.temperature


@pytest.mark.regression
@pytest.mark.skipif(
    importlib.util.find_spec("pyfluids") is None, reason="thermo modules are not installed"
)
def test_demo_case(ge_7ea_2014):
    P_ambient = 101325.0  # Pa
    Trel_ambient = 15.0  # Pa
    rel_humidity_ambient = 60

    working_fluid = make_humid_air_mixture(P_ambient, Trel_ambient, rel_humidity_ambient)
    fluid_ambient = working_fluid.with_state(
        pyfluids.Input.pressure(P_ambient),
        pyfluids.Input.temperature(Trel_ambient),
    )

    result = ge_7ea_2014.run_turbine_model([fluid_ambient])[0]

    net_work = result.get_net_work()
    net_heat_input = result.get_net_heat_input()
    efficiency = net_work / net_heat_input
    exhaust_temperature = result.states[4].temperature

    print(f"net work: {net_work}")
    print(f"net heat input: {net_heat_input}")
    print(f"efficiency: {efficiency}")
    print(f"exhaust temperature: {exhaust_temperature}")

    net_work_ref = 119869.90666935727
    net_heat_input_ref = 331489.32714693167
    efficiency_ref = 0.3616101540917041
    exhaust_temperature_ref = 571.4635913592466

    assert net_work == pytest.approx(net_work_ref, rel=1.0e-6)
    assert net_heat_input == pytest.approx(net_heat_input_ref, rel=1.0e-6)
    assert efficiency == pytest.approx(efficiency_ref, rel=1.0e-6)
    assert exhaust_temperature == pytest.approx(exhaust_temperature_ref, rel=1.0e-6)


@pytest.mark.integration
@pytest.mark.skipif(
    importlib.util.find_spec("pyfluids") is None, reason="thermo modules are not installed"
)
def test_ideal_brayton_cycle_energy_balance(iso_ambient_state):
    ideal_ngct = NGCT(
        ratio_P=15.0,
        Trel_firing=1300.0,
        isentropic_efficiency_compressor=1.0,
        isentropic_efficiency_turbine=1.0,
        Q_fluid_max=1.0,
    )
    result = ideal_ngct.run_turbine_model([iso_ambient_state])[0]
    net_heat = result.get_net_heat_input() + result.get_net_heat_rejection()

    assert result.get_net_work() == pytest.approx(net_heat, rel=1e-9)


@pytest.mark.integration
@pytest.mark.skipif(
    importlib.util.find_spec("pyfluids") is None, reason="thermo modules are not installed"
)
def test_varied_ambient_conditions_produce_finite_outputs(ge_7ea_2014, varied_ambient_state):
    result = ge_7ea_2014.run_turbine_model([varied_ambient_state])[0]

    assert np.isfinite(result.mass_flowrate)
    assert np.isfinite(result.get_net_work())
    assert np.isfinite(result.get_efficiency())
    assert 0.0 < result.get_efficiency() < 1.0
