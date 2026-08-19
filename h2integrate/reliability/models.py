from abc import ABC, abstractmethod
from typing import Any

import numpy as np
from attrs import field, define, validators
from numpy.typing import ArrayLike

from h2integrate.core.utilities import BaseConfig


# generated from np.random.SeedSequence().entropy
rng = np.random.default_rng(279299947538423226929715083173412195503)


N_TIMESTEPS = 8760


def create_failure_model(config: dict):
    """Retrieves and initializes a matching reliability model."""
    name = config["failure_model"]
    fail_config = config["failure_parameters"]
    match name:
        case "WeibullReliability":
            return WeibullReliability.from_dict()
        case "FixedIntervalReliability":
            return FixedIntervalReliability.from_dict(fail_config)
        case _:
            raise NotImplementedError(f"{name} is not a valid model name")


def create_maintenance_model(config: dict):
    """Retrieves and initializes a matching reliability model."""
    name = config.pop("maintenance_model")
    maintenance_config = config["maintenance_parameters"]
    match name:
        case "WeibullReliability":
            return WeibullReliability.from_dict(maintenance_config)
        case "FixedIntervalReliability":
            return FixedIntervalReliability.from_dict(maintenance_config)
        case _:
            raise NotImplementedError(f"{name} is not a valid model name")


def generate_downtime_model(config: dict):
    name = config.pop("model")
    match name:
        case "LogNormalDowntime":
            return LogNormalDowntime.from_dict(config)
        case _:
            raise NotImplementedError(f"{name} is not a valid model name")


@define(kw_only=True)
class BaseDowntime(ABC, BaseConfig):
    @abstractmethod
    def sample_downtime(self) -> np.ndarray: ...


@define(kw_only=True)
class BaseReliability(ABC, BaseConfig):
    @abstractmethod
    def sample_events(self) -> np.ndarray: ...


def float_array_converter(val: int | float | ArrayLike):
    return np.ndarray(val).astype(float).reshape(-1, 1)


def int_array_converter(val: int | float | ArrayLike):
    return np.ndarray(val).astype(float).reshape(-1, 1)


@define(kw_only=True)
class LogNormalDowntime(BaseDowntime):
    """Basic log-normal downtime model for generating the length of downtime for a given event.

    Args:
        mean (float): Average length of downtime per event, in hours.
        sigma (float): Standard deviation of the distribution(s), in hours.
        n_components (int): Number of identical components to sample. Primarily for convenience.
            Defaults to 1.
    """

    mean: float = field(
        converter=float_array_converter,
        validator=(validators.instance_of(np.ndarray), validators.ge(0)),
    )
    sigma: float = field(
        converter=float_array_converter,
        validator=(validators.instance_of(np.ndarray), validators.ge(0)),
    )
    n_components: int = field(default=1, validator=(validators.instance_of(int), validators.ge(1)))

    @sigma.validator
    def validate_shape(self, attribute, value):
        """Validates that :py:attr:`mean` and :py:attr:`sigma` are the same size."""
        if self.mean.shape != value.shape:
            msg = (
                "Inputs to 'mean' and 'sigma' must be the same length. Received"
                f" 'mean': {self.mean.size}, 'sigma': {value.size}"
            )
            raise ValueError(msg)

    def __attrs_post_init__(self):
        if self.mean.size == 1 and self.n_components > 1:
            broadcaster = np.ones((self.n_components, 1))
            self.mean *= broadcaster
            self.sigma *= broadcaster

    def sample_downtime(self) -> np.ndarray:
        return rng.lognormal(self.mean, self.sigma, size=(self.mean.shape[0], 100))


@define(kw_only=True)
class WeibullReliability(BaseReliability):
    r"""Basic reliability model for operating/not operating statuses.

    Assumes a full operational shutdown with zero ramping of production for an hourly, 1 year
    simulation.

    Args:
        scale (float): Also referred to as :math:`\lambda` or :math:`\alpha`. Determines
            the scale of distribution, and is equivalent to the mean time
            between failure in years (MTBF), or 1 / annual failure rate.
        shape (float): Also referred to as ``k`` or :math:`\beta`. A value less than 1
            corresponds to a decreasing hazard rate over time (break-in period failures);
            a value greater than 1 corresponds to an increasing hazard rate over time (
            aging/wear-out failures); and a value of 1 corresponds to a constant hazard
            rate over time (exponential distribution).
        downtime (float): Average amount of downtime per failure.

    Attributes:
        rng (np.random._generator.Generator): NumPy random generator object.

    TODO:
        - how to pass n_timesteps through from plant?
        - stabilize random generator/determine how to manage random seeding across library
    """

    scale: float = field(validator=validators.instance_of(float))
    shape: float = field(validator=validators.instance_of(float))
    downtime: Any = field(converter=generate_downtime_model)
    downtime_per_event: np.ndarray = field(init=False, validator=validators.instance_of(np.ndarray))
    availability: np.ndarray = field(
        default=np.ones(N_TIMESTEPS), init=False, validator=validators.instance_of(np.ndarray)
    )

    def __attrs_post_init__(self):
        self.create_downtime_events()
        self.calculate_availability()

    def sample_events(self):
        return np.ceil(self.rng.weibul(self.shape, size=100) * self.scale * N_TIMESTEPS).astype(int)

    def create_downtime_events(self):
        """Creates a ``time_to_failure`` and ``downtime_per_event``."""
        # NOTE: Arrays are default length 30 to ensure enough events are created for a 1-year
        # simulation without burdening the memory usage.
        self.time_to_failures = self.sample_events()
        self.downtime_per_event = self.downtime.sample_downtime()

    def calculate_availability(self):
        """Determine the timing and duration of outages for a single year of simulation time."""
        accumulated = 0
        while accumulated < N_TIMESTEPS:
            event, self.time_to_failures = self.time_to_failures[0], self.time_to_failures[1:]
            duration, self.downtime_per_event = (
                self.downtime_per_event[0],
                self.downtime_per_event[1:],
            )
            if event + accumulated > N_TIMESTEPS:
                break

            start = accumulated + event
            end = start + duration
            self.availability[start:end] = 0
            accumulated = end
            if not self.time_to_failures:
                self.create_downtime_events()


@define(kw_only=True)
class FixedIntervalReliability(BaseReliability):
    """Basic fixed interval downtime reliability model.

    Args:
        frequency (int | float | array-like): The annual frequency of events, e.g., 4 is equivalent
            to a quarterly downtime event and 0.25 is equivalent to an every 4 years downtime event.
            For all events the timing of the first event will be sampled within the first year or
            interval period to offset events from being based on January 1st in an 8760.
        downtime (int | float | dict): Either fixed length of each downtime, in hours, or a
            configuration dictionary for a downtime length model.

    """

    frequency: float = field(validator=(validators.instance_of((float, int)), validators.gt(0)))
    downtime: Any = field(converter=generate_downtime_model)
    downtime_per_event: np.ndarray = field(init=False, validator=validators.instance_of(np.ndarray))
    availability: np.ndarray = field(
        default=np.ones(N_TIMESTEPS), init=False, validator=validators.instance_of(np.ndarray)
    )

    def __attrs_post_init__(self):
        self.create_downtime_events()
        self.calculate_availability()

    def sample_events(self):
        frequency = np.array([0.1, 20, 30]).reshape(-1, 1)
        interval = np.ceil(8760 / frequency).astype(int)
        first_occurrence = rng.integers(0, np.where(interval > 8760, 8760, interval))
        return first_occurrence, interval

    def create_downtime_events(self):
        """Creates a ``time_to_failure`` and ``downtime_per_event``."""
        self.first_occurrence, self.interval = self.sample_events()
        self.downtime_per_event = self.downtime.sample_downtime()

    def calculate_availability(self):
        """Determine the timing and duration of outages for a single year of simulation time."""
        duration, self.downtime_per_event = (
            self.downtime_per_event[0],
            self.downtime_per_event[1:],
        )
        end = self.first_occurrence + duration
        self.availability[self.first_occurrence : end] = 0
        accumulated = end
        while (start := accumulated + self.interval) < N_TIMESTEPS:
            duration, self.downtime_per_event = (
                self.downtime_per_event[0],
                self.downtime_per_event[1:],
            )
            # TODO: handle start > 8760
            end = start + duration
            end = np.where(end > 8760, 8760, end)
            self.availability[start:end] = 0
            accumulated = end
            if not self.downtime_per_event:
                self.downtime.sample_downtime()
