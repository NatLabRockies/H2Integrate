from typing import ClassVar

import numpy as np
import openmdao.api as om
from attrs import field, define, validators

from h2integrate.core.utilities import BaseConfig
from h2integrate.core.validators import gte_zero, range_val_or_none


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
        require_storage_parameters (ClassVar[bool]): Class-level flag used by child config
            classes to require storage sizing and efficiency parameters. Leave False for
            controllers that do not need storage-specific fields. Set to True in child
            config classes that require optional attributes.

    Optional Attributes:
        max_capacity (float): Maximum storage capacity of the commodity (in non-rate units,
            e.g., "kg" if `commodity_rate_units` is "kg/h").
        max_soc_fraction (float): Maximum allowable state of charge (SOC) as a fraction
            of `max_capacity`, between 0 and 1.
        min_soc_fraction (float): Minimum allowable SOC as a fraction of `max_capacity`,
            between 0 and 1.
        init_soc_fraction (float): Initial SOC as a fraction of `max_capacity`,
            between 0 and 1.
        max_charge_rate (float): Maximum rate at which the commodity can be charged (in units
            per time step, e.g., "kg/time step"). This rate does not include the charge_efficiency.
        charge_equals_discharge (bool, optional): If True, set the max_discharge_rate equal to the
            max_charge_rate. If False, specify the max_discharge_rate as a value different than
            the max_charge_rate. Defaults to True.
        max_discharge_rate (float | None, optional): Maximum rate at which the commodity can be
            discharged (in units per time step, e.g., "kg/time step"). This rate does not include
            the discharge_efficiency. Only required if `charge_equals_discharge` is False.
        charge_efficiency (float | None, optional): Efficiency of charging the storage, represented
            as a decimal between 0 and 1 (e.g., 0.9 for 90% efficiency). Optional if
            `round_trip_efficiency` is provided.
        discharge_efficiency (float | None, optional): Efficiency of discharging the storage,
            represented as a decimal between 0 and 1 (e.g., 0.9 for 90% efficiency). Optional if
            `round_trip_efficiency` is provided.
        round_trip_efficiency (float | None, optional): Combined efficiency of charging and
            discharging the storage, represented as a decimal between 0 and 1 (e.g., 0.81 for
            81% efficiency). Optional if `charge_efficiency` and `discharge_efficiency` are
            provided.
    """

    commodity: str = field()
    commodity_rate_units: str = field()
    demand_profile: int | float | list | dict = field()
    commodity_amount_units: str = field(default=None)

    # Child classes can set this to True to require the storage sizing/efficiency fields.
    require_storage_parameters: ClassVar[bool] = False

    max_capacity: float | None = field(default=None)
    max_soc_fraction: float | None = field(default=None, validator=range_val_or_none(0, 1))
    min_soc_fraction: float | None = field(default=None, validator=range_val_or_none(0, 1))
    init_soc_fraction: float | None = field(default=None, validator=range_val_or_none(0, 1))
    max_charge_rate: float | None = field(default=None, validator=validators.optional(gte_zero))
    charge_equals_discharge: bool = field(default=True)
    max_discharge_rate: float | None = field(default=None)
    charge_efficiency: float | None = field(default=None, validator=range_val_or_none(0, 1))
    discharge_efficiency: float | None = field(default=None, validator=range_val_or_none(0, 1))
    round_trip_efficiency: float | None = field(default=None, validator=range_val_or_none(0, 1))

    def __attrs_post_init__(self):
        if self.commodity_amount_units is None:
            self.commodity_amount_units = f"({self.commodity_rate_units})*h"

        if self.require_storage_parameters:
            self._validate_required_storage_parameters()

    def _validate_required_storage_parameters(self):
        required_param_names = [
            "max_capacity",
            "max_soc_fraction",
            "min_soc_fraction",
            "init_soc_fraction",
            "max_charge_rate",
        ]
        missing = [name for name in required_param_names if getattr(self, name) is None]
        if missing:
            raise ValueError(
                "Missing required storage configuration parameter(s): " f"{', '.join(missing)}"
            )

        if not self.charge_equals_discharge and self.max_discharge_rate is None:
            raise ValueError(
                "max_discharge_rate must be provided when charge_equals_discharge is False."
            )

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

    _time_step_bounds = (
        3600,
        3600,
    )  # (min, max) time step lengths (in seconds) compatible with this model

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
