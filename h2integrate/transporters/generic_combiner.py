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
    commodity_rate_units: str = field()
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
            merge_shared_inputs(self.options["tech_config"]["model_inputs"], "performance"),
            additional_cls_name=self.__class__.__name__,
        )

        n_timesteps = int(self.options["plant_config"]["plant"]["simulation"]["n_timesteps"])
        plant_life = int(self.options["plant_config"]["plant"]["plant_life"])

        for i in range(1, self.config.in_streams + 1):
            self.add_input(
                f"{self.config.commodity}_in{i}",
                val=0.0,
                shape=n_timesteps,
                units=self.config.commodity_rate_units,
            )
            self.add_input(
                f"rated_{self.config.commodity}_production{i}",
                val=0.0,
                shape=1,
                units=self.config.commodity_rate_units,
            )
            self.add_input(
                f"{self.config.commodity}_capacity_factor{i}",
                val=0.0,
                shape=plant_life,
                units="unitless",
            )

        self.add_output(
            f"{self.config.commodity}_out",
            val=0.0,
            shape=n_timesteps,
            units=self.config.commodity_rate_units,
        )
        self.add_output(
            f"{self.config.commodity}_capacity_factor",
            val=0.0,
            shape=plant_life,
            units="unitless",
        )
        self.add_output(
            f"rated_{self.config.commodity}_production",
            val=0.0,
            shape=1,
            units=self.config.commodity_rate_units,
        )

    def compute(self, inputs, outputs):
        total_out = 0.0
        weighted_cf = 0.0
        total_rated = 0.0
        for key, value in inputs.items():
            if "_in" in key:
                # add the commodity_in profile
                total_out = total_out + value
            if key.startswith("rated_"):
                # add the rated_commodity_production
                total_rated = total_rated + value
            if "_capacity_factor" in key:
                # get the stream number so we can get the proper rated capacity
                stream_number = key.split("capacity_factor")[-1]
                rated_capacity = inputs[f"rated_{self.config.commodity}_production{stream_number}"]
                # weight the capacity factor with the rated capacity
                weighted_cf = weighted_cf + (value * rated_capacity)

        outputs[f"{self.config.commodity}_out"] = total_out
        outputs[f"rated_{self.config.commodity}_production"] = total_rated
        if total_rated > 0:
            # weighted CF = (CF1*S1 + CF2*S2)/(S1 + S2)
            # Where S is the rated commodity production of input stream i
            # and CF is the capacity factor of input stream i
            outputs[f"{self.config.commodity}_capacity_factor"] = weighted_cf / total_rated
        else:
            outputs[f"{self.config.commodity}_capacity_factor"] = 0.0
