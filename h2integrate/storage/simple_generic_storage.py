from attrs import field, define

from h2integrate.core.utilities import BaseConfig, merge_shared_inputs
from h2integrate.core.model_baseclasses import PerformanceModelBaseClass


@define(kw_only=True)
class SimpleGenericStorageConfig(BaseConfig):
    commodity_name: str = field()
    commodity_units: str = field()  # TODO: update to commodity_rate_units


class SimpleGenericStorage(PerformanceModelBaseClass):
    """
    Simple generic storage model.
    """

    # def initialize(self):
    #     self.options.declare("tech_config", types=dict)
    #     self.options.declare("plant_config", types=dict)
    #     self.options.declare("driver_config", types=dict)

    def setup(self):
        # n_timesteps = self.options["plant_config"]["plant"]["simulation"]["n_timesteps"]
        self.config = SimpleGenericStorageConfig.from_dict(
            merge_shared_inputs(self.options["tech_config"]["model_inputs"], "performance"),
            strict=False,
            additional_cls_name=self.__class__.__name__,
        )
        self.commodity = self.config.commodity_name
        self.commodity_rate_units = self.config.commodity_units
        self.commodity_amount_units = f"({self.commodity_rate_units})*h"
        super().setup()
        self.add_input(
            f"{self.commodity}_set_point",
            val=0.0,
            shape=self.n_timesteps,
            units=self.commodity_rate_units,
        )

    def compute(self, inputs, outputs):
        outputs[f"{self.commodity}_out"] = inputs[f"{self.commodity}_set_point"]

        outputs[f"rated_{self.commodity}_production"] = inputs[f"{self.commodity}_set_point"].max()
        outputs[f"total_{self.commodity}_produced"] = outputs[f"{self.commodity}_out"].sum()
        outputs[f"annual_{self.commodity}_produced"] = outputs[
            f"total_{self.commodity}_produced"
        ] * (1 / self.fraction_of_year_simulated)

        max_production = (
            inputs[f"{self.commodity}_set_point"].max() * self.n_timesteps * (self.dt / 3600)
        )

        outputs["capacity_factor"] = outputs[f"total_{self.commodity}_produced"] / max_production
