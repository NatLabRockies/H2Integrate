import numpy as np
from attrs import field, define, validators

from h2integrate.core.utilities import BaseConfig


N_TIMESTEPS = 8760


@define(kw_only=True)
class WeibullReliabilityModel(BaseConfig):
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
    downtime: float = field(validator=validators.gt(1))
    rng: np.random._generator.Generator = field(
        default=np.random.default_rng(),
        init=False,
        validator=validators.instance_of(np.random._generator.Generator),
    )
    availability: np.ndarray = field(
        default=np.ones(N_TIMESTEPS), init=False, validator=validators.instance_of(np.ndarray)
    )
    downtime_per_event: np.ndarray = field(
        default=np.zeros(N_TIMESTEPS), init=False, validator=validators.instance_of(np.ndarray)
    )

    def __attrs_post_init__(self):
        self.create_downtime_events()
        self.calculate_availability()

    def create_downtime_events(self):
        """Creates a ``time_to_failure`` and ``downtime_per_event`` array based on the distributions
        described in ``WeibullReliabilityConfig``.
        """
        # NOTE: Arrays are default length 30 to ensure enough events are created for a 1-year
        # simulation without burdening the memory usage.
        self.time_to_failures = np.ceil(
            self.config.rng.weibul(self.config.shape, size=30) * self.config.scale * N_TIMESTEPS
        ).astype(int)
        downtime_per_event = np.ceil(np.rng.normal(loc=self.config.downtime, size=30)).astype(int)
        self.downtime_per_event = np.where(downtime_per_event >= 1, downtime_per_event, 1)

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
            accumulated = start
            if not self.time_to_failures:
                self.create_downtime_events()
