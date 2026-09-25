import numpy as np
import openmdao.api as om
from attrs import field, define

from h2integrate.core.utilities import BaseConfig, merge_shared_inputs


@define(kw_only=True)
class SummaryStatisticsPerformanceConfig(BaseConfig):
    """
    Configuration class for a summary statistics component.

    Attributes:
        commodity (str): name of the commodity for which summary statistics are computed.
        commodity_rate_units (str): units of the commodity (e.g., "kg/h").
        percentiles (list[float]): list of percentiles to compute for the commodity timeseries.
            Defaults to [2.275, 5.0, 15.865, 50.0, 84.135, 95.0, 97.725]
            (2-sigma, 5%, 1-sigma, 50%, ...).
    """

    commodity: str = field(converter=(str.lower, str.strip))
    commodity_rate_units: str = field()
    percentiles: list[float] = field(
        factory=lambda: [2.275, 5.0, 15.865, 50.0, 84.135, 95.0, 97.725]
    )


class SummaryStatisticsPerformanceModel(om.ExplicitComponent):
    """
    A component for summary statistics of simulation timeseries as optimization QoIs

    This component takes 8760 hourly timeseries (or other timeseries) and computes
    summary statistics for use in optimization (post-processing would otherwise
    suffice).

    The available statistics are currently: mean, stdev, median, min, max, and
    percentiles (with the ability to set user-defined percentile targets).

    Inputs:
        commodity_in (array): timeseries of commodity values (e.g., electricity flow in MW)

    Outputs:
        commodity_mean (float): mean value of the commodity timeseries (with the same units)
        commodity_stdev (float): standard deviation of the commodity timeseries
            (with the same units)
        commodity_median (float): median value of the commodity timeseries (with the same units)
        commodity_min (float): minimum value of the commodity timeseries (with the same units)
        commodity_max (float): maximum value of the commodity timeseries (with the same units)
        commodity_percentiles (array): percentiles of the commodity timeseries (with the same
            units) as specified in config
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
            f"{self.config.commodity}_stdev",
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

        # compute statistics
        outputs[f"{self.config.commodity}_mean"] = np.mean(commodity_in)
        outputs[f"{self.config.commodity}_stdev"] = np.std(commodity_in)
        outputs[f"{self.config.commodity}_median"] = np.median(commodity_in)
        outputs[f"{self.config.commodity}_min"] = np.min(commodity_in)
        outputs[f"{self.config.commodity}_max"] = np.max(commodity_in)
        outputs[f"{self.config.commodity}_percentiles"] = np.percentile(
            commodity_in, self.config.percentiles
        )
