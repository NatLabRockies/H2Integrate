import openmdao.api as om
from attrs import field, define

from h2integrate.core.utilities import BaseConfig, merge_shared_inputs


@define(kw_only=True)
class GenericCombinerPerformanceConfig(BaseConfig):
    """Configuration class for a generic combiner.

    Attributes:
        commodity (str): name of commodity type
        commodity_units (str): units of commodity production profile
        in_streams (int): how many inflow streams will be connected, defaults to 2
    """

    commodity: str = field(converter=(str.lower, str.strip))
    commodity_units: str = field()
    in_streams: int = field(default=2)


class GenericCombinerPerformanceModel(om.ExplicitComponent):
    """
    Combine any commodity or resource from multiple sources into one output without losses.

    This component is purposefully simple; a more realistic case might include
    losses or other considerations from system components.
    """

    def initialize(self):
        self.options.declare("driver_config", types=dict)
        self.options.declare("plant_config", types=dict)
        self.options.declare("tech_config", types=dict)

    def setup(self):
        self.config = GenericCombinerPerformanceConfig.from_dict(
            merge_shared_inputs(self.options["tech_config"]["model_inputs"], "performance")
        )

        n_timesteps = int(self.options["plant_config"]["plant"]["simulation"]["n_timesteps"])

        for i in range(1, self.config.in_streams + 1):
            self.add_input(
                f"{self.config.commodity}_in{i}",
                val=0.0,
                shape=n_timesteps,
                units=self.config.commodity_units,
            )

        self.add_output(
            f"{self.config.commodity}_out",
            val=0.0,
            shape=n_timesteps,
            units=self.config.commodity_units,
        )

    def compute(self, inputs, outputs):
        total = 0.0
        for key, value in inputs.items():
            if "_in" in key:
                total = total + value
        outputs[f"{self.config.commodity}_out"] = total
