import numpy as np
from attrs import field, define

from h2integrate.core.utilities import merge_shared_inputs
from h2integrate.control.control_strategies.storage.openloop_storage_control_base import (
    StorageOpenLoopControlBase,
    StorageOpenLoopControlBaseConfig,
)


@define(kw_only=True)
class SimpleStorageOpenLoopControllerConfig(StorageOpenLoopControlBaseConfig):
    """Configuration class for the SimpleStorageOpenLoopController

    Attributes:
        commodity (str): name of commodity
        commodity_rate_units (str): Units of the commodity (e.g., kW or kg/h).
        set_demand_as_avg_commodity_in (bool): If True, assume the demand is
            equal to the mean input commodity. If False, uses the demand input.
        demand_profile (int | float | list, optional): Demand values for each timestep, in
            the same units as `commodity_rate_units`. May be a scalar for constant
            demand or a list/array for time-varying demand.
            Only used if `set_demand_as_avg_commodity_in` is False. Defaults to 0.

    """

    set_demand_as_avg_commodity_in: bool = field()
    demand_profile: int | float | list = field(default=0.0)

    def __attrs_post_init__(self):
        super().__attrs_post_init__()

        if isinstance(self.demand_profile, list | np.ndarray):
            user_input_dmd = True if sum(self.demand_profile) > 0 else False
        else:
            user_input_dmd = True if self.demand_profile > 0 else False

        if self.set_demand_as_avg_commodity_in and user_input_dmd:
            # If using the average commodity in as the demand,
            # warn users if they input the demand profile
            msg = (
                "A non-zero demand profile was provided but set_demand_as_avg_commodity_in is True."
                " The provided demand profile will not be used, the demand profile will be "
                f"calculated as the mean of ``{self.commodity}_in``. "
            )
            raise ValueError(msg)


class SimpleStorageOpenLoopController(StorageOpenLoopControlBase):
    """
    A simple open-loop controller for storage systems.

    This controller directly sets a storage control set point as the difference between the
    demand and the available input commodity. It is useful for testing, as a placeholder for
    more complex storage controllers, and for maintaining consistency between controlled and
    uncontrolled frameworks.
    """

    def setup(self):
        self.config = SimpleStorageOpenLoopControllerConfig.from_dict(
            merge_shared_inputs(self.options["tech_config"]["model_inputs"], "control"),
            additional_cls_name=self.__class__.__name__,
            strict=False,
        )

        super().setup()

    def compute(self, inputs, outputs):
        """
        Simple controller that outputs `commodity_set_point`,
        the dispatch set-points for each timestep in `commodity_rate_units`.
        Negative values command charging, positive values command discharging.

        """

        if (
            self.config.set_demand_as_avg_commodity_in
            and inputs[f"{self.config.commodity}_demand"].sum() > 0
        ):
            msg = (
                "A non-zero demand profile was input but set_demand_as_avg_commodity_in is True."
                " The input demand profile will not be used, the demand profile will be "
                f"calculated as the mean of ``{self.config.commodity}_in``. "
            )
            raise ValueError(msg)

        if self.config.set_demand_as_avg_commodity_in:
            # Assume the demand is the average of the input commodity
            commodity_demand = np.mean(inputs[f"{self.config.commodity}_in"]) * np.ones(
                self.n_timesteps
            )
        else:
            commodity_demand = inputs[f"{self.config.commodity}_demand"]

        # Assign the set point as the difference between the demand and the input commodity
        # when demand > input, the set point is positive to command discharging
        # when demand < input, the set point is negative to command charging
        outputs[f"{self.config.commodity}_set_point"] = (
            commodity_demand - inputs[f"{self.config.commodity}_in"]
        )
