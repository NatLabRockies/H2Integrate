import numpy as np
import openmdao.api as om
from attrs import field, define

from h2integrate.core.utilities import BaseConfig, merge_shared_inputs


@define(kw_only=True)
class SummaryStatisticsPerformanceConfig(BaseConfig):
    """Configuration class for a statistical summary component.

    Fields include `commodity`, `commodity_rate_units`, and `percentiles`.
    """

    commodity: str = field(converter=(str.lower, str.strip))
    commodity_rate_units: str = field()
    percentiles: list[float] = field(
        factory=lambda: [2.275, 5.0, 15.865, 50.0, 84.135, 95.0, 97.725]
    )


class SummaryStatisticsPerformanceModel(om.ExplicitComponent):
    """
    Compute summary statistics on a given input timeseries commodity.
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
        self.config = SummaryStatisticsPerformanceConfig.from_dict(
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

        self.add_output(
            f"{self.config.commodity}_mean",
            val=0.0,
            shape=1,
            units=self.config.commodity_rate_units,
        )

        self.add_output(
            f"{self.config.commodity}_median",
            val=0.0,
            shape=1,
            units=self.config.commodity_rate_units,
        )

        self.add_output(
            f"{self.config.commodity}_min",
            val=0.0,
            shape=1,
            units=self.config.commodity_rate_units,
        )

        self.add_output(
            f"{self.config.commodity}_max",
            val=0.0,
            shape=1,
            units=self.config.commodity_rate_units,
        )

        self.add_output(
            f"{self.config.commodity}_percentiles",
            val=0.0,
            shape=len(self.config.percentiles),
            units=self.config.commodity_rate_units,
        )

    def compute(self, inputs, outputs):
        commodity_in = inputs[f"{self.config.commodity}_in"]

        outputs[f"{self.config.commodity}_mean"] = np.mean(commodity_in)
        outputs[f"{self.config.commodity}_median"] = np.median(commodity_in)
        outputs[f"{self.config.commodity}_min"] = np.min(commodity_in)
        outputs[f"{self.config.commodity}_max"] = np.max(commodity_in)
        outputs[f"{self.config.commodity}_percentiles"] = np.percentile(
            commodity_in, self.config.percentiles
        )
