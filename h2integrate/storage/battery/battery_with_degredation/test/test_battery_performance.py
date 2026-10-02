"""Unit tests for the container/HVAC-equipped BatteryPerformanceModel.

These tests exercise the model directly (short, synthetic resource data sized to
match n_timesteps exactly) rather than through a full H2IntegrateModel/example run,
since matching the notebook's actual multi-year weather resource requires the
resource-resampling / arbitrary-duration updates that are still in progress. Once
those land, add regression tests pinning the notebook's full-horizon numeric
results (final SOH_Q/SOH_R, degree-hours outside the safe range, energy totals).
"""

import numpy as np
import pytest
import openmdao.api as om

from h2integrate.storage.battery.battery_with_degredation.battery_performance import (
    BatteryPerformanceModel,
    BatteryPerformanceModelConfig,
)


SHARED_PARAMETERS = {
    "commodity": "electricity",
    "commodity_rate_units": "kW",
    "max_charge_rate": 2000.0,
    "max_discharge_rate": 2000.0,
    "charge_equals_discharge": True,
    "max_capacity": 3854.0,
    "max_soc_fraction": 0.9,
    "min_soc_fraction": 0.1,
    "init_soc_fraction": 0.9,
    "charge_efficiency": 1.0,
    "discharge_efficiency": 1.0,
    "demand_profile": 0.0,
}


def _plant_config(n_timesteps, dt=3600):
    return {
        "plant": {
            "plant_life": 30,
            "simulation": {
                "n_timesteps": n_timesteps,
                "dt": dt,
                "start_time": "01/01 00:00:00",
                "timezone": 0,
            },
        }
    }


def _tech_config(**performance_overrides):
    return {
        "model_inputs": {
            "shared_parameters": dict(SHARED_PARAMETERS),
            "performance_parameters": performance_overrides,
        }
    }


def _build_problem(n_timesteps, dt=3600, power_profile=None, performance_overrides=None):
    """Build an OpenMDAO problem with a single BatteryPerformanceModel subsystem.

    Latitude/longitude are connected via a site IndepVarComp (required since those
    inputs use ``require_connection=True``). The ``solar_resource_data`` discrete
    input is left at its default empty dict; set it via ``prob.set_val`` after
    ``setup()`` if the test needs ambient temperature/GHI data.
    """
    if power_profile is None:
        power_profile = np.zeros(n_timesteps)

    prob = om.Problem()
    prob.model.add_subsystem(
        "ivc",
        om.IndepVarComp("electricity_command_value", val=power_profile, units="kW"),
        promotes=["*"],
    )
    site_ivc = om.IndepVarComp()
    site_ivc.add_output("latitude", val=39.7392, units="deg")
    site_ivc.add_output("longitude", val=-104.9903, units="deg")
    prob.model.add_subsystem("site", site_ivc, promotes=["*"])
    prob.model.add_subsystem(
        "battery",
        BatteryPerformanceModel(
            plant_config=_plant_config(n_timesteps, dt),
            tech_config=_tech_config(**(performance_overrides or {})),
        ),
        promotes=["*"],
    )
    prob.setup()
    return prob


def _set_resource(prob, n_timesteps, temperature_c=25.0, ghi=0.0):
    prob.set_val(
        "battery.solar_resource_data",
        {
            "temperature": np.full(n_timesteps, temperature_c),
            "ghi": np.full(n_timesteps, ghi),
        },
    )


@pytest.mark.unit
def test_config_defaults():
    config = BatteryPerformanceModelConfig.from_dict(SHARED_PARAMETERS, strict=False)

    assert config.deg_scale == pytest.approx(0.115)
    assert config.eol_soh_capacity == pytest.approx(0.8)
    assert config.hvac_cop_cooling_nominal == pytest.approx(3.2)
    assert config.hvac_cop_heating_nominal == pytest.approx(3.8)
    assert config.hvac_max_power == pytest.approx(12.0)
    assert config.thermostat_setpoint == pytest.approx(25.0)
    assert config.thermostat_deadband == pytest.approx(5.0)
    assert config.thermal_substep_max == pytest.approx(60.0)
    assert config.azimuth == pytest.approx(0.0)
    assert config.battery_temp_safe_lower == pytest.approx(15.0)
    assert config.battery_temp_safe_upper == pytest.approx(45.0)


@pytest.mark.unit
def test_missing_resource_data_raises():
    n_timesteps = 4
    prob = _build_problem(n_timesteps)
    # solar_resource_data left at its default empty dict (never set).
    with pytest.raises(ValueError, match="ambient temperature and GHI data"):
        prob.run_model()


@pytest.mark.unit
def test_thermal_interlock_zeros_power_when_battery_too_hot():
    n_timesteps = 3
    power_profile = np.full(n_timesteps, 500.0)  # kW, constant discharge command
    prob = _build_problem(
        n_timesteps,
        power_profile=power_profile,
        # Start above the default battery_temp_safe_upper (45 degC).
        performance_overrides={"battery_temperature_c": 50.0},
    )
    _set_resource(prob, n_timesteps, temperature_c=25.0, ghi=0.0)
    prob.run_model()

    assert prob.get_val("battery.system_derated")[0] == pytest.approx(1.0)
    assert prob.get_val("battery.electricity_out", units="kW")[0] == pytest.approx(0.0, abs=1e-6)


@pytest.mark.unit
def test_hvac_heats_when_battery_is_cold():
    n_timesteps = 2
    prob = _build_problem(
        n_timesteps,
        # Below the thermostat's heating threshold (setpoint 25 - deadband 5 = 20 degC)
        # but above battery_temp_safe_lower (15 degC), so only HVAC heating engages.
        performance_overrides={"battery_temperature_c": 18.0},
    )
    _set_resource(prob, n_timesteps, temperature_c=18.0, ghi=0.0)
    prob.run_model()

    assert prob.get_val("battery.hvac_thermal_power", units="W")[0] > 0.0
    assert prob.get_val("battery.hvac_electrical_power", units="W")[0] > 0.0


@pytest.mark.unit
def test_solar_heat_gain_is_zero_at_night():
    n_timesteps = 2
    prob = _build_problem(n_timesteps)
    _set_resource(prob, n_timesteps, temperature_c=25.0, ghi=0.0)
    prob.run_model()

    assert np.allclose(prob.get_val("battery.solar_heat_gain", units="W"), 0.0)


@pytest.mark.unit
def test_output_shapes_match_n_timesteps():
    n_timesteps = 5
    prob = _build_problem(n_timesteps)
    _set_resource(prob, n_timesteps, temperature_c=25.0, ghi=0.0)
    prob.run_model()

    for name in (
        "voltage",
        "temperature",
        "container_air_temperature",
        "container_wall_temperature_inner",
        "container_wall_temperature_mid",
        "container_wall_temperature_outer",
        "solar_heat_gain",
        "system_derated",
    ):
        assert prob.get_val(f"battery.{name}").shape == (n_timesteps,)
