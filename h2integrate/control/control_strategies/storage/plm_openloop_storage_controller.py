import warnings
from copy import deepcopy
from datetime import datetime, timedelta

import numpy as np
import pandas as pd
from attrs import field, define

from h2integrate.core.utilities import merge_shared_inputs, build_time_series_from_plant_config
from h2integrate.core.validators import contains, has_required_keys
from h2integrate.control.control_strategies.storage.openloop_storage_control_base import (
    StorageOpenLoopControlBase,
    StorageOpenLoopControlBaseConfig,
)


@define(kw_only=True)
class PeakLoadManagementHeuristicOpenLoopStorageControllerConfig(StorageOpenLoopControlBaseConfig):
    """
    Configuration class for the PeakLoadManagementHeuristicOpenLoopStorageController.

    Defines peak-selection and dispatch-priority rules used to pre-compute
    an open-loop discharge and recharge schedule.

    Attributes:
        demand_profile_upstream (int | float | list | None, optional): Demand values for
            additional connected system for each timestep, in the same units as
            `commodity_rate_units`. May be a scalar for constant demand or a list/array for
            time-varying demand.
        dispatch_priority_demand_profile (str | None, optional): which demand profile takes
            precedence for dispatch decisions. One of ["demand_profile", "demand_profile_upstream"].
        n_override_events: (int | None, optional): The maximum number of discharge events
            allowed for the priority profile in the period specified in override_events_period,
            or across all time steps if override_events_period is None.
        override_events_period: (int | None, optional): Duration, in time steps, of the period
            in which the n_override_events must occur or a str indicating the time period (e.g.
            W for week, M for month). Defaults to the length of the simulation.
        peak_range (dict): Daily time window restricting which timesteps are considered as peak
            candidates in the primary demand profile. Keys ``start`` and ``end`` must be
            ``HH:MM:SS`` strings (e.g. ``{'start': '12:00:00', 'end': '17:00:00'}``). Only
            the highest-demand timestep within this window is marked as a candidate peak for
            each day.
        advance_discharge_period (dict): Lead time before a detected peak at which discharge
            mode activates. Dict with keys ``units`` (pandas timedelta unit string, e.g. ``'h'``)
            and ``val`` (numeric). For example ``{'units': 'h', 'val': 2}`` begins discharge two
            hours before the identified peak.
        delay_charge_period (dict): Minimum time to wait after the battery reaches minimum SOC
            before recharging is permitted. Dict with keys ``units`` and ``val``, using the same
            format as ``advance_discharge_period``.
        allow_charge_in_peak_range (bool, optional): If ``True``, charging is never suppressed.
            If ``False``, charging is blocked for timesteps that fall inside ``peak_range`` to
            prevent charging whilst peak demand is expected. Defaults to ``True``.
        min_peak_proximity (dict): Minimum required time separation between consecutive retained
            peak events. A ``ValueError`` is raised during setup if selected peaks violate this
            constraint. Dict with keys ``units`` and ``val``, using the same format as
            ``advance_discharge_period``.

    """

    require_storage_parameters = True

    demand_profile_upstream: int | float | list | None = field()
    dispatch_priority_demand_profile: str = field(
        validator=contains(["demand_profile", "demand_profile_upstream"]),
    )
    n_override_events: int | None = field(default=None)
    override_events_period: int | str | None = field(default=None)
    peak_range: dict = field(validator=has_required_keys(["start", "end"]))
    advance_discharge_period: dict = field(validator=has_required_keys(["units", "val"]))
    delay_charge_period: dict = field(validator=has_required_keys(["units", "val"]))
    allow_charge_in_peak_range: bool = field(default=True)
    min_peak_proximity: dict = field(validator=has_required_keys(["units", "val"]))

    def __attrs_post_init__(self):
        super().__attrs_post_init__()

        self.common_post_init_operations()

        # Validate and normalize dict parameters
        # peak_range: must have 'start' and 'end' keys as HH:MM:SS strings.
        # YAML automatically converts HH:MM:SS to an integer number of seconds,
        # so non-string values are converted back here.
        for _key in ("start", "end"):
            if _key not in self.peak_range:
                raise ValueError(
                    f"peak_range is missing required key '{_key}'. "
                    "Expected dict with 'start' and 'end' as HH:MM:SS strings."
                )
        for key, value in self.peak_range.items():
            if not isinstance(value, str):
                self.peak_range[key] = str(timedelta(seconds=value))

        # advance_discharge_period / delay_charge_period / min_peak_proximity:
        # must each be a dict with 'units' (str) and 'val' (int or float).
        for _param_name, _param_val in (
            ("advance_discharge_period", self.advance_discharge_period),
            ("delay_charge_period", self.delay_charge_period),
            ("min_peak_proximity", self.min_peak_proximity),
        ):
            if not isinstance(_param_val, dict):
                raise ValueError(
                    f"'{_param_name}' must be a dict with keys 'units' and 'val', "
                    f"got {type(_param_val).__name__}."
                )
            for _key in ("units", "val"):
                if _key not in _param_val:
                    raise ValueError(
                        f"'{_param_name}' is missing required key '{_key}'. "
                        "Expected dict with 'units' (str) and 'val' (int or float)."
                    )
            if not isinstance(_param_val["units"], str) or not _param_val["units"].strip():
                raise ValueError(
                    f"'{_param_name}[\"units\"]' must be a non-empty string, "
                    f"got {_param_val['units']!r}."
                )
            if not isinstance(_param_val["val"], int | float):
                raise ValueError(
                    f"'{_param_name}[\"val\"]' must be a numeric value (int or float), "
                    f"got {type(_param_val['val']).__name__}."
                )


class PeakLoadManagementHeuristicOpenLoopStorageController(StorageOpenLoopControlBase):
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
        3. Detects peaks in the demand profile (demand_profile and demand_profile_upstream)
        4. Merges peaks with demand_profile_upstream prioritization if configured
        5. Computes time-to-next-peak for each timestep
        6. Identifies allowed charging windows based on peak_range configuration

        Raises:
            ValueError: If configuration is invalid or required keys are missing
        """
        self.config = PeakLoadManagementHeuristicOpenLoopStorageControllerConfig.from_dict(
            merge_shared_inputs(self.options["tech_config"]["model_inputs"], "control"),
            strict=False,
            additional_cls_name=self.__class__.__name__,
        )
        super().setup()

        if (
            self.config.demand_profile_upstream is None
            and self.config.dispatch_priority_demand_profile == "demand_profile_upstream"
        ):
            raise (
                ValueError(
                    "If demand_profile_upstream is None, then dispatch_priority_demand_profile"
                    "must be demand_profile"
                )
            )

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
        self.time_index = build_time_series_from_plant_config(self.options["plant_config"])

        if len(self.time_index) != self.n_timesteps:
            raise (
                ValueError(
                    f"Time series is of length {len(self.time_index)}, "
                    f"but self.n_timesteps is {self.n_timesteps}."
                )
            )

        # Detect peaks in demand profile 2 (if provided)
        if self.config.demand_profile_upstream is not None:
            demand_profile_upstream = self._build_demand_profile_dict(
                self.config.demand_profile_upstream,
                self.time_index,
            )
            self.peaks_2_df = self.get_peaks(
                demand_profile=demand_profile_upstream,
                n_override_events=self.config.n_override_events,
                override_events_period=self.config.override_events_period,
                min_proximity=self.config.min_peak_proximity,
            )
        else:
            self.peaks_2_df = None

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

        Dispatch strategy outline:
        - Discharge:
          * Starting when time_to_peak <= advance_discharge_period
          * Discharge at max rate (or less to reach targets)
          * Stop discharging only when SOC reaches min_soc
        - Charge:
          * When not discharging, SOC < max, and allow_charge window is active
          * Start charging only after delay_charge_period since last discharge
          * Charge at max rate (or less to reach target)
          * Stop charging when SOC reaches max_soc

        Expected input keys:
            * ``<commodity>_in``: Timeseries of commodity available at each time step.
            * ``<commodity>_demand``: Timeseries demand profile.
            * ``max_charge_rate``: Maximum charge rate permitted.
            * ``max_capacity``: Maximum total storage capacity.

        Outputs populated:
            * ``<commodity>_set_point``: Dispatch command to storage,
                negative when charging, positive when discharging.

        Raises:
            UserWarning: If the demand profile is entirely zero.
            UserWarning: If ``max_charge_rate`` or ``max_capacity`` is negative.

        Returns:
            None
        """

        self.common_checks_needed_in_compute(inputs)

        commodity = self.config.commodity

        if self.config.charge_equals_discharge:
            max_discharge_rate = inputs["max_charge_rate"].item()
        else:
            max_discharge_rate = inputs["max_discharge_rate"].item()

        max_capacity = inputs["storage_capacity"].item()
        max_charge_rate = inputs["max_charge_rate"].item()

        soc_max = self.config.max_soc_fraction
        soc_min = self.config.min_soc_fraction
        init_soc_fraction = self.config.init_soc_fraction

        charge_eff = float(self.config.charge_efficiency)
        discharge_eff = float(self.config.discharge_efficiency)

        # Build timestamped demand dictionaries from simulation timeline.
        demand_profile = self._build_demand_profile_dict(
            inputs[f"{commodity}_demand"],
            self.time_index,
        )

        # Detect daily peaks in demand profile (always computed)
        # Respects the configured peak_range time window for each day
        self.peaks_1_df = self.get_peaks(
            demand_profile=demand_profile,
            peak_range=self.config.peak_range,
        )

        if self.config.dispatch_priority_demand_profile == "demand_profile_upstream":
            self.peaks_df = self.merge_peaks(self.peaks_2_df, self.peaks_1_df)
        else:
            self.peaks_df = self.merge_peaks(self.peaks_1_df, self.peaks_2_df)

        self.get_time_to_peak()

        self.get_allowed_charge()

        # Initialize time-step state of charge prior to loop so the loop starts with
        # the previous time step's value
        soc = deepcopy(init_soc_fraction)

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
        for i in range(self.n_timesteps):
            time_stamp = self.peaks_df["date_time"].iloc[i]
            time_to_peak = self.peaks_df["time_to_peak"].iloc[i]

            # Get the input flow at the current time step
            inputs[f"{commodity}_in"][i]

            # Calculate the available charge/discharge capacity
            available_charge = float((soc_max - soc) * max_capacity)
            available_discharge = float((soc - soc_min) * max_capacity)

            # start discharging when we approach a peak and have some charge
            if time_to_peak <= advance_discharge_period and soc > soc_min:
                discharging = True
                charging = False

            if not discharging and soc < soc_max:
                if self.peaks_df["allow_charge"].iloc[i]:
                    if (time_stamp - last_discharge) > delay_charge_period:
                        charging = True
                        discharging = False

            if discharging:
                # DISCHARGE MODE: Supply commodity to meet peak demand
                # Note: available_discharge is internal (storage view),
                # max_discharge_rate is external
                discharge = min(available_discharge, max_discharge_rate / discharge_eff)

                soc -= discharge / max_capacity  # Deplete storage state of charge
                # Output setpoint is the external (delivered) rate after efficiency loss
                set_point_array[i] = discharge * discharge_eff

                # Mark discharge completion time for charging delay calculation
                if soc <= soc_min:
                    last_discharge = time_stamp

            elif charging:
                # CHARGE MODE: Store commodity by charging from assumed infinite source
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

        # insert warning message if for any time step the magnitude of
        # any negative entry in set_point_array is greater than inputs[f"{commodity}_in"]
        charging_requested = -np.minimum(set_point_array, 0.0)
        available_input = np.asarray(inputs[f"{commodity}_in"])
        exceeds_available_input = charging_requested > available_input

        if np.any(exceeds_available_input):
            first_idx = int(np.where(exceeds_available_input)[0][0])
            msg = (
                f"WARNING: At time step index {first_idx}, requested charging rate "
                f"({charging_requested[first_idx]}) exceeds available {commodity} input "
                f"({available_input[first_idx]})."
            )
            warnings.warn(msg, UserWarning)

    @staticmethod
    def _build_demand_profile_dict(demand_profile, time_series):
        """Convert scalar/list demand input into a timestamped demand dictionary."""
        n_timesteps = len(time_series)
        if np.isscalar(demand_profile):
            demand_values = np.full(n_timesteps, float(demand_profile), dtype=float)
        else:
            demand_values = np.asarray(demand_profile, dtype=float)

        if len(demand_values) != n_timesteps:
            raise ValueError(
                "demand_profile length must equal n_timesteps "
                f"({len(demand_values)} != {n_timesteps})"
            )

        return {
            "date_time": time_series,
            "demand": demand_values,
        }

    @staticmethod
    def _parse_peak_range(peak_range):
        """Validate and parse peak_range values from HH:MM:SS strings.

        Returns a dict with datetime.time objects.
        """
        if not isinstance(peak_range, dict):
            raise ValueError("peak_range must be a dict with keys 'start' and 'end'")
        if "start" not in peak_range or "end" not in peak_range:
            raise ValueError("peak_range must be a dict with keys 'start' and 'end'")

        parsed = {}
        for key, value in peak_range.items():
            if not isinstance(value, str):
                raise ValueError(f"peak_range['{key}'] must be an HH:MM:SS string")
            parsed[key] = datetime.strptime(value, "%H:%M:%S").time()

        return parsed

    @staticmethod
    def get_peaks(
        demand_profile: dict,
        n_override_events=None,
        override_events_period=None,
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
            n_override_events (int | None): Maximum number of peaks to keep globally or per period.
                If None, returns all daily peaks. Defaults to None.
            override_events_period (int | str | None): Grouping period for n_override_events limit.
                - None: apply n_override_events limit globally (keep top-N peaks overall)
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

        peak_range = PeakLoadManagementHeuristicOpenLoopStorageController._parse_peak_range(
            peak_range
        )

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
        if n_override_events is not None:
            if n_override_events < 0:
                raise ValueError("n_override_events must be >= 0 or None")

            peak_candidates = demand_df.loc[demand_df["is_peak"]].copy()
            keep_idx = []

            if override_events_period is None:
                # Global limit: keep the N largest peaks across all time
                keep_idx = peak_candidates.nlargest(n_override_events, "demand").index.tolist()
            else:
                # Period-based limit: keep top-N peaks within each period
                if isinstance(override_events_period, int):
                    if override_events_period <= 0:
                        raise ValueError(
                            "override_events_period must be positive when provided as an int"
                        )

                    # Group by timestep intervals (e.g., 288 timesteps = 1 day)
                    demand_df["period_id"] = np.arange(len(demand_df)) // override_events_period
                    peak_candidates["period_id"] = demand_df.loc[peak_candidates.index, "period_id"]

                elif isinstance(override_events_period, str):
                    # Group by pandas period frequency (W=week, M=month, etc.)
                    period_freq = override_events_period.strip()
                    try:
                        demand_df["period_id"] = demand_df["date_time"].dt.to_period(period_freq)
                    except ValueError as exc:
                        raise ValueError(
                            "Invalid override_events_period string. Use a pandas period frequency "
                            "(for example 'Y', 'Q', 'M', 'W', 'D', 'H')."
                        ) from exc

                    peak_candidates["period_id"] = demand_df.loc[peak_candidates.index, "period_id"]
                else:
                    raise ValueError(
                        "override_events_period must be None, a positive integer, or a pandas "
                        "period frequency string"
                    )

                # Within each period, retain only the top-N peaks by demand
                for _, period_group in peak_candidates.groupby("period_id"):
                    keep_idx.extend(
                        period_group.nlargest(n_override_events, "demand").index.tolist()
                    )

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
    def merge_peaks(peaks_1, peaks_2):
        """Merge peaks_1 and peak_2 schedules with peak_1 precedence.

        Combines two peak schedules (primary and fallback) using day-level precedence:
        - For each day, if the peaks_1 profile has any peaks on that day,
          use all peaks_1 peaks for that day
        - Otherwise, use the peaks_2 peaks for that day

        This allows overriding peaks (peaks_1) to take scheduling precedence while
        falling back to peaks_2 peaks for days with no overriding peaks.

        Args:
            peaks_1 (pd.DataFrame | None): primary peak schedule with columns
                ['date_time', 'is_peak', 'demand', ...].
            peaks_2 (pd.DataFrame): fallback peak schedule with same columns.

        Returns:
            pd.DataFrame: Merged peak schedule. If peaks_2 is None, returns peaks_1 unchanged.
                Otherwise, returns peaks_2 with 'is_peak' flags overridden on peak_1 peak
                days.
        """
        if peaks_1 is None:
            raise (ValueError("Input, peaks_1, must contain a dataframe, but None was given."))
        elif peaks_2 is None:
            peaks_df = peaks_1.copy()
        else:
            peaks_df = peaks_2.copy()
            for day in peaks_2["date_time"].dt.floor("D").unique():
                day_df = peaks_1[peaks_1["date_time"].dt.floor("D") == day]
                # For each day in the data, check if peaks_1 has any peaks
                # If peaks_1 has peaks on the day, use peaks_1's flags for all rows that day
                if any(day_df["is_peak"]):
                    peaks_df.loc[peaks_df["date_time"].dt.floor("D") == day, "is_peak"] = day_df[
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

    def get_allowed_charge(self):
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
            peak_range = self._parse_peak_range(self.config.peak_range)
            # Selective allow: suppress charging during peak window only
            self.peaks_df["allow_charge"] = False
            for i in range(self.n_timesteps):
                time_of_day = self.peaks_df["date_time"].iloc[i].time()
                # Allow charging if outside peak window
                if time_of_day < peak_range["start"] or time_of_day >= peak_range["end"]:
                    self.peaks_df.loc[i, "allow_charge"] = True
