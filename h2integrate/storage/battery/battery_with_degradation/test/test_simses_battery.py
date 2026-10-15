"""Tests for the container/HVAC-equipped SimSESBatteryPerformanceModel.

Short component tests use synthetic weather. Integration coverage includes a two-year
state-continuity check and notebook-aligned one-year regressions using bundled Denver
weather, both at the component and full H2Integrate system level.
"""

from pathlib import Path

import numpy as np
import pandas as pd
import pytest
import openmdao.api as om

from h2integrate import RESOURCE_DEFAULT_DIR, H2IntegrateModel
from h2integrate.core.file_utils import load_yaml
from h2integrate.storage.battery.battery_with_degradation.simses_battery import (
    SimSESBatteryPerformanceModel,
    SimSESBatteryPerformanceModelConfig,
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


def _plant_config(n_timesteps, dt=3600, start_time="01/01 00:00:00", timezone=0):
    return {
        "plant": {
            "plant_life": 30,
            "simulation": {
                "n_timesteps": n_timesteps,
                "dt": dt,
                "start_time": start_time,
                "timezone": timezone,
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


def _build_problem(
    n_timesteps,
    dt=3600,
    power_profile=None,
    performance_overrides=None,
    start_time="01/01 00:00:00",
    timezone=0,
):
    """Build an OpenMDAO problem with a single SimSESBatteryPerformanceModel subsystem.

    Latitude/longitude are connected via a site IndepVarComp (required since those
    inputs use ``require_connection=True``). The ``solar_resource_data`` discrete
    input is left at its default empty dict; set it via ``prob.set_val`` after
    ``setup()`` if the test needs ambient temperature/GHI data.
    """
    if power_profile is None:
        power_profile = np.zeros(n_timesteps)

    prob = om.Problem()
    ivc = om.IndepVarComp()
    ivc.add_output("electricity_command_value", val=power_profile, units="kW")
    ivc.add_output("electricity_in", val=np.full(n_timesteps, 1.0e6), units="kW")
    prob.model.add_subsystem("ivc", ivc, promotes=["*"])
    site_ivc = om.IndepVarComp()
    site_ivc.add_output("latitude", val=39.7392, units="deg")
    site_ivc.add_output("longitude", val=-104.9903, units="deg")
    prob.model.add_subsystem("site", site_ivc, promotes=["*"])
    prob.model.add_subsystem(
        "battery",
        SimSESBatteryPerformanceModel(
            plant_config=_plant_config(n_timesteps, dt, start_time, timezone),
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


def _notebook_power_profile(n_timesteps, dt):
    usable_energy_wh = 336 * 3.2 * 280 * 16 * 0.8
    t_mid = (np.arange(n_timesteps) + 0.5) * dt
    time_of_day = t_mid % 86400
    power_profile_w = np.where(
        time_of_day < 2 * 3600,
        -0.5 * usable_energy_wh,
        np.where(time_of_day < 12 * 3600, 0.1 * usable_energy_wh, 0.0),
    )
    return -power_profile_w / 1000.0


def _notebook_weather_year_inputs(dt):
    n_timesteps = 365 * 24 * 3600 // dt
    weather_path = RESOURCE_DEFAULT_DIR / "solar" / "Denver_weather_2009_h2i.csv"
    weather = pd.read_csv(weather_path, header=2)
    weather.index = pd.to_datetime(weather[["Year", "Month", "Day", "Hour", "Minute"]], utc=True)
    weather = weather.rename(columns={"Temperature": "air_temp", "GHI": "ghi"})[["air_temp", "ghi"]]
    last_timestamp = weather.index.max()
    dynamic_end = last_timestamp + pd.Timedelta(seconds=3600) - pd.Timedelta(seconds=1)
    weather_index = pd.date_range(
        start=weather.index.min(), end=dynamic_end, freq=pd.Timedelta(seconds=dt)
    )
    weather = weather.reindex(weather_index)
    numeric_columns = weather.select_dtypes(include=["number"]).columns
    weather[numeric_columns] = weather[numeric_columns].interpolate(
        method="time", fill_value="extrapolate"
    )
    return n_timesteps, weather, _notebook_power_profile(n_timesteps, dt)


def _assert_notebook_weather_year_outputs(prob, dt, subtests):
    final_soh_capacity = prob.get_val("battery.soh_capacity")[-1]
    final_soh_resistance = prob.get_val("battery.soh_resistance")[-1]
    with subtests.test("final capacity SOH matches notebook"):
        assert final_soh_capacity == pytest.approx(0.992751, abs=5e-5)
    with subtests.test("final resistance SOH matches notebook"):
        assert final_soh_resistance == pytest.approx(1.002277, abs=5e-5)

    battery_temperature = prob.get_val("battery.temperature", units="degC")
    with subtests.test("maximum battery temperature matches notebook"):
        assert battery_temperature.max() == pytest.approx(30.06, abs=0.1)
    with subtests.test("minimum battery temperature matches notebook"):
        assert battery_temperature.min() == pytest.approx(18.70, abs=0.1)
    degree_hours_above = np.maximum(battery_temperature - 30.0, 0.0).sum() * dt / 3600
    degree_hours_below = np.maximum(20.0 - battery_temperature, 0.0).sum() * dt / 3600
    with subtests.test("upper-bound degree hours match notebook"):
        assert degree_hours_above == pytest.approx(1.2363, abs=0.1)
    with subtests.test("lower-bound degree hours match notebook"):
        assert degree_hours_below == pytest.approx(30.2573, abs=0.1)

    power_ac = prob.get_val("battery.power_ac", units="W")
    power_dc = prob.get_val("battery.power_dc", units="W")
    energy_mwh = {
        "auxiliary": np.abs(prob.get_val("battery.electricity_auxiliary_demand")).sum()
        * dt
        / 3.6e6,
        "thermal": np.abs(prob.get_val("battery.hvac_thermal_power", units="W")).sum() * dt / 3.6e9,
        "ac": np.abs(power_ac).sum() * dt / 3.6e9,
        "dc": np.abs(power_dc).sum() * dt / 3.6e9,
        "converter_loss": np.abs(prob.get_val("battery.converter_loss", units="W")).sum()
        * dt
        / 3.6e9,
        "ac_charge": np.maximum(power_ac, 0.0).sum() * dt / 3.6e9,
        "ac_discharge": np.maximum(-power_ac, 0.0).sum() * dt / 3.6e9,
        "dc_charge": np.maximum(power_dc, 0.0).sum() * dt / 3.6e9,
        "dc_discharge": np.maximum(-power_dc, 0.0).sum() * dt / 3.6e9,
    }
    notebook_energy_mwh = {
        "auxiliary": 2.877530,
        "thermal": 11.900800,
        "ac": 2694.079170,
        "dc": 2691.465556,
        "converter_loss": 109.909076,
        "ac_charge": 1406.533632,
        "ac_discharge": 1287.545538,
        "dc_charge": 1350.272287,
        "dc_discharge": 1341.193269,
    }
    for name, expected in notebook_energy_mwh.items():
        with subtests.test(f"{name} energy matches notebook"):
            assert energy_mwh[name] == pytest.approx(expected, abs=0.5)


@pytest.mark.unit
def test_config_defaults():
    config = SimSESBatteryPerformanceModelConfig.from_dict(SHARED_PARAMETERS, strict=False)

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


@pytest.mark.integration
def test_multiyear_simulation_preserves_state_and_annual_discharge():
    steps_per_year = 8760
    n_timesteps = 2 * steps_per_year
    hour_of_day = np.arange(n_timesteps) % 24
    power_profile = np.zeros(n_timesteps)
    power_profile[hour_of_day < 2] = -500.0
    power_profile[(hour_of_day >= 12) & (hour_of_day < 14)] = 500.0
    power_profile[steps_per_year:] *= 0.5
    prob = _build_problem(
        n_timesteps=n_timesteps,
        dt=3600,
        power_profile=power_profile,
        performance_overrides={"deg_scale": 0.01, "eol_soh_capacity": 0.0},
    )
    _set_resource(prob, n_timesteps=n_timesteps)
    prob.run_model()

    for name in ("SOC", "temperature", "soh_capacity", "soh_resistance", "power_ac"):
        values = prob.get_val(f"battery.{name}")
        assert values.shape == (n_timesteps,)
        assert np.all(np.isfinite(values))

    soh = prob.get_val("battery.soh_capacity")
    assert soh[steps_per_year] <= soh[steps_per_year - 1]
    assert soh[-1] < soh[steps_per_year - 1] < soh[0]

    discharge = prob.get_val("battery.storage_electricity_discharge", units="kW")
    annual_discharge = discharge.reshape(2, steps_per_year).sum(axis=1)
    assert annual_discharge[0] > annual_discharge[1] > 0.0
    rated_discharge = prob.get_val("battery.rated_electricity_production", units="kW")[0]
    annual_production = prob.get_val("battery.annual_electricity_produced", units="kW*h/year")
    standard_cf = prob.get_val("battery.standard_capacity_factor", units="unitless")
    net_cf = prob.get_val("battery.capacity_factor", units="unitless")
    replacements = prob.get_val("battery.replacement_schedule")
    for values in (annual_production, standard_cf, net_cf, replacements):
        assert values.shape == (30,)
        assert np.all(np.isfinite(values))
    np.testing.assert_allclose(annual_production[:2], annual_discharge)
    np.testing.assert_allclose(
        standard_cf[:2], annual_discharge / (rated_discharge * steps_per_year)
    )
    np.testing.assert_allclose(annual_production, standard_cf * rated_discharge * steps_per_year)
    net_power = prob.get_val("battery.electricity_out", units="kW")
    np.testing.assert_allclose(
        prob.get_val("battery.total_electricity_produced", units="kW*h")[0],
        net_power.sum(),
    )


@pytest.mark.integration
def test_notebook_weather_year_regression(subtests):
    dt = 60
    n_timesteps, weather, power_profile_kw = _notebook_weather_year_inputs(dt)
    with subtests.test("resampled notebook weather covers one year"):
        assert len(weather) == n_timesteps

    prob = _build_problem(
        n_timesteps,
        dt=dt,
        power_profile=power_profile_kw,
        start_time="2009-01-01 07:00:00",
        timezone=0,
    )
    prob.set_val(
        "battery.solar_resource_data",
        {
            "temperature": weather["air_temp"].to_numpy(),
            "ghi": weather["ghi"].to_numpy(),
        },
    )
    prob.run_model()

    _assert_notebook_weather_year_outputs(prob, dt, subtests)


@pytest.mark.integration
def test_notebook_weather_year_full_h2i_system(subtests):
    dt = 60
    n_timesteps = 365 * 24 * 3600 // dt
    power_profile_kw = _notebook_power_profile(n_timesteps, dt)
    example_dir = Path(__file__).resolve().parents[5] / "examples" / "38_battery_degradation"
    config = load_yaml(example_dir / "38_battery_degradation.yaml")
    for key in ("driver_config", "technology_config", "plant_config"):
        config[key] = load_yaml(example_dir / config[key])

    config["driver_config"].setdefault("general", {})["create_om_reports"] = False
    plant_config = config["plant_config"]
    battery_tech = config["technology_config"]["technologies"]["battery"]
    battery_tech.pop("control_strategy")
    battery_tech["model_inputs"].pop("control_parameters")
    plant_config.pop("tech_to_dispatch_connections")
    plant_config["plant"]["simulation"].update(
        {
            "dt": dt,
            "n_timesteps": n_timesteps,
            "start_time": "2009-01-01 07:00:00",
            "timezone": 0,
        }
    )
    plant_config["sites"]["site"].update({"latitude": 39.7392, "longitude": -104.9903})
    resource_parameters = plant_config["sites"]["site"]["resources"]["solar_resource"][
        "resource_parameters"
    ]
    resource_parameters.clear()
    resource_parameters.update(
        {
            "resource_year": 2009,
            "resource_filename": "Denver_weather_2009_h2i.csv",
            "upsample_method": "time",
        }
    )

    h2i = H2IntegrateModel(config)
    h2i.setup()
    h2i.prob.set_val("battery.electricity_set_point", power_profile_kw, units="kW")
    h2i.run()

    _assert_notebook_weather_year_outputs(h2i.prob, dt, subtests)
