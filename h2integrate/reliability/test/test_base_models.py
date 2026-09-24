import pytest

from h2integrate.reliability.models import (
    BaseDowntime,
    FixedDowntime,
    BaseReliability,
    UniformDowntime,
    SimulationConfig,
    LogNormalDowntime,
    WeibullReliability,
    FixedIntervalReliability,
)


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
        "FixedIntervalReliability": {"hours": 100},
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
    minimal_model_config["reliability"][name] |= standard_config

for name in minimal_model_config["downtime"]:
    minimal_model_config["downtime"][name] |= standard_config


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
    for attribute, value in config.items():
        if attribute in ("n_components", "simulation"):
            continue
        assert getattr(model, attribute) == value

    event_durations = model.sample_downtime()
    assert event_durations.shape == (4, 100)


@pytest.mark.unit
@pytest.mark.parametrize("name, config", minimal_model_config["reliability"].items())
def test_reliability_model_initialization(subtests, name, config):
    """Tests that all reliability models initialize correctly and sample 100 events worth of time
    to next event.
    """
    config["downtime"] = minimal_model_config["downtime"]["FixedDowntime"]
    model = reliability_models[name].from_dict(config)

    with subtests.test("Ensure initialization correctness"):
        for attribute, value in config.items():
            if attribute in ("n_components", "simulation"):
                continue
            assert getattr(model, attribute) == value

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

    with subtests.test("Ensure correctness of form post event sampling"):
        event_timing = model.sample_events()
        assert event_timing.shape == (4, 100)
        assert model.time_to_failures.shape == (4, 100)
        assert model.downtime_per_event.shape == (4, 100)
        assert not getattr(model, "component_availability", False)
        assert not getattr(model, "system_availability", False)

    with subtests.test("Ensure correctness of form post availability computation"):
        event_timing = model.calculate_availability()
        assert model.time_to_failures.shape[1] < 100
        assert model.downtime_per_event.shape[1] < 100
        assert model.component_availability.shape == (4, model.simulation.n_timesteps)
        assert model.system_availability.shape == (model.simulation.n_timesteps,)
