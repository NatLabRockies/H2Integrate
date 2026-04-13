from copy import deepcopy

import numpy as np
from attrs import field, define

from h2integrate.core.utilities import merge_shared_inputs
from h2integrate.core.validators import gte_zero, range_val, range_val_or_none
from h2integrate.control.control_strategies.storage.openloop_storage_control_base import (
    StorageOpenLoopControlBase,
    StorageOpenLoopControlBaseConfig,
)


@define(kw_only=True)
class DemandOpenLoopStorageControllerConfig(StorageOpenLoopControlBaseConfig):
    """
    Configuration class for the DemandOpenLoopStorageController.

    This class defines the parameters required to configure the `DemandOpenLoopStorageController`.

    Attributes:
        commodity (str): Name of the commodity being controlled
            (e.g., "hydrogen"). Stripped of whitespace.
        commodity_rate_units (str): Units of the commodity (e.g., "kg/h").
        demand_profile (int | float | list): Demand values for each timestep, in
            the same units as `commodity_rate_units`. May be a scalar for constant
            demand or a list/array for time-varying demand.
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
        commodity_amount_units (str | None, optional): Units of the commodity as an amount
            (i.e., kW*h or kg). If not provided, defaults to commodity_rate_units*h.
    """

    max_capacity: float = field()
    max_soc_fraction: float = field(validator=range_val(0, 1))
    min_soc_fraction: float = field(validator=range_val(0, 1))
    init_soc_fraction: float = field(validator=range_val(0, 1))
    max_charge_rate: float = field(validator=gte_zero)
    charge_equals_discharge: bool = field(default=True)
    max_discharge_rate: float | None = field(default=None)
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
        super().__attrs_post_init__()

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


class DemandOpenLoopStorageController(StorageOpenLoopControlBase):
    """
    A controller that manages commodity flow based on demand and storage constraints.

    The `DemandOpenLoopStorageController` computes the dispatch commands for a commodity storage
    system. It uses a demand profile and storage parameters to determine how much of the
    commodity to charge, discharge, or curtail at each time step.
    """

    _time_step_bounds = (
        3600,
        3600,
    )  # (min, max) time step lengths (in seconds) compatible with this model

    def setup(self):
        self.config = DemandOpenLoopStorageControllerConfig.from_dict(
            merge_shared_inputs(self.options["tech_config"]["model_inputs"], "control"),
            strict=False,
            additional_cls_name=self.__class__.__name__,
        )
        super().setup()

        self.n_timesteps = self.options["plant_config"]["plant"]["simulation"]["n_timesteps"]

        # Design constraints of storage system
        self.add_input(
            "max_charge_rate",
            val=self.config.max_charge_rate,
            units=self.config.commodity_rate_units,
            desc="Storage charge/discharge rate",
        )

        self.add_input(
            "storage_capacity",
            val=self.config.max_capacity,
            units=self.config.commodity_amount_units,
            desc="Maximum storage capacity",
        )

        if not self.config.charge_equals_discharge:
            self.add_input(
                "max_discharge_rate",
                val=self.config.max_discharge_rate,
                units=self.config.commodity_rate_units,
                desc="Storage discharge rate",
            )

    def compute(self, inputs, outputs):
        """
        Compute storage state of charge (SOC), delivered output, curtailment, and unmet
        demand over the simulation horizon.

        This method applies an open-loop storage control strategy to balance the
        commodity demand and input flow. When input exceeds demand, excess commodity
        is used to charge storage (subject to rate, efficiency, and SOC limits). When
        demand exceeds input, storage is discharged to meet the deficit (also subject
        to constraints). SOC is updated at each time step, ensuring it remains within
        allowable bounds.

        Expected input keys:
            * ``<commodity>_in``: Timeseries of commodity available at each time step.
            * ``<commodity>_demand``: Timeseries demand profile.
            * ``max_charge_rate``: Maximum charge rate permitted.
            * ``max_capacity``: Maximum total storage capacity.

        Outputs populated:
            * ``<commodity>_set_point``: Dispatch command to storage,
                negative when charging, positive when discharging.

        Control logic includes:
            * Enforcing SOC limits (min, max, and initial conditions).
            * Applying charge and discharge efficiencies.
            * Observing charge/discharge rate limits.
            * Tracking energy shortfalls and excesses at each time step.

        Raises:
            UserWarning: If the demand profile is entirely zero.
            UserWarning: If ``max_charge_rate`` or ``max_capacity`` is negative.

        Returns:
            None
        """
        commodity = self.config.commodity
        if np.all(inputs[f"{commodity}_demand"] == 0.0):
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

        max_capacity = inputs["storage_capacity"].item()
        max_charge_rate = inputs["max_charge_rate"].item()

        if self.config.charge_equals_discharge:
            max_discharge_rate = inputs["max_charge_rate"].item()
        else:
            max_discharge_rate = inputs["max_discharge_rate"].item()

        soc_max = self.config.max_soc_fraction
        soc_min = self.config.min_soc_fraction
        init_soc_fraction = self.config.init_soc_fraction

        charge_eff = float(self.config.charge_efficiency)
        discharge_eff = float(self.config.discharge_efficiency)

        # Initialize time-step state of charge prior to loop so the loop starts with
        # the previous time step's value
        soc = deepcopy(init_soc_fraction)

        demand_profile = inputs[f"{commodity}_demand"]

        # initialize outputs
        soc_array = np.zeros(self.n_timesteps)
        set_point_array = np.zeros(self.n_timesteps)
        combined_output_array = np.zeros(self.n_timesteps)
        # Loop through each time step
        for t, demand_t in enumerate(demand_profile):
            # Get the input flow at the current time step
            input_flow = inputs[f"{commodity}_in"][t]

            # Calculate the available charge/discharge capacity
            available_charge = float((soc_max - soc) * max_capacity)
            available_discharge = float((soc - soc_min) * max_capacity)

            # Determine the output flow based on demand_t and SOC
            if demand_t > input_flow:
                # Discharge storage to meet demand.
                # `discharge_needed` is as seen by the storage
                discharge_needed = (demand_t - input_flow) / discharge_eff
                # `discharge` is as seen by the storage, but `max_discharge_rate` is as observed
                # outside the storage
                discharge = min(
                    discharge_needed, available_discharge, max_discharge_rate / discharge_eff
                )

                soc -= discharge / max_capacity  # soc is a ratio with value between 0 and 1
                # output is as observed outside the storage, so we need to adjust `discharge` by
                # applying `discharge_efficiency`.
                combined_output_array[t] = input_flow + discharge * discharge_eff
                set_point_array[t] = discharge * discharge_eff
            else:
                # Charge storage with unused input
                # `unused_input` is as seen outside the storage
                unused_input = input_flow - demand_t
                unused_input = unused_input.item()
                # `charge` is as seen by the storage, but the things being compared should all be as
                # seen outside the storage so we need to adjust `available_charge` outside the
                # storage view and the final result back into the storage view.
                charge = (
                    min(unused_input, available_charge / charge_eff, max_charge_rate) * charge_eff
                )
                soc += charge / max_capacity  # soc is a ratio with value between 0 and 1
                combined_output_array[t] = demand_t
                set_point_array[t] = -1 * charge / charge_eff

            # Ensure SOC stays within bounds
            soc = max(soc_min, min(soc_max, soc))

            # Record the SOC for the current time step
            soc_array[t] = deepcopy(soc)

        outputs[f"{commodity}_set_point"] = set_point_array
