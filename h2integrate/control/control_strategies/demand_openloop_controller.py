import openmdao.api as om
from attrs import field, define

from h2integrate.core.utilities import BaseConfig


@define(kw_only=True)
class DemandOpenLoopControlBaseConfig(BaseConfig):
    """Configuration for defining an open-loop demand profile.

    This configuration object specifies the commodity being controlled and the
    demand profile that should be met by downstream components.

    Attributes:
        commodity_units (str): Units of the commodity (e.g., "kg/h").
        commodity_name (str): Name of the commodity being controlled
            (e.g., "hydrogen"). Converted to lowercase and stripped of whitespace.
        demand_profile (int | float | list): Demand values for each timestep, in
            the same units as `commodity_units`. May be a scalar for constant
            demand or a list/array for time-varying demand.
    """

    commodity_units: str = field(converter=str.strip)
    commodity_name: str = field(converter=(str.strip, str.lower))
    demand_profile: int | float | list = field()


class DemandOpenLoopControlBase(om.ExplicitComponent):
    """Base OpenMDAO component for open-loop demand tracking.

    This component defines the interfaces required for open-loop demand
    controllers, including inputs for demand, supplied commodity, and outputs
    tracking unmet demand, unused production, and total unmet demand.
    Subclasses must implement the :meth:`compute` method to define the
    controller behavior.
    """

    def initialize(self):
        """Declare component options.

        Options:
            driver_config (dict): Driver-level configuration parameters.
            plant_config (dict): Plant-level configuration, including number of
                simulation timesteps.
            tech_config (dict): Technology-specific configuration, including
                controller settings.
        """
        self.options.declare("driver_config", types=dict)
        self.options.declare("plant_config", types=dict)
        self.options.declare("tech_config", types=dict)

    def setup(self):
        """Define inputs and outputs for demand control.

        Creates time-series inputs and outputs for commodity demand, supply,
        unmet demand, unused commodity, and total unmet demand. Shapes and units
        are determined by the plant configuration and controller configuration.

        Raises:
            KeyError: If required configuration keys are missing from
                ``plant_config`` or ``tech_config``.
        """
        n_timesteps = int(self.options["plant_config"]["plant"]["simulation"]["n_timesteps"])

        commodity = self.config.commodity_name

        self.add_input(
            f"{commodity}_demand",
            val=self.config.demand_profile,
            shape=(n_timesteps),
            units=self.config.commodity_units,  # NOTE: hardcoded to align with controllers
            desc=f"Demand profile of {commodity}",
        )

        self.add_input(
            f"{commodity}_in",
            val=0.0,
            shape=(n_timesteps),
            units=self.config.commodity_units,
            desc=f"Amount of {commodity} demand that has already been supplied",
        )

        self.add_output(
            f"{commodity}_unmet_demand",
            val=self.config.demand_profile,
            shape=(n_timesteps),
            units=self.config.commodity_units,
            desc=f"Remaining demand profile of {commodity}",
        )

        self.add_output(
            f"{commodity}_unused_commodity",
            val=0.0,
            shape=(n_timesteps),
            units=self.config.commodity_units,
            desc=f"Excess production of {commodity}",
        )

        self.add_output(
            f"{commodity}_out",
            val=0.0,
            shape=(n_timesteps),
            units=self.config.commodity_units,
            desc=f"Production profile of {commodity}",
        )

        self.add_output(
            f"total_{commodity}_unmet_demand",
            units=self.config.commodity_units,
            desc="Total unmet demand",
        )

    def compute():
        """This method must be implemented by subclasses to define the
        controller.

        Raises:
            NotImplementedError: Always, unless implemented in a subclass.
        """
        raise NotImplementedError("This method should be implemented in a subclass.")
