import openmdao.api as om
from attrs import field, define

from h2integrate.core.utilities import BaseConfig, merge_shared_inputs
from h2integrate.core.validators import contains


@define(kw_only=True)
class GenericSummerPerformanceConfig(BaseConfig):
    """Configuration class for a generic summer for commodities or feedstocks.

    Fields include `commodity`, `commodity_rate_units`, and `operation_mode`.
    """

    commodity: str = field(converter=(str.lower, str.strip))
    commodity_rate_units: str = field()
    operation_mode: str = field(
        default="production",
        converter=(str.lower, str.strip),
        validator=contains(["production", "consumption"]),
    )


class GenericSummerPerformanceModel(om.ExplicitComponent):
    """
    Sum the production or consumption profile of some commodity from a single source.
    """

    _time_step_bounds = (1, 1e9)  # (min, max) time step lengths compatible with this model

    def initialize(self):
        self.options.declare("driver_config", types=dict)
        self.options.declare("plant_config", types=dict)
        self.options.declare("tech_config", types=dict)

    def setup(self):
        self.config = GenericSummerPerformanceConfig.from_dict(
            merge_shared_inputs(self.options["tech_config"]["model_inputs"], "performance"),
            additional_cls_name=self.__class__.__name__,
        )

        n_timesteps = int(self.options["plant_config"]["plant"]["simulation"]["n_timesteps"])
        plant_life = int(self.options["plant_config"]["plant"]["plant_life"])

        if self.config.commodity == "electricity":
            # NOTE: this should be updated in overhaul required for flexible dt
            # and flexible simulation length
            summed_units = f"{self.config.commodity_rate_units}*h/year"
        else:
            summed_units = f"{self.config.commodity_rate_units}*h/year"

        self.add_input(
            f"{self.config.commodity}_in",
            val=0.0,
            shape=n_timesteps,
            units=self.config.commodity_rate_units,
        )

        if self.config.operation_mode == "consumption":
            self.add_output(
                f"total_{self.config.commodity}_consumed",
                val=0.0,
                shape=plant_life,
                units=summed_units,
            )
        else:  # production mode (default)
            self.add_output(
                f"total_{self.config.commodity}_produced",
                val=0.0,
                shape=plant_life,
                units=summed_units,
            )

    def compute(self, inputs, outputs):
        if self.config.operation_mode == "consumption":
            outputs[f"total_{self.config.commodity}_consumed"] = sum(
                inputs[f"{self.config.commodity}_in"]
            )
        else:  # production mode (default)
            outputs[f"total_{self.config.commodity}_produced"] = sum(
                inputs[f"{self.config.commodity}_in"]
            )
