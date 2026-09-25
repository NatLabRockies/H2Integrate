from abc import ABC, abstractmethod

import attrs
import numpy as np
from attrs import field, define, validators
from numpy.typing import ArrayLike

from h2integrate.core.utilities import BaseConfig
from h2integrate.core.array_validators import array_ge, array_gt, to_array, match_shape
from h2integrate.reliability.utilities import (
    update_dimensions,
    calculate_annual_timesteps,
    calculate_hourly_timesteps,
    calculate_simulation_years,
)


# Per the SciPy and NumPy documentation, a large, uncommon seed needs to be created to ensure
# a sufficiently independent and large state space and the initial seed to ensure replication
# of results is generated from: np.random.SeedSequence().entropy.
rng = np.random.default_rng(279299947538423226929715083173412195503)


VALID_RELIABILITY = (
    "WeibullReliability",
    "FixedIntervalReliability",
)


def create_reliability_model(name: str, config: dict):
    """Creates and returns a reliability model based on the name.

    Args:
        name (str): Name of the reliability model corresponding directly to the class name.
        config (dict): Configuration dictionary that will be passed to the :py:attr:`name` model.

    Returns:
        BaseReliability: An initialized reliability model.
    """
    match name:
        case "WeibullReliability":
            return WeibullReliability.from_dict(config)
        case "FixedIntervalReliability":
            return FixedIntervalReliability.from_dict(config)
        case _:
            raise NotImplementedError(f"{name} is not a valid model name")


def create_downtime_model(config: dict | int):
    """Creates and returns a downtime model.

    Args:
        config (dict): Configuration dictionary with a "model" key and value to indicate the model
            that will be passed to the model.

    Returns:
        BaseDowntime: An initialized downtime model.
    """
    if not isinstance(config, dict):
        return FixedDowntime(hours=config)
    name = config["model"]
    parameters = {k: v for k, v in config.items() if k != "model"}
    match name:
        case "LogNormalDowntime":
            return LogNormalDowntime.from_dict(parameters)
        case "FixedDowntime":
            return FixedDowntime.from_dict(parameters)
        case "UniformDowntime":
            return UniformDowntime.from_dict(parameters)
        case _:
            raise NotImplementedError(f"{name} is not a valid model name")


AVAILABILITY_TYPES = (
    "minimum",
    "fractional",
)


@define
class SimulationConfig(BaseConfig):
    """Shared configuration for the simulation details contained in the plant configuration.

    Args:
        dt (int): Timestep in seconds.
        n_timesteps (int): Number of timesteps in a simulation.

    Attributes:
        n_timesteps_in_year (int): Number of rounded up, whole timesteps in a calendar year.
        n_timesteps_in_hour (int): Number of rounded up, whole timesteps in an hour.
        simulation_years (float): Length of the simulation period, in years.
    """

    dt: int = field(validator=validators.gt(0))
    n_timesteps: int = field(validator=validators.gt(0))
    n_timesteps_in_year: int = field(
        default=0,
        init=False,
        converter=attrs.Converter(calculate_annual_timesteps, takes_self=True),
    )
    n_timesteps_in_hour: int = field(
        default=0,
        init=False,
        converter=attrs.Converter(calculate_hourly_timesteps, takes_self=True),
    )
    simulation_years: float = field(
        init=False,
        default=0,
        converter=attrs.Converter(calculate_simulation_years, takes_self=True),
        validator=validators.instance_of(float),
    )


@define(kw_only=True)
class BaseDowntime(ABC, BaseConfig):
    """Base downtime class responsible for common definitions and functionality.

    Args:
        simulation (dict | ``SimulationConfig``): Configuration consisting of:

            - dt (int): Timestep in seconds.
            - n_timesteps (int): Number of timesteps in a simulation.

        n_components (int): Number of iid components to generate based on the distribution's
            single input. After initialization this value changes
            to align with the number of components being simulated, regardless of identicality.
            Defaults to 1.
    """

    simulation: SimulationConfig = field(
        converter=SimulationConfig.from_dict, validator=validators.instance_of(SimulationConfig)
    )
    n_components: int = field(default=1, validator=(validators.instance_of(int), validators.ge(1)))

    @abstractmethod
    def sample_downtime(self) -> np.ndarray:
        """Downtime length sampling method that all models must implement to create the first 100
        events' downtime duration without ramping.

        Raises:
            NotImplementedError: Subclass must implement this method.

        Returns:
            np.ndarray: First 100 downtime events' duration with shape
                (:py:attr:`n_components`, 100).
        """
        raise NotImplementedError("Failed to successfully subclass, please implement me.")


@define(kw_only=True)
class BaseReliability(ABC, BaseConfig):
    r"""Base downtime class providing the minimal specifications for the model, and
    calculations for the downtime sampling and availability. Subclasses need to
    implement the following:

        - any required model model parameters (e.g., ``scale``, ``shape``, ``mean``)
        - ``__attrs_post_init__`` that updates the model parameters and
          :py:attr:`n_components`
        - :py:meth:`sample_events` to implement the sampling of the first 100 events with shape
          ( :py:attr:`n_components`, 100).

    Args:
        simulation (dict | ``SimulationConfig``): Configuration consisting of:

            - dt (int): Timestep in seconds.
            - n_timesteps (int): Number of timesteps in a simulation.

        availability_type (str): One of "minimum" or "fractional".

            - fractional: Use when components are representative of different systems, i.e., 100
              wind turbines within a wind farm instead of 100 components of a single wind turbine.
              :math:`availability_{system} = \frac{1}{N} \sum_{i=0}^{N} availability_i` where
              :math:`i` is a single system in a grouping of systems.
            - minimum: Minimum of all components at all timesteps. Use when components are
              representative of a single system, i.e., multiple components of a single wind
              turbine, rather than a grouping of systems (i.e., a wind power plant).

        burn_in (float): Number of years into the simulation to use as the starting point of the
            the simulation's availability record. Defaults to 0.
        n_components (int): Number of identical components to sample to avoid defining an array of
            mean and sigma values when they are the same. After initialization this value changes
            to align with the number of components being simulated, regardless of identicality.
            Defaults to 1.
        downtime (dict): Configuration for a downtime model.

    Attributes:
        time_to_failures (np.ndarray): Array of the hours to the next failure for each modeled
            component. Generated by each subclass' :py:meth:`sample_events`.
        downtime_per_event (np.ndarray): Number of hours of downtime corresponding to each downtime
            event in :py:attr:`time_to_failures`.
        availability (np.ndarray): Operational ratio of each modeled component for every time step
            of the simulation.
        system_availability (np.ndarray): Minimum operational ratio of all components for every time
            time step of the simulation.
    """

    simulation: SimulationConfig = field(
        converter=SimulationConfig.from_dict, validator=validators.instance_of(SimulationConfig)
    )
    availability_type: str = field(validator=validators.in_(AVAILABILITY_TYPES))
    burn_in: float = field(default=0, converter=float, validator=validators.ge(0))
    n_components: int = field(default=1, validator=(validators.instance_of(int), validators.ge(1)))
    downtime: dict | BaseDowntime = field(validator=validators.instance_of((dict, BaseDowntime)))

    time_to_failures: np.ndarray = field(init=False, validator=validators.instance_of(np.ndarray))
    downtime_per_event: np.ndarray = field(init=False, validator=validators.instance_of(np.ndarray))
    component_availability: np.ndarray = field(
        init=False, validator=validators.instance_of(np.ndarray)
    )
    system_availability: np.ndarray = field(
        init=False, validator=validators.instance_of(np.ndarray)
    )

    def __attrs_post_init__(self):
        """Provides the automatic downtime model initialization. All subclasses should implement
        the following.

        >>> self.n_components, self.model_param1, self.model_param2 = update_dimensions(
                self.n_components, self.model_param1, self.model_param2
            )
        >>> super().__attrs_post_init__()
        """
        downtime_config = (
            self.downtime | {"simulation": self.simulation} | {"n_components": self.n_components}
        )
        self.downtime = create_downtime_model(downtime_config)
        if self.n_components != self.downtime.n_components:
            msg = (
                "Reliability and their downtime models must have the same 'n_components':"
                f" {self.n_components} != {self.downtime.n_components}."
            )
            raise ValueError(msg)

    def run(self):
        self.create_downtime_events()
        self.calculate_availability()

    @abstractmethod
    def sample_events(self) -> np.ndarray:
        """Event sampling method that all models must implement to create the first 100 downtime
        events.

        Raises:
            NotImplementedError: Subclass must implement this method.

        Returns:
            np.ndarray: First 100 downtime events with shape (:py:attr:`n_components`, 100).
        """
        raise NotImplementedError("Failed to successfully subclass, please implement me.")

    def create_downtime_events(self):
        """Creates the ``time_to_failure`` and ``downtime_per_event`` arrays."""
        self.time_to_failures = self.sample_events()
        self.downtime_per_event = self.downtime.sample_downtime()

    def calculate_availability(self):
        """Determine the timing and duration of outages for a single year of simulation time."""
        burn_in_time = np.ceil(self.burn_in * self.simulation.n_timesteps_in_year).astype(int)
        simulation_end = burn_in_time + self.simulation.n_timesteps

        accumulated = np.zeros((self.n_components, 1), dtype=int)
        component_availability = np.ones((self.n_components, simulation_end), dtype=float)

        while any(accumulated < simulation_end):
            if self.time_to_failures.size == 0:
                self.create_downtime_events()
            event = self.time_to_failures[:, 0].reshape(-1, 1)
            self.time_to_failures = self.time_to_failures[:, 1:]
            duration = self.downtime_per_event[:, 0].reshape(-1, 1)
            self.downtime_per_event = self.downtime_per_event[:, 1:]

            if all(event + accumulated) > simulation_end:
                break

            start = accumulated + event
            end = start + duration
            for i, (s, e) in enumerate(zip(start.flatten(), end.flatten())):
                if s < simulation_end:
                    e = min(simulation_end, e)
                    component_availability[i, s:e] = 0
            accumulated = end

        self.component_availability = component_availability[:, burn_in_time:simulation_end]

        match self.availability_type:
            case "fractional":
                self.system_availability = (
                    np.sum(self.component_availability, axis=0) / self.n_components
                )
            case "minimum":
                self.system_availability = np.min(self.component_availability, axis=0)


@define
class PerformanceReliability(BaseConfig):
    r"""General performance model to coordinate downtime from failure and maintenance events. Does
    not consider the timing within or between models to coordinate downtime. This is a highly
    simplified version of WOMBAT (https://github.com/NLRWindSystems/WOMBAT) without any
    advanced scheduling, equipment dispatching, site conditions, etc.

    Args:
        simulation (dict | SimulationConfig): Simulation configuration based on
            :py:class:`SimulationConfig`.
        availability_type (str): One of "minimum" or "fractional". When using both a
            :py:attr:`failure_model` and :py:attr:`maintenance_model` with "fractional"
            availability, :py:attr:`n_components` for both models must be equal.

            - fractional: Use when components are representative of different systems, i.e., 100
              wind turbines within a wind farm instead of 100 components of a single wind turbine.
              :math:`availability_{system} = \frac{1}{N} \sum_{i=0}^{N} availability_i` where
              :math:`i` is a single system in a grouping of systems.
            - minimum: Minimum of all components at all timesteps. Use when components are
              representative of a single system, i.e., multiple components of a single wind
              turbine, rather than a grouping of systems (i.e., a wind power plant).

        use_reliability (bool, optional): Used for the performance model to toggle the use of the
            reliability modeling. Defaults to True to match the assumption contained in performance
            models.
        burn_in (float): Number of years into the simulation to use as the starting point of the
            the simulation's availability record. Applied to both the failure and maintenance models
            as an override. Defaults to 0.
        failure_model (str | None): Name of the failure model to use, when modeling.
        maintenance_model (str | None): Name of the maintenance model to use, when modeling.
        failure_parameters (str | None): Configuration for the failure model, when modeling. The
            simulation configuration will be provided through the initialization process, and does
            not need to be defined here.
        maintenance_parameters (str | None): Configuration the maintenance model, when modeling. The
            simulation configuration will be provided through the initialization process, and does
            not need to be defined here.

    Attributes:
        availability (np.ndarray): Total availability, with shape
            (:py:attr:`simulation.n_timesteps`).
        failures (BaseReliability): Reliability model for the failure-based downtime events.
        maintenance (BaseReliability): Reliability model for the maintenance downtime events.
    """

    simulation: dict | SimulationConfig = field(converter=SimulationConfig.from_dict)
    availability_type: str = field(validator=validators.in_(AVAILABILITY_TYPES))
    use_reliability: bool = field(default=True, validator=validators.instance_of(bool))
    burn_in: float = field(default=0, converter=float, validator=validators.ge(0))
    failure_model: str | None = field(
        default=None, validator=validators.optional(validators.in_(VALID_RELIABILITY))
    )
    maintenance_model: str | None = field(
        default=None, validator=validators.optional(validators.in_(VALID_RELIABILITY))
    )
    failure_parameters: dict | None = field(
        default=None, validator=validators.optional(validators.instance_of(dict))
    )
    maintenance_parameters: dict | None = field(
        default=None, validator=validators.optional(validators.instance_of(dict))
    )
    availability: np.ndarray = field(
        validator=validators.optional(validators.instance_of(np.ndarray)), init=False
    )
    failures: BaseReliability | None = field(default=None, init=False)
    maintenance: BaseReliability | None = field(default=None, init=False)
    n_components: int = field(default=1, init=False)

    def __attrs_post_init__(self):
        """Creates and runs the failure and maintenance models, and calculates availability."""
        shared_config = {
            "simulation": self.simulation,
            "availability_type": self.availability_type,
            "burn_in": self.burn_in,
        }
        self.availability = np.ones(self.simulation.n_timesteps)

        has_maintenance = False
        has_failure = False
        if self.failure_model is not None:
            if self.failure_parameters is not None:
                has_failure = True
                self.failures = create_reliability_model(
                    self.failure_model, self.failure_parameters | shared_config
                )
                self.n_components = self.failures.n_components

        if self.maintenance_model is not None:
            if self.maintenance_parameters is not None:
                has_maintenance = True
                self.maintenance = create_reliability_model(
                    self.maintenance_model, self.maintenance_parameters | shared_config
                )
                self.n_components = self.maintenance.n_components

        if self.availability_type == "fractional":
            if has_failure and has_maintenance:
                failure_components = self.failures.n_components
                maintenance_components = self.maintenance.n_components
                if failure_components != maintenance_components:
                    msg = (
                        "Failure and maintenance models must have the same number of components"
                        f" when using 'fractional' availability: {failure_components} !="
                        f" {maintenance_components}"
                    )
                    raise ValueError(msg)

    def calculate_availability(self):
        """Calculates the final system availability as the minimum availability between the
        failure-based downtime and maintenance-based downtime with shape
        (:py:attr:`simulation.n_timesteps`, ).

        Returns:
            np.ndarray: An array of availability with shape(:py:attr:`simulation.n_timesteps`, )
                with values in the range [0, 1].
        """
        is_fractional = self.availability_type == "fractional"
        failure_availability = maintenance_availability = self.availability
        if self.failures is not None:
            if is_fractional:
                failure_availability = self.failures.component_availability
            else:
                failure_availability = self.failures.system_availability
        if self.maintenance is not None:
            if is_fractional:
                maintenance_availability = self.maintenance.component_availability
            else:
                maintenance_availability = self.maintenance.system_availability

        availability = np.minimum(failure_availability, maintenance_availability)
        if is_fractional:
            return np.sum(availability, axis=0) / self.n_components
        return availability

    def run(self):
        """Runs the failure and maintenance models, and calculates the total availability."""
        if self.failures is not None:
            self.failures.run()
        if self.maintenance is not None:
            self.maintenance.run()
        self.availability = self.calculate_availability()


@define(kw_only=True)
class FixedDowntime(BaseDowntime):
    """Basic fixed duration downtime model for generating the length of downtime for a given event.

    Args:
        hours (int | array-like): Length of downtime per event, in hours. Must be at least 1 hour.
        simulation (dict | ``SimulationConfig``): Configuration consisting of:

            - dt (int): Timestep in seconds.
            - n_timesteps (int): Number of timesteps in a simulation.

        n_components (int): Number of iid components to generate based on the distribution's
            single input. After initialization this value changes
            to align with the number of components being simulated, regardless of identicality.
            Defaults to 1.
    """

    hours: int | ArrayLike = field(
        converter=to_array(int, (-1, 1)),
        validator=(validators.instance_of(np.ndarray), array_ge(1)),
    )

    def __attrs_post_init__(self):
        self.n_components, self.hours = update_dimensions(self.n_components, self.hours)

    def sample_downtime(self):
        """Return an array of shape (:py:attr:`n_components`, 100) :py:attr:`hours` as the downtime
        duration for the next 100 downtime events.

        Returns:
            np.ndarray: An array of the next 100 events' downtime durations.
        """
        return np.ones((1, 100), dtype=int) * self.hours * self.simulation.n_timesteps_in_hour


@define(kw_only=True)
class UniformDowntime(BaseDowntime):
    """Basic uniform distribution-based downtime model for generating the length of downtime for a
    given event.

    Args:
        min_hours (int | array-like): Minimum length of downtime per event, in hours. Must be at
            least 1 hour.
        max_hours (int | array-like): Maximum length of downtime per event, in hours. Must be at
            least 1 hour and greater than :py:attr:`min_hours`.
        simulation (dict | ``SimulationConfig``): Configuration consisting of:

            - dt (int): Timestep in seconds.
            - n_timesteps (int): Number of timesteps in a simulation.

        n_components (int): Number of iid components to generate based on the distribution's
            single input. After initialization this value changes
            to align with the number of components being simulated, regardless of identicality.
            Defaults to 1.
    """

    min_hours: int | ArrayLike = field(
        converter=to_array(int, (-1, 1)),
        validator=(validators.instance_of(np.ndarray), array_ge(1)),
    )
    max_hours: int | ArrayLike = field(
        converter=to_array(int, (-1, 1)),
        validator=(validators.instance_of(np.ndarray), array_ge(1)),
    )

    @max_hours.validator
    def validate_max_hours(self, attribute, value: int):
        """Ensures that :py:attr:`value` is greater than :py:attr:`min_hours`."""
        if (value <= self.min_hours).any():
            msg = f"'max_hours' ({value}) must be greater than 'min_hours'({self.min_hours})."
            raise ValueError(msg)

    def __attrs_post_init__(self):
        self.n_components, self.min_hours, self.max_hours = update_dimensions(
            self.n_components, self.min_hours, self.max_hours
        )

    def sample_downtime(self):
        """Return an array of 100 samples from a uniform distribution.

        Returns:
            np.ndarray: An array of shape (:py:attr:`n_components`, 100) for the next 100 events'
                downtime durations.
        """
        return (
            rng.integers(self.min_hours, self.max_hours, size=(self.n_components, 100))
            * self.simulation.n_timesteps_in_hour
        )


@define(kw_only=True)
class LogNormalDowntime(BaseDowntime):
    """Basic log-normal downtime model for generating the length of downtime for a given event.

    Args:
        mean (float | array-like): Average length of downtime per event, in hours.
        sigma (float | array-like): Standard deviation of the distribution(s), in hours.
        simulation (dict | ``SimulationConfig``): Configuration consisting of:

            - dt (int): Timestep in seconds.
            - n_timesteps (int): Number of timesteps in a simulation.

        n_components (int): Number of iid components to generate based on the distribution's
            single input. After initialization this value changes
            to align with the number of components being simulated, regardless of identicality.
            Defaults to 1.
    """

    mean: float = field(
        converter=to_array(float, (-1, 1)),
        validator=(validators.instance_of(np.ndarray), array_ge(0)),
    )
    sigma: float = field(
        converter=to_array(float, (-1, 1)),
        validator=(validators.instance_of(np.ndarray), match_shape("mean"), array_ge(0)),
    )

    def __attrs_post_init__(self):
        self.n_components, self.mean, self.sigma = update_dimensions(
            self.n_components, self.mean, self.sigma
        )

    def sample_downtime(self) -> np.ndarray:
        """Return an array of shape (:py:attr:`n_components`, 100) samples of each
        lognormal distribution.

        Returns:
            np.ndarray: An array of the next 100 events' downtime durations.
        """
        return np.ceil(
            rng.lognormal(self.mean, self.sigma, size=(self.mean.shape[0], 100))
            / self.simulation.n_timesteps_in_hour
        ).astype(int)


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
        simulation (dict | ``SimulationConfig``): Configuration consisting of:

            - dt (int): Timestep in seconds.
            - n_timesteps (int): Number of timesteps in a simulation.

        availability_type (str): One of "minimum" or "fractional".

            - fractional: Use when components are representative of different systems, i.e., 100
              wind turbines within a wind farm instead of 100 components of a single wind turbine.
              :math:`availability_{system} = \frac{1}{N} \sum_{i=0}^{N} availability_i` where
              :math:`i` is a single system in a grouping of systems.
            - minimum: Minimum of all components at all timesteps. Use when components are
              representative of a single system, i.e., multiple components of a single wind
              turbine, rather than a grouping of systems (i.e., a wind power plant).

        burn_in (float): Number of years into the simulation to use as the starting point of the
            the simulation's availability record. Defaults to 0.
        n_components (int): Number of identical components to sample to avoid defining an array of
            mean and sigma values when they are the same. After initialization this value changes
            to align with the number of components being simulated, regardless of identicality.
            Defaults to 1.
        downtime (dict): Configuration for a downtime model.

    Attributes:
        time_to_failures (np.ndarray): Array of the hours to the next failure for each modeled
            component. Generated by each subclass' :py:meth:`sample_events`.
        downtime_per_event (np.ndarray): Number of hours of downtime corresponding to each downtime
            event in :py:attr:`time_to_failures`.
        availability (np.ndarray): Operational ratio of each modeled component for every time step
            of the simulation.
        system_availability (np.ndarray): Minimum operational ratio of all components for every time
            time step of the simulation.
    """

    scale: float = field(
        converter=to_array(float, (-1, 1)),
        validator=validators.instance_of(np.ndarray),
    )
    shape: float = field(
        converter=to_array(float, (-1, 1)),
        validator=(validators.instance_of(np.ndarray), match_shape("scale")),
    )

    def __attrs_post_init__(self):
        super().__attrs_post_init__()
        self.n_components, self.scale, self.shape = update_dimensions(
            self.n_components, self.scale, self.shape
        )

    def sample_events(self):
        """Samples 100 events for each simulated component, rounding up to the nearest timestep.

        Returns:
            np.ndarray: An array of shape (:py:attr:`n_components`, 100) for the next 100 events'
                time to next failure.
        """
        return np.ceil(
            rng.weibull(self.shape, size=(self.shape.size, 100))
            * self.scale
            * self.simulation.n_timesteps_in_year
        ).astype(int)


@define(kw_only=True)
class FixedIntervalReliability(BaseReliability):
    r"""Basic fixed interval downtime reliability model.

    Args:
        frequency (int | float | array-like): The annual frequency of events, e.g., 4 is equivalent
            to a quarterly downtime event and 0.25 is equivalent to an every 4 years downtime event.
            For all events the timing of the first event will be sampled within the first year or
            interval period to offset events from being based on January 1st in an 8760.
        simulation (dict | ``SimulationConfig``): Configuration consisting of:

            - dt (int): Timestep in seconds.
            - n_timesteps (int): Number of timesteps in a simulation.

        availability_type (str): One of "minimum" or "fractional".

            - fractional: Use when components are representative of different systems, i.e., 100
              wind turbines within a wind farm instead of 100 components of a single wind turbine.
              :math:`availability_{system} = \frac{1}{N} \sum_{i=0}^{N} availability_i` where
              :math:`i` is a single system in a grouping of systems.
            - minimum: Minimum of all components at all timesteps. Use when components are
              representative of a single system, i.e., multiple components of a single wind
              turbine, rather than a grouping of systems (i.e., a wind power plant).

        burn_in (float): Number of years into the simulation to use as the starting point of the
            the simulation's availability record. Defaults to 0.
        n_components (int): Number of identical components to sample to avoid defining an array of
            mean and sigma values when they are the same. After initialization this value changes
            to align with the number of components being simulated, regardless of identicality.
            Defaults to 1.
        downtime (dict): Configuration for a downtime model.

    Attributes:
        time_to_failures (np.ndarray): Array of the hours to the next failure for each modeled
            component. Generated by each subclass' :py:meth:`sample_events`.
        downtime_per_event (np.ndarray): Number of hours of downtime corresponding to each downtime
            event in :py:attr:`time_to_failures`.
        availability (np.ndarray): Operational ratio of each modeled component for every time step
            of the simulation.
        system_availability (np.ndarray): Minimum operational ratio of all components for every time
            time step of the simulation.
    """

    frequency: float = field(
        converter=to_array(float, (-1, 1)),
        validator=(validators.instance_of(np.ndarray), array_gt(0)),
    )

    def __attrs_post_init__(self):
        super().__attrs_post_init__()
        self.n_components, self.frequency = update_dimensions(self.n_components, self.frequency)

    def sample_events(self):
        """Creates the time to next failure array for each event's modality with the first event
        occurring randomly either in the simulation period or first downtime interval, whichever
        is shorter.

        Returns:
            np.ndarray: An array of shape (:py:attr:`n_components`, 100) for the next 100 events'
                time to next failure.
        """
        interval = np.ceil(
            8760 / (1 / self.frequency) / self.simulation.n_timesteps_in_hour
        ).astype(int)
        max_first_occurrence = np.where(
            interval > self.simulation.n_timesteps, self.simulation.n_timesteps, interval
        )
        first_occurrence = rng.integers(0, max_first_occurrence)
        time_to_failures = np.hstack(
            (first_occurrence, np.broadcast_to(interval, (interval.size, 99)))
        )
        return time_to_failures
