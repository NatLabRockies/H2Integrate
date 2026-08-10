import numpy as np
from attrs import field, define, validators

from h2integrate.core.utilities import BaseConfig, merge_shared_inputs
from h2integrate.core.model_baseclasses import ReliabilityModelBaseClass


@define(kw_only=True)
class WeibullReliabilityConfig(BaseConfig):
    r"""Basic reliability model for operating/not operating statuses.

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


class WeibullReliabilityModel(ReliabilityModelBaseClass):
    """
    Performance model for natural gas power plants.

    This model calculates electricity output from natural gas input based on
    the plant's heat rate. It can be used for both natural gas combustion
    turbines (NGCT) and natural gas combined cycle (NGCC) plants by providing
    appropriate heat rate values.

    The model implements the relationship:
        electricity_out = natural_gas_in / heat_rate

    Inputs:
        system_capacity (float): Natural gas plant rated capacity in MW
        natural_gas_in (array): Natural gas input energy in MMBtu/h
        heat_rate_mmbtu_per_mwh (float): Plant heat rate in MMBtu/MWh
        electricity_command_value (array): Electricity command value in MW for each timestep

    Outputs:
        electricity_out (array): Electricity output in MW for each timestep
        natural_gas_consumed (array): Natural gas consumed in MMBtu/h

    """

    def initialize(self):
        super().initialize()
        self.commodity = "electricity"

    def setup(self):
        super().setup()

        self.config = WeibullReliabilityConfig.from_dict(
            merge_shared_inputs(self.options["tech_config"]["model_inputs"], "reliability"),
            additional_cls_name=self.__class__.__name__,
        )

        self.create_downtime_events()

    def create_downtime_events(self):
        """Creates a ``time_to_failure`` and ``downtime_per_event`` array based on the distributions
        described in ``WeibullReliabilityConfig``.
        """
        self.time_to_failures = np.floor(
            self.config.rng.weibul(self.config.shape, size=12) * self.config.scale * 8760
        ).astype(int)
        downtime_per_event = np.floor(np.rng.normal(loc=self.config.downtime, size=12)).astype(int)
        self.downtime_per_event = np.where(downtime_per_event >= 1, downtime_per_event, 1)

    def calculate_availability(self):
        """Determine the timing and duration of outages for a single year of simulation time."""
        accumulated = 0
        while accumulated < 8760:
            event, self.time_to_failures = self.time_to_failures[0], self.time_to_failures[1:]
            duration, self.downtime_per_event = (
                self.downtime_per_event[0],
                self.downtime_per_event[1:],
            )
            if event + accumulated > 8760:
                break

            start = accumulated + event
            end = start + duration
            self.availability[start:end] = 0
            accumulated = start
            if not self.time_to_failures:
                self.create_downtime_events()
