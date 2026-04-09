import numpy as np
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
        demand_profile (int | float | list | dict): Demand values for each timestep, in
            the same units as `commodity_rate_units`. May be a scalar for constant
            demand or a list/array/dict for time-varying demand. If a dict is provided, it
            it should have two keys: "time_date" and "demand".
        commodity_amount_units (str | None, optional): Units of the commodity as an amount
            (i.e., kW*h or kg). If not provided, defaults to `commodity_rate_units*h`.

    """

    commodity: str = field()
    commodity_rate_units: str = field()
    demand_profile: int | float | list | dict = field()
    commodity_amount_units: str = field(default=None)

    # max_capacity: float = field()
    # max_soc_fraction: float = field(validator=range_val(0, 1))
    # min_soc_fraction: float = field(validator=range_val(0, 1))
    # init_soc_fraction: float = field(validator=range_val(0, 1))
    # max_charge_rate: float = field(validator=gte_zero)
    # charge_equals_discharge: bool = field(default=True)
    # max_discharge_rate: float | None = field(default=None)
    # charge_efficiency: float | None = field(default=None, validator=range_val_or_none(0, 1))
    # discharge_efficiency: float | None = field(default=None, validator=range_val_or_none(0, 1))
    # round_trip_efficiency: float | None = field(default=None, validator=range_val_or_none(0, 1))

    def __attrs_post_init__(self):
        if self.commodity_amount_units is None:
            self.commodity_amount_units = f"({self.commodity_rate_units})*h"

    def common_post_init_operations(self):
        """
        Post-initialization logic to validate and calculate efficiencies.

        Ensures that either `charge_efficiency` and `discharge_efficiency` are provided,
        or `round_trip_efficiency` is provided. If `round_trip_efficiency` is provided,
        it calculates `charge_efficiency` and `discharge_efficiency` as the square root
        of `round_trip_efficiency`.
        """
        if (self.round_trip_efficiency is not None) and (
            self.charge_efficiency is None and self.discharge_efficiency is None
        ):
            # Calculate charge and discharge efficiencies from round-trip efficiency
            self.charge_efficiency = np.sqrt(self.round_trip_efficiency)
            self.discharge_efficiency = np.sqrt(self.round_trip_efficiency)
            self.round_trip_efficiency = None
        if self.charge_efficiency is None or self.discharge_efficiency is None:
            raise ValueError(
                "Exactly one of the following sets of parameters must be set: (a) "
                "`round_trip_efficiency`, or (b) both `charge_efficiency` "
                "and `discharge_efficiency`."
            )

        if self.charge_equals_discharge:
            if (
                self.max_discharge_rate is not None
                and self.max_discharge_rate != self.max_charge_rate
            ):
                msg = (
                    "Max discharge rate does not equal max charge rate but charge_equals_discharge "
                    f"is True. Discharge rate is {self.max_discharge_rate} and charge rate "
                    f"is {self.max_charge_rate}."
                )
                raise ValueError(msg)

            self.max_discharge_rate = self.max_charge_rate


class StorageOpenLoopControlBase(om.ExplicitComponent):
    """Base OpenMDAO component for open-loop demand tracking.

    This component defines the interfaces required for open-loop demand
    controllers, including inputs for demand, available commodity, and outputs
    dispatch command profile.
    """

    def initialize(self):
        self.options.declare("driver_config", types=dict)
        self.options.declare("plant_config", types=dict)
        self.options.declare("tech_config", types=dict)

    def setup(self):
        self.n_timesteps = int(self.options["plant_config"]["plant"]["simulation"]["n_timesteps"])

        commodity = self.config.commodity

        demand_data = self.config.demand_profile

        self.add_input(
            f"{commodity}_demand",
            val=demand_data if not isinstance(demand_data, dict) else demand_data["demand"],
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

    def common_checks_needed_in_compute(self, inputs):
        if np.all(inputs[f"{self.config.commodity}_demand"] == 0.0):
            msg = "Demand profile is zero, check that demand profile is input"
            raise UserWarning(msg)
        if inputs["max_charge_rate"][0] < 0:
            msg = (
                f"max_charge_rate cannot be less than zero and has value of "
                f"{inputs['max_charge_rate']}"
            )
            raise UserWarning(msg)
        if inputs["storage_capacity"][0] < 0:
            msg = (
                f"storage_capacity cannot be less than zero and has value of "
                f"{inputs['storage_capacity']}"
            )
            raise UserWarning(msg)
