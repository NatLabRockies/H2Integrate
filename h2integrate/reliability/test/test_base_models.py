import numpy as np
import pytest
import numpy.testing as npt
from attrs import field, define, validators

from h2integrate.reliability.models import BaseDowntime, BaseReliability, SimulationConfig
from h2integrate.core.array_validators import to_array
from h2integrate.reliability.utilities import update_dimensions


@pytest.mark.unit
def test_SimulationConfig(subtests):
    """Tests basic parameterizations of ``SimulationConfig``."""
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


@define
class IncompleteDowntime(BaseDowntime):
    hours: int = field()


@define
class DiscretelyIncompleteDowntime(BaseDowntime):
    hours: int = field()

    def sample_downtime(self):
        return np.ones((1, 100), dtype=int) * self.hours


@define
class SimpleDowntime(BaseDowntime):
    hours: int = field(
        converter=to_array(int, (-1, 1)),
        validator=validators.instance_of(np.ndarray),
    )

    def __attrs_post_init__(self):
        """Post initialization hook to correct the dimensionality of inputs."""
        self.n_components, self.hours = update_dimensions(self.n_components, self.hours)

    def sample_downtime(self):
        """Samples the time to downtime duration for 100 events."""
        return np.ones((1, 100), dtype=int) * self.hours


@pytest.mark.unit
def test_base_downtime(subtests):
    """Tests the ``BaseDowntime`` class and provides a demonstration of correct minimal form."""
    with subtests.test("Obviously bad routines fail"):
        missing_msg = "without an implementation for abstract method 'sample_downtime'"
        with pytest.raises(TypeError, match=missing_msg):
            BaseDowntime()

        config = {"hours": 2, "simulation": {"dt": 3600, "n_timesteps": 8760}}
        with pytest.raises(TypeError, match=missing_msg):
            IncompleteDowntime.from_dict(config)

    with subtests.test("Missing post initialization hook causes misconfiguration"):
        config = {"hours": 3, "n_components": 2, "simulation": {"dt": 3600, "n_timesteps": 8760}}
        downtime = DiscretelyIncompleteDowntime.from_dict(config)
        assert downtime.hours == config["hours"]
        assert downtime.simulation.dt == config["simulation"]["dt"]
        assert downtime.simulation.n_timesteps == config["simulation"]["n_timesteps"]
        assert downtime.n_components == config["n_components"]

    with subtests.test("Correct implementation"):
        config = {"hours": 3, "n_components": 2, "simulation": {"dt": 3600, "n_timesteps": 8760}}
        downtime = SimpleDowntime.from_dict(config)
        assert all(downtime.hours == config["hours"])
        assert downtime.hours.shape == (2, 1)
        assert downtime.simulation.dt == config["simulation"]["dt"]
        assert downtime.simulation.n_timesteps == config["simulation"]["n_timesteps"]
        assert downtime.n_components == config["n_components"]

        durations = downtime.sample_downtime()
        correct_durations = np.ones((config["n_components"], 100)) * config["hours"]
        npt.assert_array_equal(durations, correct_durations)


@define
class IncompleteReliability(BaseReliability):
    hours: int = field()


@define
class DiscretelyIncompleteReliability(BaseReliability):
    hours: int = field()

    def sample_events(self):
        return np.ones((1, 100), dtype=int) * self.hours


@define
class SimpleReliability(BaseReliability):
    hours: int = field(
        converter=to_array(int, (-1, 1)),
        validator=validators.instance_of(np.ndarray),
    )

    def __attrs_post_init__(self):
        """Post initialization hook to correct the dimensionality of inputs and run the models."""
        super().__attrs_post_init__()
        self.n_components, self.hours = update_dimensions(self.n_components, self.hours)

        self.create_downtime_events()
        self.calculate_availability()

    def sample_events(self):
        """Samples the time to next downtime event for 100 events."""
        return np.ones((1, 100), dtype=int) * self.hours


@pytest.mark.unit
def test_base_reliability(subtests):
    """Tests the ``BaseReliability`` class and provides a demonstration of correct minimal form."""
    with subtests.test("Obviously bad routines fail"):
        missing_msg = "without an implementation for abstract method 'sample_events'"
        with pytest.raises(TypeError, match=missing_msg):
            BaseReliability()

        config = {
            "hours": 2,
            "availability_type": "minimum",
            "downtime": {"model": "FixedDowntime", "hours": 2},
            "simulation": {"dt": 3600, "n_timesteps": 8760},
        }
        with pytest.raises(TypeError, match=missing_msg):
            IncompleteReliability.from_dict(config)

    with subtests.test("Missing base parameterizations cause failure"):
        config = {
            "hours": [200, 2000],
            "n_components": 2,
        }
        msg = r"missing the following inputs: \['availability_type', 'downtime', 'simulation'\]"
        with pytest.raises(AttributeError, match=msg):
            DiscretelyIncompleteReliability.from_dict(config)

    with subtests.test("Missing post initialization hook causes misconfiguration"):
        config = {
            "hours": [200, 2000],
            "n_components": 3,
            "availability_type": "minimum",
            "downtime": {"model": "FixedDowntime", "hours": 2},
            "simulation": {"dt": 3600, "n_timesteps": 8760},
        }
        reliability = DiscretelyIncompleteReliability.from_dict(config)
        assert reliability.hours == config["hours"]
        assert reliability.n_components == config["n_components"]

        # non-problematic checks
        assert reliability.simulation.dt == config["simulation"]["dt"]
        assert reliability.simulation.n_timesteps == config["simulation"]["n_timesteps"]
        assert reliability.availability_type == "minimum"
        assert reliability.burn_in == 0
        assert isinstance(reliability.downtime, BaseDowntime)  # Checked thoroughly in test_models
        assert getattr(reliability, "time_to_failures", None) is None
        assert getattr(reliability, "downtime_per_event", None) is None
        assert getattr(reliability, "availability", None) is None
        assert getattr(reliability, "system_availability", None) is None

    with subtests.test("Correct implementation"):
        config = {
            "hours": [200, 2000],
            "n_components": 3,
            "availability_type": "minimum",
            "downtime": {"model": "FixedDowntime", "hours": 2},
            "simulation": {"dt": 3600, "n_timesteps": 8760},
        }
        base_hours = np.array([[200], [2000]])
        reliability = SimpleReliability.from_dict(config)

        npt.assert_array_equal(reliability.hours, base_hours)
        assert reliability.simulation.dt == config["simulation"]["dt"]
        assert reliability.simulation.n_timesteps == config["simulation"]["n_timesteps"]
        assert reliability.n_components == len(config["hours"])

        assert reliability.availability_type == "minimum"
        assert reliability.burn_in == 0
        assert isinstance(reliability.downtime, BaseDowntime)  # Checked thoroughly in test_models

        # First
        # npt.assert_array_equal(reliability.time_to_failures, np.ones((2, 99), dtype=int) * base_hours)  # noqa: E501
        # npt.assert_array_equal(reliability.downtime_per_event, )
        # npt.assert_array_equal(reliability.availability, )
        # npt.assert_array_equal(reliability.system_availability, )

        # correct_durations = np.ones((config["n_components"], 100)) * config["hours"]
        # npt.assert_array_equal(durations, correct_durations)
