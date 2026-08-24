import numpy as np
import openmdao.api as om
from attrs import field, define, validators

from h2integrate.core.utilities import BaseConfig, merge_shared_inputs


@define(kw_only=True)
class ThresholdStatisticsPerformanceConfig(BaseConfig):
    """Configuration class for a statistical counting component.

    Fields include `commodity`, `commodity_rate_units`, and `thresholds`.
    """

    commodity: str = field(converter=(str.lower, str.strip))
    commodity_rate_units: str = field()
    epsilon_comparison: float = field(default=0.0, validator=validators.ge(0.0))


class ThresholdStatisticsPerformanceModel(om.ExplicitComponent):
    """
    Compute counting statistics on a given input timeseries commodity.
    """

    _time_step_bounds = (
        1,
        1e9,
    )  # (min, max) time step lengths (in seconds) compatible with this model

    def initialize(self):
        self.options.declare("driver_config", types=dict)
        self.options.declare("plant_config", types=dict)
        self.options.declare("tech_config", types=dict)

    def setup(self):
        self.config = ThresholdStatisticsPerformanceConfig.from_dict(
            merge_shared_inputs(self.options["tech_config"]["model_inputs"], "performance"),
            additional_cls_name=self.__class__.__name__,
        )

        n_timesteps = int(self.options["plant_config"]["plant"]["simulation"]["n_timesteps"])

        self.add_input(
            f"{self.config.commodity}_in",
            val=0.0,
            shape=n_timesteps,
            units=self.config.commodity_rate_units,
        )

        self.add_input(
            f"{self.config.commodity}_threshold",
            val=0.0,
            shape=n_timesteps,
            units=self.config.commodity_rate_units,
        )

        self.add_output(
            f"net_{self.config.commodity}_deficit",
            val=0.0,
            shape=1,
            units=self.config.commodity_rate_units,
        )

        self.add_output(
            f"net_{self.config.commodity}_surplus",
            val=0.0,
            shape=1,
            units=self.config.commodity_rate_units,
        )

        self.add_output(
            f"frac_timestep_{self.config.commodity}_deficit",
            val=0.0,
            shape=1,
            units="unitless",
        )

        self.add_output(
            f"frac_timestep_{self.config.commodity}_surplus",
            val=0.0,
            shape=1,
            units="unitless",
        )

    def compute(self, inputs, outputs):
        commodity_in = inputs[f"{self.config.commodity}_in"]
        commodity_threshold = inputs[f"{self.config.commodity}_threshold"]

        net_deficit = np.sum(np.maximum(0.0, commodity_threshold - commodity_in))
        net_surplus = np.sum(np.maximum(0.0, commodity_in - commodity_threshold))

        frac_deficit = np.mean(
            commodity_in < (commodity_threshold - self.config.epsilon_comparison)
        )
        frac_surplus = np.mean(
            commodity_in >= (commodity_threshold - self.config.epsilon_comparison)
        )

        outputs[f"frac_timestep_{self.config.commodity}_deficit"] = frac_deficit
        outputs[f"frac_timestep_{self.config.commodity}_surplus"] = frac_surplus
        outputs[f"net_{self.config.commodity}_deficit"] = net_deficit
        outputs[f"net_{self.config.commodity}_surplus"] = net_surplus
