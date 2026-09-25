import sys
from copy import deepcopy

import numpy as np
import pytest
import numpy.testing as npt
from attrs import field, define, validators

from h2integrate.reliability.models import (
    BaseDowntime,
    FixedDowntime,
    BaseReliability,
    UniformDowntime,
    SimulationConfig,
    LogNormalDowntime,
    WeibullReliability,
    PerformanceReliability,
    FixedIntervalReliability,
)
from h2integrate.core.array_validators import to_array
from h2integrate.reliability.utilities import update_dimensions


PY_MINOR_VERSION = int(sys.version.split(".")[1])


# NOTE: If you add a new model, ensure it's added to the appropriate mapping
downtime_models = {
    "FixedDowntime": FixedDowntime,
    "UniformDowntime": UniformDowntime,
    "LogNormalDowntime": LogNormalDowntime,
}
reliability_models = {
    "WeibullReliability": WeibullReliability,
    "FixedIntervalReliability": FixedIntervalReliability,
}


# NOTE: If you added a model above, add a minimal, 1-component configuration for it
minimal_model_config = {
    "reliability": {
        "WeibullReliability": {"scale": 1, "shape": 10},
        "FixedIntervalReliability": {"frequency": 100},
    },
    "downtime": {
        "FixedDowntime": {"hours": 1},
        "UniformDowntime": {"min_hours": 1, "max_hours": 10},
        "LogNormalDowntime": {"mean": 1, "sigma": 2},
    },
}


# Ensure all models get the same number of components and simulation configuration for initial tests
standard_config = {"n_components": 4, "simulation": {"dt": 3600, "n_timesteps": 8760}}
for name in minimal_model_config["reliability"]:
    minimal_model_config["reliability"][name] |= standard_config | {"availability_type": "minimum"}

for name in minimal_model_config["downtime"]:
    minimal_model_config["downtime"][name] |= standard_config


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
        msg_312_plus = "without an implementation for abstract method 'sample_downtime'"
        msg_311 = r"Can't instantiate abstract class (.*) with abstract method sample_downtime"
        missing_msg = msg_311 if PY_MINOR_VERSION < 12 else msg_312_plus
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
        self.n_components, self.hours = update_dimensions(self.n_components, self.hours)
        super().__attrs_post_init__()

    def sample_events(self):
        """Samples the time to next downtime event for 100 events."""
        return np.ones((1, 100), dtype=int) * self.hours


@pytest.mark.unit
def test_base_reliability(subtests):
    """Tests the ``BaseReliability`` class and provides a demonstration of correct minimal form."""
    with subtests.test("Obviously bad routines fail"):
        msg_312_plus = "without an implementation for abstract method 'sample_events'"
        msg_311 = r"Can't instantiate abstract class (.*) with abstract method sample_events"
        missing_msg = msg_311 if PY_MINOR_VERSION < 12 else msg_312_plus
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
        assert getattr(reliability, "component_availability", None) is None
        assert getattr(reliability, "system_availability", None) is None

        msg = r"operands could not be broadcast together with shapes \(1,100\) \(2,\)"
        with pytest.raises(ValueError, match=msg):
            reliability.run()

    with subtests.test("Mismatched n_components fail"):
        config = {
            "hours": [200, 2000, 20000],
            "n_components": 3,
            "availability_type": "minimum",
            "downtime": {"model": "FixedDowntime", "hours": [2, 3]},
            "simulation": {"dt": 3600, "n_timesteps": 8760},
        }
        msg = "Reliability and their downtime models must have the same 'n_components': 3 != 2"
        with pytest.raises(ValueError, match=msg):
            SimpleReliability.from_dict(config)

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


@pytest.mark.regression
def test_base_reliability_results(subtests):
    """Tests the ``BaseReliability`` class results against a basic setup."""
    config = {
        "hours": [200, 2000],
        "n_components": 3,
        "availability_type": "minimum",
        "downtime": {"model": "FixedDowntime", "hours": 2},
        "simulation": {"dt": 3600, "n_timesteps": 8760},
    }
    base_hours = np.array([[200], [2000]])
    reliability = SimpleReliability.from_dict(config)
    reliability.run()

    with subtests.test("Check array shapes for iterations until completion"):
        remaining_samples = 56  # 100 - 44 [ceiling of 8760 / (200 + 2)]
        base_remainder = np.ones((2, remaining_samples), dtype=int)
        remaining_to_failure = base_remainder * base_hours
        remaining_downtime = base_remainder * config["downtime"]["hours"]
        npt.assert_array_equal(reliability.time_to_failures, remaining_to_failure)
        print(reliability.downtime_per_event)
        npt.assert_array_equal(reliability.downtime_per_event, remaining_downtime)

    # Manually calculate where the downtime events are supposed to occur for each
    # of the components and test for correctness
    with subtests.test("Check component-level availabilities"):
        n_events1 = 43  # 44 ensures we're past the 8760 end point, so 43 actual events
        avail1 = np.ones(8760)
        i = 0
        events = 0
        while (start := i + 200) < 8760:
            start = i + 200
            end = start + 2
            avail1[start:end] = 0
            i = end
            events += 1
        assert events == n_events1
        assert avail1.sum() == 8760 - n_events1 * 2

        n_events2 = np.floor(8760 / (2000 + 2))
        avail2 = np.ones(8760)
        i = 0
        events = 0
        while (start := i + 2000) < 8760:
            start = i + 2000
            end = start + 2
            avail2[start:end] = 0
            i = end
            events += 1
        assert events == n_events2
        assert avail2.sum() == 8760 - n_events2 * 2

    with subtests.test("Check total availability"):
        expected_component_availability = np.vstack((avail1, avail2))
        assert reliability.component_availability.shape == (2, 8760)
        assert np.all(reliability.component_availability >= 0)
        assert np.all(reliability.component_availability <= 1)
        npt.assert_array_equal(reliability.component_availability, expected_component_availability)

        expected_system_availability = np.min(expected_component_availability, axis=0)
        assert reliability.system_availability.shape == (8760,)
        assert np.all(reliability.system_availability >= 0)
        assert np.all(reliability.system_availability <= 1)
        npt.assert_array_equal(reliability.system_availability, expected_system_availability)


@pytest.mark.unit
def test_PerformanceReliability(subtests):
    """Tests the ``PerformanceReliability`` initialization and a basic setup."""
    availability_config = {"availability_type": "minimum"}
    simulation_config = {"simulation": {"dt": 3600, "n_timesteps": 8760}}
    base_config = availability_config | simulation_config
    failure_config = {
        "simulation": {"dt": 3600, "n_timesteps": 8760},
        "failure_model": "SimpleReliability",
        "failure_parameters": {
            "hours": 2000,
            "n_components": 3,
            "availability_type": "minimum",
            "downtime": {"model": "FixedDowntime", "hours": 2},
        },
    }
    maintenance_config = {
        "simulation": {"dt": 3600, "n_timesteps": 8760},
        "maintenance_model": "SimpleReliability",
        "maintenance_parameters": {
            "hours": 200,
            "n_components": 3,
            "availability_type": "minimum",
            "downtime": {"model": "FixedDowntime", "hours": 1},
        },
    }
    with subtests.test("Check minimal specification for defaults"):
        msg = r"missing the following inputs: \['availability_type'\]"
        with pytest.raises(AttributeError, match=msg):
            PerformanceReliability.from_dict(simulation_config)

        reliability = PerformanceReliability.from_dict(base_config)
        assert reliability.availability_type == "minimum"
        assert reliability.n_components == 1
        assert reliability.burn_in == 0
        assert reliability.failure_model is None
        assert reliability.failure_parameters is None
        assert reliability.failures is None
        assert reliability.maintenance_model is None
        assert reliability.maintenance_parameters is None
        assert reliability.maintenance is None
        assert isinstance(reliability.simulation, SimulationConfig)
        assert reliability.simulation.dt == base_config["simulation"]["dt"]
        assert reliability.simulation.n_timesteps == base_config["simulation"]["n_timesteps"]

        assert reliability.run() is None  # run should run nothing without failure
        npt.assert_array_equal(
            reliability.availability, np.ones(reliability.simulation.n_timesteps)
        )

    config = {
        "simulation": {"dt": 3600, "n_timesteps": 8760},
        "use_reliability": False,
        "availability_type": "fractional",
        "burn_in": 6.5,
        "failure_model": "WeibullReliability",
        "maintenance_model": "FixedIntervalReliability",
        "failure_parameters": {
            "scale": 0.5,
            "shape": 1,
            "n_components": 3,
            "downtime": {
                "model": "FixedDowntime",
                "hours": 5,
                "n_components": 3,
            },
        },
        "maintenance_parameters": {
            "frequency": [0.25, 1, 4],
            "n_components": 3,
            "downtime": {
                "model": "FixedDowntime",
                "hours": 5,
                "n_components": 1,
            },
        },
    }

    with subtests.test("Check attribute pass-through"):
        config["failure_parameters"]["n_components"] = 4
        msg = (
            "Failure and maintenance models must have the same number of components when using"
            f" 'fractional' availability: {config['failure_parameters']['n_components']}"
            f' != {config["maintenance_parameters"]["n_components"]}'
        )
        with pytest.raises(ValueError, match=msg):
            reliability = PerformanceReliability.from_dict(config)

        config["availability_type"] = "minimum"
        reliability = PerformanceReliability.from_dict(config)
        assert reliability.burn_in == config["burn_in"]
        assert reliability.failures.burn_in == config["burn_in"]
        assert reliability.maintenance.burn_in == config["burn_in"]
        assert reliability.failures.n_components == config["failure_parameters"]["n_components"]
        assert (
            reliability.maintenance.n_components == config["maintenance_parameters"]["n_components"]
        )

    with subtests.test("Check SimpleReliability invalid"):
        config = base_config | failure_config | maintenance_config
        with pytest.raises(ValueError, match=r" \(got 'SimpleReliability'\)"):
            PerformanceReliability.from_dict(config)

    config = {
        "simulation": {"dt": 3600, "n_timesteps": 8760},
        "use_reliability": False,
        "availability_type": "fractional",
        "failure_model": "WeibullReliability",
        "maintenance_model": "FixedIntervalReliability",
        "failure_parameters": {
            "scale": 0.5,
            "shape": 1,
            "n_components": 3,
            "burn_in": 6.5,
            "downtime": {
                "model": "FixedDowntime",
                "hours": 5,
                "n_components": 3,
            },
        },
        "maintenance_parameters": {
            "frequency": [0.25, 1, 4],
            "downtime": {
                "model": "FixedDowntime",
                "hours": 5,
                "n_components": 1,
            },
        },
    }
    reliability = PerformanceReliability.from_dict(config)
    with subtests.test("Check correct setup"):
        assert reliability.availability_type == "fractional"
        assert not reliability.use_reliability
        npt.assert_array_equal(
            reliability.availability, np.ones(config["simulation"]["n_timesteps"])
        )
        assert reliability.n_components == reliability.failures.n_components

        assert isinstance(reliability.simulation, SimulationConfig)
        assert reliability.simulation.dt == config["simulation"]["dt"]
        assert reliability.simulation.n_timesteps == config["simulation"]["n_timesteps"]
        assert (
            reliability.simulation
            == reliability.failures.simulation
            == reliability.maintenance.simulation
        )

        assert reliability.failure_model == config["failure_model"]
        assert reliability.failure_parameters == config["failure_parameters"]
        assert isinstance(reliability.failures, WeibullReliability)
        assert isinstance(reliability.failures.downtime, FixedDowntime)

        assert reliability.maintenance_model == config["maintenance_model"]
        assert reliability.maintenance_parameters == config["maintenance_parameters"]
        assert isinstance(reliability.maintenance, FixedIntervalReliability)
        assert isinstance(reliability.maintenance.downtime, FixedDowntime)


@pytest.mark.regression
def test_PerformanceReliability_results(subtests):
    """Tests the ``PerformanceReliability`` initialization and a basic setup."""
    config = {
        "simulation": {"dt": 3600, "n_timesteps": 8760},
        "use_reliability": False,
        "availability_type": "minimum",
        "failure_model": "WeibullReliability",
        "maintenance_model": "FixedIntervalReliability",
        "failure_parameters": {
            "scale": 0.5,
            "shape": 1,
            "n_components": 3,
            "burn_in": 6.5,
            "downtime": {
                "model": "FixedDowntime",
                "hours": 5,
                "n_components": 3,
            },
        },
        "maintenance_parameters": {
            "frequency": [0.25, 1, 4],
            "downtime": {
                "model": "FixedDowntime",
                "hours": 5,
                "n_components": 1,
            },
        },
    }

    reliability = PerformanceReliability.from_dict(config)
    reliability.run()
    failure_availability = reliability.failures.system_availability
    maintenance_availability = reliability.maintenance.system_availability
    total_availability = np.minimum(failure_availability, maintenance_availability)
    npt.assert_array_equal(reliability.availability, total_availability)

    config["availability_type"] = "fractional"
    reliability = PerformanceReliability.from_dict(config)
    reliability.run()
    failure_availability = reliability.failures.component_availability
    maintenance_availability = reliability.maintenance.component_availability
    total_availability = np.sum(np.minimum(failure_availability, maintenance_availability), axis=0)
    total_availability /= reliability.failures.n_components
    npt.assert_array_equal(reliability.availability, total_availability)

    with subtests.test("Missing reliability models replicate individual availability"):
        no_maint_config = deepcopy(config)
        no_maint_config.pop("maintenance_model")
        reliability = PerformanceReliability.from_dict(no_maint_config)
        reliability.run()
        npt.assert_array_equal(reliability.availability, reliability.failures.system_availability)

        no_maint_config = deepcopy(config)
        no_maint_config.pop("maintenance_parameters")
        reliability = PerformanceReliability.from_dict(no_maint_config)
        reliability.run()
        npt.assert_array_equal(reliability.availability, reliability.failures.system_availability)

        no_fail_config = deepcopy(config)
        no_fail_config.pop("failure_model")
        reliability = PerformanceReliability.from_dict(no_fail_config)
        reliability.run()
        npt.assert_array_equal(
            reliability.availability, reliability.maintenance.system_availability
        )

        no_fail_config = deepcopy(config)
        no_fail_config.pop("failure_parameters")
        reliability = PerformanceReliability.from_dict(no_fail_config)
        reliability.run()
        npt.assert_array_equal(
            reliability.availability, reliability.maintenance.system_availability
        )


@pytest.mark.unit
@pytest.mark.parametrize("name, config", minimal_model_config["downtime"].items())
def test_downtime_model_initial_sampling(name, config):
    """Tests that all downtime models initialize correctly and sample 100 events worth of downtime
    durations.
    """
    model = downtime_models[name].from_dict(config)

    assert isinstance(model, BaseDowntime)
    assert isinstance(model.simulation, SimulationConfig)
    assert model.n_components == 4
    for attribute, expected in config.items():
        if attribute in ("n_components", "simulation"):
            continue
        actual = getattr(model, attribute)
        assert np.all(actual == expected)
        assert actual.shape == (4, 1)

    event_durations = model.sample_downtime()
    assert event_durations.shape == (4, 100)


@pytest.mark.unit
@pytest.mark.parametrize("name, config", minimal_model_config["reliability"].items())
def test_reliability_model_initialization(subtests, name, config):
    """Tests that all reliability models initialize correctly and sample 100 events worth of time
    to next event.
    """
    config["downtime"] = minimal_model_config["downtime"]["FixedDowntime"] | {
        "model": "FixedDowntime"
    }
    config["downtime"]["model"] = "FixedDowntime"
    model = reliability_models[name].from_dict(config)

    with subtests.test("Ensure initialization correctness"):
        for attribute, expected in config.items():
            if attribute in ("n_components", "simulation", "availability_type", "downtime"):
                continue
            actual = getattr(model, attribute)
            print(attribute, actual)
            assert np.all(actual == expected)
            assert actual.shape == (4, 1)

        assert isinstance(model, BaseReliability)
        assert isinstance(model.simulation, SimulationConfig)
        assert isinstance(model.downtime, BaseDowntime)
        assert model.burn_in == 0
        assert model.n_components == 4
        assert model.availability_type == "minimum"
        assert not getattr(model, "component_availability", False)
        assert not getattr(model, "system_availability", False)
        assert not getattr(model, "time_to_failures", False)
        assert not getattr(model, "downtime_per_event", False)

    model.create_downtime_events()
    with subtests.test("Ensure correctness of form post event sampling"):
        assert model.time_to_failures.shape == (4, 100)
        assert model.downtime_per_event.shape == (4, 100)
        assert not getattr(model, "component_availability", False)
        assert not getattr(model, "system_availability", False)

    model.calculate_availability()
    with subtests.test("Ensure correctness of form post availability computation"):
        assert model.time_to_failures.shape[1] < 100
        assert model.downtime_per_event.shape[1] < 100
        assert model.component_availability.shape == (4, model.simulation.n_timesteps)
        assert model.system_availability.shape == (model.simulation.n_timesteps,)
