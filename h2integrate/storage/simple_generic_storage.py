from attrs import field, define

from h2integrate.core.utilities import BaseConfig, merge_shared_inputs
from h2integrate.core.model_baseclasses import PerformanceModelBaseClass


@define(kw_only=True)
class SimpleGenericStorageConfig(BaseConfig):
    commodity_name: str = field()
    commodity_units: str = field()  # TODO: update to commodity_rate_units


class SimpleGenericStorage(PerformanceModelBaseClass):
    """
    Simple generic storage model that acts as a pass-through component.

    Note: this storage performance model is intended to be used with the
    `DemandOpenLoopStorageController` controller.

    """

    def setup(self):
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
        # Pass the commodity_out as the commodity_set_point
        outputs[f"{self.commodity}_out"] = inputs[f"{self.commodity}_set_point"]

        # Estimate the rated commodity production as the maximum value from the commodity_set_point
        outputs[f"rated_{self.commodity}_production"] = inputs[f"{self.commodity}_set_point"].max()

        # Calculate the total and annual commodity produced
        outputs[f"total_{self.commodity}_produced"] = outputs[f"{self.commodity}_out"].sum()
        outputs[f"annual_{self.commodity}_produced"] = outputs[
            f"total_{self.commodity}_produced"
        ] * (1 / self.fraction_of_year_simulated)

        # Calculate the maximum commodity production over the simulation
        max_production = (
            inputs[f"{self.commodity}_set_point"].max() * self.n_timesteps * (self.dt / 3600)
        )

        outputs["capacity_factor"] = outputs[f"total_{self.commodity}_produced"] / max_production
