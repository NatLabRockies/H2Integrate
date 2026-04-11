import numpy as np
from attrs import field, define

from h2integrate.core.utilities import merge_shared_inputs
from h2integrate.core.validators import gt_zero, range_val, range_val_or_none
from h2integrate.storage.storage_baseclass import (
    StoragePerformanceBase,
    StoragePerformanceBaseConfig,
)


@define(kw_only=True)
class StoragePerformanceModelConfig(StoragePerformanceBaseConfig):
    """Configuration class for storage performance models.

    This class defines configuration parameters for simulating storage
    performance with the Pyomo controllers. It includes
    specifications such as capacity, charge rate, state-of-charge limits,
    and charge/discharge efficiencies.

    Attributes:
        commodity (str): name of commodity
        commodity_rate_units (str): Units of the commodity (e.g., "kg/h").
        demand_profile (int | float | list): Demand values for each timestep, in
            the same units as `commodity_rate_units`. May be a scalar for constant
            demand or a list/array for time-varying demand.
        max_capacity (float):  Maximum storage energy capacity in commodity_amount_units.
            Must be greater than zero.
        max_charge_rate (float): Rated commodity capacity of the storage  in commodity_rate_units.
            Must be greater than zero.
        min_soc_fraction (float): Minimum allowable state of charge as a fraction (0 to 1).
        max_soc_fraction (float): Maximum allowable state of charge as a fraction (0 to 1).
        init_soc_fraction (float): Initial state of charge as a fraction (0 to 1).
        commodity_amount_units (str | None, optional): Units of the commodity as an amount
            (i.e., kW*h or kg). If not provided, defaults to commodity_rate_units*h.
        max_discharge_rate (float | None, optional): Maximum rate at which the commodity can be
            discharged (in units per time step, e.g., "kg/time step"). This rate does not include
            the discharge_efficiency. Only required if `charge_equals_discharge` is False.
        charge_equals_discharge (bool, optional): If True, set the max_discharge_rate equal to the
            max_charge_rate. If False, specify the max_discharge_rate as a value different than
            the max_charge_rate. Defaults to True.
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

    max_capacity: float = field(validator=gt_zero)
    max_charge_rate: float = field(validator=gt_zero)

    init_soc_fraction: float = field(validator=range_val(0, 1))

    commodity_amount_units: str = field(default=None)
    max_discharge_rate: float | None = field(default=None)
    charge_equals_discharge: bool = field(default=True)

    charge_efficiency: float | None = field(default=None, validator=range_val_or_none(0, 1))
    discharge_efficiency: float | None = field(default=None, validator=range_val_or_none(0, 1))
    round_trip_efficiency: float | None = field(default=None, validator=range_val_or_none(0, 1))

    def __attrs_post_init__(self):
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

        if not self.charge_equals_discharge and self.max_discharge_rate is None:
            msg = (
                "max_discharge_rate is required when charge_equals_discharge is False. "
                "Please input the discharge rate using the key `max_discharge_rate`."
            )
            raise ValueError(msg)

        if self.commodity_amount_units is None:
            self.commodity_amount_units = f"({self.commodity_rate_units})*h"


class StoragePerformanceModel(StoragePerformanceBase):
    """OpenMDAO component for a storage component."""

    _time_step_bounds = (3600, 3600)  # (min, max) time step lengths compatible with this model

    def setup(self):
        self.config = StoragePerformanceModelConfig.from_dict(
            merge_shared_inputs(self.options["tech_config"]["model_inputs"], "performance"),
            strict=False,
            additional_cls_name=self.__class__.__name__,
        )

        self.commodity = self.config.commodity
        self.commodity_rate_units = self.config.commodity_rate_units
        self.commodity_amount_units = self.config.commodity_amount_units

        super().setup()

    def compute(self, inputs, outputs, discrete_inputs=[], discrete_outputs=[]):
        """Run the storage performance model."""
        self.current_soc = self.config.init_soc_fraction

        charge_rate = inputs["max_charge_rate"][0]
        if "max_discharge_rate" in inputs:
            discharge_rate = inputs["max_discharge_rate"][0]
        else:
            discharge_rate = inputs["max_charge_rate"][0]
        storage_capacity = inputs["storage_capacity"][0]
        outputs = self.run_storage(
            charge_rate, discharge_rate, storage_capacity, inputs, outputs, discrete_inputs
        )
