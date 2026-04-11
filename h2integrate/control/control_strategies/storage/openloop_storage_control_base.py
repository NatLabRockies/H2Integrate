import openmdao.api as om
from attrs import field, define

from h2integrate.core.utilities import BaseConfig


@define(kw_only=True)
class StorageOpenLoopControlBaseConfig(BaseConfig):
    """
    Configuration class for the open-loop storage control models.

     Attributes:
        commodity (str): Name of the commodity being stored (e.g., "hydrogen").
        commodity_rate_units (str): Rate units of the commodity (e.g., "kg/h" or "kW").
        demand_profile (int | float | list): Demand values for each timestep, in
            the same units as `commodity_rate_units`. May be a scalar for constant
            demand or a list/array for time-varying demand.
        commodity_amount_units (str | None, optional): Units of the commodity as an amount
            (i.e., kW*h or kg). If not provided, defaults to `commodity_rate_units*h`.

    """

    commodity: str = field()
    commodity_rate_units: str = field()
    demand_profile: int | float | list = field()
    commodity_amount_units: str = field(default=None)

    def __attrs_post_init__(self):
        if self.commodity_amount_units is None:
            self.commodity_amount_units = f"({self.commodity_rate_units})*h"


class StorageOpenLoopControlBase(om.ExplicitComponent):
    """Base OpenMDAO component for open-loop demand tracking.

    This component defines the interfaces required for open-loop demand
    controllers, including inputs for demand, available commodity, and outputs
    dispatch command profile.
    """

    _time_step_bounds = (3600, 3600)  # (min, max) time step lengths compatible with this model

    def initialize(self):
        self.options.declare("driver_config", types=dict)
        self.options.declare("plant_config", types=dict)
        self.options.declare("tech_config", types=dict)

    def setup(self):
        self.n_timesteps = int(self.options["plant_config"]["plant"]["simulation"]["n_timesteps"])

        commodity = self.config.commodity

        self.add_input(
            f"{commodity}_demand",
            val=self.config.demand_profile,
            shape=self.n_timesteps,
            units=self.config.commodity_rate_units,
            desc=f"Demand profile of {commodity}",
        )

        self.add_input(
            f"{commodity}_in",
            val=0.0,
            shape=self.n_timesteps,
            units=self.config.commodity_rate_units,
            desc=f"Amount of {commodity} demand that has already been supplied",
        )

        self.add_output(
            f"{commodity}_set_point",
            val=0.0,
            shape=self.n_timesteps,
            units=self.config.commodity_rate_units,
            desc=f"Dispatch commands for {commodity} storage",
        )

    def compute():
        """This method must be implemented by subclasses to define the
        controller.

        Raises:
            NotImplementedError: Always, unless implemented in a subclass.
        """
        raise NotImplementedError("This method should be implemented in a subclass.")
