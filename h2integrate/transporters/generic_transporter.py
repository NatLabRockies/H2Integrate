import openmdao.api as om
from attrs import field, define

from h2integrate.core.utilities import BaseConfig, merge_shared_inputs


@define(kw_only=True)
class GenericTransporterPerformanceConfig(BaseConfig):
    """Configuration class for a generic transporter.

    Fields include `commodity` and `commodity_rate_units`.
    """

    commodity: str = field(converter=(str.strip))
    commodity_rate_units: str = field()


class GenericTransporterPerformanceModel(om.ExplicitComponent):
    """
    Transport any commodity from a source technology to a destination technology.

    This component is purposefully simple; a more realistic case might include
    losses or other considerations from system components.
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
        self.config = GenericTransporterPerformanceConfig.from_dict(
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
            f"{self.config.commodity}_out",
            val=0.0,
            shape=n_timesteps,
            units=self.config.commodity_rate_units,
        )

    def compute(self, inputs, outputs):
        outputs[f"{self.config.commodity}_out"] = inputs[f"{self.config.commodity}_in"]
