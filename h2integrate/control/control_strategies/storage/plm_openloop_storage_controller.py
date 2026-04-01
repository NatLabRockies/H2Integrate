from copy import deepcopy
from datetime import datetime

import numpy as np
import pandas as pd
from attrs import field, define

from h2integrate.core.utilities import merge_shared_inputs, build_time_series_from_plant_config
from h2integrate.core.validators import contains, gte_zero, range_val, range_val_or_none
from h2integrate.control.control_strategies.storage.openloop_storage_control_base import (
    StorageOpenLoopControlBase,
    StorageOpenLoopControlBaseConfig,
)


@define(kw_only=True)
class PeakLoadManagementOpenLoopStorageControllerConfig(StorageOpenLoopControlBaseConfig):
    """
    Configuration class for the PeakLoadManagementOpenLoopStorageController.

    Defines all parameters required to configure the peak-load management storage controller,
    including storage constraints, efficiency parameters, peak detection, and operation strategies.

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
        demand_profile_supervisor (int | float | list | None, optional): Demand values for
            additional connected system for each timestep, in the same units as
            `commodity_rate_units`. May be a scalar for constant demand or a list/array for
            time-varying demand.
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
    demand_profile_supervisor: int | float | list | None = field()
    dispatch_priority_demand_profile: str = field(
        validator=contains(["demand_profile", "demand_profile_supervisor"]),
    )
    max_supervisor_events: int | None = (field(default=None),)
    max_supervisor_event_period: int | str | None = field(default=None)
    peak_range: dict = field(
        metadata={
            "description": "Daily time window for peak detection. "
            "Dict with 'start' and 'end' as HH:MM:SS strings."
        },
    )
    advance_discharge_period: dict = field(
        metadata={
            "description": "How long before a peak to start discharging. "
            "Dict with 'units' (timedelta unit str) and 'val' (numeric)."
        },
    )
    delay_charge_period: dict = field(
        metadata={
            "description": "Minimum delay after discharge completes before charging resumes. "
            "Dict with 'units' and 'val'."
        },
    )
    allow_charge_in_peak_range: bool = field(
        default=True,
        metadata={"description": "If False, charging is suppressed during peak_range."},
    )
    min_peak_proximity: dict = field(
        metadata={
            "description": "Minimum time allowed between peak events. An error is raised if "
            "peak events do not respect the given time separation."
            "Dict with 'units' and 'val'."
        },
    )

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
    Peak-load management storage controller implementing an open-loop control strategy.

    This controller manages commodity (e.g., hydrogen) storage to reduce detected demand peaks.
    It detects peaks in the demand profile using configurable time
    windows and event limits, then uses multi-stage state machine control to:

    1. Discharge storage in advance of peaks (configurable lead time)
    2. Charge storage during expected low-demand periods (using provided charging window bounds)
    3. Enforce SOC, rate, and efficiency limits throughout

    The controller uses an open-loop architecture where peak discharge/charge decisions are
    pre-planned during setup() rather than dynamically optimized during compute().
    """

    def setup(self):
        """Initialize controller configuration, storage inputs, and compute peak schedules.

        During setup:
        1. Loads and validates configuration from tech_config and plant_config options
        2. Registers OpenMDAO inputs for storage parameters (capacity, charge rates, etc.)
        3. Detects peaks in the demand profile (supervisor and secondary)
        4. Merges peaks with supervisor prioritization if configured
        5. Computes time-to-next-peak for each timestep
        6. Identifies allowed charging windows based on peak_range configuration

        Raises:
            ValueError: If configuration is invalid or required keys are missing
        """
        self.config = PeakLoadManagementOpenLoopStorageControllerConfig.from_dict(
            merge_shared_inputs(self.options["tech_config"]["model_inputs"], "control"),
            strict=False,
            additional_cls_name=self.__class__.__name__,
        )
        super().setup()

        if (
            self.config.demand_profile_supervisor is None
            and self.config.dispatch_priority_demand_profile == "demand_profile_supervisor"
        ):
            raise (
                ValueError(
                    "If demand_profile_supervisor is None, then dispatch_priority_demand_profile"
                    "must be demand_profile"
                )
            )

        self.n_timesteps = self.options["plant_config"]["plant"]["simulation"]["n_timesteps"]

        # Register storage system design constraint inputs
        self.add_input(
            "max_charge_rate",
            val=self.config.max_charge_rate,
            units=self.config.commodity_rate_units,
            desc="Maximum charging rate for the storage system",
        )

        self.add_input(
            "storage_capacity",
            val=self.config.max_capacity,
            units=self.config.commodity_amount_units,
            desc="Total storage capacity (including unusable amounts)",
        )

        if not self.config.charge_equals_discharge:
            self.add_input(
                "max_discharge_rate",
                val=self.config.max_discharge_rate,
                units=self.config.commodity_rate_units,
                desc="Maximum discharging rate for the storage system",
            )

        # Store simulation parameters for later use
        self.dt = self.options["plant_config"]["plant"]["simulation"]["dt"]
        self.time_index = build_time_series_from_plant_config(self.options["plant_config"])

        # Build timestamped demand dictionaries from simulation timeline.
        secondary_demand_profile = self._build_demand_profile_dict(self.config.demand_profile)

        # Detect peaks in supervisor demand profile (if provided)
        if self.config.demand_profile_supervisor is not None:
            supervisor_demand_profile = self._build_demand_profile_dict(
                self.config.demand_profile_supervisor
            )
            self.supervisor_peaks_df = self.get_peaks(
                demand_profile=supervisor_demand_profile,
                n_max_events=self.config.max_supervisor_events,
                max_events_period=self.config.max_supervisor_event_period,
                min_proximity=self.config.min_peak_proximity,
            )
        else:
            self.supervisor_peaks_df = None

        # Detect daily peaks in secondary demand profile (always computed)
        # Respects the configured peak_range time window for each day
        self.secondary_peaks_df = self.get_peaks(
            demand_profile=secondary_demand_profile,
            peak_range=self.config.peak_range,
        )

        if self.config.dispatch_priority_demand_profile == "demand_profile_supervisor":
            self.peaks_df = self.merge_peaks(self.supervisor_peaks_df, self.secondary_peaks_df)
        else:
            self.peaks_df = self.merge_peaks(self.secondary_peaks_df, self.supervisor_peaks_df)

        self.get_time_to_peak()

        self.get_allowed_discharge()

    def _build_demand_profile_dict(self, demand_profile):
        """Convert scalar/list demand input into a timestamped demand dictionary."""
        if np.isscalar(demand_profile):
            demand_values = np.full(self.n_timesteps, float(demand_profile), dtype=float)
        else:
            demand_values = np.asarray(demand_profile, dtype=float)

        if len(demand_values) != self.n_timesteps:
            raise ValueError(
                "demand_profile length must equal n_timesteps "
                f"({len(demand_values)} != {self.n_timesteps})"
            )

        return {
            "date_time": self.time_index,
            "demand": demand_values,
        }

    @staticmethod
    def _normalize_peak_range(peak_range):
        """Validate and parse peak_range values from HH:MM:SS strings.

        Returns a dict with datetime.time objects.
        """
        if not isinstance(peak_range, dict):
            raise ValueError("peak_range must be a dict with keys 'start' and 'end'")
        if "start" not in peak_range or "end" not in peak_range:
            raise ValueError("peak_range must be a dict with keys 'start' and 'end'")

        parsed = {}
        for key in ["start", "end"]:
            value = peak_range[key]
            if not isinstance(value, str):
                raise ValueError(f"peak_range['{key}'] must be an HH:MM:SS string")
            try:
                parsed[key] = datetime.strptime(value, "%H:%M:%S").time()
            except ValueError as exc:
                raise ValueError(f"peak_range['{key}'] must be an HH:MM:SS string") from exc

        return parsed

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

        # Dispatch strategy outline:
        # - Discharge: Starting when time_to_peak <= advance_discharge_period
        #   * Discharge at max rate (or less to reach targets)
        #   * Stop discharging only when SOC reaches min_soc
        # - Charge: When not discharging, SOC < max, and allow_charge window is active
        #   * Start charging only after delay_charge_period since last discharge
        #   * Charge at max rate (or less to reach target)
        #   * Stop charging when SOC reaches max_soc

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

        # State machine to track discharge/charge mode
        discharging = False
        charging = False

        advance_discharge_period = pd.Timedelta(
            value=self.config.advance_discharge_period["val"],
            unit=self.config.advance_discharge_period["units"],
        )
        delay_charge_period = pd.Timedelta(
            value=self.config.delay_charge_period["val"],
            unit=self.config.delay_charge_period["units"],
        )

        # Initialize: no discharge has occurred yet
        last_discharge = self.peaks_df["date_time"].iloc[0] - delay_charge_period

        # Process each timestep using the pre-computed peak schedule
        for i, _demand_t in enumerate(self.peaks_df["demand"].tolist()):
            td = self.peaks_df["date_time"].iloc[i]
            time_to_peak = self.peaks_df["time_to_peak"].iloc[i]

            # Get the input flow at the current time step
            inputs[f"{commodity}_in"][i]

            # Calculate the available charge/discharge capacity
            available_charge = float((soc_max - soc) * max_capacity)
            available_discharge = float((soc - soc_min) * max_capacity)

            # start discharging when we approach a peak and have some charge
            if time_to_peak <= advance_discharge_period and soc > soc_min:
                discharging = True

            if not discharging and soc < soc_max:
                if self.peaks_df["allow_charge"].iloc[i]:
                    if (td - last_discharge) > delay_charge_period:
                        charging = True

            if discharging:
                # DISCHARGE MODE: Supply commodity to meet peak demand
                # Note: discharge_needed is internal (storage view), max_discharge_rate is external
                discharge_needed = max_discharge_rate / discharge_eff
                discharge = min(
                    discharge_needed, available_discharge, max_discharge_rate / discharge_eff
                )

                soc -= discharge / max_capacity  # Deplete storage state of charge
                # Output setpoint is the external (delivered) rate after efficiency loss
                set_point_array[i] = discharge * discharge_eff

                # Mark discharge completion time for charging delay calculation
                if soc <= soc_min:
                    last_discharge = td

            elif charging:
                # CHARGE MODE: Store commodity by charging from assumed infinite source
                # unused_input is external (delivered commodity not needed for demand)
                # unused_input = input_flow - demand_t
                # unused_input = unused_input.item()
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

    @staticmethod
    def get_peaks(
        demand_profile: dict,
        n_max_events=None,
        max_events_period=None,
        min_proximity=None,
        peak_range={"start": "00:00:00", "end": "23:59:59"},
    ):
        """Detect demand peaks using configurable time windows and event limits.

        Identifies peak demand periods from a demand profile, with control over:
        - Daily time windows (e.g., peak detection only 12:00-17:00 each day)
        - Event frequency (e.g., max 1 peak per week)
        - Temporal spacing (e.g., minimum 24 hours between peaks)

        Args:
            demand_profile (dict): Timeseries data with keys:
                - 'date_time': timestamps (list or DatetimeIndex convertible)
                - 'demand': demand values (list or array)
            n_max_events (int | None): Maximum number of peaks to keep globally or per period.
                If None, returns all daily peaks. Defaults to None.
            max_events_period (int | str | None): Grouping period for n_max_events limit.
                - None: apply n_max_events limit globally (keep top-N peaks overall)
                - int: group by timestep intervals (e.g., 288 for 24-hour periods)
                - str: pandas period frequency (e.g., 'W' for week, 'M' for month)
                Defaults to None.
            min_proximity (dict | None): Minimum time gap between sequential peaks.
                Dict with keys {'units': <pandas timedelta unit str>, 'val': <numeric>}.
                Example: {'units': 'D', 'val': 1} enforces 1-day minimum gap.
                Raises ValueError if violated. Defaults to None (no constraint).
            peak_range (dict, optional): Daily time window for peak detection. Dict with keys:
                - 'start': HH:MM:SS string (inclusive)
                - 'end': HH:MM:SS string (exclusive)
                Defaults to full day.

        Returns:
            pd.DataFrame: Input demand_profile with added 'is_peak' boolean column.
                Each row is True if that timestep is a peak, False otherwise.

        Raises:
            ValueError: If configuration is invalid (bad period frequency, type mismatches, etc.)
        """

        if not isinstance(demand_profile, dict):
            raise ValueError("demand_profile must be a dict with 'date_time' and 'demand' keys")

        peak_range = PeakLoadManagementOpenLoopStorageController._normalize_peak_range(peak_range)

        demand_df = pd.DataFrame(demand_profile)
        if "date_time" not in demand_df or "demand" not in demand_df:
            raise ValueError("demand_profile must include 'date_time' and 'demand' keys")

        # Normalize timestamps and tag by day
        demand_df["date_time"] = pd.to_datetime(demand_df["date_time"])
        demand_df["period_day"] = demand_df["date_time"].dt.floor("D")

        # Validate and apply time-of-day window
        time_of_day = demand_df["date_time"].dt.time
        if peak_range["start"] <= peak_range["end"]:
            # Normal window: 12:00-17:00
            in_peak_range = (time_of_day >= peak_range["start"]) & (
                time_of_day <= peak_range["end"]
            )
        else:
            raise ValueError("Peak range start must come before peak range end in the same day")

        # Identify highest-demand timestep within each day's peak window
        demand_df["is_peak"] = False
        daily_peak_idx = demand_df.loc[in_peak_range].groupby("period_day")["demand"].idxmax()
        demand_df.loc[daily_peak_idx, "is_peak"] = True

        # Optional: Limit number of peaks globally or per period
        if n_max_events is not None:
            if n_max_events < 0:
                raise ValueError("n_max_events must be >= 0 or None")

            peak_candidates = demand_df.loc[demand_df["is_peak"]].copy()
            keep_idx = []

            if max_events_period is None:
                # Global limit: keep the N largest peaks across all time
                keep_idx = peak_candidates.nlargest(n_max_events, "demand").index.tolist()
            else:
                # Period-based limit: keep top-N peaks within each period
                if isinstance(max_events_period, int):
                    if max_events_period <= 0:
                        raise ValueError(
                            "max_events_period must be positive when provided as an int"
                        )

                    # Group by timestep intervals (e.g., 288 timesteps = 1 day)
                    demand_df["period_id"] = np.arange(len(demand_df)) // max_events_period
                    peak_candidates["period_id"] = demand_df.loc[peak_candidates.index, "period_id"]

                elif isinstance(max_events_period, str):
                    # Group by pandas period frequency (W=week, M=month, etc.)
                    period_freq = max_events_period.strip()
                    try:
                        demand_df["period_id"] = demand_df["date_time"].dt.to_period(period_freq)
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

                # Within each period, retain only the top-N peaks by demand
                for _, period_group in peak_candidates.groupby("period_id"):
                    keep_idx.extend(period_group.nlargest(n_max_events, "demand").index.tolist())

                demand_df = demand_df.drop(columns=["period_id"])

            # Reset "is_peak" flags and reapply only to surviving indices
            demand_df["is_peak"] = False
            demand_df.loc[keep_idx, "is_peak"] = True

        # Optional: Validate minimum spacing between consecutive peaks
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

            # Convert specification to timedelta
            min_delta = pd.to_timedelta(val, unit=units.strip())
            if min_delta > pd.Timedelta(0):
                # Check consecutive peak spacing
                selected_peaks = demand_df.loc[demand_df["is_peak"], ["date_time", "demand"]]
                selected_peaks = selected_peaks.sort_values("date_time")

                if len(selected_peaks) > 1:
                    deltas = selected_peaks["date_time"].diff().dropna()
                    if (deltas < min_delta).any():
                        raise ValueError(
                            "Selected peaks violate min_proximity. "
                            "Increase spacing between events or relax min_proximity."
                        )

        return demand_df.drop(columns=["period_day"])

    @staticmethod
    def merge_peaks(supervisory_peaks_df, secondary_peaks_df):
        """Merge supervisor and secondary peak schedules with supervisor precedence.

        Combines two peak schedules (primary and fallback) using day-level precedence:
        - For each day, if the primary (supervisory) profile has any peaks on that day,
          use all primary peaks for that day
        - Otherwise, use the secondary peaks for that day

        This allows critical demand (supervisor) to take scheduling precedence while
        falling back to secondary peaks for days with no critical demand.

        Args:
            supervisory_peaks_df (pd.DataFrame | None): Primary peak schedule with columns
                ['date_time', 'is_peak', 'demand', ...].
            secondary_peaks_df (pd.DataFrame): Secondary/fallback peak schedule with same columns.

        Returns:
            pd.DataFrame: Merged peak schedule. If supervisory is None, returns secondary unchanged.
                Otherwise, returns secondary with 'is_peak' flags overridden on supervisor-peak
                days.
        """
        if secondary_peaks_df is None:
            peaks_df = supervisory_peaks_df.copy()
        else:
            peaks_df = secondary_peaks_df.copy()
            # For each day in the data, check if supervisor has any peaks
            for day in secondary_peaks_df["date_time"].dt.floor("D").unique():
                day_df = supervisory_peaks_df[
                    supervisory_peaks_df["date_time"].dt.floor("D") == day
                ]
                # If supervisor has peaks on the day, use supervisor's flags for all rows that day
                if any(day_df["is_peak"]):
                    peaks_df["is_peak"][peaks_df["date_time"].dt.floor("D") == day] = day_df[
                        "is_peak"
                    ]

        return peaks_df

    def get_time_to_peak(self):
        """Compute time delta from each timestep to the next detected peak.

        For each row in peaks_df, determines how long until the next peak (marked
        as is_peak=True) will occur. This enables the discharge trigger: when
        time_to_peak <= advance_discharge_period, discharge mode activates.

        Timesteps after the final peak receive time.max as their time_to_peak value.
        This default prevents charging at simulation end (since advance_discharge_period
        will never be reached). TODO: Consider configurable end-of-horizon behavior.

        Side effect: Modifies self.peaks_df by adding/updating 'time_to_peak' column
        with pd.Timedelta values or time.max.
        """
        # Initialize with sentinel value for "no future peak"
        self.peaks_df["time_to_peak"] = pd.Timedelta(value=24, unit="h")
        for _i, idx in enumerate(self.peaks_df.index):
            # Find next peak at or after current index
            next_peak_time = self.peaks_df.loc[
                self.peaks_df["is_peak"] & (self.peaks_df.index >= idx), "date_time"
            ]
            if len(next_peak_time) > 0:
                next_peak_time = next_peak_time.iloc[0]
                self.peaks_df.loc[idx, "time_to_peak"] = (
                    next_peak_time - self.peaks_df.loc[idx, "date_time"]
                )

    def get_allowed_discharge(self):
        """Compute allowed charging time windows based on peak range configuration.

        Determines for each timestep whether charging is permitted. If
        allow_charge_in_peak_range=True, charging is allowed at all times.
        Otherwise, charging is suppressed during the configured peak_range window
        (e.g., 12:00-17:00 each day) to prioritize meeting peak demand from storage.

        Side effect: Modifies self.peaks_df by adding/updating 'allow_charge' column
        with boolean values (True=charging allowed, False=charging suppressed).
        """
        if self.config.allow_charge_in_peak_range:
            # Global allow: charging always permitted
            self.peaks_df["allow_charge"] = True
        else:
            peak_range = self._normalize_peak_range(self.config.peak_range)
            # Selective allow: suppress charging during peak window only
            self.peaks_df["allow_charge"] = False
            for i in range(self.n_timesteps):
                time_of_day = self.peaks_df["date_time"].iloc[i].time()
                # Allow charging if outside peak window
                if time_of_day < peak_range["start"] or time_of_day >= peak_range["end"]:
                    self.peaks_df["allow_charge"].iloc[i] = True
