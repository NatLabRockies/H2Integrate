import numpy as np
import openmdao.api as om
from attrs import field, define, validators

from h2integrate.core.utilities import BaseConfig, merge_shared_inputs


@define(kw_only=True)
class ThresholdStatisticsPerformanceConfig(BaseConfig):
    """
    Configuration class for a threshold statistics component.

    Attributes:
        commodity (str): name of the commodity for which threshold statistics are computed.
        commodity_rate_units (str): units of the commodity (e.g., "kg/h").
        epsilon_comparison (float): small positive value used to define a tolerance when comparing
    """

    commodity: str = field(converter=(str.lower, str.strip))
    commodity_rate_units: str = field()
    epsilon_comparison: float = field(default=0.0, validator=validators.ge(0.0))


class ThresholdStatisticsPerformanceModel(om.ExplicitComponent):
    """
    A component for threshold statistics of simulation timeseries as optimization QoIs.

    This component takes 8760 hourly timeseries (or other timeseries) and computes
    threshold statistics for use in optimization (post-processing would otherwise
    suffice).

    The available statistics are currently: net deficit, net surplus, fraction of timesteps
    below threshold, and fraction of timesteps above threshold.

    Inputs:
        commodity_in (array): timeseries of commodity values (e.g., electricity flow in MW
        commodity_threshold (array): timeseries of threshold values for the commodity
            (e.g., electricity demand in MW)

    Outputs:
        net_commodity_deficit (float): net deficit of the commodity timeseries below the threshold
        net_commodity_surplus (float): net surplus of the commodity timeseries above the threshold
        frac_timestep_commodity_deficit (float): fraction of timesteps where the commodity is
            below the threshold
        frac_timestep_commodity_surplus (float): fraction of timesteps where the commodity is
            above the threshold
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

        # compute deficit/surplus (using threshold epsilons)
        commodity_difference = commodity_in - (commodity_threshold - self.config.epsilon_comparison)
        deficit = np.maximum(0.0, -commodity_difference)
        surplus = np.maximum(0.0, commodity_difference)
        # use the epsilons conservatively to ID surplus or deficit

        # extract the statistics on the deficit or surplus and package outputs
        outputs[f"frac_timestep_{self.config.commodity}_deficit"] = np.mean(
            commodity_difference < 0.0
        )
        outputs[f"frac_timestep_{self.config.commodity}_surplus"] = np.mean(
            commodity_difference >= 0.0
        )
        outputs[f"net_{self.config.commodity}_deficit"] = np.sum(deficit)
        outputs[f"net_{self.config.commodity}_surplus"] = np.sum(surplus)
