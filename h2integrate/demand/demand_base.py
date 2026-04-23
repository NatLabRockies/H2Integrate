import numpy as np
from attrs import field, define

from h2integrate.core.utilities import BaseConfig
from h2integrate.core.model_baseclasses import PerformanceModelBaseClass


@define(kw_only=True)
class DemandComponentBaseConfig(BaseConfig):
    """Configuration for defining a demand profile.

    This configuration object specifies the commodity being demanded and the
    demand profile that should be met by downstream components.

    Attributes:
        commodity (str): Name of the commodity being demanded
            (e.g., "hydrogen"). Converted to lowercase and stripped of whitespace.
        commodity_rate_units (str): Units of the commodity (e.g., "kg/h").
        demand_profile (int | float | list): Demand values for each timestep, in
            the same units as `commodity_rate_units`. May be a scalar for constant
            demand or a list/array for time-varying demand.
        commodity_amount_units (str | None, optional): Units of the commodity as an amount
            (i.e., kW*h or kg). If not provided, defaults to commodity_rate_units*h.
    """

    commodity: str = field(converter=str.strip)
    commodity_rate_units: str = field(converter=str.strip)
    demand_profile: int | float | list = field()
    commodity_amount_units: str = field(default=None)

    def __attrs_post_init__(self):
        if self.commodity_amount_units is None:
            self.commodity_amount_units = f"({self.commodity_rate_units})*h"


class DemandComponentBase(PerformanceModelBaseClass):
    """Base OpenMDAO component for open-loop demand tracking.

    This component defines the interfaces required for demand
    components, including inputs for demand, supplied commodity, and outputs
    tracking unmet demand, unused production, and total unmet demand.
    Subclasses must implement the :meth:`compute` method to define the
    demand component behavior.
    """

    _time_step_bounds = (3600, 3600)  # (min, max) time step lengths compatible with this model

    def setup(self):
        """Define inputs and outputs for demand component.

        Creates time-series inputs and outputs for commodity demand, supply,
        unmet demand, unused commodity, and total unmet demand. Shapes and units
        are determined by the plant configuration and load component configuration.

        Raises:
            KeyError: If required configuration keys are missing from
                ``plant_config`` or ``tech_config``.
        """
        self.commodity = self.config.commodity
        self.commodity_rate_units = self.config.commodity_rate_units
        self.commodity_amount_units = self.config.commodity_amount_units

        super().setup()

        self.add_input(
            f"{self.commodity}_demand",
            val=self.config.demand_profile,
            shape=self.n_timesteps,
            units=self.commodity_rate_units,
            desc=f"Demand profile of {self.commodity}",
        )

        self.add_input(
            f"{self.commodity}_in",
            val=0.0,
            shape=self.n_timesteps,
            units=self.commodity_rate_units,
            desc=f"Amount of {self.commodity} demand that has already been supplied",
        )

        self.add_output(
            f"unmet_{self.commodity}_demand_out",
            val=self.config.demand_profile,
            shape=self.n_timesteps,
            units=self.commodity_rate_units,
            desc=f"Remaining demand profile of {self.commodity}",
        )

        self.add_output(
            f"unused_{self.commodity}_out",
            val=0.0,
            shape=self.n_timesteps,
            units=self.commodity_rate_units,
            desc=f"Excess production of {self.commodity}",
        )

    def compute():
        """This method must be implemented by subclasses to define the
        demand component.

        Raises:
            NotImplementedError: Always, unless implemented in a subclass.
        """
        raise NotImplementedError("This method should be implemented in a subclass.")

    def calculate_outputs(self, commodity_in, commodity_demand, outputs):
        """Compute unmet demand, unused commodity, and converter output.

        This method compares the demand profile to the supplied commodity for
        each timestep and assigns unmet demand, curtailed production, and
        actual delivered output.

        Args:
            commodity_in (np.array): supplied commodity profile
            commodity_demand (np.array): entire commodity demand profile
            outputs (dict-like): Mapping of output variable names where results
                will be written, including:

                    * ``unmet_{commodity}_demand_out``: Unmet demand.
                    * ``unused_{commodity}_out``: Curtailed production.
                    * ``{commodity}_out``: Actual output delivered.

        Notes:
            All variables operate on a per-timestep basis and typically have
            array shape ``(n_timesteps,)``.
        """

        remaining_demand = commodity_demand - commodity_in

        # Calculate missed load and curtailed production
        outputs[f"unmet_{self.commodity}_demand_out"] = np.where(
            remaining_demand > 0, remaining_demand, 0
        )
        outputs[f"unused_{self.commodity}_out"] = np.where(
            remaining_demand < 0, -1 * remaining_demand, 0
        )

        # Calculate actual output based on demand met and curtailment
        outputs[f"{self.commodity}_out"] = commodity_in - outputs[f"unused_{self.commodity}_out"]

        outputs[f"rated_{self.commodity}_production"] = commodity_demand.mean()

        outputs[f"total_{self.commodity}_produced"] = np.sum(outputs[f"{self.commodity}_out"]) * (
            self.dt / 3600
        )

        outputs[f"annual_{self.commodity}_produced"] = (
            outputs[f"total_{self.commodity}_produced"] / self.fraction_of_year_simulated
        )

        outputs["capacity_factor"] = outputs[f"{self.commodity}_out"].sum() / commodity_demand.sum()

        return outputs
