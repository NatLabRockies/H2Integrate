from copy import deepcopy
from datetime import time

import numpy as np
import pandas as pd
from attrs import field, define

from h2integrate.core.utilities import merge_shared_inputs
from h2integrate.core.validators import contains, gte_zero, range_val, range_val_or_none
from h2integrate.control.control_strategies.storage.openloop_storage_control_base import (
    StorageOpenLoopControlBase,
    StorageOpenLoopControlBaseConfig,
)


@define(kw_only=True)
class PeakLoadManagementOpenLoopStorageControllerConfig(StorageOpenLoopControlBaseConfig):
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
        demand_profile_supervisor (dict | None, optional): Demand values for additional
            connected system for each timestep, in the same units as `commodity_rate_units`.
            May be a scalar for constant demand or a list/array for time-varying demand.
        dispatch_priority_demand_profile (str | None, optional): which demand profile takes
            precedence for dispatch decisions.
        max_supervisor_event_period: (int | None, optional): Duration, in time steps, of the period
            in which the max_supervisor_events must occur. Defaults to the length of the simulation,
            or in other words self.n_timesteps
        max_supervisor_events: (int | None, optional): The maximum number of discharge events
            allowed for the supervisor in the period specified in max_supervisor_event_period,
            or across all time steps if max_supervisor_event_period is None.

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
    demand_profile: dict = field()
    demand_profile_supervisor: dict | None = field(default=None)
    dispatch_priority_demand_profile: str = field(
        default="demand_profile_supervisor",
        validator=contains(["demand_profile", "demand_profile_supervisor"]),
    )
    max_supervisor_events: int | None = (field(default=None),)
    supervisor_event_period: int | str | None = field(default=None)
    peak_range: dict = field(default={"start": time.min, "end": time.max})
    advance_discharge_period: dict = field(default={"units": "H", "val": 2})
    delay_charge_period: dict = field(default={"units": "H", "val": 4})
    allow_charge_in_peak_range: bool = field(default=True)

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


class PeakLoadManagementOpenLoopStorageController(StorageOpenLoopControlBase):
    """
    A controller that manages commodity flow based on demand and storage constraints.

    The `DemandOpenLoopStorageController` computes the dispatch commands for a commodity storage
    system. It uses a demand profile and storage parameters to determine how much of the
    commodity to charge, discharge, or curtail at each time step.
    """

    def setup(self):
        self.config = PeakLoadManagementOpenLoopStorageController.from_dict(
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

        # n_timesteps is number of timesteps in a simulation
        self.n_timesteps = self.options["plant_config"]["plant"]["simulation"]["n_timesteps"]

        # dt is seconds per timestep
        self.dt = self.options["plant_config"]["plant"]["simulation"]["dt"]

        # determine demand_profile_supervisor peaks
        if self.config.demand_profile_supervisor is not None:
            self.supervisor_peaks_df = self.get_peaks(
                demand_profile=self.config.demand_profile_supervisor,
                n_max_events=self.config.max_supervisor_events,
                max_events_period=self.config.max_supervisor_event_period,
                min_proximity={"units": "H", "val": 4},
            )
        else:
            self.supervisor_peaks_df = None

        # determine demand_profile peaks using defaults of daily peaks inside peak_range
        # for the full simulation but respecting the peak range specified in the config
        self.secondary_peaks_df = self.get_peaks(
            demand_profile=self.condig.demand_profile,
            peak_range=self.config.peak_range,
        )

        if self.config.dispatch_priority_demand_profile == "demand_profile_supervisor":
            self.peaks_df = self.merge_peaks(self.supervisor_peaks_df, self.secondary_peaks_df)
        else:
            self.peaks_df = self.merge_peaks(self.secondary_peaks_df, self.supervisor_peaks_df)

        self.get_time_to_peak()

        self.get_allowed_discharge()

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

        # we need to discharge starting at advance_discharge_period before each peak
        # we also need to only discharge the peak_range
        # we also need to discharge until the SOC is at the min_soc
        # discharge at the max discharge rate always except to reach min charge

        # we need to charge soon after the battery reaches the min_charge, but not too soon
        # we cannot charge during the peak range if allow_charge_during_peak is False
        # charge at the max charge rate always except to reach max charge

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

        # demand_profile = inputs[f"{commodity}_demand"]

        # initialize outputs
        soc_array = np.zeros(self.n_timesteps)
        set_point_array = np.zeros(self.n_timesteps)

        # we need a bool to track if we are discharging or charging or neither
        discharging = False
        charging = False
        advance_discharge_period = pd.Timedelta(self.config.advance_discharge_period)
        delay_charge_period = pd.Timedelta(self.config.delay_charge_period)

        last_discharge = self.peaks_df["time_date"].iloc[0] - delay_charge_period

        # Loop through each time step
        for i, demand_t in enumerate(self.peaks_df["demand"].tolist()):
            td = self.peaks_df["time_date"]
            time_to_peak = self.peaks_df["time_to_peak"].iloc[i]

            # Get the input flow at the current time step
            input_flow = inputs[f"{commodity}_in"][i]

            # Calculate the available charge/discharge capacity
            available_charge = float((soc_max - soc) * max_capacity)
            available_discharge = float((soc - soc_min) * max_capacity)

            # start discharging when we approach a peak and have some charge
            if time_to_peak <= advance_discharge_period and soc > soc_min:
                discharging = True

            if not discharging and soc < soc_max:
                if self.peaks_df["allow_discharge"].iloc[i]:
                    if (td - last_discharge) > delay_charge_period:
                        charging = True

            if discharging:
                # Discharge storage to meet demand.
                # `discharge_needed` is as seen by the storage
                discharge_needed = max_discharge_rate / discharge_eff
                # `discharge` is as seen by the storage, but `max_discharge_rate` is as observed
                # outside the storage
                discharge = min(
                    discharge_needed, available_discharge, max_discharge_rate / discharge_eff
                )

                soc -= discharge / max_capacity  # soc is a ratio with value between 0 and 1
                # output is as observed outside the storage, so we need to adjust `discharge` by
                # applying `discharge_efficiency`.
                set_point_array[i] = discharge * discharge_eff

                # get time discharge completion
                if soc <= soc_min:
                    last_discharge = td

            elif charging:
                # Charge storage with unused input
                # `unused_input` is as seen outside the storage
                unused_input = input_flow - demand_t
                unused_input = unused_input.item()
                # `charge` is as seen by the storage, but the things being compared should all be as
                # seen outside the storage so we need to adjust `available_charge` outside the
                # storage view and the final result back into the storage view.
                charge = min(available_charge / charge_eff, max_charge_rate) * charge_eff
                soc += charge / max_capacity  # soc is a ratio with value between 0 and 1
                set_point_array[i] = -1 * charge / charge_eff

            # Ensure SOC stays within bounds
            soc = max(soc_min, min(soc_max, soc))

            # Record the SOC for the current time step
            soc_array[i] = deepcopy(soc)

            # stay in discharge mode until the battery is fully discharged
            if soc <= soc_min:
                discharging = False
            if soc >= soc_max:
                charging = False

        outputs[f"{commodity}_set_point"] = set_point_array

    def get_peaks(
        self,
        demand_profile: dict,
        n_max_events=None,
        max_events_period=None,
        min_proximity=None,
        peak_range={"start": time.min, "end": time.max},
    ):
        """Determines the peaks of the demand profile

        Args:
            demand_profile (dict): with keys "time_date" and "demand"
            max_events (_type_, optional): _description_. Defaults to None.
            max_events_period (_type_, optional): _description_. Defaults to None.
            min_proximity (dict | None, optional): Minimum spacing between peaks,
                provided as {"units": <timedelta unit>, "val": <non-negative number>}.
            peak_range (dict, optional): Daily time window used to determine
                candidate peaks, with keys {"start", "end"} as `datetime.time`.
                Defaults to include the full day. Start must come before end and both
                must be in the same day.
        """

        # create dataframe from dictionary
        demand_df = pd.DataFrame(demand_profile)
        if "time_date" not in demand_df or "demand" not in demand_df:
            raise ValueError("demand_profile must include 'time_date' and 'demand' keys")

        demand_df["time_date"] = pd.to_datetime(demand_df["time_date"])
        demand_df["period_day"] = demand_df["time_date"].dt.floor("D")

        if not isinstance(peak_range["start"], time) or not isinstance(peak_range["end"], time):
            raise ValueError("peak_range['start'] and peak_range['end'] must be datetime.time")
        time_of_day = demand_df["time_date"].dt.time
        if peak_range["start"] <= peak_range["end"]:
            in_peak_range = (time_of_day >= peak_range["start"]) & (
                time_of_day <= peak_range["end"]
            )
        else:
            raise (ValueError("Peak range start must come before peak range end in the same day"))

        # flag daily peaks up to n_max_events per max_events_period unless None, then flag all
        # daily peaks. When using max events, the highest n_max_events in the max_events_period
        # should be used.
        demand_df["is_peak"] = False
        daily_peak_idx = demand_df.loc[in_peak_range].groupby("period_day")["demand"].idxmax()
        demand_df.loc[daily_peak_idx, "is_peak"] = True

        if n_max_events is not None:
            if n_max_events < 0:
                raise ValueError("n_max_events must be >= 0")

            peak_candidates = demand_df.loc[demand_df["is_peak"]].copy()
            keep_idx = []

            if max_events_period is None:
                keep_idx = peak_candidates.nlargest(n_max_events, "demand").index.tolist()
            else:
                if isinstance(max_events_period, int):
                    if max_events_period <= 0:
                        raise ValueError(
                            "max_events_period must be positive when provided as an int"
                        )

                    demand_df["period_id"] = np.arange(len(demand_df)) // max_events_period
                    peak_candidates["period_id"] = demand_df.loc[peak_candidates.index, "period_id"]

                elif isinstance(max_events_period, str):
                    period_freq = max_events_period.strip()
                    try:
                        demand_df["period_id"] = demand_df["time_date"].dt.to_period(period_freq)
                    except ValueError as exc:
                        raise ValueError(
                            "Invalid max_events_period string. Use a pandas period frequency "
                            "(for example 'Y', 'Q', 'M', 'W', 'D', 'H')."
                        ) from exc

                    peak_candidates["period_id"] = demand_df.loc[peak_candidates.index, "period_id"]
                else:
                    raise ValueError(
                        "max_events_period must be None, a positive integer, or a pandas period "
                        "frequency string"
                    )

                for _, period_group in peak_candidates.groupby("period_id"):
                    keep_idx.extend(period_group.nlargest(n_max_events, "demand").index.tolist())

                demand_df = demand_df.drop(columns=["period_id"])

            demand_df["is_peak"] = False
            demand_df.loc[keep_idx, "is_peak"] = True

        if min_proximity is not None:
            if not isinstance(min_proximity, dict):
                raise ValueError("min_proximity must be a dict with keys 'units' and 'val'")
            if "units" not in min_proximity or "val" not in min_proximity:
                raise ValueError("min_proximity must include keys 'units' and 'val'")

            units = min_proximity["units"]
            val = min_proximity["val"]
            if not isinstance(units, str) or not units.strip():
                raise ValueError("min_proximity['units'] must be a non-empty string")
            if not isinstance(val, int | float) or val < 0:
                raise ValueError("min_proximity['val'] must be a non-negative number")

            min_delta = pd.to_timedelta(val, unit=units.strip())
            if min_delta > pd.Timedelta(0):
                selected_peaks = demand_df.loc[demand_df["is_peak"], ["time_date", "demand"]]
                selected_peaks = selected_peaks.sort_values("time_date")

                if len(selected_peaks) > 1:
                    deltas = selected_peaks["time_date"].diff().dropna()
                    if (deltas < min_delta).any():
                        raise ValueError(
                            "Selected peaks violate min_proximity. "
                            "Increase spacing between events or relax min_proximity."
                        )

        return demand_df.drop(columns=["period_day"])

    def merge_peaks(supervisory_peaks_df, secondary_peaks_df):
        # take exactly one peak per day with supervisor_peaks taking precedence if present
        # the result should be a dictionary with time_date and "is_peak" bool
        peaks_df = secondary_peaks_df.copy()
        if supervisory_peaks_df is not None:
            for day in secondary_peaks_df["time_date"].dt.floor("D").unique():
                day_df = supervisory_peaks_df[
                    supervisory_peaks_df["time_date"].dt.floor("D") == day
                ]
                if any(day_df["is_peak"]):
                    peaks_df["is_peak"][peaks_df["time_date"].dt.floor("D") == day] = day_df[
                        "is_peak"
                    ]

        return peaks_df

    def get_time_to_peak(self):
        self.peaks_df["time_to_peak"] = (
            time.max
        )  # TODO This may not be the best default. It will cause no charging at the end of the time series
        for _i, idx in enumerate(self.peaks_df.index):
            next_peak_time = self.peaks_df.loc[
                self.peaks_df["is_peak"] & (self.peaks_df.index >= idx), "time_date"
            ]
            if len(next_peak_time) > 0:
                next_peak_time = next_peak_time.iloc[0]
                self.peaks_df.loc[idx, "time_to_peak"] = (
                    next_peak_time - self.peaks_df.loc[idx, "time_date"]
                )
            else:
                continue

    def get_allowed_discharge(self):
        # we will also need to know if a point is in an allowed charging time
        if self.config.allow_charge_in_peak_range:
            self.peaks_df["allow_charge"] = True
        else:
            # only allow_charge when time step is not in peak range
            self.peaks_df["allow_charge"] = False
            for i in range(self.n_timesteps):
                if (
                    self.peaks_df["time_date"].iloc[i].time() < self.config.peak_range["start"]
                    or self.peaks_df["time_date"].iloc[i].time() >= self.config.peak_range["end"]
                ):
                    self.peaks_df["allow_charge"].iloc[i] = True
