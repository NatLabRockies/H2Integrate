import pytest

from h2integrate.reliability.models import SimulationConfig


@pytest.mark.unit
def test_SimulationConfig(subtests):
    """Tests basic parameterizations of ``SimulationConfig`` and the time-based
    utilities functions: ``calculate_simulation_years``, ``calculate_annual_timesteps``,
    and ``calculate_hourly_timesteps``.
    """
    with subtests.test("Standard 8760"):
        config = {"dt": 3600, "n_timesteps": 8760}
        sim = SimulationConfig.from_dict(config)
        assert sim.dt == config["dt"]
        assert sim.n_timesteps == config["n_timesteps"]
        assert sim.n_timesteps_in_year == 8760
        assert sim.n_timesteps_in_hour == 1
        assert sim.simulation_years == 1

    with subtests.test("Hourly 1/2 year"):
        config = {"dt": 3600, "n_timesteps": 8760 / 2}
        sim = SimulationConfig.from_dict(config)
        assert sim.dt == config["dt"]
        assert sim.n_timesteps == config["n_timesteps"]
        assert sim.n_timesteps_in_year == 8760
        assert sim.n_timesteps_in_hour == 1
        assert sim.simulation_years == 0.5

    with subtests.test("Minutely 2 years"):
        config = {"dt": 60, "n_timesteps": 8760 * 60 * 2}
        sim = SimulationConfig.from_dict(config)
        assert sim.dt == config["dt"]
        assert sim.n_timesteps == config["n_timesteps"]
        assert sim.n_timesteps_in_year == 8760 * 60
        assert sim.n_timesteps_in_hour == 60
        assert sim.simulation_years == 2

    with subtests.test("Daily 1/2 year shows hourly limitation"):
        config = {"dt": 3600 * 24, "n_timesteps": 365 / 2}
        sim = SimulationConfig.from_dict(config)
        assert sim.dt == config["dt"]
        assert sim.n_timesteps == config["n_timesteps"]
        assert sim.n_timesteps_in_year == 365
        assert sim.n_timesteps_in_hour == 1
        assert sim.simulation_years == 0.5
