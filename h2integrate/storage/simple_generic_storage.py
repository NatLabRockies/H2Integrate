import openmdao.api as om
from attrs import field, define

from h2integrate.core.utilities import BaseConfig, merge_shared_inputs


@define(kw_only=True)
class SimpleGenericStorageConfig(BaseConfig):
    commodity_name: str = field()
    commodity_units: str = field()


class SimpleGenericStorage(om.ExplicitComponent):
    """
    Simple generic storage model.
    """

    def initialize(self):
        self.options.declare("tech_config", types=dict)
        self.options.declare("plant_config", types=dict)
        self.options.declare("driver_config", types=dict)

    def setup(self):
        n_timesteps = self.options["plant_config"]["plant"]["simulation"]["n_timesteps"]
        self.config = SimpleGenericStorageConfig.from_dict(
            merge_shared_inputs(self.options["tech_config"]["model_inputs"], "performance"),
            strict=False,
        )
        commodity_name = self.config.commodity_name
        commodity_units = self.config.commodity_units
        self.add_input(f"{commodity_name}_in", val=0.0, shape=n_timesteps, units=commodity_units)

    def compute(self, inputs, outputs):
        pass
